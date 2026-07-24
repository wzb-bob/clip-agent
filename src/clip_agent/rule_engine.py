"""
规则引擎 · 自动匹配+应用编辑规则到ClipPlan的每个segment

输入: ClipPlan + script_type
输出: 每个segment被精确编辑规则增强——含切点/文字/音频/变速参数
"""
from __future__ import annotations
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def apply_rules_to_plan(plan, script_type: str = "团购售卖"):
    """
    自动为ClipPlan的每个segment匹配并应用编辑规则。
    规则匹配: script_type × material_role × material_category → EditRule
    """
    from .editing_rules import get_rules_for, apply_rule_to_segment

    if not hasattr(plan, 'segments') or not plan.segments:
        return plan

    applied_count = 0
    for seg in plan.segments:
        # 确定素材角色
        role = "hook" if seg.section == "opening" else ("outro" if seg.section == "ending" else "body")
        # 确定素材类型
        cat = "talking" if seg.sub_type == "talking" else "product"
        if seg.covers_audio:
            cat = "product"  # B-roll大概率是产品/环境

        # 匹配规则
        rule = get_rules_for(script_type, role, cat)
        if not rule:
            rule = get_rules_for(script_type, role)  # 降级: 不限制素材类型

        if rule:
            # 应用规则到segment(修改segment的dict表示)
            seg_dict = {
                "shot_type": seg.shot_type, "duration_sec": seg.duration_sec,
                "covers_audio": seg.covers_audio, "section": seg.section,
            }
            enhanced = apply_rule_to_segment(rule, seg_dict)

            # 回写增强参数到segment
            if enhanced.get("shot_size_hint"):
                seg.shot_type = enhanced["shot_size_hint"]
            if enhanced.get("text_overlay"):
                to = enhanced["text_overlay"]
                if not seg.subtitle_text:
                    seg.subtitle_text = to.get("text", "")
                seg.subtitle_position = to.get("position", seg.subtitle_position)
            if enhanced.get("speed") and enhanced["speed"]["action"] != "normal":
                seg.description += f" [变速:{enhanced['speed']['action']}x{enhanced['speed']['factor']}]"
            if enhanced.get("audio"):
                seg.description += f" [音频:{enhanced['audio']['action']}]"
            if enhanced.get("cut_triggers"):
                triggers = [t["trigger"] for t in enhanced["cut_triggers"]]
                seg.description += f" [切点:{','.join(triggers[:2])}]"

            applied_count += 1

    logger.info("规则引擎: %s → %d/%d segments已增强", script_type, applied_count, len(plan.segments))
    return plan


def auto_enhance_plans(plans: list, script_type: str = "团购售卖") -> list:
    """批量增强所有方案"""
    return [apply_rules_to_plan(p, script_type) for p in plans]
