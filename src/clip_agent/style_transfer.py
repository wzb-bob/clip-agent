"""
参考视频风格迁移 · 分析参考视频→提取剪辑DNA→应用到目标素材

"让我的视频剪得像这个一样" — 业界最需要的功能
"""
from __future__ import annotations
import json, logging, os, subprocess, time
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EditingDNA:
    """从参考视频中提取的剪辑DNA"""
    # 节奏
    avg_shot_duration: float      # 平均镜头时长(秒)
    shot_duration_variance: float # 镜头时长变化幅度
    rhythm: str                   # fast/medium/slow
    bpm_estimate: float           # 估算BPM

    # 转场
    transition_types: dict        # {cut: 0.7, dissolve: 0.2, fade: 0.1}
    avg_transition_duration: float

    # 色彩
    dominant_colors: list[str]    # 主导色调
    color_filter: str             # 滤镜名称
    saturation_level: float       # 饱和度(0-2)

    # 构图
    shot_size_distribution: dict  # {CU: 0.3, MS: 0.4, LS: 0.3}
    camera_moves: list[str]       # 常用运镜

    # 文字
    text_density: float           # 文字出现频率
    text_position_preference: str # bottom/center/top
    text_animation_style: str     # 常用动画

    # B-roll
    broll_ratio: float            # B-roll占比
    broll_insertion_pattern: str  # 均匀分布/集中/开头密集

    # 音频
    bgm_energy: str               # high/medium/low
    voiceover_to_bgm_ratio: float # 人声:BGM音量比

    # Hook
    hook_duration: float          # 开头钩子时长
    hook_style: str               # 价格冲击/反常识/情感/故事


DNA_ANALYSIS_PROMPT = """你是顶级视频剪辑分析师。分析这段视频的剪辑风格。返回严格JSON。

## 需要精确判断:
1. 平均每个镜头几秒? 镜头时长变化大吗(有的2秒有的8秒)?
2. 用什么转场? 硬切多还是叠化多? 有淡入淡出吗?
3. 整体色调: 暖色/冷色/高对比/柔和/鲜艳?
4. 景别分布: 特写多(CU)? 中景多(MS)? 全景多(LS)?
5. 运镜: 固定多? 推拉多? 手持多?
6. 画面中有文字吗? 文字什么位置? 什么动画?
7. B-roll(非人物画面)占比多少? 怎么插入的?
8. 有没有BGM? BGM能量感如何?
9. 开头几秒? 什么钩子类型?
10. 整体节奏: 快(平均<2s/镜)/中(2-4s)/慢(>4s)?

## 输出(严格JSON):
{"avg_shot_duration":3.5,"shot_duration_variance":1.2,"rhythm":"medium","bpm_estimate":110,
 "transition_types":{"cut":0.7,"dissolve":0.2,"fade":0.1},"avg_transition_duration":0.4,
 "dominant_colors":["暖色","红色"],"color_filter":"亮夏","saturation_level":1.2,
 "shot_sizes":{"CU":0.3,"MS":0.5,"LS":0.2},"camera_moves":["static","push_in"],
 "text_density":0.4,"text_position":"bottom","text_animation":"fade_in",
 "broll_ratio":0.35,"broll_pattern":"均匀分布",
 "bgm_energy":"medium","voiceover_bgm_ratio":0.3,
 "hook_duration":3,"hook_style":"价格冲击",
 "editing_style_description":"快节奏产品展示风格,大量特写+硬切,红色/暖色调,文字密集在底部","confidence":0.85}"""


def extract_editing_dna(video_path: str) -> EditingDNA | None:
    """从参考视频中提取剪辑DNA"""
    import re

    if not os.path.exists(video_path):
        return None

    try:
        # 先做技术分析
        from app.services.open_source_edit import detect_scenes_adaptive, detect_beats_librosa

        scenes = detect_scenes_adaptive(video_path, threshold=30)
        durations = [s["duration"] for s in scenes] if scenes else [3.0]
        avg_dur = float(np.mean(durations))
        dur_var = float(np.std(durations))

        beats = detect_beats_librosa(video_path)
        bpm = beats.get("bpm", 120.0)

        rhythm = "fast" if avg_dur < 2.5 else ("slow" if avg_dur > 5 else "medium")

        # 用Kimi K2.6视觉分析风格
        from app.services.material_analyzer import MaterialAnalyzer
        ma = MaterialAnalyzer()
        mid_frame = ma._extract_frame(Path(video_path), 5.0)

        style_data = {}
        if mid_frame:
            from app.services.clip_agent.media_analyzer import _call_vision_api
            style_data = _call_vision_api(mid_frame, DNA_ANALYSIS_PROMPT, "参考视频风格分析")

        return EditingDNA(
            avg_shot_duration=round(avg_dur, 1),
            shot_duration_variance=round(dur_var, 1),
            rhythm=rhythm,
            bpm_estimate=round(bpm, 1),
            transition_types=style_data.get("transition_types", {"cut": 0.7, "dissolve": 0.2, "fade": 0.1}),
            avg_transition_duration=float(style_data.get("avg_transition_duration", 0.4)),
            dominant_colors=style_data.get("dominant_colors", ["中性"]),
            color_filter=style_data.get("color_filter", "亮肤"),
            saturation_level=float(style_data.get("saturation_level", 1.0)),
            shot_size_distribution=style_data.get("shot_sizes", {"CU": 0.3, "MS": 0.5, "LS": 0.2}),
            camera_moves=style_data.get("camera_moves", ["static"]),
            text_density=float(style_data.get("text_density", 0.3)),
            text_position_preference=style_data.get("text_position", "bottom"),
            text_animation_style=style_data.get("text_animation", "fade_in"),
            broll_ratio=float(style_data.get("broll_ratio", 0.35)),
            broll_insertion_pattern=style_data.get("broll_pattern", "均匀分布"),
            bgm_energy=style_data.get("bgm_energy", "medium"),
            voiceover_to_bgm_ratio=float(style_data.get("voiceover_bgm_ratio", 0.3)),
            hook_duration=float(style_data.get("hook_duration", 3.0)),
            hook_style=style_data.get("hook_style", "价格冲击"),
        )

    except Exception as e:
        logger.warning("风格提取失败: %s", e)
        return None


def apply_style_to_segments(segments: list, dna: EditingDNA) -> list:
    """将剪辑DNA应用到分镜片段上——按照参考视频的风格重新编排"""
    shot_sizes = list(dna.shot_size_distribution.keys())
    transitions = list(dna.transition_types.keys())
    cam_moves = dna.camera_moves

    styled = []
    for i, seg in enumerate(segments):
        # 应用参考视频的景别分布
        target_size = shot_sizes[i % len(shot_sizes)] if shot_sizes else "MS"
        # 应用转场分布
        trans_out = transitions[i % len(transitions)] if transitions else "cut"
        # 应用运镜
        cam = cam_moves[i % len(cam_moves)] if cam_moves else "static"
        # 应用镜头时长
        dur = max(1.5, min(dna.avg_shot_duration, 8.0))

        seg.update({
            "shot_type": target_size,
            "transition_out": trans_out,
            "camera_move": cam,
            "duration_sec": round(dur, 1),
            "_style_source": "reference_transfer",
        })
        styled.append(seg)

    return styled


def describe_dna(dna: EditingDNA) -> str:
    """人类可读的风格描述"""
    return (
        f"节奏: {dna.rhythm}({dna.avg_shot_duration}s/镜) | "
        f"转场: {max(dna.transition_types, key=dna.transition_types.get)}为主 | "
        f"滤镜: {dna.color_filter} | "
        f"B-roll: {dna.broll_ratio:.0%} | "
        f"色调: {','.join(dna.dominant_colors[:2])} | "
        f"钩子: {dna.hook_duration}s {dna.hook_style}"
    )
