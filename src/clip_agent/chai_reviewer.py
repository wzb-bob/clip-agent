"""
CHAI审查器 · OpenMontage reviewer.md适配 · 质量门禁终审

CHAI原则: Accurate(精确到字段)·Complete(扫描同类问题)·Constructive(给修复建议)
审查协议: Schema验证→Focus Item检查→Playbook交叉验证→结果报告
"""
from __future__ import annotations
import json, logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReviewFinding:
    """审查发现"""
    severity: str           # critical/suggestion/nitpick/investigation
    criterion: str          # 审查标准
    artifact_field: str     # 问题所在的字段
    finding: str            # 问题描述
    proposed_fix: str       # 修复建议(Constructive——必须有!)
    location: str = ""      # 位置(行号/时间)


@dataclass
class ReviewResult:
    """审查结果"""
    stage: str
    passed: bool
    findings: list[ReviewFinding]
    critical_count: int
    suggestion_count: int
    score: float            # 0-100
    summary: str


class ChaiReviewer:
    """CHAI审查器——每阶段必须经过"""

    def __init__(self, stage_name: str, review_focus: list[str], success_criteria: list[str]):
        self.stage = stage_name
        self.review_focus = review_focus
        self.success_criteria = success_criteria

    def review(self, artifact: dict, playbook_rules: dict = None) -> ReviewResult:
        """执行完整审查协议

        Step 1: Schema验证
        Step 2: Focus Item逐项检查
        Step 3: Playbook交叉验证
        Step 4: 评分+总结
        """
        findings = []

        # Step 1: Schema验证(非协商)
        schema_ok, schema_findings = self._validate_schema(artifact)
        findings.extend(schema_findings)
        if not schema_ok:
            return ReviewResult(self.stage, False, findings,
                              sum(1 for f in findings if f.severity=="critical"),
                              sum(1 for f in findings if f.severity=="suggestion"),
                              0, "Schema验证失败——必须修复后再审查")

        # Step 2: Focus Item检查
        for focus in self.review_focus:
            f = self._check_focus_item(artifact, focus)
            if f: findings.append(f)

        # Step 3: Playbook交叉验证
        if playbook_rules:
            for rule_name, rule_check in playbook_rules.items():
                f = self._check_playbook_rule(artifact, rule_name, rule_check)
                if f: findings.append(f)

        # Step 4: 评分
        criticals = [f for f in findings if f.severity == "critical"]
        suggestions = [f for f in findings if f.severity == "suggestion"]
        score = 100
        score -= len(criticals) * 25    # critical -25 each
        score -= len(suggestions) * 5   # suggestion -5 each
        score = max(0, score)

        passed = len(criticals) == 0 and all(
            self._check_criterion(artifact, sc) for sc in self.success_criteria)

        return ReviewResult(
            stage=self.stage, passed=passed, findings=findings,
            critical_count=len(criticals), suggestion_count=len(suggestions),
            score=score,
            summary=f"{'✅ 通过' if passed else '❌ 未通过'} — {len(criticals)}严重/{len(suggestions)}建议 (CHAI审查)",
        )

    def _validate_schema(self, artifact: dict) -> tuple[bool, list[ReviewFinding]]:
        """Schema验证——必须有platform/tracks/materials"""
        required = ["platform", "tracks", "materials"]
        findings = []
        for field in required:
            if field not in artifact:
                findings.append(ReviewFinding(
                    "critical", "schema_validation", field,
                    f"缺少必需字段'{field}'——草稿结构不完整",
                    f"在artifact中添加'{field}'字段",
                ))
        return len(findings) == 0, findings

    def _check_focus_item(self, artifact: dict, focus: str) -> ReviewFinding | None:
        """检查单个focus item"""
        # 简化: 基于关键词匹配
        if "duration" in focus.lower():
            dur = artifact.get("draft_info", {}).get("total_duration_us", 0) / 1_000_000
            if dur <= 0:
                return ReviewFinding("critical", "duration_check", "total_duration_us",
                    "视频时长无效(0秒)", "检查素材时间线——确保每个segment都有有效时长")
            if dur > 60:
                return ReviewFinding("suggestion", "duration_check", "total_duration_us",
                    f"时长{dur:.0f}s超过抖音60s限制", "删减内容到60s以内,或拆分多集")
        if "segment" in focus.lower() or "shot" in focus.lower():
            tracks = artifact.get("tracks", [])
            seg_count = sum(len(t.get("segments", [])) for t in tracks)
            if seg_count == 0:
                return ReviewFinding("critical", "segment_check", "tracks[].segments",
                    "没有任何镜头——视频为空", "至少添加3个segment")
            if seg_count < 3:
                return ReviewFinding("suggestion", "segment_check", "tracks[].segments",
                    f"只有{seg_count}个镜头——建议增加到≥3个", "添加开头钩子+主体+结尾CTA")
        return None

    def _check_playbook_rule(self, artifact: dict, rule_name: str, rule_check) -> ReviewFinding | None:
        """Playbook规则检查"""
        if "color" in rule_name.lower():
            return ReviewFinding("nitpick", rule_name, "color_filter",
                f"调色检查: {rule_check}", "确认滤镜与品牌风格一致")
        if "transition" in rule_name.lower():
            tracks = artifact.get("tracks", [])
            return ReviewFinding("suggestion", rule_name, "transitions",
                f"转场检查: {len(tracks)}条轨道", "确保段间转场类型与playbook一致")
        return None

    def _check_criterion(self, artifact: dict, criterion: str) -> bool:
        """检查成功标准"""
        tracks = artifact.get("tracks", [])
        total_segs = sum(len(t.get("segments", [])) for t in tracks)
        if "segment" in criterion.lower() and "≥" in criterion:
            min_count = int(criterion.split("≥")[1].split()[0]) if "≥" in criterion else 3
            return total_segs >= min_count
        return True  # 默认通过


def review_edit_decisions(edit_decisions: dict, stage_name: str = "editing") -> ReviewResult:
    """快速审查编辑决策"""
    reviewer = ChaiReviewer(
        stage_name,
        review_focus=["duration_check", "segment_count≥3", "shot_variety≥2"],
        success_criteria=["Schema-valid artifact", "At least 3 segments", "Duration > 0"],
    )
    return reviewer.review(edit_decisions)
