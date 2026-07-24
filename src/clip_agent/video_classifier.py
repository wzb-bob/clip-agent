"""
视频素材分类器 · 自动将上传视频分为: 口播/产品特写/环境空镜/废片 × editing_role

对每个视频提取3帧(头/中/尾)→视觉模型分析→综合判断→输出分类+编辑角色
"""
from __future__ import annotations
import base64, json, logging, os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """作为短视频剪辑导演，精确分类这段视频素材。返回严格JSON。

## 内容类型(必选一):
- talking_head: 人物出镜说话/讲解/口播
- product_show: 产品/物品展示(特写为主)
- environment: 环境/场景/空间展示(全景为主)
- action: 动作/运动/过程展示
- text_card: 纯文字/图表画面
- waste: 废片——严重抖动/失焦/过曝/无意义画面

## 编辑角色(必选一——这个素材最适合放在视频的哪个位置):
- hook: 适合做开头钩子——有冲击力/吸引眼球/价格数字/惊艳镜头
- body: 适合做主体内容——稳定/清晰/信息量足
- broll: 适合做辅助空镜——覆盖口播画面时用
- outro: 适合做结尾——有收束感/CTA引导/联系方式
- none: 不适合使用(废片)

## 质量评分(1-5):
5: 专业级——光线构图完美，可直接用
4: 良好——基本合格，稍作调整即可
3: 可用——能用但需裁剪/调色
2: 勉强——有明显问题，仅应急用
1: 废片——不可用

## B-roll覆盖判断:
- 如果这段素材的画面可以覆盖到口播音轨上，cover_audio=true
- 如果这段素材的人声/原声是核心内容，cover_audio=false

## 输出格式(严格JSON):
{"content_type":"talking_head","editing_role":"hook","quality":4.5,"tags":["标签1","标签2"],"cover_audio":false,"usable":true,"issues":[],"best_duration_sec":5.0,"notes":"15字以内的使用建议"}"""


@dataclass
class VideoClassification:
    """单个视频的分类结果"""
    filename: str
    file_type: str               # video/image
    duration_sec: float
    content_type: str            # talking_head/product_show/environment/action/text_card/waste
    editing_role: str            # hook/body/broll/outro/none
    quality: float               # 1-5
    tags: list[str] = field(default_factory=list)
    cover_audio: bool = False    # 是否可覆盖口播音轨
    usable: bool = True
    issues: list[str] = field(default_factory=list)
    best_duration_sec: float = 5.0  # 建议使用时长
    notes: str = ""              # 使用建议
    confidence: float = 0.5      # 分类置信度
    frame_count: int = 0         # 分析帧数


@dataclass
class BatchClassification:
    """批量分类结果——可直接指导剪辑"""
    classifications: list[VideoClassification]
    summary: dict                 # {hook: N, body: N, broll: N, outro: N, waste: N}
    recommendations: list[str]    # 剪辑建议
    ready_for_editing: bool       # 素材是否足够开始剪辑


def classify_video(temp_path: str, filename: str, duration_sec: float = 0.0) -> VideoClassification:
    """对单个视频做多帧分析+分类（使用专用分类prompt）"""
    from app.services.clip_agent.media_analyzer import _probe_video
    from app.services.gateway_client import chat_vision
    from app.services.material_analyzer import MaterialAnalyzer
    import re as _re

    if not duration_sec:
        info = _probe_video(temp_path)
        duration_sec = info.get("duration", 0.0) or 5.0

    # 提取多帧: 头25%/中50%/尾75%
    frames = []
    try:
        ma = MaterialAnalyzer()
        for pos, pct in [("head", 0.25), ("mid", 0.50), ("tail", 0.75)]:
            t = duration_sec * pct
            b64 = ma._extract_frame(Path(temp_path), t)
            if b64:
                frames.append({"position": pos, "time_sec": round(t, 1), "base64": b64})
    except Exception as e:
        logger.debug("帧提取失败(%s): %s", filename, e)

    if not frames:
        return _fallback_classify(filename, duration_sec)

    # 对每帧用专用CLASSIFY_PROMPT做分类
    results = []
    for fr in frames:
        try:
            r = chat_vision(image_base64=fr["base64"],
                prompt=CLASSIFY_PROMPT + f"\n这是{filename}的第{fr['time_sec']}秒帧",
                system="你是短视频剪辑导演。只返回JSON。")
            c = r.get("content", "")
            m = _re.search(r'\{.*\}', c, _re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                data["_position"] = fr["position"]
                results.append(data)
        except Exception as e:
            logger.debug("分类帧分析失败(%s): %s", filename, e)

    if not results:
        return _fallback_classify(filename, duration_sec)

    # 综合多帧结果: 投票+取最高质量
    content_types = [r.get("content_type", r.get("type", "unknown")) for r in results]
    editing_roles = [r.get("editing_role", "body") for r in results]
    qualities = [float(r.get("quality", 3.0)) for r in results]
    cover_audios = [r.get("cover_audio", False) for r in results]
    all_tags = list(set(tag for r in results for tag in r.get("tags", [])))
    all_issues = list(set(iss for r in results for iss in r.get("issues", [])))

    # 多数投票
    from collections import Counter
    ct = Counter(content_types).most_common(1)[0][0]
    er = Counter(editing_roles).most_common(1)[0][0]
    avg_quality = round(sum(qualities) / len(qualities), 1)
    cover = Counter(cover_audios).most_common(1)[0][0]
    confidence = Counter(content_types).most_common(1)[0][1] / len(results)

    # 质量调整 + 时长建议
    usable = avg_quality >= 2.0 and ct != "waste"
    best_dur = min(duration_sec, 8.0) if ct in ("product_show", "environment") else min(duration_sec, 15.0)
    # 编辑角色修正: content_type强约束 → 默认角色映射
    ROLE_DEFAULTS = {
        "talking_head": "body",       # 人物出镜→主体口播
        "product_show": "broll",      # 产品展示→B-roll覆盖
        "environment": "broll",       # 环境空镜→B-roll覆盖
        "action": "broll",            # 动作过程→B-roll覆盖
        "text_card": "broll",         # 文字图→B-roll覆盖
        "waste": "none",              # 废片→不用
    }
    er = ROLE_DEFAULTS.get(ct, er)  # 内容类型强约束优先, 模型建议做参考
    # 特例: 如果质量>=4.5且是产品/环境且时长<5s, 可以作hook
    if ct in ("product_show", "environment") and avg_quality >= 4.5 and duration_sec <= 5.0:
        er = "hook"
    # 如果质量>=4.0且是人物出镜且检测到CTA关键词, 可以作outro
    if ct == "talking_head" and avg_quality >= 4.0:
        all_text = " ".join(all_tags + [str(r.get("content", "")) for r in results]).lower()
        if any(kw in all_text for kw in ["引导","cta","关注","点赞","左下","地址","定位","来","找"]):
            er = "outro"

    return VideoClassification(
        filename=filename, file_type="video", duration_sec=duration_sec,
        content_type=ct, editing_role=er, quality=avg_quality,
        tags=all_tags, cover_audio=cover, usable=usable,
        issues=all_issues, best_duration_sec=best_dur,
        notes=f"{ct}素材,建议用作{er},质量{avg_quality}/5" + (f",注意:{','.join(all_issues[:2])}" if all_issues else ""),
        confidence=round(confidence, 2), frame_count=len(results),
    )


def _fallback_classify(filename: str, duration_sec: float) -> VideoClassification:
    """视觉分析失败时的降级分类——基于文件名+时长"""
    fn = filename.lower()
    if any(kw in fn for kw in ["口播","talking","主","人","face","A1_","A2_","A3_","A4_","A5_"]):
        ct, er, tags = "talking_head", "body", ["人物","口播"]
    elif any(kw in fn for kw in ["产品","product","货","特写"]):
        ct, er, tags = "product_show", "broll", ["产品","特写"]
    elif any(kw in fn for kw in ["环境","场景","门头","店","空镜"]):
        ct, er, tags = "environment", "broll", ["环境","空镜"]
    elif duration_sec < 1.0:
        ct, er, tags = "waste", "none", ["废片"]
    else:
        ct, er, tags = "environment", "broll", ["未分类"]

    return VideoClassification(
        filename=filename, file_type="video", duration_sec=duration_sec,
        content_type=ct, editing_role=er, quality=3.0,
        tags=tags, cover_audio=(er == "broll"), usable=(ct != "waste"),
        notes=f"降级分类({ct}→{er})", confidence=0.3, frame_count=0,
    )


def classify_batch(materials: list) -> BatchClassification:
    """批量分类所有上传的素材"""
    classifications = []
    for mf in materials:
        if hasattr(mf, 'temp_path') and mf.temp_path and os.path.exists(mf.temp_path):
            try:
                dur = getattr(mf, 'duration_sec', 0.0) or 0.0
                cls = classify_video(mf.temp_path, mf.filename, dur)
                classifications.append(cls)
            except Exception as e:
                logger.warning("分类失败(%s): %s", mf.filename, e)
                classifications.append(_fallback_classify(mf.filename, 5.0))

    # 统计
    summary = {"hook": 0, "body": 0, "broll": 0, "outro": 0, "waste": 0}
    for c in classifications:
        summary[c.editing_role] = summary.get(c.editing_role, 0) + 1

    # 生成建议
    recs = []
    if summary["hook"] == 0:
        recs.append("⚠️ 缺少开头钩子素材——建议拍摄一个产品特写或惊艳镜头(CU,3秒)")
    if summary["body"] == 0:
        recs.append("⚠️ 缺少主体口播素材——需要人物出镜讲解的镜头(MS,10秒+)")
    if summary["broll"] < 2:
        recs.append("💡 B-roll素材较少——建议多拍产品特写/环境空镜用于覆盖口播画面")
    if summary["outro"] == 0:
        recs.append("💡 缺少结尾素材——建议拍人物CTA引导镜头(MS,3秒)")
    if summary["waste"] > 0:
        recs.append(f"🗑️ {summary['waste']}个废片——建议重新拍摄")

    ready = summary["hook"] >= 1 and summary["body"] >= 1 and summary["broll"] >= 1

    return BatchClassification(
        classifications=classifications,
        summary=summary,
        recommendations=recs if recs else ["✅ 素材齐全，可以开始剪辑!"],
        ready_for_editing=ready,
    )


def format_classification_report(batch: BatchClassification) -> str:
    """格式化分类报告给用户"""
    lines = [
        "══════════════════════",
        "  📊 素材分类报告",
        f"  {'✅ 素材齐全,可以剪辑!' if batch.ready_for_editing else '⚠️ 素材不足,需要补充'}",
        "══════════════════════",
        "", "━━━ 📸 分类详情 ━━━", ""
    ]
    role_icon = {"hook": "🎯", "body": "🎤", "broll": "📷", "outro": "🏁", "waste": "🗑️", "none": "❌"}
    for c in batch.classifications:
        icon = role_icon.get(c.editing_role, "📹")
        usable = "✅" if c.usable else "❌"
        lines.append(f"  {icon} {usable} {c.filename}")
        lines.append(f"     类型:{c.content_type} | 角色:{c.editing_role} | 质量:{c.quality}/5 | 置信度:{c.confidence:.0%}")
        if c.issues: lines.append(f"     问题: {', '.join(c.issues)}")
        lines.append(f"     {c.notes}")
        lines.append("")

    lines.extend(["━━━ 🎬 素材统计 ━━━", ""])
    for role, count in batch.summary.items():
        if count > 0:
            lines.append(f"  {role_icon.get(role,'📹')} {role}: {count}个")

    lines.extend(["", "━━━ 💡 建议 ━━━", ""])
    for rec in batch.recommendations:
        lines.append(f"  {rec}")

    return "\n".join(lines)
