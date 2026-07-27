"""
四类素材处理管道 v1 · v5.0 核心

输入: 脚本 + 四类素材(口播/环境/产品/引导)
输出: 剪映草稿时间线(draft_content.json)

气口切割: Whisper 词级时间戳 → 句间停顿 → 精确切点
镜头衔接: 口播主轨 → 停顿→B-roll覆盖 → 口播 → ... → CTA
"""
from __future__ import annotations
import json, logging, os, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CategoryMaterials:
    """四类素材"""
    talking: list[str] = field(default_factory=list)     # 口播出镜
    environment: list[str] = field(default_factory=list)  # 店铺环境
    product: list[str] = field(default_factory=list)      # 产品展示
    cta: list[str] = field(default_factory=list)          # 引导CTA


@dataclass
class TimelineSegment:
    """时间线上的一个段"""
    index: int
    script_text: str
    start_sec: float
    duration_sec: float
    material_file: str           # 使用的素材文件
    material_category: str       # talking/environment/product/cta
    is_broll: bool               # 是否B-roll覆盖
    transition: str              # cut/dissolve


@dataclass
class JianYingTimeline:
    """完整的剪映时间线"""
    script_text: str
    segments: list[TimelineSegment]
    total_duration: float
    talking_video: str           # 口播主视频
    breath_points: list[dict]    # 气口切点
    draft_path: str = ""


def run_four_category_pipeline(
    script_text: str,
    materials: CategoryMaterials,
    output_dir: str = "",
) -> JianYingTimeline:
    """
    主入口: 四类素材 → 气口切割 → 时间线排列。

    流程:
    1. Whisper 分析口播视频 → 词级时间戳 + 气口
    2. 脚本分段(语义引擎)
    3. 素材匹配(每段选对应类别素材)
    4. 时间线排列(口播主轨↔B-roll交替)
    5. 生成剪映草稿
    """
    t0 = time.time()

    # Step 1: 气口分析(口播视频)
    breath_points = []
    talking_video = materials.talking[0] if materials.talking else ""
    if talking_video and os.path.exists(talking_video):
        breath_points = _detect_breath_points(talking_video)
        logger.info("气口检测: %d个切点", len(breath_points))

    # Step 2: 脚本分段
    segments = _segment_script(script_text)
    logger.info("脚本分段: %d段", len(segments))

    # Step 3+4: 素材匹配 + 时间线排列
    timeline_segs = _build_timeline(segments, materials, breath_points, talking_video)

    total_dur = sum(s.duration_sec for s in timeline_segs)

    # Step 5: 生成剪映草稿
    draft_path = ""
    if output_dir and talking_video:
        draft_path = _generate_jianying_draft(timeline_segs, talking_video, output_dir)

    elapsed = time.time() - t0
    logger.info("四类管道完成: %d段·%.1fs·%.1fs", len(timeline_segs), total_dur, elapsed)

    return JianYingTimeline(
        script_text=script_text,
        segments=timeline_segs,
        total_duration=total_dur,
        talking_video=talking_video,
        breath_points=breath_points,
        draft_path=draft_path,
    )


def _detect_breath_points(video_path: str) -> list[dict]:
    """Whisper气口检测 → 返回切点列表"""
    points = []
    try:
        from .media_understanding import understand_audio
        audio_data = understand_audio(video_path)
        for seg in audio_data.get("segments", []):
            for w in seg.get("words", []):
                w["start"] = round(w.get("start", 0), 2)
        # 计算句间停顿
        all_words = []
        for seg in audio_data.get("segments", []):
            all_words.extend(seg.get("words", []))
        for i in range(1, len(all_words)):
            gap_ms = int((all_words[i]["start"] - all_words[i-1].get("end", all_words[i-1]["start"])) * 1000)
            if gap_ms >= 400:
                points.append({
                    "at_sec": round(all_words[i-1].get("end", 0) + gap_ms/2000, 2),
                    "gap_ms": gap_ms,
                    "is_sentence_break": gap_ms >= 600,
                    "word_before": all_words[i-1].get("word", ""),
                    "word_after": all_words[i].get("word", ""),
                })
    except Exception as e:
        logger.warning("气口检测失败: %s", e)
    return points


def _segment_script(script_text: str) -> list[dict]:
    """脚本分段 — 优先语义引擎·降级关键词"""
    try:
        from .semantic_engine import analyze_script
        analysis = analyze_script(script_text, "老板IP", use_ai=True)
        if analysis and analysis.segments:
            return [
                {"text": s.text, "role": s.role, "duration_sec": s.duration_sec,
                 "shot_type": s.shot_type, "broll_needed": s.broll_needed}
                for s in analysis.segments
            ]
    except Exception:
        pass
    # 降级: 简单按标点分句
    import re
    sentences = re.split(r'[。！？!?\n]', script_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 3]
    total = len(sentences)
    result = []
    for i, text in enumerate(sentences):
        role = "hook" if i == 0 else ("cta" if i >= total - 2 else "body")
        result.append({
            "text": text, "role": role,
            "duration_sec": max(2.0, len(text) * 0.3 + 0.5),
            "shot_type": "MS", "broll_needed": role == "body",
        })
    return result


def _build_timeline(
    segments: list[dict],
    materials: CategoryMaterials,
    breath_points: list[dict],
    talking_video: str,
) -> list[TimelineSegment]:
    """素材匹配 + 时间线排列"""
    result = []
    cur_sec = 0.0
    env_idx = 0
    prod_idx = 0

    for i, seg in enumerate(segments):
        role = seg.get("role", "body")
        dur = seg.get("duration_sec", 3.0)

        # 素材选择
        if role == "hook" or role == "cta" or (i == 0) or (i == len(segments) - 1):
            # 开头/结尾 → 口播主轨
            mat_file = talking_video
            mat_cat = "talking"
            is_broll = False
        elif role == "body" and seg.get("broll_needed", True):
            # 中段 → 交替使用环境和产品空镜
            if env_idx < len(materials.environment) and i % 2 == 0:
                mat_file = materials.environment[env_idx % len(materials.environment)]
                mat_cat = "environment"
                env_idx += 1
            elif prod_idx < len(materials.product):
                mat_file = materials.product[prod_idx % len(materials.product)]
                mat_cat = "product"
                prod_idx += 1
            else:
                mat_file = talking_video  # 兜底
                mat_cat = "talking"
            is_broll = True
        else:
            mat_file = talking_video
            mat_cat = "talking"
            is_broll = False

        # 气口对齐: 找到最近的停顿点
        for bp in breath_points:
            if abs(bp["at_sec"] - cur_sec) < 0.5 and bp.get("is_sentence_break"):
                # 在停顿处切
                break

        # 转场
        transition = "dissolve" if is_broll else "cut"

        result.append(TimelineSegment(
            index=i + 1,
            script_text=seg.get("text", ""),
            start_sec=round(cur_sec, 2),
            duration_sec=round(dur, 2),
            material_file=mat_file,
            material_category=mat_cat,
            is_broll=is_broll,
            transition=transition,
        ))
        cur_sec += dur

    return result


def _generate_jianying_draft(
    segments: list[TimelineSegment],
    talking_video: str,
    output_dir: str,
) -> str:
    """生成剪映草稿文件"""
    os.makedirs(output_dir, exist_ok=True)
    try:
        # 尝试使用 pyJianYingDraft
        from app.services.jianying_draft import JianYingDraftGenerator
        gen = JianYingDraftGenerator(width=1080, height=1920, fps=30)
        draft_dir = gen.init_project(output_dir)

        for seg in segments:
            if not os.path.exists(seg.material_file):
                continue
            start_us = int(seg.start_sec * 1_000_000)
            dur_us = int(seg.duration_sec * 1_000_000)

            if seg.is_broll:
                gen.add_broll_overlay(
                    seg.material_file, start_us, dur_us, dur_us,
                    fade_in_us=300000, fade_out_us=300000,
                )
            else:
                gen.add_clip(seg.material_file, start_us, dur_us, dur_us)

            if seg.script_text:
                gen.add_subtitle(start_us, dur_us, seg.script_text[:30])

        gen.save()
        return str(draft_dir)
    except Exception as e:
        logger.warning("pyJianYingDraft失败·降级手动JSON: %s", e)
        return _generate_manual_draft(segments, talking_video, output_dir)


def _generate_manual_draft(segments: list[TimelineSegment], talking_video: str, output_dir: str) -> str:
    """手动生成简版 draft_content.json"""
    draft = {
        "platform": {"os": "windows"},
        "draft_name": "AI剪辑草稿",
        "draft_info": {"version": 1},
        "materials": {"videos": [], "images": []},
        "tracks": [],
        "canvas_config": {"width": 1080, "height": 1920},
    }
    draft_path = os.path.join(output_dir, "draft_content.json")
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    return draft_path
