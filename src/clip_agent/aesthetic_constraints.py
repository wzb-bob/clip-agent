"""
美学约束层 v1 · 帧级编辑硬规则 · 防止明显错误

专业剪辑师的"肌肉记忆"——这些人不会犯的错误,AI必须避免。"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AestheticIssue:
    """一个美学问题"""
    at_sec: float
    severity: str          # error/warning/info
    rule: str              # 触发的规则
    detail: str            # 具体描述
    fix: str               # 修复建议


def check_aesthetics(segments: list, script_type: str = "团购售卖") -> list[AestheticIssue]:
    """
    对一组剪辑段做美学约束检查。

    规则:
    1. 相邻3个相同景别 → error (强制变化)
    2. 同一素材重复>2次 → warning
    3. 单段>8秒无变化 → warning (太长了观众流失)
    4. 单段<0.5秒 → warning (太快看不清)
    5. B-roll段没有过渡 → info
    6. 钩子段<2秒 → warning (太短冲击力不够)
    7. CTA段>5秒 → warning (结尾拖沓)
    """
    issues = []

    if len(segments) < 2:
        return issues

    # R1: 相邻3个相同景别
    for i in range(len(segments) - 2):
        s1 = _get_shot(segments[i])
        s2 = _get_shot(segments[i+1])
        s3 = _get_shot(segments[i+2])
        if s1 == s2 == s3 and s1 in ("CU", "MS", "LS", "MCU"):
            issues.append(AestheticIssue(
                at_sec=_get_start(segments[i+1]),
                severity="error",
                rule="R1: 重复景别×3",
                detail=f"连续3个{s1}景别——观众会感觉单调",
                fix=f"将第{i+2}段{s1}改为{CU if s1!='CU' else 'MS' if s1!='MS' else 'LS'}",
            ))

    # R2: 同一素材重复>2次
    file_counts = {}
    for seg in segments:
        f = _get_file(seg)
        if f:
            file_counts[f] = file_counts.get(f, 0) + 1
    for f, count in file_counts.items():
        if count > 2:
            issues.append(AestheticIssue(
                at_sec=0, severity="warning",
                rule="R2: 素材重复",
                detail=f"素材'{f[:20]}'使用了{count}次·超过2次",
                fix="插入过渡镜头或替换为其他素材",
            ))

    # R3-R5: 逐段检查
    for i, seg in enumerate(segments):
        dur = _get_duration(seg)
        start = _get_start(seg)
        is_broll = _get_broll(seg)
        role = _get_role(seg, i, len(segments))

        # R3: 单段>8秒
        if dur > 8:
            issues.append(AestheticIssue(
                at_sec=start, severity="warning",
                rule="R3: 单段过长",
                detail=f"第{i+1}段{dur:.1f}秒——>8秒观众流失",
                fix=f"在{start+4:.1f}s处插入B-roll或切分为2段",
            ))

        # R4: 单段<0.5秒
        if dur < 0.5:
            issues.append(AestheticIssue(
                at_sec=start, severity="warning",
                rule="R4: 单段过短",
                detail=f"第{i+1}段{dur:.1f}秒——<0.5秒观众反应不过来",
                fix="延长到至少1秒或合并到相邻段",
            ))

        # R5: B-roll无过渡
        if is_broll and i > 0:
            prev_trans = _get_trans_out(segments[i-1])
            if prev_trans == "cut":
                issues.append(AestheticIssue(
                    at_sec=start, severity="info",
                    rule="R5: B-roll硬切",
                    detail=f"B-roll段前为硬切·建议dissolve过渡",
                    fix=f"将第{i}段transition改为dissolve(300ms)",
                ))

        # R6: 钩子<2秒
        if role == "hook" and dur < 2.0:
            issues.append(AestheticIssue(
                at_sec=start, severity="warning",
                rule="R6: 钩子太短",
                detail=f"钩子段{dur:.1f}秒——<2秒冲击力不足",
                fix="延长钩子到2-3秒·确保4层钩子(视觉/文字/口头/音频)同时作用",
            ))

        # R7: CTA>5秒
        if role == "cta" and dur > 5.0:
            issues.append(AestheticIssue(
                at_sec=start, severity="warning",
                rule="R7: CTA拖沓",
                detail=f"CTA段{dur:.1f}秒——>5秒结尾拖沓",
                fix="缩减到3-4秒·快节奏收尾",
            ))

    return issues


def apply_fixes(segments: list, issues: list[AestheticIssue]) -> list:
    """自动应用可修复的美学问题"""
    for issue in issues:
        if issue.severity == "error" and "R1" in issue.rule:
            # 自动修复重复景别
            fix_shot = issue.fix.split("改为")[-1].split("'")[0] if "改为" in issue.fix else "MS"
            for seg in segments:
                if abs(_get_start(seg) - issue.at_sec) < 0.5:
                    _set_shot(seg, fix_shot.split(" ")[0] if " " in fix_shot else fix_shot)
                    break

    return segments


def validate_plan(segments: list, script_type: str = "团购售卖") -> dict:
    """
    验证剪辑计划的美学质量, 返回报告。

    返回: {"score": 0-100, "issues": [...], "passed": bool}
    """
    issues = check_aesthetics(segments, script_type)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    # 评分: 每个error扣20分, 每个warning扣5分
    score = max(0, 100 - len(errors) * 20 - len(warnings) * 5)

    return {
        "score": score,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len([i for i in issues if i.severity == "info"]),
        "issues": [{"at": i.at_sec, "severity": i.severity, "rule": i.rule, "detail": i.detail, "fix": i.fix} for i in issues],
        "passed": len(errors) == 0,
    }


# Helpers for accessing segment attributes (works with dict, dataclass, or object)
def _get_shot(s): return getattr(s, "shot_type", None) or s.get("shot_type", "") if isinstance(s, dict) else (getattr(s, "required_shot", "") if hasattr(s, "required_shot") else "")
def _get_start(s): return getattr(s, "start_sec", None) or s.get("start_sec", 0) if isinstance(s, dict) else 0
def _get_duration(s): return getattr(s, "duration_sec", None) or s.get("duration_sec", 3.0) if isinstance(s, dict) else 3.0
def _get_file(s): return getattr(s, "video_file", None) or s.get("video_file", "") if isinstance(s, dict) else ""
def _get_broll(s): return getattr(s, "is_broll", None) or s.get("is_broll", False) if isinstance(s, dict) else False
def _get_trans_out(s): return getattr(s, "transition_out", "cut") if hasattr(s, "transition_out") else "cut"
def _get_role(s, idx, total): return "hook" if idx==0 else ("cta" if idx==total-1 else "body")
def _set_shot(s, shot):
    if hasattr(s, "shot_type"): s.shot_type = shot
    elif hasattr(s, "required_shot"): s.required_shot = shot
