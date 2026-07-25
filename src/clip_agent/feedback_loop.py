"""
剪辑→脚本 闭环反馈系统 v1

剪辑结果回传给脚本Agent, 驱动脚本生成持续优化:
  - 分镜匹配率 → 调整ShotList复杂度
  - 素材质量分 → 优化拍摄指导
  - 编辑质量分 → 验证剪辑策略
  - 用户手动修改 → 学习真实偏好

存储: JSONL文件 (追加式, 无需SQLite依赖)
查询: 按脚本类型/时间段聚合统计
"""
from __future__ import annotations
import json, logging, os, time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FEEDBACK_DIR = Path(__file__).parent.parent.parent / "data" / "feedback"
FEEDBACK_FILE = FEEDBACK_DIR / "clip_feedback.jsonl"


@dataclass
class FeedbackReport:
    """一次完整剪辑的反馈报告"""
    # 源信息
    feedback_id: str
    timestamp: str                    # ISO格式
    session_id: str = ""

    # 脚本信息 (来自Tab1)
    script_type: str = "团购售卖"
    script_text: str = ""
    shot_count_planned: int = 0       # ShotList计划镜头数
    hook_type: str = ""               # 使用的钩子类型

    # 素材信息
    material_count_total: int = 0      # 上传素材总数
    material_count_talking: int = 0    # 口播素材数
    material_count_broll: int = 0      # B-roll素材数
    material_quality_avg: float = 0.0  # 素材平均质量分

    # 剪辑结果
    clip_success: bool = False
    clip_duration: float = 0.0         # 成片时长(秒)
    clip_quality_score: float = 0.0    # 质量门禁得分
    sentence_count: int = 0            # 解析出的句子数
    editing_cuts: int = 0              # 切点数

    # 匹配分析
    shot_coverage_pct: float = 0.0     # 分镜覆盖率(实际匹配/计划)
    missing_material_types: list[str] = field(default_factory=list)  # 缺少的素材类型
    broll_coverage_pct: float = 0.0    # B-roll覆盖率

    # 模板匹配
    template_used: str = ""
    color_grade: str = ""
    bgm_genre: str = ""
    editing_style: str = ""

    # 优化建议
    optimization_hints: list[dict] = field(default_factory=list)

    # 原始数据
    raw_job_summary: dict = field(default_factory=dict)


class FeedbackStore:
    """反馈存储 — JSONL文件追加式"""

    def __init__(self, file_path: str = ""):
        self.file_path = Path(file_path) if file_path else FEEDBACK_FILE
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, report: FeedbackReport) -> bool:
        """追加一条反馈记录"""
        try:
            record = {
                "feedback_id": report.feedback_id,
                "timestamp": report.timestamp,
                "script_type": report.script_type,
                "shot_count_planned": report.shot_count_planned,
                "material_count_total": report.material_count_total,
                "clip_success": report.clip_success,
                "clip_quality_score": report.clip_quality_score,
                "shot_coverage_pct": report.shot_coverage_pct,
                "missing_material_types": report.missing_material_types,
                "template_used": report.template_used,
                "color_grade": report.color_grade,
                "optimization_hints": report.optimization_hints,
            }
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.debug("反馈已保存: %s", report.feedback_id)
            return True
        except Exception as e:
            logger.warning("反馈保存失败: %s", e)
            return False

    def load_all(self, limit: int = 100) -> list[dict]:
        """加载最近N条反馈"""
        if not self.file_path.exists():
            return []
        records = []
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    records.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return records[-limit:]

    def get_stats(self, script_type: str = "", days: int = 30) -> dict:
        """聚合统计: 某脚本类型的剪辑效果"""
        records = self.load_all(limit=500)
        if script_type:
            records = [r for r in records if r.get("script_type") == script_type]
        if not records:
            return {"count": 0, "message": "无反馈数据"}

        scores = [r.get("clip_quality_score", 0) for r in records]
        coverages = [r.get("shot_coverage_pct", 0) for r in records]
        successes = sum(1 for r in records if r.get("clip_success"))

        # 最常见的缺失素材类型
        missing_counts = {}
        for r in records:
            for mt in r.get("missing_material_types", []):
                missing_counts[mt] = missing_counts.get(mt, 0) + 1

        return {
            "count": len(records),
            "success_rate": round(successes / len(records) * 100, 1),
            "avg_quality_score": round(sum(scores) / len(scores), 1),
            "avg_shot_coverage": round(sum(coverages) / len(coverages), 1),
            "top_missing_materials": sorted(missing_counts.items(), key=lambda x: -x[1])[:5],
        }


def generate_feedback(
    bridge_config: dict,
    job_result: dict,
    material_stats: dict = None,
) -> FeedbackReport:
    """
    从剪辑作业结果生成反馈报告。

    Args:
        bridge_config: 来自BridgeConfig的输出
        job_result: execution_engine返回的作业结果
        material_stats: {"total": N, "talking": N, "broll": N, "quality_avg": X}
    """
    feedback_id = f"fb_{int(time.time())}"
    ts = datetime.now().isoformat()

    # 计算分镜覆盖率
    planned = len(bridge_config.get("shot_map", []))
    actual = len(job_result.get("sentences", []))
    coverage = round(min(actual / max(planned, 1), 1.0) * 100, 1)

    # 分析缺失素材类型
    missing = _analyze_missing_materials(bridge_config, job_result)

    # 生成优化建议
    hints = _generate_optimization_hints(bridge_config, job_result, coverage, missing)

    report = FeedbackReport(
        feedback_id=feedback_id,
        timestamp=ts,
        script_type=bridge_config.get("script_type", "团购售卖"),
        script_text=bridge_config.get("script_text", "")[:200],
        shot_count_planned=planned,
        material_count_total=(material_stats or {}).get("total", 0),
        material_count_talking=(material_stats or {}).get("talking", 0),
        material_count_broll=(material_stats or {}).get("broll", 0),
        material_quality_avg=(material_stats or {}).get("quality_avg", 0),
        clip_success=job_result.get("success", False),
        clip_duration=job_result.get("total_duration", 0),
        clip_quality_score=job_result.get("quality_score", 0),
        sentence_count=job_result.get("sentence_count", 0),
        editing_cuts=job_result.get("editing_cuts", 0),
        shot_coverage_pct=coverage,
        missing_material_types=missing,
        broll_coverage_pct=_calc_broll_coverage(job_result),
        template_used=bridge_config.get("template_key", ""),
        color_grade=bridge_config.get("color_grade", ""),
        bgm_genre=bridge_config.get("bgm_genre", ""),
        editing_style=bridge_config.get("editing_style", ""),
        optimization_hints=hints,
        raw_job_summary={
            "draft_path": job_result.get("draft_path", ""),
            "mp4_path": job_result.get("mp4_path", ""),
            "errors": job_result.get("errors", []),
        },
    )

    return report


def _analyze_missing_materials(bridge_config: dict, job_result: dict) -> list[str]:
    """分析缺少了哪些素材类型"""
    shot_map = bridge_config.get("shot_map", [])
    if not shot_map:
        return []

    # 统计需求
    required_types = {}
    for s in shot_map:
        mat = s.get("required_material", "unknown")
        required_types[mat] = required_types.get(mat, 0) + 1

    # 简单判断: 如果某类型需求>0但质量分为0, 标记为缺失
    missing = []
    quality = job_result.get("quality_score", 0)
    if quality < 5:
        # 低分 → 可能素材不够
        for mat_type, count in required_types.items():
            if count >= 2 and mat_type not in ("talking_head",):
                missing.append(mat_type)

    return missing[:3]


def _calc_broll_coverage(job_result: dict) -> float:
    """计算B-roll覆盖率"""
    cuts = job_result.get("editing_cuts", 0)
    total = job_result.get("sentence_count", 1)
    if total == 0:
        return 0.0
    # 粗略估算: 切点数的30%是B-roll覆盖
    return round(min(cuts * 0.3 / total, 1.0) * 100, 1)


def _generate_optimization_hints(
    bridge_config: dict, job_result: dict, coverage: float, missing: list
) -> list[dict]:
    """生成可执行的优化建议 — 脚本Agent可直接消费"""
    hints = []

    # 1. 分镜覆盖不足 → 简化ShotList
    if coverage < 50:
        hints.append({
            "target": "shotlist",
            "severity": "high",
            "hint": f"分镜覆盖率仅{coverage}% — 减少镜头类型, 增加通用素材提示",
            "action": "reduce_shot_variety",
            "detail": "将景别限制在2-3种, 降低B-roll密度到0.2以下",
        })

    # 2. 质量分低 → 加强素材指导
    quality = job_result.get("quality_score", 0)
    if quality < 5:
        hints.append({
            "target": "shooting_guide",
            "severity": "medium",
            "hint": f"成片质量{quality}分偏低 — 脚本中的拍摄指导需要更具体",
            "action": "enhance_shooting_guide",
            "detail": "分镜指导中加入'保持3秒稳定''对焦XX'等具体动作",
        })

    # 3. 缺少产品特写 → 脚本中强调
    if "product_closeup" in missing:
        hints.append({
            "target": "script",
            "severity": "high",
            "hint": "缺少产品特写素材 — 脚本中需要明确标注'【插入产品特写CU】'",
            "action": "mark_product_closeup_explicitly",
            "detail": "在价格/工艺描述段落后, 添加分镜标注",
        })

    # 4. 缺少环境空镜 → 引导拍摄
    if "environment" in missing:
        hints.append({
            "target": "shotlist",
            "severity": "medium",
            "hint": "缺少环境/门头空镜 — 引流类脚本至少拍2条环境镜头",
            "action": "add_environment_shots",
            "detail": "在分镜清单开头加入门头全景LS, 结尾加入店内环境LS",
        })

    # 5. 默认通用建议
    hints.append({
        "target": "hook",
        "severity": "low",
        "hint": f"{bridge_config.get('script_type', '')}脚本建议搭配{bridge_config.get('hook_type', '价格冲击')}型钩子",
        "action": "suggest_hook_type",
        "detail": "开篇0-3s用CU特写+大字覆盖, 提高完播率",
    })

    return hints


def get_script_optimization_hints(script_type: str = "", limit: int = 20) -> dict:
    """
    查询历史剪辑反馈, 返回脚本Agent可用的优化建议。

    脚本Agent调用此函数获取"上次这样写的脚本, 剪辑效果如何"。
    """
    store = FeedbackStore()
    records = store.load_all(limit=limit)

    if not records:
        return {"has_data": False, "message": "暂无剪辑反馈数据, 按默认策略生成"}

    if script_type:
        records = [r for r in records if r.get("script_type") == script_type]

    if not records:
        return {"has_data": False, "message": f"无{script_type}类型反馈数据"}

    # 聚合所有优化建议
    all_hints = []
    for r in records:
        all_hints.extend(r.get("optimization_hints", []))

    # 按严重程度排序
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_hints.sort(key=lambda h: severity_order.get(h.get("severity", "low"), 9))

    # 去重
    seen = set()
    unique_hints = []
    for h in all_hints:
        key = h.get("action", "")
        if key not in seen:
            seen.add(key)
            unique_hints.append(h)

    stats = store.get_stats(script_type)

    return {
        "has_data": True,
        "stats": stats,
        "top_hints": unique_hints[:5],
        "total_feedback_count": len(records),
    }
