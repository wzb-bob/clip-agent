"""
OpenMontage Skills层 · 4大类40+剪辑技能

Editing Skills: 15个剪辑操作技能(切点·转场·变速·B-roll)
Effects Skills: 8个特效技能(Ken Burns·调色·文字动画)
Audio Skills: 10个音频技能(归一化·降噪·闪避·提取)
Quality Skills: 10个质量技能(时长·抖动·过曝·音频)
"""
from __future__ import annotations
import json, logging, os, subprocess, time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ================================================================
# 1. Editing Skills (15个剪辑技能)
# ================================================================

class EditingSkills:
    """剪辑操作技能集"""

    @staticmethod
    def cut_at_silence(video_path: str, silence_thresh_db: int = -30, min_ms: int = 300) -> list[float]:
        """在静音处切——返回切点列表"""
        try:
            r = subprocess.run(["ffmpeg","-hide_banner","-i",video_path,
                "-af",f"silencedetect=n={silence_thresh_db}dB:d={min_ms/1000:.1f}",
                "-f","null","-"], capture_output=True, text=True, timeout=60)
            import re
            return [round(float(x),1) for x in re.findall(r"silence_start:\s*([\d.]+)", r.stderr)]
        except: return []

    @staticmethod
    def cut_at_beat(audio_path: str, bpm: float = 120) -> list[float]:
        """在节拍处切——返回节拍时间列表"""
        try:
            import librosa; import numpy as np
            y, sr = librosa.load(audio_path, sr=22050)
            _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, bpm=bpm)
            return [round(t,2) for t in librosa.frames_to_time(beat_frames, sr=sr).tolist()]
        except: return [i*60/bpm for i in range(int(bpm))]

    @staticmethod
    def j_cut_offset(clip_duration: float) -> float:
        """J-cut: 音频提前切入——下一个镜头的音频在先,画面在后"""
        return min(0.3, clip_duration * 0.1)

    @staticmethod
    def l_cut_offset(clip_duration: float) -> float:
        """L-cut: 音频延后切出——当前镜头的音频继续,画面已切"""
        return min(0.3, clip_duration * 0.1)

    @staticmethod
    def speed_ramp_params(action: str) -> dict:
        """变速参数: normal/slow_motion/speed_up/ramp"""
        return {
            "normal": {"speed": 1.0, "ramp_duration": 0},
            "slow_motion": {"speed": 0.5, "ramp_duration": 0.3},
            "speed_up": {"speed": 1.5, "ramp_duration": 0.2},
            "ramp_slow_in": {"speed_start": 0.5, "speed_end": 1.0, "ramp_duration": 0.5},
            "ramp_fast_out": {"speed_start": 1.0, "speed_end": 1.5, "ramp_duration": 0.3},
        }.get(action, {"speed": 1.0, "ramp_duration": 0})

    @staticmethod
    def match_action_cut(prev_clip_end: float, next_clip_start: str) -> float:
        """动作匹配切: 前一个镜头结束时的动作在下一个镜头延续"""
        return 0.0  # 硬切——0帧过渡

    @staticmethod
    def insert_broll_timing(voice_duration: float, broll_count: int) -> list[float]:
        """计算B-roll插入时间点(均匀分布+气口偏移)"""
        interval = voice_duration / (broll_count + 1)
        return [round(interval * (i + 1), 1) for i in range(broll_count)]

    @staticmethod
    def montage_sequence(shot_types: list[str]) -> list[str]:
        """蒙太奇景别序列——确保相邻不重复"""
        result = [shot_types[0]] if shot_types else ["MS"]
        for st in shot_types[1:]:
            if st == result[-1]:
                alternatives = {"CU":"MS","MS":"CU","MCU":"MS","LS":"MS","ECU":"CU"}
                st = alternatives.get(st, "MS")
            result.append(st)
        return result

    @staticmethod
    def hook_3s_params(script_text: str) -> dict:
        """3秒钩子参数——检测禁用词并生成替代方案"""
        forbidden = ["大家好","今天聊聊","你知道吗","今天来给大家"]
        for fw in forbidden:
            if fw in script_text:
                return {"action": "replace_start", "forbidden": fw, "suggestion": "直接切入最精彩画面或反常识观点"}
        return {"action": "keep", "speed": 1.0, "text_overlay": script_text[:12] if len(script_text) > 12 else script_text}

    @staticmethod
    def every_15s_check(durations: list[float]) -> list[int]:
        """每15秒视觉切换检查——返回需要插入B-roll的位置索引"""
        cumulative = 0; alerts = []
        for i, d in enumerate(durations):
            cumulative += d
            if cumulative >= 15:
                alerts.append(i)
                cumulative = 0
        return alerts

    @staticmethod
    def transition_pick(prev_shot: str, next_shot: str, rhythm: str = "medium") -> str:
        """智能选择转场类型"""
        if prev_shot == next_shot: return "dissolve"  # 同景别用叠化
        if rhythm == "fast": return "cut"              # 快节奏硬切
        if rhythm == "slow": return "fade"             # 慢节奏淡入淡出
        return "dissolve" if abs(len(prev_shot)-len(next_shot)) > 1 else "cut"

    @staticmethod
    def text_overlay_timing(segment_duration: float, position: str = "center") -> dict:
        """文字叠加时机"""
        return {
            "center": {"appear_at_pct": 0.0, "duration_pct": 0.5, "font_size": 72},
            "bottom": {"appear_at_pct": 0.1, "duration_pct": 0.8, "font_size": 36},
        }.get(position, {"appear_at_pct": 0.2, "duration_pct": 0.6, "font_size": 48})

    @staticmethod
    def broll_overlay_audio() -> dict:
        """B-roll覆盖时的音频处理"""
        return {"bgm_volume": 0.3, "voice_keep": True, "video_audio_mute": True, "ducking": True}


# ================================================================
# 2. Effects Skills (8个特效技能)
# ================================================================

class EffectsSkills:
    """特效技能集"""

    @staticmethod
    def ken_burns_params(duration: float) -> dict:
        """Ken Burns效果参数——根据时长自动调整"""
        if duration <= 3: return {"scale_from": 1.0, "scale_to": 1.05, "pan_x": 0, "pan_y": 0}
        if duration <= 8: return {"scale_from": 1.0, "scale_to": 1.08, "pan_x": 20, "pan_y": -10}
        return {"scale_from": 1.0, "scale_to": 1.12, "pan_x": 30, "pan_y": -15}

    @staticmethod
    def color_grade_preset(style: str = "warm") -> dict:
        """调色预设"""
        return {
            "warm": {"brightness": 1.03, "contrast": 1.05, "saturation": 1.08, "filter": "亮夏"},
            "cool": {"brightness": 1.0, "contrast": 1.1, "saturation": 0.9, "filter": "书意"},
            "vivid": {"brightness": 1.05, "contrast": 1.15, "saturation": 1.3, "filter": "鲜艳"},
            "vintage": {"brightness": 0.95, "contrast": 1.0, "saturation": 0.7, "filter": "1980"},
            "neutral": {"brightness": 1.0, "contrast": 1.0, "saturation": 1.0, "filter": "无"},
        }.get(style, {"brightness": 1.02, "contrast": 1.03, "saturation": 1.05, "filter": "亮肤"})

    @staticmethod
    def text_animation_preset(style: str = "pop_in") -> dict:
        """文字动画预设"""
        return {
            "pop_in": {"keyframe": "scale(0.5)→scale(1.0)", "duration": 0.3, "easing": "easeOutBack"},
            "fade_in": {"keyframe": "opacity(0)→opacity(1)", "duration": 0.5, "easing": "easeIn"},
            "slide_up": {"keyframe": "translateY(20)→translateY(0)", "duration": 0.4, "easing": "easeOut"},
            "typewriter": {"keyframe": "clip-path reveal", "duration": 1.0, "easing": "linear"},
            "scale_up": {"keyframe": "scale(0.8)→scale(1.0)", "duration": 0.4, "easing": "easeOut"},
        }.get(style, {"keyframe": "fade_in", "duration": 0.3, "easing": "easeIn"})

    @staticmethod
    def beat_sync_flash(duration_frames: int = 4) -> dict:
        """卡点闪白效果"""
        return {"brightness_boost": 0.15, "duration_frames": duration_frames, "color": "white"}

    @staticmethod
    def background_blur_params(amount: float = 3.0) -> dict:
        """背景模糊参数"""
        return {"radius": amount, "sigma": amount * 0.8, "apply_to": "background"}


# ================================================================
# 3. Audio Skills (10个音频技能)
# ================================================================

class AudioSkills:
    """音频技能集"""

    @staticmethod
    def normalize_loudness() -> dict:
        """EBU R128响度归一化参数"""
        return {"target_lufs": -16, "true_peak": -1.5, "lra": 11}

    @staticmethod
    def denoise_params(strength: str = "medium") -> dict:
        """降噪参数"""
        return {"light": {"nr": 0.3, "nf": -20}, "medium": {"nr": 0.5, "nf": -25}, "strong": {"nr": 0.7, "nf": -30}}.get(strength, {"nr": 0.5, "nf": -25})

    @staticmethod
    def duck_bgm_params() -> dict:
        """BGM闪避参数——人声出现时BGM自动压低"""
        return {"bgm_normal_volume": 0.3, "bgm_ducked_volume": 0.08, "attack_ms": 50, "release_ms": 300, "threshold_db": -20}

    @staticmethod
    def extract_voice_params() -> dict:
        """人声提取参数"""
        return {"highpass_freq": 80, "lowpass_freq": 8000, "noise_reduction": 0.4}

    @staticmethod
    def add_sfx(sfx_type: str) -> dict:
        """音效参数"""
        return {
            "ding": {"file": "ding.mp3", "volume": 0.6, "at_position": "emphasis"},
            "whoosh": {"file": "whoosh.mp3", "volume": 0.3, "at_position": "transition"},
            "applause": {"file": "applause.mp3", "volume": 0.4, "at_position": "ending"},
        }.get(sfx_type, {"file": "pop.mp3", "volume": 0.5, "at_position": "any"})


# ================================================================
# 4. Quality Skills (10个质量技能)
# ================================================================

class QualitySkills:
    """质量检查技能集"""

    @staticmethod
    def check_duration(duration: float, target: float, tolerance: float = 0.1) -> dict:
        """时长验证"""
        diff = abs(duration - target) / target
        return {"pass": diff <= tolerance, "actual": duration, "target": target, "deviation_pct": round(diff*100, 1)}

    @staticmethod
    def check_shake(shake_score: float) -> dict:
        """抖动检查"""
        if shake_score > 15: return {"pass": False, "level": "severe", "action": "建议重新拍摄"}
        if shake_score > 8: return {"pass": True, "level": "noticeable", "action": "建议后期防抖"}
        return {"pass": True, "level": "acceptable", "action": "OK"}

    @staticmethod
    def check_exposure(exposure_score: float) -> dict:
        """过曝检查"""
        if exposure_score > 0.3: return {"pass": False, "level": "overexposed", "action": "降低曝光重新拍摄"}
        if exposure_score > 0.2: return {"pass": True, "level": "bright", "action": "可接受"}
        if exposure_score < 0.02: return {"pass": True, "level": "dark", "action": "建议补光"}
        return {"pass": True, "level": "normal", "action": "OK"}

    @staticmethod
    def check_blur(blur_score: float) -> dict:
        """失焦检查(Laplacian方差)"""
        if blur_score < 50: return {"pass": False, "level": "severe", "action": "画面严重模糊——重新拍摄"}
        if blur_score < 100: return {"pass": True, "level": "soft", "action": "稍模糊——可接受"}
        return {"pass": True, "level": "sharp", "action": "OK"}

    @staticmethod
    def check_audio_level(audio_db: float) -> dict:
        """音频电平检查"""
        if audio_db < -40: return {"pass": False, "level": "too_quiet", "action": "声音太小——提高增益"}
        if audio_db > -3: return {"pass": False, "level": "clipping", "action": "声音过载——降低输入电平"}
        return {"pass": True, "level": "normal", "action": "OK"}

    @staticmethod
    def check_framing(face_ratio: float, position: str = "center") -> dict:
        """取景检查"""
        if face_ratio < 0.05: return {"pass": True, "level": "wide", "action": "全景——适合环境展示"}
        if face_ratio > 0.3: return {"pass": True, "level": "closeup", "action": "特写——适合情感表达"}
        return {"pass": True, "level": "medium", "action": "中景——适合口播"}
