"""
节奏引擎 v1 · 语速+能量→自动调 pacing

核心: 不是死板的"每段3秒"——根据实际说话节奏动态调整
  快语速(>5字/秒)→短镜(1-2s)·快切
  慢语速(<3字/秒)→长镜(4-8s)·缓切
  能量峰值→强调点(缩放/大字/音效)
  自然停顿→B-roll插入时机
"""
from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RhythmProfile:
    """一段口播的节奏特征"""
    avg_speed_cps: float = 4.0      # 平均语速(字/秒)
    speed_variance: float = 0.0      # 语速变化幅度
    energy_peaks: list[float] = None  # 能量峰值时间点
    pause_points: list[float] = None  # 自然停顿时间点
    overall_pace: str = "medium"      # fast/medium/slow
    recommended_shot_dur: float = 3.0 # 推荐镜长


def analyze_rhythm(whisper_segments: list[dict], energy_data: list[dict] = None) -> RhythmProfile:
    """
    分析口播的节奏特征。

    输入: Whisper转录段(含speed_cps)+ 可选librosa能量数据
    输出: RhythmProfile — 驱动剪辑 pacing 的核心参数
    """
    profile = RhythmProfile()

    if not whisper_segments:
        return profile

    # 语速分析
    speeds = [s.get("speed_cps", 4.0) for s in whisper_segments if s.get("speed_cps", 0) > 0]
    if speeds:
        profile.avg_speed_cps = sum(speeds) / len(speeds)
        mean_s = profile.avg_speed_cps
        profile.speed_variance = sum((s - mean_s) ** 2 for s in speeds) / len(speeds)

    # 节奏分类
    if profile.avg_speed_cps > 5.0:
        profile.overall_pace = "fast"
        profile.recommended_shot_dur = 2.0
    elif profile.avg_speed_cps < 3.0:
        profile.overall_pace = "slow"
        profile.recommended_shot_dur = 5.0
    else:
        profile.overall_pace = "medium"
        profile.recommended_shot_dur = 3.0

    # 能量峰值
    if energy_data:
        profile.energy_peaks = [
            e.get("at_sec", 0) for e in energy_data
            if e.get("type") == "emphasis" or e.get("energy", 0) > 0.7
        ]

    # 停顿点
    profile.pause_points = [
        s.get("end", s.get("start", 0) + s.get("duration_sec", 3.0))
        for s in whisper_segments if s.get("speed_cps", 4.0) < profile.avg_speed_cps * 0.5
    ]

    logger.info("节奏: %s·%.1f字/s·镜长%.1fs·%d峰值·%d停顿",
               profile.overall_pace, profile.avg_speed_cps,
               profile.recommended_shot_dur,
               len(profile.energy_peaks or []), len(profile.pause_points or []))

    return profile


def apply_rhythm_to_plan(plan_segments: list, rhythm: RhythmProfile) -> list:
    """
    将节奏特征应用到剪辑计划——调整每段的时长和转场。

    - 语速快的段缩短20-30%
    - 语速慢的段延长20-30%
    - 能量峰值处用cut硬切(冲击感)
    - 停顿处用dissolve(柔和过渡)
    """
    if not plan_segments or rhythm.avg_speed_cps == 0:
        return plan_segments

    for i, seg in enumerate(plan_segments):
        dur = getattr(seg, "duration_sec", None) or seg.get("duration_sec", 3.0) if isinstance(seg, dict) else 3.0

        # 语速调整
        if rhythm.overall_pace == "fast":
            dur *= 0.75
        elif rhythm.overall_pace == "slow":
            dur *= 1.3

        # 能量峰值用硬切
        start = getattr(seg, "start_sec", 0) or (seg.get("start_sec", 0) if isinstance(seg, dict) else 0)
        near_peak = any(abs(p - start) < 0.5 for p in (rhythm.energy_peaks or []))

        if hasattr(seg, "duration_sec"):
            seg.duration_sec = round(dur, 2)
        elif isinstance(seg, dict):
            seg["duration_sec"] = round(dur, 2)

        if near_peak and hasattr(seg, "transition_in"):
            seg.transition_in = "cut"
            if hasattr(seg, "emphasis_effect"):
                seg.emphasis_effect = "能量峰值强调"
                seg.is_golden_moment = True

    return plan_segments
