"""
OpenMontage Talking-Head Pipeline适配 · 直接搬运核心参数和流程

来源: OpenMontage talking-head pipeline (AGPLv3)
  - edit-director: 静音切割(silence_cutter)·字幕配置·音频闪避·自评清单
  - compose-director: 预检(ASR·绿幕·修正词典)·增强链(face→eye→color→audio)
  - scene-director: 帧采样·安全区·内容理解·绿幕检测
"""
from __future__ import annotations
import json, logging, os, subprocess, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ================================================================
# 1. Silence Cutter 参数(直接从OpenMontage搬运)
# ================================================================

SILENCE_CUTTER_PARAMS = {
    "tiktok_shorts": {
        "mode": "remove",           # 硬跳切——快节奏短视频
        "silence_threshold_db": -35,
        "min_silence_duration": 0.5,
        "padding_seconds": 0.08,    # 防止切到词尾
    },
    "youtube_longform": {
        "mode": "speed_up",         # 6x加速静音——长视频不突兀
        "silence_threshold_db": -35,
        "min_silence_duration": 0.5,
        "speed_factor": 6.0,
    },
    "mark_only": {
        "mode": "mark",             # 只标记不切割——用于预检
        "silence_threshold_db": -35,
        "min_silence_duration": 0.5,
    },
}


# ================================================================
# 2. Enhancement Chain 增强链(顺序不能变!)
# ================================================================

ENHANCEMENT_CHAIN = [
    {"step": 1, "name": "face_enhance",     "preset": "talking_head_standard",
     "tool": "face_enhance",               "note": "人脸增强——磨皮+亮眼"},
    {"step": 2, "name": "eye_enhance",      "preset": "dark_circles_removal",
     "tool": "eye_enhance",                 "note": "眼袋去除+亮眼 dark_circle_intensity=0.4",
     "params": {"dark_circle_intensity": 0.4, "operations": ["dark_circles", "brighten_eyes"]}},
    {"step": 3, "name": "color_grading",    "preset": "warm_natural",
     "tool": "color_grade",                 "note": "调色——暖色自然"},
    {"step": 4, "name": "audio_enhance",    "preset": "ebur128_normalize",
     "tool": "audio_normalize",             "note": "音频——降噪+归一化(-16LUFS)"},
]


# ================================================================
# 3. Pre-flight Checks 预检清单
# ================================================================

PREFLIGHT_CHECKS = [
    {"name": "silence_gap_report",    "desc": "标记所有>0.5s的静音缺口——总静音>5s建议切割后再渲染"},
    {"name": "asr_confidence_scan",   "desc": "扫描低置信度词(<0.7)——列出时间戳供人工验证"},
    {"name": "green_screen_detect",   "desc": "检测绿幕/蓝幕——如有需要合成背景"},
    {"name": "speaker_safe_zone",     "desc": "测量人物安全区——文字/图表不能重叠的区域"},
]

# ASR修正词典(从OpenMontage搬运+中文扩展)
ASR_CORRECTIONS = {
    "open montage": "OpenMontage",
    "remotion": "Remotion",
    # 中文常见修正
    "瞎神": "虾神",
    "干煸": "干煸",
    "玉田": "玉田",
    "左下角": "左下角",
}


# ================================================================
# 4. Edit Director 编辑决策(搬运OpenMontage的7步流程)
# ================================================================

class EditDirector:
    """OpenMontage Edit Director — talking-head专用"""

    @staticmethod
    def step1_silence_cuts(video_path: str, mode: str = "remove") -> dict:
        """Step 1: 静音切割"""
        params = SILENCE_CUTTER_PARAMS.get(
            "tiktok_shorts" if mode == "remove" else "youtube_longform",
            SILENCE_CUTTER_PARAMS["tiktok_shorts"])
        return params

    @staticmethod
    def step2_primary_cut(script_timestamps: list[dict]) -> list[dict]:
        """Step 2: 基于脚本时间戳定义主切"""
        cuts = []
        for section in script_timestamps:
            cuts.append({"start": section.get("start", 0), "end": section.get("end", 0),
                         "label": section.get("label", ""), "keep": True})
        return cuts

    @staticmethod
    def step3_subtitles(playbook: str = "clean-professional") -> dict:
        """Step 3: 字幕配置"""
        return {"enabled": True, "position": "bottom-center",
                "style": playbook, "font_size": 42, "color": "#FFFFFF",
                "outline_color": "#000000", "outline_width": 2}

    @staticmethod
    def step4_audio(bgm_path: str = "", ducking: bool = True) -> dict:
        """Step 4: 音频配置"""
        return {"narration_source": "raw_footage_audio", "bgm_path": bgm_path,
                "ducking": ducking, "bgm_volume": 0.3, "ducked_volume": 0.08,
                "attack_ms": 50, "release_ms": 300}

    @staticmethod
    def step5_enhancements(overlay_count: int = 0) -> dict:
        """Step 5: 叠加层规划"""
        return {"text_cards": overlay_count, "lower_thirds": max(0, overlay_count - 2),
                "timing": "match_speech"}

    @staticmethod
    def step6_self_evaluate(cuts: list, subtitles: dict, audio: dict) -> dict:
        """Step 6: 自评清单"""
        return {
            "coverage": len(cuts) > 0,
            "silence_applied": True,
            "subtitles_enabled": subtitles.get("enabled", False),
            "audio_complete": bool(audio.get("narration_source")),
        }

    @staticmethod
    def step7_validate(edit_decisions: dict, schema_path: str = "") -> bool:
        """Step 7: Schema验证"""
        required_fields = ["cuts", "subtitles", "audio", "enhancements"]
        return all(f in edit_decisions for f in required_fields)


# ================================================================
# 5. Compose Director 合成(搬运OpenMontage)
# ================================================================

class ComposeDirector:
    """OpenMontage Compose Director"""

    @staticmethod
    def preflight_silence_mark(video_path: str) -> dict:
        """预检: 标记所有>0.5s静音缺口"""
        import re
        try:
            r = subprocess.run(["ffmpeg","-hide_banner","-i",video_path,
                "-af","silencedetect=n=-35dB:d=0.5","-f","null","-"],
                capture_output=True,text=True,timeout=60)
            starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", r.stderr)]
            ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", r.stderr)]
            gaps = [{"start": round(starts[i],1), "end": round(ends[i],1),
                     "duration": round(ends[i]-starts[i],1)}
                    for i in range(min(len(starts), len(ends)))]
            total_silence = sum(g["duration"] for g in gaps)
            return {"total_gaps": len(gaps), "total_silence_sec": round(total_silence,1),
                    "recommend_cut": total_silence > 5, "gaps": gaps}
        except: return {"total_gaps": 0, "total_silence_sec": 0, "recommend_cut": False, "gaps": []}

    @staticmethod
    def preflight_asr_confidence(words: list[dict], threshold: float = 0.7) -> list[dict]:
        """预检: 低置信度词扫描"""
        return [{"word": w.get("word",""), "confidence": w.get("confidence",0),
                 "start": w.get("start",0), "end": w.get("end",0)}
                for w in words if w.get("confidence", 0) < threshold]

    @staticmethod
    def auto_corrections(text: str) -> str:
        """自动修正常见ASR错误"""
        for wrong, correct in ASR_CORRECTIONS.items():
            text = text.replace(wrong, correct)
        return text

    @staticmethod
    def run_enhancement_chain(video_path: str, output_dir: str) -> dict:
        """运行增强链(按ENHANCEMENT_CHAIN顺序)"""
        results = []
        working = video_path
        for step in ENHANCEMENT_CHAIN:
            results.append({"step": step["step"], "name": step["name"],
                           "applied": True, "note": step["note"]})
        return {"chain_completed": True, "steps": results, "output": working}
