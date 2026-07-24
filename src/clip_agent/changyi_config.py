"""
长益剪辑Agent 定制化配置 · OpenMontage能力内化

将OpenMontage的通用能力定制为中国实体店短视频场景:
- 三脚本类型(老板IP/团购售卖/引流进店) × 专属增强链
- 6素材分类 × OpenMontage工具映射
- 15编辑规则 × 决策引擎
- 抖音参数(9:16竖屏·60s限制·3s钩子)
- 虾神龙虾案例完整配置
"""
from __future__ import annotations
import json, logging

logger = logging.getLogger(__name__)


# ================================================================
# 1. 脚本类型专属增强链(定制化——不是通用talking_head!)
# ================================================================

SCRIPT_ENHANCEMENT_CHAINS = {
    "老板IP": {
        "name": "老板IP·人物故事增强",
        "face_enhance": {"preset": "natural_trust", "intensity": 0.3},    # 微美颜——保持真实感
        "eye_enhance": {"dark_circle_intensity": 0.2},                     # 轻度去眼袋——太假反而不好
        "color_grade": {"preset": "warm_documentary", "warmth": 1.15},     # 暖色调——纪录片质感
        "audio": {"normalize": -16, "denoise": "light", "keep_natural": True},  # 保留自然语气
        "text_style": "typewriter_gentle",                                 # 逐字温和出现
        "bgm": {"genre": "温暖钢琴", "volume": 0.25, "fade_in": 1.5},    # BGM轻——不抢人声
        "rhythm": "contemplative",                                         # 沉思型长镜
        "shot_duration": 6.0,
        "broll_ratio": 0.15,
    },
    "团购售卖": {
        "name": "团购售卖·快节奏冲击增强",
        "face_enhance": {"preset": "bright_clean", "intensity": 0.5},      # 亮肤——产品旁要精神
        "eye_enhance": {"dark_circle_intensity": 0.6},                     # 强去眼袋——镜头近
        "color_grade": {"preset": "vivid_sale", "saturation": 1.2, "contrast": 1.1},  # 鲜艳——产品诱人
        "audio": {"normalize": -14, "denoise": "medium", "keep_energy": True},  # 提高响度——有冲击力
        "text_style": "pop_in_bold",                                       # 弹入大字
        "bgm": {"genre": "快节奏卡点", "volume": 0.35, "beat_sync": True},  # BGM卡点
        "rhythm": "alternating",                                           # 交替型快切
        "shot_duration": 2.0,
        "broll_ratio": 0.50,
    },
    "引流进店": {
        "name": "引流进店·真实感增强",
        "face_enhance": {"preset": "natural_clean", "intensity": 0.35},
        "eye_enhance": {"dark_circle_intensity": 0.3},
        "color_grade": {"preset": "warm_real", "warmth": 1.1, "sharpness": 1.1},  # 锐化——环境清晰
        "audio": {"normalize": -16, "denoise": "medium", "keep_ambient": True},    # 保留环境音
        "text_style": "slide_up_clean",
        "bgm": {"genre": "轻松生活", "volume": 0.25, "fade_in": 1.0},
        "rhythm": "regular_cadence",
        "shot_duration": 2.5,
        "broll_ratio": 0.45,
    },
}


# ================================================================
# 2. 6素材分类 × 工具映射(定制化)
# ================================================================

MATERIAL_TOOL_MAP = {
    "product": {         # 商品/产品展示
        "enhance": ["ken_burns", "color_grade_vivid", "sharpen"],
        "transition_in": "cut",
        "transition_out": "dissolve",
        "text_position": "center",
        "text_animation": "pop_in",
        "max_duration": 6.0,
    },
    "service": {         # 服务/体验过程
        "enhance": ["stabilize", "color_grade_warm", "speed_ramp_normal"],
        "transition_in": "dissolve",
        "transition_out": "cut",
        "text_position": "bottom",
        "text_animation": "slide_up",
        "max_duration": 15.0,
    },
    "environment": {     # 店内环境
        "enhance": ["ken_burns_slow", "color_grade_warm", "sharpen"],
        "transition_in": "dissolve",
        "transition_out": "dissolve",
        "text_position": "bottom",
        "text_animation": "fade_in",
        "max_duration": 10.0,
    },
    "storefront": {      # 门头/外景
        "enhance": ["stabilize", "sharpen", "color_grade_natural"],
        "transition_in": "cut",
        "transition_out": "fade_out",
        "text_position": "center",
        "text_animation": "scale_up",
        "max_duration": 8.0,
    },
    "talking": {         # 人物出镜
        "enhance": ["face_enhance", "eye_enhance", "color_grade_natural"],
        "transition_in": "fade_in",
        "transition_out": "cut",
        "text_position": "bottom",
        "text_animation": "typewriter",
        "max_duration": 20.0,
    },
    "social": {          # 社交证明/顾客
        "enhance": ["color_grade_warm", "sharpen"],
        "transition_in": "dissolve",
        "transition_out": "cut",
        "text_position": "center",
        "text_animation": "fade_in",
        "max_duration": 8.0,
    },
}


# ================================================================
# 3. 编辑规则引擎配置(定制化——使用我们的15条规则)
# ================================================================

EDITING_RULES_CONFIG = {
    "douyin_constraints": {
        "aspect_ratio": "9:16",
        "max_duration_sec": 60,
        "min_duration_sec": 8,
        "hook_max_sec": 3,
        "hook_forbidden_starts": ["大家好", "今天聊聊", "你知道吗", "欢迎来到"],
        "cta_position": "last_5s",
    },
    "quality_thresholds": {
        "min_quality_score": 3.0,
        "max_shake_dji": 20,       # DJI设备容忍度
        "max_shake_phone": 10,     # 手机拍摄容忍度
        "min_sharpness": 50,       # DJI 4K
        "max_exposure_ratio": 0.25,
    },
    "breath_cut_rules": {
        "word_gap_cut_ms": 300,
        "sentence_gap_broll_ms": 500,
        "margin_before_sec": 0.15,
        "margin_after_sec": 0.10,
        "emphasis_zoom_pct": 1.05,
        "emphasis_duration_frames": 4,
        "transition_speed_words": 1.4,
        "every_15s_check": True,
    },
}


# ================================================================
# 4. 虾神龙虾案例完整配置(定制化案例)
# ================================================================

XIASHEN_CASE_CONFIG = {
    "brand": "虾神龙虾",
    "location": "玉田建设路",
    "script_type": "团购售卖",
    "key_products": ["招牌小龙虾", "干煸小龙虾", "花雕小龙虾"],
    "key_processes": ["干煸盱眙技术", "花雕酒泡8小时", "凌晨四点挑活虾"],
    "price_point": "68块/108块/168块三档",
    "unique_selling_point": "湖北活虾当天到·盱眙技术·花雕泡制",
    "customer_proof": "山西老板专门开车来吃",
    "shooting_plan": [
        {"shot": 1, "type": "product_closeup", "desc": "小龙虾特写——腮部白色·调料流淌", "duration": 3, "text": "68块!"},
        {"shot": 2, "type": "talking_head",   "desc": "老板出镜——手指产品·介绍价格",   "duration": 8, "text": ""},
        {"shot": 3, "type": "product_closeup", "desc": "干煸过程特写——技术展示",       "duration": 5, "text": "干煸盱眙技术"},
        {"shot": 4, "type": "environment",     "desc": "店内环境——展示用餐氛围",       "duration": 5, "text": ""},
        {"shot": 5, "type": "social",          "desc": "顾客吃虾反应——满足表情",       "duration": 4, "text": ""},
        {"shot": 6, "type": "talking_head",   "desc": "老板结尾——CTA引导团购",        "duration": 3, "text": "左下角团购"},
    ],
    "bgm": "快节奏卡点",
    "total_duration": 28,
}


# ================================================================
# 5. 一键获取定制配置
# ================================================================

def get_script_enhancement(script_type: str) -> dict:
    """根据脚本类型获取专属增强链"""
    return SCRIPT_ENHANCEMENT_CHAINS.get(script_type, SCRIPT_ENHANCEMENT_CHAINS["团购售卖"])


def get_material_tools(material_category: str) -> dict:
    """根据素材分类获取工具映射"""
    return MATERIAL_TOOL_MAP.get(material_category, MATERIAL_TOOL_MAP["product"])


def get_editing_constraints() -> dict:
    """获取编辑约束(Douyin定制)"""
    return EDITING_RULES_CONFIG


def get_case_config(case_name: str = "虾神龙虾") -> dict:
    """获取案例完整配置"""
    cases = {"虾神龙虾": XIASHEN_CASE_CONFIG}
    return cases.get(case_name, XIASHEN_CASE_CONFIG)


def build_custom_pipeline_params(script_type: str, material_categories: list[str]) -> dict:
    """
    构建完整的定制化管线参数——整合脚本类型+素材类型的全部配置
    这是OpenMontage通用能力→长益定制化的最终转换函数
    """
    enhancement = get_script_enhancement(script_type)
    constraints = get_editing_constraints()
    material_tools = {cat: get_material_tools(cat) for cat in set(material_categories)}

    return {
        "pipeline": {
            "name": f"长益_{script_type}_管线",
            "stages": 7,
            "budget_usd": 0.15,  # 单次约¥1
        },
        "enhancement": enhancement,
        "constraints": constraints,
        "material_tools": material_tools,
        "output": {
            "format": "douyin_vertical",
            "aspect": "9:16",
            "resolution": "1080x1920",
            "max_duration_sec": 60,
        },
    }
