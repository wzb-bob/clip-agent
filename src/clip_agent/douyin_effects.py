"""
抖音剪映能力补齐 · 自动卡点+字幕动画+调色滤镜+Ken Burns关键帧

对照剪映自动剪辑能力，补齐我们缺失的核心功能。
"""
from __future__ import annotations
import json, logging, os, subprocess, tempfile
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


# ================================================================
# 1. 自动卡点 — 音频节拍检测 → 剪辑时间线对齐
# ================================================================

@dataclass
class BeatInfo:
    """节拍信息"""
    bpm: float
    beat_times: list[float]    # 每个节拍的时间点(秒)
    downbeat_times: list[float] # 重拍时间点
    energy_curve: list[float]   # 能量曲线(用于找高潮段)
    has_audio: bool

def detect_beats(audio_path: str, bpm_hint: float = 120.0) -> BeatInfo:
    """检测音频节拍——返回BPM和节拍时间点列表"""
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=22050, duration=60.0)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, start_bpm=bpm_hint)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # 检测重拍(每4拍的第一拍)
        downbeat_times = [beat_times[i] for i in range(0, len(beat_times), 4)]

        # 能量曲线(找音乐高潮段)
        energy = librosa.feature.rms(y=y)[0]
        energy_times = librosa.frames_to_time(range(len(energy)), sr=sr)
        energy_curve = [float(e) for e in energy[::10][:len(beat_times)]]

        logger.info("节拍检测: BPM=%.1f, %d拍, %d重拍", float(tempo), len(beat_times), len(downbeat_times))
        return BeatInfo(
            bpm=float(tempo), beat_times=[float(t) for t in beat_times],
            downbeat_times=downbeat_times, energy_curve=energy_curve,
            has_audio=True,
        )
    except ImportError:
        logger.warning("librosa未安装,降级使用BPM提示")
    except Exception as e:
        logger.warning("节拍检测失败: %s", e)

    # 降级: 用BPM提示生成均匀节拍
    beat_interval = 60.0 / bpm_hint
    return BeatInfo(
        bpm=bpm_hint,
        beat_times=[i * beat_interval for i in range(int(60 / beat_interval))],
        downbeat_times=[i * beat_interval * 4 for i in range(int(60 / beat_interval / 4))],
        energy_curve=[1.0] * 100, has_audio=False,
    )


def align_cuts_to_beats(segments: list, beat_info: BeatInfo) -> list[dict]:
    """将剪辑时间线对齐到最近的节拍点——抖音卡点剪辑核心"""
    if not beat_info.beat_times:
        return [{"original_sec": s.duration_sec if hasattr(s, 'duration_sec') else 3.0,
                 "aligned_sec": s.duration_sec if hasattr(s, 'duration_sec') else 3.0,
                 "beat_index": 0} for s in segments]

    aligned = []
    cur_beat_idx = 0
    for seg in segments:
        dur = seg.duration_sec if hasattr(seg, 'duration_sec') else 3.0
        # 找到包含当前时间点的最近节拍
        beats_in_range = [b for b in beat_info.beat_times if b >= (cur_beat_idx * 60 / beat_info.bpm) * 0.8]
        if beats_in_range:
            nearest_beat = min(beats_in_range, key=lambda b: abs(b - (aligned[-1]["aligned_end"] if aligned else 0)))
            beat_dur = round(nearest_beat - (aligned[-1]["aligned_end"] if aligned else 0), 2)
            if 1.0 <= beat_dur <= 10.0:
                dur = beat_dur

        aligned.append({
            "original_sec": seg.duration_sec if hasattr(seg, 'duration_sec') else 3.0,
            "aligned_sec": dur,
            "aligned_end": (aligned[-1]["aligned_end"] if aligned else 0) + dur,
            "beat_index": cur_beat_idx,
        })
        cur_beat_idx += max(1, int(dur / (60 / beat_info.bpm)))

    return aligned


# ================================================================
# 2. 字幕动画预设 — 抖音风格文字动画
# ================================================================

TEXT_ANIMATIONS = {
    "fade_in": {"name": "淡入", "in_dur_ms": 300, "out_dur_ms": 200, "css_class": "fade-in"},
    "slide_up": {"name": "上滑入", "in_dur_ms": 400, "out_dur_ms": 300, "css_class": "slide-up"},
    "pop_in": {"name": "弹入", "in_dur_ms": 250, "out_dur_ms": 200, "css_class": "pop-in", "scale_from": 0.5},
    "typewriter": {"name": "打字机", "in_dur_ms": 800, "out_dur_ms": 200, "css_class": "typewriter"},
    "fly_right": {"name": "右飞入", "in_dur_ms": 400, "out_dur_ms": 300, "css_class": "fly-right"},
    "scale_bounce": {"name": "缩放弹跳", "in_dur_ms": 350, "out_dur_ms": 250, "css_class": "scale-bounce", "scale_from": 1.2},
    "glitch": {"name": "故障风格", "in_dur_ms": 200, "out_dur_ms": 150, "css_class": "glitch"},
    "countdown": {"name": "倒计时闪烁", "in_dur_ms": 150, "out_dur_ms": 100, "css_class": "countdown", "blink": True},
}

TEXT_STYLES = {
    "price": {"font_size": 72, "color": "#FF4444", "stroke": "#000000", "stroke_width": 4, "animation": "pop_in", "position": "center"},
    "hook": {"font_size": 56, "color": "#FFFFFF", "stroke": "#000000", "stroke_width": 3, "animation": "fade_in", "position": "center"},
    "body": {"font_size": 42, "color": "#FFFFFF", "stroke": "#333333", "stroke_width": 2, "animation": "slide_up", "position": "bottom"},
    "cta": {"font_size": 48, "color": "#FFD700", "stroke": "#000000", "stroke_width": 3, "animation": "scale_bounce", "position": "center"},
    "tag": {"font_size": 32, "color": "#AAAAAA", "stroke": "#000000", "stroke_width": 1, "animation": "fade_in", "position": "bottom"},
}


def get_text_style_for_segment(seg_label: str, text_overlay: str) -> dict:
    """根据分镜标签和文字内容自动选择文字样式"""
    if not text_overlay:
        return TEXT_STYLES["body"]

    label_lower = seg_label.lower()
    text_len = len(text_overlay)

    # 价格/数字 → price样式(红色大字)
    if any(c.isdigit() for c in text_overlay) and text_len < 10:
        return TEXT_STYLES["price"]
    # 钩子/开头 → hook样式(白色大字居中)
    if "钩子" in label_lower or "开头" in label_lower or text_len < 12:
        return TEXT_STYLES["hook"]
    # CTA/结尾 → cta样式(金色)
    if "cta" in label_lower or "结尾" in label_lower or "关注" in text_overlay or "团购" in text_overlay:
        return TEXT_STYLES["cta"]
    # 标签 → tag样式
    if text_overlay.startswith("#"):
        return TEXT_STYLES["tag"]

    return TEXT_STYLES["body"]


# ================================================================
# 3. 自动调色 + Ken Burns关键帧
# ================================================================

COLOR_FILTERS = {
    "亮夏": {"brightness": 0.05, "contrast": 1.1, "saturation": 1.15, "warmth": 0.1},
    "书意": {"brightness": -0.05, "contrast": 1.05, "saturation": 0.85, "warmth": -0.05},
    "亮肤": {"brightness": 0.1, "contrast": 1.0, "saturation": 0.95, "warmth": 0.15},
    "无(自然色)": {"brightness": 0, "contrast": 1.0, "saturation": 1.0, "warmth": 0},
    "无(保持原色)": {"brightness": 0, "contrast": 1.0, "saturation": 1.0, "warmth": 0},
    "高对比": {"brightness": 0, "contrast": 1.3, "saturation": 1.2, "warmth": 0},
    "鲜艳": {"brightness": 0.05, "contrast": 1.15, "saturation": 1.4, "warmth": 0.1},
}


def apply_color_filter_cmd(color_name: str) -> str:
    """生成FFmpeg调色滤镜命令"""
    f = COLOR_FILTERS.get(color_name, COLOR_FILTERS["无(自然色)"])
    parts = []
    if f["brightness"] != 0:
        parts.append(f"eq=brightness={1+f['brightness']:.2f}")
    if abs(f["contrast"] - 1.0) > 0.01:
        if parts: parts[-1] += f":contrast={f['contrast']:.2f}"
        else: parts.append(f"eq=contrast={f['contrast']:.2f}")
    if f["saturation"] != 1.0:
        parts.append(f"eq=saturation={f['saturation']:.2f}")
    if not parts:
        parts.append("null")
    return ",".join(parts)


def ken_burns_keyframes(duration_sec: float, is_image: bool = True) -> list[dict]:
    """生成Ken Burns效果关键帧（缓慢缩放+平移，用于静态图片）"""
    if not is_image or duration_sec < 2.0:
        return []
    return [
        {"time": 0.0, "scale": 1.0, "pan_x": 0.0, "pan_y": 0.0},
        {"time": duration_sec * 0.3, "scale": 1.03, "pan_x": 0.01, "pan_y": -0.01},
        {"time": duration_sec * 0.7, "scale": 1.06, "pan_x": -0.01, "pan_y": 0.01},
        {"time": duration_sec, "scale": 1.08, "pan_x": 0.0, "pan_y": 0.0},
    ]


# ================================================================
# 4. 抖音风格效果综合应用
# ================================================================

def apply_douyin_style_to_plan(plan, audio_path: str = "", template_key: str = "") -> dict:
    """对剪辑方案应用抖音风格效果: 卡点对齐+文字样式+调色+Ken Burns

    Returns: 包含所有效果参数的dict,供导出时使用
    """
    from app.services.clip_agent.clip_templates import get_template

    template = get_template(template_key) or {}
    dna = template.get("editing_dna", {})

    effects = {
        "beat_alignment": None,
        "text_styles": [],
        "color_filter": dna.get("color_filter", "无(自然色)"),
        "ken_burns_segments": [],
        "bpm": template.get("default_bpm", 120),
    }

    # 1. 卡点对齐
    if audio_path and os.path.exists(audio_path):
        beats = detect_beats(audio_path, template.get("default_bpm", 120))
        if beats.has_audio:
            aligned = align_cuts_to_beats(plan.segments, beats)
            effects["beat_alignment"] = {
                "bpm": beats.bpm,
                "beat_count": len(beats.beat_times),
                "aligned_segments": aligned,
            }
            # 按节拍调整分镜时长
            for i, seg in enumerate(plan.segments):
                if i < len(aligned):
                    seg.duration_sec = aligned[i]["aligned_sec"]

    # 2. 文字样式
    for seg in plan.segments:
        if seg.has_subtitle and seg.subtitle_text:
            style = get_text_style_for_segment(seg.label, seg.subtitle_text)
            effects["text_styles"].append({
                "segment_id": seg.segment_id,
                "text": seg.subtitle_text,
                "style": style["animation"],
                "font_size": style["font_size"],
                "color": style["color"],
                "position": style["position"],
            })

    # 3. Ken Burns(对图片素材)
    for seg in plan.segments:
        if seg.covers_audio and seg.material_filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            effects["ken_burns_segments"].append({
                "segment_id": seg.segment_id,
                "keyframes": ken_burns_keyframes(seg.duration_sec, True),
            })

    return effects
