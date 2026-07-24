"""
电影级剪辑规则 · 从开源项目提炼的6大编辑约束

来源:
- oximedia_shots: 6种节奏模式(RegularCadence/Alternating/BuildUp/CoolDown/Montage/Contemplative)
- EditIQ: 5条电影规则(无跳切/节奏一致/无瞬切/正确取景/反应镜头优先)
- Auto-Editor: 安全边距(margin)控制切点前后的缓冲
- chrislema/videoeditor: 3级缩放节奏(normal/emphasis/critical)
- CutClaw: 节拍对齐+多Agent管线
"""
from __future__ import annotations
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


# ================================================================
# 1. 6种节奏模式 (oximedia_shots)
# ================================================================

RHYTHM_PATTERNS = {
    "regular_cadence": {
        "name": "稳定节奏型",
        "desc": "每镜时长基本相同,偏差<15%。适合产品展示、知识口播。",
        "shot_duration_range": (2.0, 3.0),
        "variation_max": 0.15,
        "transition": "cut",
        "best_for": ["product_show", "knowledge_share"],
    },
    "alternating": {
        "name": "交替节奏型",
        "desc": "长镜↔短镜交替。长镜=主体(5-8s),短镜=B-roll(1-2s)。口播+空镜经典模式。",
        "shot_duration_pattern": [5.0, 1.5, 5.0, 1.5, 5.0, 1.5],
        "transition": "dissolve",
        "best_for": ["talking_head_with_broll", "store_tour"],
    },
    "build_up": {
        "name": "加速型",
        "desc": "镜头越来越短,节奏越来越快——制造紧张感或兴奋感。",
        "shot_duration_ramp": (4.0, 1.0),  # 从4s渐变到1s
        "transition": "cut",
        "best_for": ["action", "before_after_reveal"],
    },
    "cool_down": {
        "name": "减速型",
        "desc": "镜头越来越长,节奏越来越慢——让观众沉淀、思考。",
        "shot_duration_ramp": (1.5, 5.0),
        "transition": "dissolve",
        "best_for": ["ending", "emotional_close"],
    },
    "montage": {
        "name": "蒙太奇型",
        "desc": "极快速切换(<1s/镜),大量短镜密集排列。适合高潮/总结/卡点视频。",
        "shot_duration_range": (0.5, 1.5),
        "min_shots": 8,
        "transition": "whip_pan",
        "best_for": ["highlight", "music_sync", "product_montage"],
    },
    "contemplative": {
        "name": "沉思型",
        "desc": "长镜头(>8s),极少切换。适合情感故事、品牌宣传、纪录片风格。",
        "shot_duration_range": (8.0, 15.0),
        "max_shots": 5,
        "transition": "fade",
        "best_for": ["brand_story", "founder_interview"],
    },
}


# ================================================================
# 2. 5条电影约束 (EditIQ) + 安全边距 (Auto-Editor)
# ================================================================

CINEMATIC_CONSTRAINTS = {
    "no_jump_cuts": {
        "rule": "禁止跳切——同一主体(同一个人/同一个产品)的连续两个镜头之间角度或景别必须变化至少30°或一个景别级别",
        "check": "相邻镜头景别差<1级 AND 角度差<30° → 违规",
        "fix": "在第N镜和第N+1镜之间插入B-roll空镜,或调整景别",
        "severity": "high",
    },
    "rhythm_consistency": {
        "rule": "节奏一致性——同一段内的镜头时长变化不应超过50%(除非有意加速/减速)",
        "check": "std(durations)/mean(durations) > 0.5 AND not in build_up/cool_down pattern → 违规",
        "fix": "调整异常镜头时长到均值±50%范围内",
        "severity": "medium",
    },
    "no_transient_shots": {
        "rule": "无瞬切——任何镜头不能短于0.5秒(观众无法看清)",
        "check": "任意镜头 duration < 0.5s → 违规",
        "fix": "删除该镜头或将时长延长到≥1.0s",
        "severity": "high",
    },
    "proper_framing": {
        "rule": "正确取景——人物出镜时,眼睛应在画面上1/3处,不能切到下巴或额头",
        "check": "人物CU/MCU镜头中,人脸占比>70%或<15% → 可能取景不当",
        "fix": "标记该素材'建议重新取景拍摄'",
        "severity": "medium",
    },
    "reaction_shot_priority": {
        "rule": "反应镜头优先——当一句话说完(>500ms静音),应切到听众反应,而不是继续拍说话者",
        "check": "silence > 500ms after talking_head segment AND next segment is also talking_head → 违规",
        "fix": "在静音处插入B-roll或听众反应镜头",
        "severity": "medium",
    },
    "safe_margin": {
        "rule": "安全边距——切点前后各保留0.2s缓冲,避免切到词语中间或动作半截",
        "check": "cut point is at word/action midpoint",
        "fix": "切点前移0.2s(切在词间静音处)或后移0.2s(等词说完)",
        "severity": "low",
        "margin_sec": 0.2,
    },
}


# ================================================================
# 3. 3级缩放节奏 (chrislema/videoeditor)
# ================================================================

ZOOM_PACING = {
    "normal": {
        "zoom": 1.0,
        "description": "铺垫/过渡/背景信息——正常缩放,稳定画面",
        "content_ratio": 0.40,  # 占视频40%
        "best_for": ["setup", "context", "transition"],
    },
    "emphasis": {
        "zoom": 1.25,
        "description": "关键信息/核心卖点——轻微放大,吸引注意",
        "content_ratio": 0.35,
        "best_for": ["key_point", "feature_highlight", "rising_energy"],
    },
    "critical": {
        "zoom": 1.6,
        "description": "核心论点/情感爆发——显著放大,冲击力最强",
        "content_ratio": 0.25,
        "best_for": ["thesis", "emotional_peak", "hook"],
    },
}


# ================================================================
# 4. 节奏模式检测 + 约束验证
# ================================================================

def detect_rhythm_pattern(segments: list) -> str:
    """根据镜头时长序列自动检测节奏模式"""
    if not segments or len(segments) < 3:
        return "regular_cadence"

    durations = [s.duration_sec if hasattr(s, 'duration_sec') else s.get('duration_sec', 3) for s in segments]
    mean_dur = sum(durations) / len(durations)

    # 检查是否为蒙太奇型(全部<1.5s)
    if all(d < 1.5 for d in durations) and len(durations) >= 6:
        return "montage"

    # 检查是否为沉思型(全部>8s)
    if all(d > 8 for d in durations):
        return "contemplative"

    # 检查交替型(长-短-长-短)
    alt_count = sum(1 for i in range(1, len(durations)) if abs(durations[i] - durations[i-1]) > 2)
    if alt_count >= len(durations) * 0.5:
        return "alternating"

    # 检查加速型(前长后短)
    if durations[0] > durations[-1] * 2:
        return "build_up"

    # 检查减速型(前短后长)
    if durations[-1] > durations[0] * 2:
        return "cool_down"

    # 默认稳定节奏
    return "regular_cadence"


def validate_cinematic_rules(segments: list) -> list[dict]:
    """验证5条电影约束+安全边距,返回违规列表"""
    violations = []
    if not segments or len(segments) < 2:
        return violations

    durations = [s.duration_sec if hasattr(s, 'duration_sec') else s.get('duration_sec', 3) for s in segments]

    for i in range(len(segments)):
        d = durations[i]

        # 无瞬切
        if d < 0.5:
            violations.append({"rule": "no_transient_shots", "segment": i+1, "detail": f"镜头{i+1}时长{d}s<0.5s", "fix": "延长到≥1.0s或删除"})

    # 无跳切(相邻景别检查)
    for i in range(len(segments)-1):
        s1 = segments[i]; s2 = segments[i+1]
        st1 = s1.shot_type if hasattr(s1, 'shot_type') else s1.get('shot_type', 'MS')
        st2 = s2.shot_type if hasattr(s2, 'shot_type') else s2.get('shot_type', 'MS')
        shot_levels = {"ELS":0,"LS":1,"MLS":2,"MS":3,"MCU":4,"CU":5,"ECU":6}
        if abs(shot_levels.get(st1,3) - shot_levels.get(st2,3)) < 1:
            violations.append({"rule": "no_jump_cuts", "segment": f"{i+1}-{i+2}", "detail": f"镜{i+1}({st1})→镜{i+2}({st2})景别变化不足", "fix": "插入B-roll或调整景别"})

    # 节奏一致性
    if len(durations) >= 3:
        std_dur = (sum((d - sum(durations)/len(durations))**2 for d in durations) / len(durations)) ** 0.5
        cv = std_dur / (sum(durations)/len(durations))
        if cv > 0.5:
            violations.append({"rule": "rhythm_consistency", "segment": "all", "detail": f"时长变异系数{cv:.1f}>0.5", "fix": "调整异常镜头时长"})

    return violations


def get_rhythm_for_script_type(script_type: str) -> str:
    """根据脚本类型推荐最佳节奏模式"""
    mapping = {
        "老板IP": "contemplative",      # 长镜,沉思型
        "团购售卖": "alternating",       # 长-短交替
        "引流进店": "regular_cadence",  # 稳定节奏
    }
    return mapping.get(script_type, "regular_cadence")
