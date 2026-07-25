"""
脚本Agent → 剪辑Agent 联通桥 v1

Tab1 脚本输出 → 自动配置 Tab4 剪辑管线:
  - 脚本类型 → 模板+编辑规则+调色+BGM
  - 分镜信息 → 素材类型+景别+时长
  - 留存时间线 → B-roll插入时机
  - 钩子策略 → 文字叠加样式

用法:
  from .script_clip_bridge import bridge_script_to_clip
  job = bridge_script_to_clip(script_output, audio_files, video_files)
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BridgeConfig:
    """联通桥配置 — 脚本→剪辑全参数"""
    script_type: str                    # 老板IP/团购售卖/引流进店
    template_key: str                   # 剪同款模板key
    color_grade: str                    # warm/vivid/bright
    bgm_genre: str                      # BGM风格
    bgm_volume: float = 0.3

    # 脚本解析
    script_text: str = ""
    sentences: list[dict] = field(default_factory=list)

    # 分镜映射 (来自脚本Agent的ShotList)
    shot_map: list[dict] = field(default_factory=list)

    # 留存时间线 → B-roll插入点
    retention_timeline: list[dict] = field(default_factory=list)

    # 钩子策略 → 文字叠加
    hook_strategy: dict = field(default_factory=dict)

    # 五要素 (喊人/提痛/优势/解决/引导)
    five_elements: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════
# 脚本类型 → 剪辑参数映射表
# ══════════════════════════════════════════════════════════

SCRIPT_TO_CLIP_CONFIG = {
    "老板IP": {
        "template_key": "ip_story_beginning",
        "color_grade": "warm",
        "bgm_genre": "温暖/治愈/钢琴",
        "bgm_volume": 0.25,
        "editing_style": "慢节奏·长镜6-10s·保留原声·无文字干扰",
        "broll_density": 0.15,
    },
    "团购售卖": {
        "template_key": "sale_price_first",
        "color_grade": "vivid",
        "bgm_genre": "快节奏卡点/电子",
        "bgm_volume": 0.35,
        "editing_style": "快节奏·每2s换镜·大字价格·鼓点卡点",
        "broll_density": 0.5,
    },
    "引流进店": {
        "template_key": "traffic_unique",
        "color_grade": "bright",
        "bgm_genre": "轻松/生活化/节奏感",
        "bgm_volume": 0.3,
        "editing_style": "中快·门头定镜·地址大字·环境音保留",
        "broll_density": 0.45,
    },
}


def bridge_script_to_clip(
    script_output: dict,
    audio_files: list[str] = None,
    video_files: list[str] = None,
    output_dir: str = "",
) -> BridgeConfig:
    """
    主入口: 将脚本Agent输出转换为剪辑Agent的完整配置。

    script_output 格式 (来自Tab1脚本Agent):
    {
        "script_text": "...",
        "script_type": "团购售卖",
        "shot_list": {...},        # 可选 — 如果有分镜信息
        "five_elements": {...},    # 可选 — 五要素
        "hook_strategy": {...},    # 可选 — 钩子策略
        "retention_timeline": [...],  # 可选 — 留存时间线
    }
    """
    script_type = script_output.get("script_type", "团购售卖")
    config = SCRIPT_TO_CLIP_CONFIG.get(script_type, SCRIPT_TO_CLIP_CONFIG["团购售卖"])

    bridge = BridgeConfig(
        script_type=script_type,
        template_key=config["template_key"],
        color_grade=config["color_grade"],
        bgm_genre=config["bgm_genre"],
        bgm_volume=config["bgm_volume"],
        script_text=script_output.get("script_text", ""),
    )

    # 1. 解析分镜→素材需求映射
    shot_list = script_output.get("shot_list", {})
    if shot_list:
        bridge.shot_map = _map_shotlist_to_materials(shot_list, script_type)

    # 2. 留存时间线→B-roll插入时机
    retention = script_output.get("retention_timeline", [])
    if retention:
        bridge.retention_timeline = _map_retention_to_broll_points(retention)

    # 3. 钩子策略→文字叠加样式
    hook = script_output.get("hook_strategy", {})
    if hook:
        bridge.hook_strategy = _map_hook_to_text_overlay(hook)

    # 4. 五要素→段落标注
    five = script_output.get("five_elements", {})
    if five:
        bridge.five_elements = five

    # 5. 解析脚本→句子级信息
    if bridge.script_text:
        try:
            from .sentence_editor import parse_script_to_sentences
            sentences = parse_script_to_sentences(bridge.script_text, script_type)
            bridge.sentences = [
                {"index": s.index, "text": s.text, "duration": s.duration_sec,
                 "material": s.required_material, "shot": s.required_shot,
                 "broll": s.is_broll, "text_overlay": s.text_overlay}
                for s in sentences
            ]
        except Exception as e:
            logger.debug("脚本解析跳过: %s", e)

    return bridge


def apply_bridge_to_job(bridge: BridgeConfig, audio_files=None, video_files=None):
    """
    将BridgeConfig应用到ExecutionJob，生成可直接执行的作业。

    返回: ExecutionJob (已配置脚本类型、模板、调色、BGM、编辑参数)
    """
    from .execution_engine import ExecutionJob, ChangyiExecutionEngine

    # 构建A/B槽
    audio_slots = {}
    video_slots = {}
    if audio_files:
        for i, f in enumerate(audio_files):
            audio_slots[i + 1] = f
    if video_files:
        for i, f in enumerate(video_files):
            video_slots[i + 1] = f

    # 如果有shot_map，尝试自动匹配素材到分镜
    if bridge.shot_map and video_files:
        matched_video = _auto_assign_materials(bridge.shot_map, video_files or [])
        video_slots = {i + 1: f for i, f in enumerate(matched_video) if f}

    job = ExecutionJob(
        job_id=f"bridge_{bridge.script_type}_{len(bridge.sentences)}句",
        script_text=bridge.script_text,
        script_type=bridge.script_type,
        audio_slots=audio_slots,
        video_slots=video_slots,
    )

    # 预填充增强报告(脚本Agent已经生成的信息)
    job.enhancement_report["bridge_config"] = {
        "template": bridge.template_key,
        "color_grade": bridge.color_grade,
        "bgm_genre": bridge.bgm_genre,
        "bgm_volume": bridge.bgm_volume,
        "shot_count": len(bridge.shot_map),
        "has_retention": bool(bridge.retention_timeline),
        "has_hook_strategy": bool(bridge.hook_strategy),
    }

    return job


def bridge_and_execute(
    script_output: dict,
    audio_files: list[str] = None,
    video_files: list[str] = None,
    output_dir: str = "",
) -> dict:
    """
    一站式: 桥接→配置→执行→返回结果。

    这是Tab1→Tab4的终极联通入口。
    """
    bridge = bridge_script_to_clip(script_output, audio_files, video_files, output_dir)
    job = apply_bridge_to_job(bridge, audio_files, video_files)

    from .execution_engine import ChangyiExecutionEngine
    engine = ChangyiExecutionEngine()
    job = engine.execute(job, output_dir, stop_on_error=False)

    return {
        "success": job.status == "done",
        "script_type": bridge.script_type,
        "template": bridge.template_key,
        "color_grade": bridge.color_grade,
        "sentence_count": len(job.sentences),
        "total_duration": sum(s.duration_sec for s in job.sentences),
        "editing_cuts": len(job.edit_decisions.get("cuts", [])),
        "quality_score": job.quality_report.get("score", 0),
        "draft_path": job.draft_path,
        "mp4_path": job.enhancement_report.get("mp4_path", ""),
        "bridge_config": job.enhancement_report.get("bridge_config", {}),
        "errors": job.errors,
    }


# ══════════════════════════════════════════════════════════
# 内部映射函数
# ══════════════════════════════════════════════════════════

def _map_shotlist_to_materials(shot_list: dict, script_type: str) -> list[dict]:
    """将ShotList中的每个ShotSpec映射为剪辑素材需求"""
    shots = shot_list.get("shots", [])
    result = []
    for s in shots:
        result.append({
            "shot_id": s.get("shot_id", 0),
            "label": s.get("label", ""),
            "required_material": s.get("required_material", "talking_head"),
            "required_shot": s.get("shot_type", "MS"),
            "duration": s.get("duration_sec", 3.0),
            "camera_move": s.get("camera_move", "static"),
            "text_overlay": s.get("text_overlay", ""),
            "text_position": s.get("text_position", "bottom"),
            "broll": s.get("broll_overlay", False),
        })
    return result


def _map_retention_to_broll_points(retention: list[dict]) -> list[dict]:
    """留存时间线→B-roll插入时机"""
    return [
        {"at_sec": r.get("at_sec", 0), "action": r.get("action", ""),
         "detail": r.get("detail", ""), "is_broll_point": r.get("action", "") != "open_hook"}
        for r in retention
    ]


def _map_hook_to_text_overlay(hook: dict) -> dict:
    """钩子策略→文字叠加样式参数"""
    return {
        "text": hook.get("text_0s", ""),
        "visual": hook.get("visual_0s", ""),
        "audio": hook.get("audio_0s", ""),
        "verbal": hook.get("verbal_0s", ""),
        "animation": "scale_up" if "冲击" in hook.get("verbal_0s", "") else "fade_in",
        "font_size": 72 if len(hook.get("text_0s", "")) <= 8 else 56,
        "color": "#FF4444" if "价" in hook.get("text_0s", "") else "#FFD700",
    }


def _auto_assign_materials(shot_map: list[dict], video_files: list[str]) -> list[str]:
    """简单贪心匹配: 按顺序分配素材到分镜需求"""
    if not video_files:
        return []
    assigned = []
    used = set()
    for shot in shot_map:
        for vf in video_files:
            if vf in used:
                continue
            # 简单规则: 文件名包含关键字的优先匹配
            fn = vf.lower()
            mat = shot.get("required_material", "")
            if mat == "product_closeup" and any(kw in fn for kw in ["产品", "product", "特写", "货"]):
                assigned.append(vf)
                used.add(vf)
                break
            elif mat == "environment" and any(kw in fn for kw in ["环境", "店", "门头", "空镜", "街"]):
                assigned.append(vf)
                used.add(vf)
                break
            elif mat == "talking_head" and any(kw in fn for kw in ["口播", "人", "talking", "face"]):
                assigned.append(vf)
                used.add(vf)
                break
        else:
            # 没匹配到 → 按顺序分配剩余素材
            remaining = [f for f in video_files if f not in used]
            if remaining:
                assigned.append(remaining[0])
                used.add(remaining[0])
    return assigned
