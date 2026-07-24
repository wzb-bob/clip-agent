"""
平台规格 · OpenMontage short-form.md + storytelling.md 直接搬运

平台安全区·编码规格·Hook模板·叙事弧线
"""
from __future__ import annotations

# ================================================================
# 平台安全区(OpenMontage short-form.md)
# ================================================================

PLATFORM_SAFE_ZONES = {
    "tiktok":     {"safe": (900, 1492), "top_dead": 108, "bottom_dead": 320, "right_dead": 120},
    "instagram":  {"safe": (996, 1400), "top_dead": 210, "bottom_dead": 310, "right_dead": 84},
    "youtube":    {"safe": (984, 1500), "top_dead": 120, "bottom_dead": 300, "right_dead": 96},
    "facebook":   {"safe": (1080, 1520), "top_dead": 100, "bottom_dead": 300, "right_dead": 60},
    "universal":  {"safe": (900, 1400), "top_dead": 108, "bottom_dead": 320, "right_dead": 120},
}

UPLOAD_SPECS = {
    "codec": "H.264 High Profile, Level 4.2",
    "bitrate": "8-15 Mbps VBR",
    "format": ".mp4",
    "max_size_desktop_mb": 500,
    "max_size_ios_mb": 287.6,
    "max_size_android_mb": 72,
    "audio_lufs": -14,
    "audio_true_peak": -1,
}

# ================================================================
# Hook模板(OpenMontage storytelling.md)
# ================================================================

HOOK_TEMPLATES = {
    "pattern_interrupt": {
        "name": "模式中断型",
        "duration": (0, 8),
        "description": "反常识/反直觉的观点或画面——打破观众预期",
        "visual": "冲击力强的画面+1-2句文字",
        "example": "90%的人不知道怎么挑活虾——"
    },
    "information_gap": {
        "name": "信息缺口型",
        "duration": (8, 30),
        "description": "\"大多数人以为...但其实不是\"——建立认知缺口",
        "visual": "展示误解+真相对比",
        "example": "你以为小龙虾都是脏的？其实——"
    },
    "palette_cleanser": {
        "name": "呼吸停顿型",
        "duration": (75, 80),
        "description": "短暂的停顿/视觉幽默——让观众消化前面的信息",
        "visual": "轻松画面/gag/留白",
        "example": "1-3秒的沉默或搞笑画面"
    },
    "key_insight": {
        "name": "核心洞察型",
        "duration": (80, 110),
        "description": "\"原来如此\"的时刻——视频的核心观点",
        "visual": "最精致的画面/动画",
        "example": "揭示后停顿1-3秒——让观众自己消化"
    },
    "reframe_close": {
        "name": "首尾呼应型",
        "duration": (165, 180),
        "description": "回扣开头的钩子——用一句话重述核心观点",
        "visual": "回到开头的视觉元素",
        "example": "\"所以，下次你吃小龙虾的时候...\""
    },
}

# 叙事弧线(3分钟视频——按比例缩放)
STORYTELLING_ARC = [
    {"section": "hook",             "start_pct": 0,   "end_pct": 5,   "desc": "反常识/反直觉——1-2句打破预期"},
    {"section": "tension",          "start_pct": 5,   "end_pct": 17,  "desc": "信息缺口——建立\"为什么我要关心\""},
    {"section": "concept_1",        "start_pct": 17,  "end_pct": 28,  "desc": "基础概念——一个想法+一个画面"},
    {"section": "concept_2",        "start_pct": 28,  "end_pct": 42,  "desc": "复杂化——在前一个概念上叠加"},
    {"section": "palette_cleanser", "start_pct": 42,  "end_pct": 45,  "desc": "呼吸——短暂停顿/幽默"},
    {"section": "key_insight",      "start_pct": 45,  "end_pct": 61,  "desc": "核心洞察——\"原来如此\"+"},
    {"section": "proof",            "start_pct": 61,  "end_pct": 78,  "desc": "证明——\"看看这个案例\""},
    {"section": "implications",     "start_pct": 78,  "end_pct": 92,  "desc": "所以呢？——连接回现实"},
    {"section": "reframe_close",    "start_pct": 92,  "end_pct": 100, "desc": "首尾呼应——回扣钩子"},
]

# 短格式节奏(抖音/Reels/Shorts)
SHORT_FORM_RULES = {
    "visual_change_interval": (1, 3),  # 每1-3秒视觉变化
    "captions": "Mandatory",            # 85%用户静音观看
    "text_min_size_px": 42,             # 最小字号
    "bgm_bpm": (120, 140),              # 快节奏BPM
    "total_duration": {15: "最高完播率", 30: "最佳互动", 60: "最灵活"},
}


def get_safe_zone(platform: str = "universal") -> dict:
    return PLATFORM_SAFE_ZONES.get(platform, PLATFORM_SAFE_ZONES["universal"])


def get_arc_timing(total_sec: float, section_name: str) -> tuple[float, float]:
    """根据总时长和章节名获取时间范围"""
    for arc in STORYTELLING_ARC:
        if arc["section"] == section_name:
            return (total_sec * arc["start_pct"] / 100, total_sec * arc["end_pct"] / 100)
    return (0, total_sec)


def get_hook_template(hook_type: str = "pattern_interrupt") -> dict:
    return HOOK_TEMPLATES.get(hook_type, HOOK_TEMPLATES["pattern_interrupt"])


# ================================================================
# 字幕规格(OpenMontage subtitle-sync.md)
# ================================================================

SUBTITLE_SPECS = {
    "vertical_short": {
        "max_words_per_cue": 4, "max_chars_per_line": 20,
        "mandatory": True, "reason": "85%静音观看",
        "min_display_sec": 0.5, "max_display_sec": 5.0,
    },
    "horizontal_standard": {
        "max_words_per_cue": 8, "max_chars_per_line": 42,
        "min_display_sec": 0.5, "max_display_sec": 5.0,
    },
    "read_speed_cps": 15,  # chars/second average
    "output_formats": {"srt":"Universal·FFmpeg/YouTube","vtt":"Web·HTML5","caption_json":"Programmatic"},
}


# ================================================================
# 调色规格(OpenMontage color-grading.md)
# ================================================================

COLOR_GRADING_SPECS = {
    "filter_chain_order": ["normalize","colortemperature","colorbalance","curves","eq","lut3d"],
    "profiles_by_content": {
        "talking_head": {"profile":"cinematic_warm","intensity":0.85,"reason":"人脸需要暖色—看起来健康自然"},
        "product_show": {"profile":"bright_clean","intensity":0.8,"reason":"产品需要鲜艳—看起来诱人"},
        "environment":  {"profile":"neutral","intensity":0.6,"reason":"环境保持真实—不要过度调色"},
        "brand_film":   {"profile":"cinematic_cool","intensity":0.7,"reason":"品牌—冷色调显专业"},
    },
    "skin_tone_line_deg": 123,  # Vectorscope I-line
    "deliver_color_space": "BT.709",
}

