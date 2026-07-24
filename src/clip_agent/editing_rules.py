"""
精确剪辑规则引擎 · 脚本类型×素材类型×编辑角色 → 帧级编辑参数

每个规则精确到: 切点触发条件/转场类型+时长(ms)/文字叠加时机+动画/音频处理/变速
"""
from __future__ import annotations
import json, logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CutRule:
    """一个精确的切点规则"""
    trigger: str              # 触发条件: "content_change"/"silence_300ms"/"sentence_end"/"beat_1"/"eye_contact_lost"
    action: str               # "cut"/"dissolve"/"fade"/"whip_pan"
    duration_ms: int          # 转场时长(毫秒)
    pre_roll_ms: int          # 切点前保留(毫秒)
    post_roll_ms: int         # 切点后跳过(毫秒)

@dataclass
class TextRule:
    """文字叠加规则"""
    text_source: str          # "price"/"hook"/"cta"/"tag"/"brand"
    animation: str            # "pop_in"/"fade_in"/"slide_up"/"typewriter"/"scale_up"
    font_size: int            # 字号
    position: str             # "center"/"bottom"/"top"
    appear_at_pct: float      # 在镜头时长的百分之几出现(0-1)
    duration_pct: float       # 持续时长占比(0-1)
    color: str                # "#FF4444"红色 "#FFFFFF"白色 "#FFD700"金色

@dataclass
class AudioRule:
    """音频处理规则"""
    action: str               # "keep"/"mute"/"duck"/"replace_with_bgm"/"replace_with_tts"
    bgm_volume: float         # BGM音量(0-1)
    voice_volume: float       # 人声音量(0-1)
    fade_in_ms: int           # 淡入时长
    fade_out_ms: int          # 淡出时长

@dataclass
class SpeedRule:
    """变速规则"""
    action: str               # "normal"/"slow_motion"/"speed_up"/"ramp"
    speed_factor: float       # 1.0=正常, 0.5=2x慢动作, 2.0=2x快进
    ramp_duration_pct: float  # 渐变时长占比

@dataclass
class EditRule:
    """一个完整的编辑规则——精确到帧"""
    rule_id: str
    script_type: str          # 老板IP/团购售卖/引流进店
    material_role: str        # hook/body/broll/outro
    material_category: str    # product/service/environment/storefront/talking/social

    # 剪辑参数
    cut_rules: list[CutRule]
    text_rules: list[TextRule]
    audio_rule: AudioRule
    speed_rule: SpeedRule

    # 蒙太奇关系
    shot_size_sequence: list[str]   # 前后镜头的景别序列要求
    emotion_arc: str                # 情绪弧线要求
    notes: str                      # 人类可读说明


# ================================================================
# 三大脚本类型×四大编辑角色 → 20条精确编辑规则
# ================================================================

EDITING_RULES = [
    # ========== 老板IP × Hook(开头钩子) ==========
    EditRule("ip_hook_01", "老板IP", "hook", "talking",
        cut_rules=[
            CutRule("sentence_end", "fade_in", 400, 200, 0),
            CutRule("eye_contact_lost", "cut", 0, 0, 500),
        ],
        text_rules=[
            TextRule("hook", "typewriter", 56, "center", 0.0, 0.5, "#FFFFFF"),
        ],
        audio_rule=AudioRule("keep", 0.25, 1.0, 500, 300),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["CU","MS","CU"],
        emotion_arc="平静→真诚→感动",
        notes="老板IP开头: 面部特写+金句逐字出现+BGM极轻淡入。让观众0.5秒内感受到真诚。"
    ),
    EditRule("ip_hook_02", "老板IP", "hook", "environment",
        cut_rules=[
            CutRule("content_change", "dissolve", 600, 300, 0),
        ],
        text_rules=[
            TextRule("brand", "fade_in", 42, "bottom", 0.2, 0.6, "#FFFFFF"),
        ],
        audio_rule=AudioRule("duck", 0.3, 1.0, 800, 500),
        speed_rule=SpeedRule("slow_motion", 0.8, 0.0),
        shot_size_sequence=["LS","MS","CU"],
        emotion_arc="环境→人物→故事",
        notes="老板IP环境开头: 慢动作展示工作环境,店名淡入,观众感受'这个老板的故事从哪开始'"
    ),

    # ========== 老板IP × Body(主体) ==========
    EditRule("ip_body_01", "老板IP", "body", "talking",
        cut_rules=[
            CutRule("silence_500ms", "cut", 0, 200, 300),
            CutRule("sentence_end", "cut", 0, 0, 0),
        ],
        text_rules=[],
        audio_rule=AudioRule("keep", 0.25, 1.0, 0, 0),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["MS","MCU","MS","CU"],
        emotion_arc="讲述→回忆→感慨→坚定",
        notes="老板IP主体口播: 长镜6-10秒不切,保持人物稳定在画面中。静音>500ms才切(尊重说话节奏)。无文字叠加——让观众专注在人脸上。"
    ),
    EditRule("ip_body_02", "老板IP", "body", "product",
        cut_rules=[
            CutRule("content_change", "dissolve", 500, 100, 0),
            CutRule("sentence_end", "dissolve", 400, 0, 100),
        ],
        text_rules=[
            TextRule("tag", "fade_in", 32, "bottom", 0.3, 0.4, "#FFD700"),
        ],
        audio_rule=AudioRule("duck", 0.2, 0.8, 200, 200),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["CU","CU","MS"],
        emotion_arc="细节→质感→信任",
        notes="老板IP中穿插产品镜头: 叠化过渡,标签淡入,不打断叙事节奏。产品要'有故事'——不是冷冰冰展示。"
    ),

    # ========== 老板IP × Outro(结尾) ==========
    EditRule("ip_outro_01", "老板IP", "outro", "talking",
        cut_rules=[
            CutRule("sentence_end", "fade_out", 800, 0, 0),
        ],
        text_rules=[
            TextRule("cta", "fade_in", 48, "center", 0.5, 0.5, "#FFFFFF"),
        ],
        audio_rule=AudioRule("keep", 0.3, 1.0, 0, 1000),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["MS","MS"],
        emotion_arc="感悟→期待",
        notes="老板IP结尾: 人物半身→缓慢拉远→CTA淡入→BGM渐弱。让观众感觉'意犹未尽,还想听'。"
    ),

    # ========== 团购售卖 × Hook(开头钩子) ==========
    EditRule("sale_hook_01", "团购售卖", "hook", "product",
        cut_rules=[
            CutRule("beat_1", "cut", 0, 0, 0),
        ],
        text_rules=[
            TextRule("price", "pop_in", 72, "center", 0.0, 0.4, "#FF4444"),
            TextRule("hook", "slide_up", 48, "bottom", 0.3, 0.7, "#FFFFFF"),
        ],
        audio_rule=AudioRule("mute", 0.35, 0.0, 0, 0),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["CU","CU"],
        emotion_arc="冲击→好奇",
        notes="团购钩子: 产品特写+价格大字红弹出+BGM鼓点同步。0.5秒冲击力——不看就划走。原声静音,只留BGM。"
    ),
    EditRule("sale_hook_02", "团购售卖", "hook", "talking",
        cut_rules=[
            CutRule("beat_1", "cut", 0, 0, 0),
        ],
        text_rules=[
            TextRule("price", "scale_up", 80, "center", 0.0, 0.3, "#FF4444"),
        ],
        audio_rule=AudioRule("keep", 0.3, 1.0, 0, 0),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["CU","MS"],
        emotion_arc="惊讶→想买",
        notes="团购人物钩子: '68块!'人脸+价格数字放大弹出——报价要快,冲击力要强。"
    ),

    # ========== 团购售卖 × Body(主体) ==========
    EditRule("sale_body_01", "团购售卖", "body", "talking",
        cut_rules=[
            CutRule("silence_300ms", "cut", 0, 100, 200),
            CutRule("content_change", "whip_pan", 200, 0, 0),
        ],
        text_rules=[
            TextRule("tag", "slide_up", 36, "bottom", 0.1, 0.8, "#FFFFFF"),
        ],
        audio_rule=AudioRule("keep", 0.3, 1.0, 0, 0),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["MS","CU","MS","CU"],
        emotion_arc="讲解→证明→说服",
        notes="团购主体口播: 快节奏,每2-3秒换镜。MS/CU交替。工艺标签底部滑动。静音300ms即切——不浪费时间。"
    ),
    EditRule("sale_body_02", "团购售卖", "body", "product",
        cut_rules=[
            CutRule("beat_1", "cut", 0, 0, 0),
            CutRule("content_change", "whip_pan", 150, 0, 0),
        ],
        text_rules=[
            TextRule("tag", "pop_in", 40, "center", 0.1, 0.3, "#FFD700"),
        ],
        audio_rule=AudioRule("duck", 0.25, 0.0, 0, 0),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["CU","CU","CU"],
        emotion_arc="细节→品质→划算",
        notes="团购产品展示: 多角度快速切换(CU→CU→CU),每镜1-2秒。鼓点卡点切换。BGM音轨保留,原声压低。"
    ),

    # ========== 团购售卖 × Outro(结尾) ==========
    EditRule("sale_outro_01", "团购售卖", "outro", "talking",
        cut_rules=[
            CutRule("sentence_end", "fade_out", 600, 0, 0),
        ],
        text_rules=[
            TextRule("cta", "scale_up", 56, "center", 0.3, 0.7, "#FFD700"),
            TextRule("tag", "fade_in", 36, "bottom", 0.6, 0.4, "#FFFFFF"),
        ],
        audio_rule=AudioRule("keep", 0.3, 1.0, 0, 800),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["MS","MS"],
        emotion_arc="紧迫→行动",
        notes="团购结尾: 人物半身+拉远+CTA大字弹出+地址标签淡入。最后3秒制造紧迫感。"
    ),

    # ========== 引流进店 × Hook(开头钩子) ==========
    EditRule("traffic_hook_01", "引流进店", "hook", "storefront",
        cut_rules=[
            CutRule("content_change", "cut", 0, 0, 0),
        ],
        text_rules=[
            TextRule("hook", "scale_up", 60, "center", 0.0, 0.4, "#FFD700"),
        ],
        audio_rule=AudioRule("keep", 0.3, 1.0, 300, 0),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["LS","LS"],
        emotion_arc="好奇→想找到",
        notes="引流门头钩子: 门头全景+独家标签大字+环境音保留(真实感)。'全玉田只此一家'。"
    ),
    EditRule("traffic_hook_02", "引流进店", "hook", "social",
        cut_rules=[
            CutRule("content_change", "dissolve", 400, 100, 0),
        ],
        text_rules=[
            TextRule("hook", "fade_in", 52, "center", 0.1, 0.5, "#FFFFFF"),
        ],
        audio_rule=AudioRule("keep", 0.25, 0.7, 200, 0),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["CU","CU","LS"],
        emotion_arc="信任→想来",
        notes="引流顾客钩子: 顾客笑脸特写+好评标签→店门全景。社交证明>任何广告。"
    ),

    # ========== 引流进店 × Body(主体) ==========
    EditRule("traffic_body_01", "引流进店", "body", "environment",
        cut_rules=[
            CutRule("content_change", "dissolve", 500, 200, 0),
        ],
        text_rules=[
            TextRule("tag", "fade_in", 36, "bottom", 0.2, 0.6, "#FFD700"),
        ],
        audio_rule=AudioRule("duck", 0.25, 0.6, 300, 300),
        speed_rule=SpeedRule("slow_motion", 0.85, 0.0),
        shot_size_sequence=["LS","MS","CU","LS"],
        emotion_arc="探索→惊喜→想来",
        notes="引流环境展示: 慢动作摇镜+环境标签+原声保留(真实感)。LS→MS→CU→LS循环——有节奏地展示空间层次。"
    ),
    EditRule("traffic_body_02", "引流进店", "body", "service",
        cut_rules=[
            CutRule("beat_1", "cut", 0, 0, 0),
        ],
        text_rules=[
            TextRule("tag", "slide_up", 36, "bottom", 0.1, 0.5, "#FFFFFF"),
        ],
        audio_rule=AudioRule("duck", 0.25, 0.5, 200, 200),
        speed_rule=SpeedRule("ramp", 1.0, 0.3),
        shot_size_sequence=["MCU","MCU","CU"],
        emotion_arc="专业→放心",
        notes="引流服务过程: 卡点切换操作步骤+标签。开头正常速度→关键动作慢动作→恢复正常。专业感+可看性。"
    ),

    # ========== 引流进店 × Outro(结尾) ==========
    EditRule("traffic_outro_01", "引流进店", "outro", "storefront",
        cut_rules=[
            CutRule("sentence_end", "fade_out", 800, 0, 0),
        ],
        text_rules=[
            TextRule("cta", "scale_up", 52, "center", 0.4, 0.6, "#FFD700"),
            TextRule("tag", "fade_in", 40, "bottom", 0.5, 0.5, "#FFFFFF"),
        ],
        audio_rule=AudioRule("keep", 0.3, 0.8, 0, 1000),
        speed_rule=SpeedRule("normal", 1.0, 0.0),
        shot_size_sequence=["LS","LS"],
        emotion_arc="决定→出发",
        notes="引流结尾: 门头定格+地址大字+导航提示。BGM渐弱。最后3秒让观众下定决心——'出发'。"
    ),
]


def get_rules_for(script_type: str, material_role: str, material_category: str = "") -> EditRule | None:
    """获取指定组合的精确编辑规则"""
    for rule in EDITING_RULES:
        if rule.script_type == script_type and rule.material_role == material_role:
            if not material_category or rule.material_category == material_category:
                return rule
    return None


def get_all_rules_for_script(script_type: str) -> list[EditRule]:
    """获取某个脚本类型的所有编辑规则"""
    return [r for r in EDITING_RULES if r.script_type == script_type]


def apply_rule_to_segment(rule: EditRule, segment: dict) -> dict:
    """将编辑规则应用到具体片段上"""
    segment["_rule_id"] = rule.rule_id
    # 应用切点规则
    segment["cut_triggers"] = [{"trigger": cr.trigger, "action": cr.action,
        "duration_ms": cr.duration_ms} for cr in rule.cut_rules]
    # 应用文字规则
    if rule.text_rules:
        tr = rule.text_rules[0]
        segment["text_overlay"] = {"text": tr.text_source, "animation": tr.animation,
            "font_size": tr.font_size, "position": tr.position, "color": tr.color}
    # 应用音频规则
    segment["audio"] = {"action": rule.audio_rule.action, "bgm_vol": rule.audio_rule.bgm_volume,
        "voice_vol": rule.audio_rule.voice_volume}
    # 应用变速规则
    segment["speed"] = {"action": rule.speed_rule.action, "factor": rule.speed_rule.speed_factor}
    # 景别序列
    segment["shot_size_hint"] = rule.shot_size_sequence[0] if rule.shot_size_sequence else "MS"
    return segment
