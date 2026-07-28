"""
扣子双通道管道 v1 · Coze工作流直出MP4

通道1(推荐): 四类素材 → Whisper气口 → JianYing草稿 → 用户精调
通道2(快速): 四类素材 → Whisper气口 → 扣子工作流 → 直接MP4

扣子12工具: audio_to_subtitle, video_trim, concat_videos,
  compile_video_audio, add_subtitle, audio_separate, etc.
"""
from __future__ import annotations
import json, logging, os, tempfile, time
from pathlib import Path

logger = logging.getLogger(__name__)


def get_available_tools() -> list[dict]:
    """返回可用的扣子视频工具列表"""
    return [
        {"name": "audio_to_subtitle", "desc": "语音转字幕·Whisper精准时间戳", "available": True},
        {"name": "video_trim", "desc": "视频裁剪·气口精切", "available": True},
        {"name": "concat_videos", "desc": "视频拼接·内置转场", "available": True},
        {"name": "compile_video_audio", "desc": "视频+音频合成", "available": True},
        {"name": "add_subtitle", "desc": "字幕烧录到视频", "available": True},
        {"name": "audio_separate", "desc": "人声分离·去BGM噪音", "available": False},
        {"name": "add_text", "desc": "文字叠加·价格/CTA", "available": True},
        {"name": "video_super_resolution", "desc": "超分辨率·画质增强", "available": False},
    ]


def run_coze_pipeline(
    script_text: str,
    talking_video: str,
    broll_videos: list[str] = None,
    output_dir: str = "",
) -> dict:
    """
    扣子快速通道: 跳过JianYing草稿·直接出MP4。

    当前状态: Stub — 等待扣子API Key配置。
    可用时调用Coze工作流API, 不可用时降级为JianYing草稿通道。
    """
    coze_key = os.getenv("COZE_API_KEY") or os.getenv("COZE_WORKFLOW_ID")
    if not coze_key:
        logger.info("扣子API未配置·降级JianYing草稿通道")
        return _fallback_to_jianying(script_text, talking_video, broll_videos, output_dir)

    # TODO: 调用扣子工作流API
    # workflow_id = os.getenv("COZE_WORKFLOW_ID")
    # POST https://api.coze.cn/v1/workflow/run
    return {"success": False, "error": "扣子API待对接·请使用JianYing草稿通道", "channel": "coze"}


def _fallback_to_jianying(script_text, talking_video, broll_videos, output_dir) -> dict:
    """降级: 使用JianYing草稿通道"""
    try:
        from .four_category_pipeline import run_four_category_pipeline, CategoryMaterials

        env_videos = [v for v in (broll_videos or []) if "空镜" in v or "环境" in v or "门头" in v]
        prod_videos = [v for v in (broll_videos or []) if "产品" in v or "制作" in v]

        materials = CategoryMaterials(
            talking=[talking_video] if talking_video else [],
            environment=env_videos, product=prod_videos, cta=[],
        )
        timeline = run_four_category_pipeline(script_text, materials, output_dir=output_dir)

        from .jianying_timeline_builder import export_draft_zip
        zip_path = export_draft_zip(timeline.draft_path) if timeline.draft_path else ""

        return {
            "success": True,
            "channel": "jianying",
            "segments": len(timeline.segments),
            "duration": timeline.total_duration,
            "draft_zip": zip_path,
            "srt_path": getattr(timeline, "srt_path", ""),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "channel": "jianying"}


def get_channel_status() -> dict:
    """检查双通道状态"""
    return {
        "channel_1_jianying": {"available": True, "desc": "剪映草稿(推荐)·精调后出片"},
        "channel_2_coze": {
            "available": bool(os.getenv("COZE_API_KEY")),
            "desc": "扣子直出·一键MP4" if os.getenv("COZE_API_KEY") else "需配置COZE_API_KEY",
        },
        "tools": get_available_tools(),
    }
