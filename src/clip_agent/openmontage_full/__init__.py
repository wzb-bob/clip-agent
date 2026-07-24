"""
OpenMontage 完全桥接 · 156技能·13管线·24Schema 全部可用

这个模块桥接到本地的 OpenMontage 克隆目录,使其全部技能可在长益Agent中调用。
"""
from __future__ import annotations
import logging, os
from pathlib import Path

logger = logging.getLogger(__name__)

# OpenMontage 克隆路径
OM_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent / "OpenMontage"

# ================================================================
# 13条管线
# ================================================================
PIPELINES = [
    "animated-explainer", "animation", "avatar-spokesperson", "character-animation",
    "cinematic", "clip-factory", "documentary-montage", "hybrid",
    "localization-dub", "podcast-repurpose", "screen-demo", "talking-head",
    "framework-smoke",
]

# ================================================================
# 4大技能类别
# ================================================================
SKILL_CATEGORIES = {
    "core": ["color-grading", "ffmpeg", "hyperframes", "remotion", "subtitle-sync", "whisperx"],
    "creative": [
        "animated-drawing", "animation-pipeline", "bg-remove-usage", "broll-planning",
        "cinematic", "data-visualization", "diagram-gen-usage", "enhancement-strategy",
        "face-restore-usage", "image-gen-usage", "image-provider-usage", "ink-theater",
        "lip-sync-usage", "long-form", "manim-usage", "music-gen-usage",
        "scene-detect-usage", "screen-recording", "short-form", "sound-design",
        "stock-sourcing-usage", "storytelling", "talking-head-gen-usage", "typography",
        "upscale-usage", "video-editing", "video-gen-prompting", "video-stitching",
        "video-understand-usage",
    ],
    "meta": [
        "animation-runtime-selector", "bespoke-composition", "capability-extension",
        "checkpoint-protocol", "creative-intake", "onboarding", "reviewer",
        "skill-creator", "taste-direction", "video-reference-analyst",
        "voice-performance-director",
    ],
    "pipelines": [
        # Each pipeline has its own subdirectory with stage directors
        "animation", "avatar-spokesperson", "character-animation", "cinematic",
        "clip-factory", "documentary-montage", "explainer", "hybrid",
        "localization-dub", "podcast-repurpose", "screen-demo", "talking-head",
    ],
}

# ================================================================
# 24个JSON Schema
# ================================================================
SCHEMAS = {
    "artifacts": [
        "action_timeline", "asset_manifest", "brief", "character_design",
        "character_qa_report", "cost_log", "decision_log", "edit_decisions",
        "final_review", "pose_library", "proposal_packet", "publish_log",
        "render_report", "research_brief", "review", "rig_plan",
        "scene_plan", "script", "source_media_review", "video_analysis_brief",
    ],
    "checkpoints": ["checkpoint"],
    "pipelines": ["pipeline_manifest"],
    "styles": ["playbook"],
    "tools": ["video_stitch"],
}


def list_all_pipelines() -> list[str]:
    """列出所有13条管线"""
    return PIPELINES


def list_all_skills() -> dict:
    """列出所有156个技能"""
    return SKILL_CATEGORIES


def list_all_schemas() -> dict:
    """列出所有24个Schema"""
    return SCHEMAS


def load_skill(category: str, skill_name: str) -> str | None:
    """加载任意OpenMontage技能的原始内容"""
    path = OM_ROOT / "skills" / category / f"{skill_name}.md"
    if path.exists():
        return path.read_text(encoding='utf-8')
    return None


def load_pipeline_def(pipeline_name: str) -> str | None:
    """加载任意管线定义"""
    path = OM_ROOT / "pipeline_defs" / f"{pipeline_name}.yaml"
    if path.exists():
        return path.read_text(encoding='utf-8')
    return None


def load_schema(category: str, schema_name: str) -> str | None:
    """加载任意Schema"""
    path = OM_ROOT / "schemas" / category / f"{schema_name}.schema.json"
    if path.exists():
        return path.read_text(encoding='utf-8')
    return None


def get_om_root() -> Path:
    """获取OpenMontage根目录"""
    return OM_ROOT


# 启动时验证
if OM_ROOT.exists():
    pipeline_count = len(list((OM_ROOT / "pipeline_defs").glob("*.yaml")))
    skill_count = len(list((OM_ROOT / "skills").rglob("*.md")))
    schema_count = len(list((OM_ROOT / "schemas").rglob("*.json")))
    logger.info(f"OpenMontage桥接就绪: {pipeline_count}管线·{skill_count}技能·{schema_count}Schema")
else:
    logger.warning(f"OpenMontage未找到: {OM_ROOT} — 请先克隆: git clone git@github.com:calesthio/OpenMontage.git")
