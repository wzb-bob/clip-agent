"""
素材匹配器 · 抖音剪映模式核心 — 用户按分镜拍摄→上传→AI自动匹配→一键成片

输入: ShotList(分镜脚本) + 用户上传的素材文件
输出: 匹配后的ClipPlan — 每个分镜自动分配到最合适的素材，时间线已填充
"""
from __future__ import annotations
import json, logging, re, os, base64
from dataclasses import dataclass, field
from pathlib import Path
logger = logging.getLogger(__name__)

from .shotlist_generator import ShotList, ShotSpec
from .media_analyzer import MediaFile, MaterialAnalysis, _call_vision_api, _probe_video

@dataclass
class MatchedShot:
    """一个已匹配的分镜——素材已分配"""
    shot: ShotSpec
    matched_material: MediaFile | None    # 匹配到的素材
    material_analysis: MaterialAnalysis | None  # 素材分析结果
    confidence: float                     # 匹配置信度 0-1
    match_reason: str                     # 为什么匹配

@dataclass
class MatchResult:
    """完整匹配结果——可直接用于生成ClipPlan"""
    shotlist: ShotList
    matched_shots: list[MatchedShot]
    unmatched_shots: list[ShotSpec]       # 没匹配到的分镜（缺素材）
    unused_materials: list[MediaFile]     # 没用上的素材
    overall_confidence: float
    ready_to_export: bool                 # 是否可以直接导出

MATCH_PROMPT = """你是视频剪辑师。判断这段素材最适合放在分镜脚本的哪个位置。
分镜要求: {shot_requirement}
素材分析: {material_analysis}
请返回匹配分数(0-1)和原因。只返回: {"score":0.85,"reason":"原因(10字)"}"""


def match_materials_to_shotlist(
    shotlist: ShotList,
    materials: list[MediaFile],
    provider: str = "",
    model: str = "",
) -> MatchResult:
    """
    核心匹配函数: 将用户上传的素材自动分配到分镜脚本的每个镜头位置上。

    算法:
    1. 对每个素材做视觉分析(如果还没分析过)
    2. 计算素材与每个分镜要求的匹配度
    3. 贪心分配: 每个分镜选最匹配的素材
    4. 标记未匹配的分镜(缺素材)和未使用的素材
    """
    if not shotlist.shots:
        raise ValueError("分镜脚本为空")
    if not materials:
        raise ValueError("没有上传素材")

    # 1. 分析所有素材
    material_analyses: list[tuple[MediaFile, MaterialAnalysis]] = []
    for mf in materials:
        analysis = _analyze_material_for_matching(mf)
        material_analyses.append((mf, analysis))

    # 2. 为每个分镜计算所有素材的匹配度
    matched_shots = []
    used_materials = set()

    for shot in shotlist.shots:
        best_match = None
        best_score = 0.0
        best_reason = ""

        for mf, analysis in material_analyses:
            if mf.filename in used_materials:
                continue
            score, reason = _score_match(shot, mf, analysis)
            if score > best_score:
                best_score = score
                best_match = (mf, analysis)
                best_reason = reason

        if best_match and best_score >= 0.3:  # 最低匹配阈值
            mf, analysis = best_match
            used_materials.add(mf.filename)
            matched_shots.append(MatchedShot(
                shot=shot, matched_material=mf,
                material_analysis=analysis,
                confidence=best_score, match_reason=best_reason,
            ))
        else:
            matched_shots.append(MatchedShot(
                shot=shot, matched_material=None,
                material_analysis=None,
                confidence=0.0,
                match_reason="未找到匹配素材——请按分镜要求拍摄",
            ))

    # 3. 统计
    unmatched = [ms.shot for ms in matched_shots if ms.matched_material is None]
    unused = [mf for mf, _ in material_analyses if mf.filename not in used_materials]
    confidences = [ms.confidence for ms in matched_shots]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return MatchResult(
        shotlist=shotlist,
        matched_shots=matched_shots,
        unmatched_shots=unmatched,
        unused_materials=unused,
        overall_confidence=round(avg_conf, 2),
        ready_to_export=(len(unmatched) == 0),
    )


def _analyze_material_for_matching(mf: MediaFile) -> MaterialAnalysis:
    """对单个素材做视觉分析（用于匹配）"""
    # 如果已有temp_path，尝试视觉分析
    if mf.temp_path and os.path.exists(mf.temp_path):
        try:
            if mf.file_type == "video":
                info = _probe_video(mf.temp_path)
                from ._imports import _try_import; MaterialAnalyzer = _try_import("app.services.material_analyzer", "MaterialAnalyzer")
                ma = MaterialAnalyzer()
                frame = ma._extract_frame(Path(mf.temp_path), info["duration"]/2)
                if frame:
                    data = _call_vision_api(frame, f"匹配用:{mf.filename}")
                    if data:
                        from .media_analyzer import _vision_to_analysis
                        a = _vision_to_analysis(data, mf.filename, mf.file_type)
                        a.duration = info["duration"]
                        return a
            else:  # image
                with open(mf.temp_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                data = _call_vision_api(b64, f"匹配用:{mf.filename}")
                if data:
                    from .media_analyzer import _vision_to_analysis
                    return _vision_to_analysis(data, mf.filename, mf.file_type)
        except Exception as e:
            logger.debug("匹配视觉分析失败(%s): %s", mf.filename, e)

    # 降级: 从文件名+类型推断
    fn = mf.filename.lower()
    has_face = any(kw in fn for kw in ["人","口播","talking","face","selfie","老板"])
    scene_type = "人物" if has_face else ("产品" if any(kw in fn for kw in ["产品","product","货"]) else "环境")
    return MaterialAnalysis(
        filename=mf.filename, file_type=mf.file_type, scene_type=scene_type,
        content_summary=f"{mf.file_type}:{mf.filename}", quality_score=3.5,
        suitable_for=["body"], analysis_source="heuristic",
    )


def _score_match(shot: ShotSpec, mf: MediaFile, analysis: MaterialAnalysis) -> tuple[float, str]:
    """计算素材与分镜要求的匹配度"""
    score = 0.0
    reasons = []

    # 1. 素材类型匹配 (40% 权重)
    mat_type = _map_required_to_scene(shot.required_material)
    if analysis.scene_type == mat_type:
        score += 0.4
        reasons.append(f"场景类型匹配({mat_type})")
    elif mat_type == "人物" and analysis.has_face:
        score += 0.3
        reasons.append("含人物")
    elif mat_type == "产品" and not analysis.has_face:
        score += 0.2
        reasons.append("非人物(可能产品)")

    # 2. 景别匹配 (30% 权重) — CU应该匹配CU级别内容
    shot_level = _shot_level(shot.shot_type)
    if analysis.quality_score >= 3.5:
        score += 0.15
        reasons.append("质量合格")
    # 内容描述关键词匹配
    if shot.what_to_shoot and analysis.content_summary:
        shot_words = set(shot.what_to_shoot)
        content_words = set(analysis.content_summary)
        overlap = len(shot_words & content_words) / max(len(shot_words), 1)
        score += overlap * 0.15
        if overlap > 0.2:
            reasons.append(f"内容匹配({overlap:.0%})")

    # 3. 文件名匹配 (20% 权重)
    fn_lower = mf.filename.lower()
    shot_words_lower = shot.what_to_shoot.lower()
    if any(w in fn_lower for w in shot_words_lower.split() if len(w) >= 2):
        score += 0.1
        reasons.append("文件名匹配")

    # 4. B-roll标记匹配 (10% 权重)
    if shot.broll_overlay and not analysis.has_face:
        score += 0.1
        reasons.append("适合B-roll")
    elif not shot.broll_overlay and analysis.has_face:
        score += 0.1
        reasons.append("适合口播")

    return min(score, 1.0), "; ".join(reasons) if reasons else "综合匹配"


def _map_required_to_scene(required: str) -> str:
    mapping = {
        "product_closeup":"产品","talking_head":"人物","environment":"环境",
        "customer":"人物","text_card":"文字","transition":"环境",
    }
    return mapping.get(required, "环境")


def _shot_level(shot_type: str) -> int:
    """景别→数字级别: 越大越特写"""
    levels = {"ELS":0,"LS":1,"MLS":2,"MS":3,"MCU":4,"CU":5,"ECU":6}
    return levels.get(shot_type, 3)


def build_clip_plan_from_match(match: MatchResult) -> "ClipPlan":
    """从匹配结果构建完整ClipPlan——自动填充时间线"""
    from .clip_planner import ClipPlan, VideoSegment
    from .clip_templates import get_template, auto_select_template

    template_key = auto_select_template([], match.shotlist.script_type)
    template = get_template(template_key) or get_template("团购售卖")

    segments = []
    cur = 0.0
    for i, ms in enumerate(match.matched_shots):
        shot = ms.shot
        if ms.matched_material:
            # 匹配成功: 用实际素材
            fn = ms.matched_material.filename
            trans_in = shot.transition_in if i > 0 else "fade_in"
            trans_out = shot.transition_out if i < len(match.matched_shots)-1 else "fade_out"
            segments.append(VideoSegment(
                segment_id=i+1, section="opening" if i==0 else ("ending" if i==len(match.matched_shots)-1 else "body"),
                sub_type="broll" if shot.broll_overlay else "talking",
                label=shot.label, material_index=i, material_filename=fn,
                start_sec=cur, duration_sec=shot.duration_sec,
                shot_type=shot.shot_type, camera_move=shot.camera_move,
                composition=shot.composition, color_tone=shot.color_tone,
                transition_in=trans_in, transition_out=trans_out,
                covers_audio=shot.broll_overlay,
                description=shot.shooting_guide,
                action_guide=shot.action_guide,
                has_subtitle=bool(shot.text_overlay),
                subtitle_text=shot.text_overlay,
                subtitle_position=shot.text_position,
            ))
        else:
            # 未匹配: 占位
            segments.append(VideoSegment(
                segment_id=i+1, section="body", sub_type="broll",
                label=f"⚠️缺素材: {shot.label}",
                material_index=0, material_filename="缺素材",
                start_sec=cur, duration_sec=shot.duration_sec,
                shot_type=shot.shot_type, camera_move="static",
                description=f"请按分镜要求拍摄: {shot.shooting_guide}",
                has_subtitle=True, subtitle_text=shot.text_overlay,
            ))
        cur += shot.duration_sec

    total_dur = sum(s.duration_sec for s in segments)
    return ClipPlan(
        plan_id=1, plan_name=f"{match.shotlist.project_name} · 自动匹配",
        plan_style=f"基于分镜脚本自动匹配 | 置信度{match.overall_confidence:.0%}",
        template_key=template_key,
        total_duration=total_dur, body_duration=total_dur-6, opening_duration=3, ending_duration=3,
        visual_strategy="good_presence",
        voiceover_duration=total_dur, voiceover_available=True,
        bgm_suggestion=match.shotlist.bgm_suggestion,
        bgm_style=template.get("bgm_style",""),
        segments=segments,
        summary=f"自动匹配剪辑: {len(match.matched_shots)}镜/{match.unmatched_shots.__len__()}未匹配 | 置信度{match.overall_confidence:.0%}",
        difficulty="简单", estimated_time="5分钟",
    )


def format_match_report(match: MatchResult) -> str:
    """生成匹配报告——给用户看"""
    lines = [
        f"══════════════════════",
        f"  📊 素材匹配报告: {match.shotlist.project_name}",
        f"  整体置信度: {match.overall_confidence:.0%}",
        f"  {'✅ 全部匹配，可以导出!' if match.ready_to_export else '⚠️ 有分镜缺少素材'}",
        f"══════════════════════",
        "", "━━━ 📸 匹配详情 ━━━", ""
    ]
    for ms in match.matched_shots:
        status = f"✅ {ms.matched_material.filename}" if ms.matched_material else "❌ 缺素材"
        conf = f"置信度{ms.confidence:.0%}" if ms.confidence > 0 else ""
        lines.append(f"  【{ms.shot.label}】→ {status} {conf}")
        if ms.match_reason:
            lines.append(f"    匹配原因: {ms.match_reason}")
        if not ms.matched_material:
            lines.append(f"    📷 请拍摄: {ms.shot.shooting_guide}")

    if match.unused_materials:
        lines.extend(["", "━━━ 📦 未使用的素材 ━━━", ""])
        for mf in match.unused_materials:
            lines.append(f"  📹 {mf.filename} — 没有对应分镜")

    return "\n".join(lines)
