"""导演模块——真人剪辑师的决策大脑

融合"眼"(素材评分/内容匹配)+"耳"(气口/BPM)+"手"(渲染引擎)
→ 做出创意决策: 哪切·用啥素材·什么效果·快慢节奏
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EditDecision:
    """单个剪辑决策"""
    segment_index: int
    start_sec: float
    duration_sec: float
    material_path: str = ""
    material_type: str = "talking"      # talking/broll/product/environment
    transition: str = "cut"             # cut/fade/dissolve
    shader: str = ""                    # bleach_bypass/warm_grade等
    text_size: int = 56                 # 字幕字号
    overlay_text: str = ""              # 叠加文字
    broll_overlay: bool = False         # B-roll覆盖口播画面
    audio_replace: bool = False         # TTS替换音频
    energy: str = "medium"              # high/medium/low·影响切速
    emotion: str = ""                   # 当前情绪


@dataclass
class DirectorPlan:
    """导演完整剪辑计划"""
    category: str
    pacing: str              # fast/slow/variable
    bpm: float = 0
    groove: float = 0
    decisions: list[EditDecision] = field(default_factory=list)
    total_duration: float = 0
    material_variety: float = 0  # 0-1 素材多样性
    peak_moments: list[float] = field(default_factory=list)  # 高能时刻
    calm_moments: list[float] = field(default_factory=list)   # 舒缓时刻


def direct(
    video_path: str,
    script_text: str,
    shot_json: list[dict] = None,
    materials: dict[str, dict] = None,
    category: str = "团购售卖",
) -> DirectorPlan:
    """真人导演的决策流程——融合所有传感器数据做创意判断

    Args:
        video_path: 口播视频
        script_text: 口播文案
        shot_json: 脚本Agent分镜语言
        materials: {path: {"type":"talking","score":0.8,"has_face":True}, ...}
        category: 脚本类别
    """
    plan = DirectorPlan(category=category, pacing="medium")

    # ── 耳朵: 听节奏 ──
    try:
        from .breath_detector import BreathDetector
        from .rhythm_engine import detect_bpm, align_to_beat, analyze_rhythm
        from pathlib import Path

        breath = BreathDetector().analyze(Path(video_path))
        beat = detect_bpm(video_path)
        plan.bpm = beat.get("bpm", 0)
        plan.groove = beat.get("groove_strength", 0)

        # 切点融合: 气口∩节拍
        raw_cuts = [p.at_sec for p in breath.best_cuts] if breath.best_cuts else []
        if not raw_cuts:
            raw_cuts = [p.at_sec for p in breath.good_cuts[:8]]
        if not raw_cuts:
            # 无气口→用节拍等分
            raw_cuts = beat.get("beats", [])[::4]  # 每4拍一个切点

        aligned_cuts = align_to_beat(raw_cuts, beat)
        logger.info("导演决策: %d切点·%d对齐节拍·BPM=%.0f",
                   len(aligned_cuts),
                   sum(1 for a, b in zip(aligned_cuts, raw_cuts) if abs(a - b) > 0.01),
                   plan.bpm)
    except Exception as e:
        logger.debug("导演·耳朵模块跳过: %s", e)
        aligned_cuts = []
        # 降级: 用JSON分镜的时间点
        if shot_json:
            aligned_cuts = [s.get("start_sec", 0) for s in shot_json]

    # ── 眼睛: 选素材 ──
    material_map = {}  # {segment_index: material_path}
    try:
        if materials and shot_json:
            from .shot_material_matcher import (
                assign_materials_to_shots, material_variety_report)
            assignments = assign_materials_to_shots(shot_json, materials)
            for a in assignments:
                material_map[a.shot_index - 1] = a
            variety = material_variety_report(assignments)
            plan.material_variety = variety.get("diversity", 0)
            logger.info("导演决策: 素材多样性=%.0f%%·%d种素材",
                       plan.material_variety * 100,
                       variety.get("unique_materials", 0))
    except Exception as e:
        logger.debug("导演·眼睛模块跳过: %s", e)

    # ── 手: 做剪辑计划 ──
    # 类别节奏策略
    from .chatcut_vfx import CATEGORY_STYLE
    style = CATEGORY_STYLE.get(category, CATEGORY_STYLE["团购售卖"])
    plan.pacing = style.get("pacing", "medium")
    shot_range = style.get("shot_duration_range", [2.0, 4.0])
    text_priority = style.get("text_priority", "price_first")

    # 从shot_json提取情绪/景别
    shots = shot_json or []
    decisions = []

    for i, cut_start in enumerate(aligned_cuts):
        if i >= len(aligned_cuts) - 1:
            break
        dur = aligned_cuts[i + 1] - cut_start
        # 节奏调整: 快节奏→缩短·慢节奏→延长
        if plan.pacing == "fast":
            dur = max(shot_range[0], dur * 0.8)
        elif plan.pacing == "slow":
            dur = min(shot_range[1], dur * 1.3)

        # 获取该段shot信息
        shot = shots[i] if i < len(shots) else {}
        emotion = shot.get("emotion", "")
        shot_type = shot.get("shot_type", "中景")

        # 素材选择
        mat = material_map.get(i)
        mat_path = mat.assigned_material if mat else (list(materials.keys())[0] if materials else "")
        mat_type = mat.material_type if mat else "talking"
        is_overlay = mat.broll_overlay if mat else False
        needs_audio = mat.audio_replace if mat else False

        # 效果选择: 情绪→着色器
        from .shot_script import SHOT_EMOTION_SHADER
        shader = SHOT_EMOTION_SHADER.get(emotion, "")

        # 转场选择: 快节奏用cut·慢节奏用dissolve
        if plan.pacing == "fast":
            transition = "fade"
        elif plan.pacing == "slow":
            transition = "dissolve"
        else:
            transition = "fade" if plan.bpm > 100 else "dissolve"

        # 字号: 景别映射
        from .shot_script import SHOT_TEXT_SIZE
        text_size = SHOT_TEXT_SIZE.get(shot_type, 56)

        # 叠加文字: 按text_priority策略
        overlay = ""
        if text_priority == "price_first" and i == 0:
            overlay = shot.get("overlay_text", "")
        elif text_priority == "story_first" and i >= len(shots) // 3:
            overlay = shot.get("overlay_text", "")
        elif text_priority == "location_first" and i >= len(shots) - 2:
            overlay = shot.get("overlay_text", "")
        else:
            overlay = shot.get("overlay_text", "")

        # 能量判断: 冲击/紧迫情绪→高能·信任/共鸣→中低能
        energy = "high" if emotion in ("冲击", "紧迫") else (
            "medium" if emotion in ("信任", "渴望") else "low")

        decision = EditDecision(
            segment_index=i + 1,
            start_sec=round(cut_start, 2),
            duration_sec=round(dur, 2),
            material_path=mat_path,
            material_type=mat_type,
            transition=transition,
            shader=shader,
            text_size=text_size,
            overlay_text=overlay,
            broll_overlay=is_overlay,
            audio_replace=needs_audio,
            energy=energy,
            emotion=emotion,
        )
        decisions.append(decision)

        # 记录能量时刻
        if energy == "high":
            plan.peak_moments.append(cut_start)
        elif energy == "low":
            plan.calm_moments.append(cut_start)

    plan.decisions = decisions
    plan.total_duration = sum(d.duration_sec for d in decisions)

    logger.info("导演计划: %d段·%.1fs·节奏=%s·峰值=%d·舒缓=%d",
               len(decisions), plan.total_duration,
               plan.pacing,
               len(plan.peak_moments), len(plan.calm_moments))

    return plan
