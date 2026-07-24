"""
抖音口播剪辑实战规则 · 从100+教程提炼

素材识别: 15秒一切换 · 景别用途分类 · 情绪触发点 · 加速段标记
气口处理: 词间切 · 300ms静音 · 0.2s边距 · 3-6秒句段 · 重音卡点
"""
from __future__ import annotations
import json, logging, os, re, subprocess, time
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


# ================================================================
# 1. 素材识别整理规则
# ================================================================

@dataclass
class EditingMarker:
    """编辑标记——在时间线上标注切点/变速/特效"""
    at_sec: float
    type: str           # "cut" / "speed_up" / "slow_down" / "zoom_in" / "emphasis" / "broll_insert"
    detail: str         # 人类可读说明
    params: dict        # 参数 {speed:1.5, zoom:1.25, margin:0.2}


MATERIAL_ORGANIZE_RULES = {
    "hook": {
        "duration_range": (1.5, 3.0),
        "action": "开头钩子——0.5秒切入,不加过渡,画面要有冲击力",
        "cut_style": "硬切,0帧过渡",
        "text_overlay": "必须——大字价格/反常识/悬念,占画面30-40%",
        "audio": "原声静音,BGM 35%",
    },
    "body": {
        "duration_range": (3.0, 8.0),
        "segment_rule": "每15秒必须插入一次视觉切换(B-roll或景别变化)",
        "cut_style": "词间切,300ms静音=切点",
        "text_overlay": "可选——关键数据/标签底部淡入",
        "audio": "保留原声,BGM 25-30%",
        "speed_rule": "过渡性内容(接下来/然后/另外)加速1.2-1.5x",
    },
    "broll": {
        "duration_range": (2.0, 6.0),
        "action": "覆盖口播画面,保留配音——展示产品/环境/细节",
        "cut_style": "叠化或硬切,根据前后镜头",
        "text_overlay": "推荐——工艺/食材/卖点标签居中",
        "audio": "原声压低或静音——保留配音音轨",
    },
    "outro": {
        "duration_range": (2.0, 5.0),
        "action": "结尾CTA——拉远+大字引导+地址/团购信息",
        "cut_style": "淡出0.5-0.8s",
        "text_overlay": "必须——CTA大字居中+地址底部",
        "audio": "保留原声,BGM渐弱至无声",
    },
}

# 过渡词检测(应加速的内容)
TRANSITION_WORDS = [
    "接下来", "然后", "另外", "还有", "除此之外", "顺便说一下",
    "值得一提的是", "那么", "所以呢", "我们来看", "首先", "其次",
]

# 强调词检测(应放大+卡点的内容)
EMPHASIS_WORDS = [
    "最重要", "关键", "核心", "记住", "注意", "千万别",
    "独家", "唯一", "只有", "第一", "最好", "绝对",
]


def detect_transition_content(text: str) -> list[dict]:
    """检测需要加速的过渡性内容"""
    markers = []
    for word in TRANSITION_WORDS:
        for m in re.finditer(word, text):
            markers.append({"at_char": m.start(), "word": word, "action": "speed_up", "speed": 1.4})
    return sorted(markers, key=lambda x: x["at_char"])


def detect_emphasis_content(text: str) -> list[dict]:
    """检测需要放大强调的关键内容"""
    markers = []
    for word in EMPHASIS_WORDS:
        for m in re.finditer(word, text):
            markers.append({"at_char": m.start(), "word": word, "action": "zoom_in", "zoom": 1.25})
    return sorted(markers, key=lambda x: x["at_char"])


# ================================================================
# 2. 气口处理规则(Douyin实战版)
# ================================================================

BREATH_EDIT_RULES = {
    "cut_on_silence": {
        "rule": "静音>300ms → 切点",
        "margin_before": 0.15,  # 切点前0.15s
        "margin_after": 0.10,   # 切点后0.10s
        "min_silence_ms": 300,
        "action": "硬切(0帧过渡)",
    },
    "cut_on_sentence_end": {
        "rule": "句子结束(>500ms静音) → 切+插入B-roll或反应镜头",
        "margin_before": 0.15,
        "margin_after": 0.15,
        "min_silence_ms": 500,
        "action": "叠化或B-roll覆盖",
    },
    "cut_on_emphasis": {
        "rule": "关键词/重音 → 放大+卡点音效",
        "margin_before": 0.05,
        "margin_after": 0.05,
        "action": "缩放105%+轻微晃动3%+4-5帧",
        "zoom": 1.05,
        "shake": 0.03,
        "duration_frames": 4,
    },
    "speed_transition": {
        "rule": "过渡词 → 1.2-1.5x加速; 情感词 → 0.9x微减速",
        "speed_up_words": TRANSITION_WORDS,
        "speed_down_contexts": ["最难", "感动", "真诚", "用心"],
        "action": "速度渐变0.3s",
    },
    "every_15sec_switch": {
        "rule": "每15秒必须插入一次视觉切换",
        "action": "B-roll覆盖 / 景别变化 / 场景切换 / 圆形蒙版强调",
        "min_interval_sec": 12,
        "max_interval_sec": 18,
    },
    "hook_3sec_rule": {
        "rule": "前3秒: 0.5s切入+大字+音效, 不放'大家好''今天聊聊'",
        "forbidden_starts": ["大家好","今天聊聊","你知道吗","今天来给大家"],
        "action": "直接切入最精彩画面或反常识观点",
    },
}


def find_breath_cut_points(
    silence_segments: list[dict],      # 静音检测结果
    word_timestamps: list[dict],       # Whisper词级时间戳
    script_text: str = "",
) -> list[EditingMarker]:
    """
    综合静音+词边界→标注精确切点

    规则:
    1. 静音300-500ms → 硬切点(词间自然停顿)
    2. 静音>500ms → B-roll插入点(句子结束)
    3. 过渡词位置 → 加速标记
    4. 强调词位置 → 放大标记
    5. 每15秒检查是否有视觉切换
    """
    markers = []

    # === 从静音段找切点 ===
    for sil in silence_segments:
        dur_ms = sil.get("duration_ms", 0)
        at_sec = (sil.get("start", 0) + sil.get("end", 0)) / 2

        if dur_ms >= 500:
            markers.append(EditingMarker(
                at_sec=round(at_sec, 1), type="broll_insert",
                detail=f"句子结束({dur_ms}ms静音)——插入B-roll或反应镜头",
                params={"margin_before": 0.15, "margin_after": 0.15},
            ))
        elif dur_ms >= 300:
            markers.append(EditingMarker(
                at_sec=round(at_sec, 1), type="cut",
                detail=f"词间停顿({dur_ms}ms)——硬切",
                params={"margin_before": 0.15, "margin_after": 0.10},
            ))

    # === 从词边界找切点 ===
    for i in range(1, len(word_timestamps)):
        gap = word_timestamps[i]["start"] - word_timestamps[i-1]["end"]
        if gap >= 0.3:
            at_sec = round(word_timestamps[i-1]["end"] + gap/2, 1)
            word_before = word_timestamps[i-1].get("word", "")
            word_after = word_timestamps[i].get("word", "")

            # 判断是否过渡词
            if any(tw in word_before for tw in TRANSITION_WORDS):
                markers.append(EditingMarker(
                    at_sec=at_sec, type="speed_up",
                    detail=f"过渡词'{word_before}'→加速1.4x",
                    params={"speed": 1.4, "ramp_duration": 0.3},
                ))
            # 判断是否强调词
            elif any(ew in word_before or ew in word_after for ew in EMPHASIS_WORDS):
                markers.append(EditingMarker(
                    at_sec=at_sec, type="emphasis",
                    detail=f"强调词→放大+卡点",
                    params={"zoom": 1.05, "shake": 0.03, "duration_frames": 4},
                ))
            elif gap < 0.5:
                markers.append(EditingMarker(
                    at_sec=at_sec, type="cut",
                    detail=f"词间{int(gap*1000)}ms→硬切",
                    params={"margin_before": 0.15, "margin_after": 0.10},
                ))

    # === 每15秒检查视觉切换 ===
    if markers:
        markers.sort(key=lambda m: m.at_sec)
        last_switch = 0
        for m in markers:
            if m.type in ("broll_insert", "cut") and m.at_sec - last_switch > 15:
                m.detail += " ⚠️超过15秒无视觉切换——建议插入B-roll"
            if m.type in ("broll_insert", "cut"):
                last_switch = m.at_sec

    return markers


def apply_douyin_edit_rules(segments: list, markers: list[EditingMarker]) -> list:
    """将Douyin剪辑规则应用到片段上"""
    for seg in segments:
        start = seg.start_sec if hasattr(seg, 'start_sec') else seg.get('start_sec', 0)
        end = start + (seg.duration_sec if hasattr(seg, 'duration_sec') else seg.get('duration_sec', 3))

        # 匹配标记
        seg_markers = [m for m in markers if start <= m.at_sec <= end]

        for m in seg_markers:
            if m.type == "speed_up":
                seg_desc = seg.description if hasattr(seg, 'description') else ''
                seg.description = f"{seg_desc} [🚀加速{m.params.get('speed',1.4)}x@{m.at_sec:.1f}s]"
            elif m.type == "emphasis":
                seg_desc = seg.description if hasattr(seg, 'description') else ''
                seg.description = f"{seg_desc} [🔍强调缩放@{m.at_sec:.1f}s]"
            elif m.type == "broll_insert":
                seg_desc = seg.description if hasattr(seg, 'description') else ''
                seg.description = f"{seg_desc} [📷B-roll插入点@{m.at_sec:.1f}s]"

        # 钩子3秒规则检查
        if hasattr(seg, 'section') and seg.section == 'opening':
            if seg.duration_sec > 3.5:
                logger.info("开头超过3.5s——建议压缩到3s以内")

        # Body段15秒规则
        if hasattr(seg, 'section') and seg.section == 'body':
            if seg.duration_sec > 15:
                logger.info("Body段%.1fs超过15s——建议插入视觉切换", seg.duration_sec)

    return segments
