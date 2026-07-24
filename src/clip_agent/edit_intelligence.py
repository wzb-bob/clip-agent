"""
编辑智能引擎 · 从OpenMontage video-editing/broll-planning 提炼

J-cut/L-cut精确规则·可切/不可切判断·B-roll决策矩阵·格式自适应节奏
"""
from __future__ import annotations
import json, logging, re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ================================================================
# 1. 切点智能判断(OpenMontage: What to Cut / NOT to Cut)
# ================================================================

CUT_RULES = {
    "must_cut": {
        "filler_words": {
            "words": ["嗯","啊","呃","那个","这个","就是说","然后呢","所以吧"],
            "action": "hard_cut_at_word_boundary",
            "note": "在语气词前后0.05s切掉,不留痕迹",
        },
        "false_starts": {
            "pattern": "重复开头——同一句话说了两次以上",
            "action": "keep_last_take",
            "note": "保留最后一遍,删除前面的虚假开头",
        },
        "dead_air_long": {
            "threshold_sec": 1.5,
            "action": "trim_to_0.5s",
            "note": ">1.5s的静音压缩到0.5s",
        },
        "off_topic": {
            "pattern": "跑题——检测到与主话题无关的内容",
            "action": "cut_to_next_relevant",
        },
        "repeated_points": {
            "pattern": "同一个观点说了两遍以上",
            "action": "keep_best_delivery",
        },
    },
    "never_cut": {
        "breath_pauses": {
            "range_sec": (0.3, 0.8),
            "reason": "自然换气——观众需要呼吸节奏",
        },
        "emphasis_pauses": {
            "pattern": "故意的戏剧性停顿",
            "reason": "增强感染力——不能破坏",
        },
        "transitional_bridges": {
            "words": ["所以","那么","现在","接下来"],
            "reason": "提供语流过渡——剪掉会让视频跳跃",
        },
    },
}

# ================================================================
# 2. J-cut/L-cut 精确规则(OpenMontage)
# ================================================================

JCUT_LCUT_RULES = {
    "j_cut": {
        "offset_sec": 0.5,          # 音频提前0.5s切入
        "best_for": ["话题转换","场景切换","B-roll覆盖开始"],
        "how": "下一个片段的音频先开始播放→0.5s后画面才切过去",
        "effect": "过渡平滑自然——观众不会注意到'被剪了'",
    },
    "l_cut": {
        "offset_sec": 0.5,          # 音频延后0.5s切出
        "best_for": ["情感延续","反应镜头","空镜过渡"],
        "how": "当前片段的音频继续播放→0.5s后画面已切到下一个片段",
        "effect": "保持思维连续性——听觉还在上一句,视觉已经进入下一画面",
    },
    "hard_cut": {
        "offset_sec": 0.0,
        "best_for": ["话题大转折","章节切换","Hook→Body"],
        "how": "音视频同时切——不拖泥带水",
    },
}

# ================================================================
# 3. 节奏控制(OpenMontage: Pacing by Format)
# ================================================================

PACING_RULES = {
    "douyin_short": {
        "max_duration": 60,
        "style": "aggressive",       # 激进——能量高,切得快
        "target_shot_duration": (1.5, 3.0),
        "max_silence_kept": 0.3,     # 保留的最大静音
        "filler_tolerance": 0,       # 零容忍——全切
        "dead_air_policy": "cut_all",
        "energy_level": "high",
    },
    "douyin_medium": {
        "max_duration": 180,
        "style": "balanced",
        "target_shot_duration": (2.5, 5.0),
        "max_silence_kept": 0.5,
        "filler_tolerance": 1,       # 容忍1个语气词
        "dead_air_policy": "trim_long",
        "energy_level": "medium",
    },
    "documentary": {
        "max_duration": 600,
        "style": "breathing",
        "target_shot_duration": (5.0, 12.0),
        "max_silence_kept": 1.0,
        "filler_tolerance": 3,
        "dead_air_policy": "keep_natural",
        "energy_level": "natural",
    },
}

# ================================================================
# 4. B-roll决策矩阵(OpenMontage: Stock vs Generated)
# ================================================================

BROLL_DECISION_MATRIX = {
    "real_scene": {
        "prefer": "stock_or_self_shot",
        "examples": ["城市航拍","办公室","自然风景","店面实拍","顾客反应"],
        "reason": "真实场景——用实拍或素材库,AI生成太假",
    },
    "abstract_concept": {
        "prefer": "generated_or_text",
        "examples": ["数据增长","算法流程","概念对比","品牌愿景"],
        "reason": "抽象概念——AI图表或文字卡片更好",
    },
    "product_detail": {
        "prefer": "self_shot_only",
        "examples": ["产品特写","工艺过程","食材展示"],
        "reason": "必须实拍——只有你自己的产品才有说服力",
    },
    "people": {
        "prefer": "self_shot_only",
        "examples": ["老板出镜","顾客反应","员工工作"],
        "reason": "真实人物——AI生成的人脸会很假",
    },
    "motion_action": {
        "prefer": "stock_or_self_shot",
        "examples": ["做菜过程","美容操作","维修动作"],
        "reason": "动作过程——实拍或素材库",
    },
}


def should_cut(word: str, context: str = "") -> dict:
    """判断这个词/位置是否应该切"""
    # 语气词→切
    for fw in CUT_RULES["must_cut"]["filler_words"]["words"]:
        if fw in word:
            return {"cut": True, "reason": f"语气词'{fw}'", "action": "hard_cut_at_word_boundary"}

    # 过渡词→不切
    for tw in CUT_RULES["never_cut"]["transitional_bridges"]["words"]:
        if word == tw:
            return {"cut": False, "reason": f"过渡词'{tw}'", "action": "keep"}

    return {"cut": False, "reason": "正常内容", "action": "keep"}


def get_pacing_for_format(total_duration: float, platform: str = "douyin") -> dict:
    """根据视频时长和平台自动选择节奏策略"""
    if platform == "douyin":
        if total_duration <= 60: return PACING_RULES["douyin_short"]
        return PACING_RULES["douyin_medium"]
    return PACING_RULES["documentary"]


def get_jcut_offset(transition_type: str) -> float:
    """获取J-cut/L-cut偏移量"""
    return JCUT_LCUT_RULES.get(transition_type, {}).get("offset_sec", 0.0)


def get_broll_source(scene_type: str) -> dict:
    """根据场景类型推荐B-roll来源"""
    for key, info in BROLL_DECISION_MATRIX.items():
        if any(ex in scene_type for ex in info["examples"]):
            return {"source": info["prefer"], "reason": info["reason"]}
    return {"source": "stock_or_self_shot", "reason": "默认——实拍或素材库"}


def build_broll_brief(section_label: str, start_sec: float, end_sec: float,
                      subject: str, mood: str = "professional") -> dict:
    """构建B-roll需求简要(OpenMontage格式)"""
    return {
        "scene": section_label,
        "time_range": f"{start_sec:.0f}s-{end_sec:.0f}s",
        "duration_needed": round(end_sec - start_sec, 1),
        "subject": subject,
        "keywords": subject.split(),
        "source": get_broll_source(subject)["source"],
        "mood": mood,
        "orientation": "vertical_9x16",
        "fallback": f"AI文字卡片: {subject[:20]}",
    }
