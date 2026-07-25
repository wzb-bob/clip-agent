"""
兼容导入层 · 统一处理独立项目与父项目后端差异

所有外部 app.services.* 依赖通过此模块导入,
独立运行时提供 None fallback + 错误提示,
集成到父项目时正常工作。
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def _try_import(module_path: str, name: str):
    """尝试从 app.services 导入, 失败返回 None"""
    try:
        mod = __import__(module_path, fromlist=[name])
        return getattr(mod, name)
    except ImportError:
        logger.debug("独立模式: %s.%s 不可用", module_path, name)
        return None


# ── 父项目外部依赖 ──
MaterialAnalyzer = _try_import("app.services.material_analyzer", "MaterialAnalyzer")
run_full_edit = _try_import("app.services.edit_orchestrator", "run_full_edit")
chat_via_gateway = _try_import("app.services.gateway_client", "chat_via_gateway")
chat_vision = _try_import("app.services.gateway_client", "chat_vision")
chat_video = _try_import("app.services.gateway_client", "chat_video")
get_model_name = _try_import("app.services.model_config", "get_model_name")
recommend_bgm = _try_import("app.services.bgm_library", "recommend_bgm")
get_video_editor = _try_import("app.services.video_editor", "get_video_editor")
ShotSplitter = _try_import("app.services.shot_splitter", "ShotSplitter")
SubtitleGenerator = _try_import("app.services.subtitle_generator", "SubtitleGenerator")
create_jianying_draft = _try_import("app.services.jianying_draft", "create_jianying_draft")
JianYingDraftGenerator = _try_import("app.services.jianying_draft", "JianYingDraftGenerator")
DouyinPublisher = _try_import("app.services.douyin_publisher", "DouyinPublisher")
ChannelsPublisher = _try_import("app.services.channels_publisher", "ChannelsPublisher")
KuaishouPublisher = _try_import("app.services.kuaishou_publisher", "KuaishouPublisher")
SHOT_TYPES = _try_import("app.services.shot_director", "SHOT_TYPES")
CAMERA_MOVEMENTS = _try_import("app.services.shot_director", "CAMERA_MOVEMENTS")
COMPOSITIONS = _try_import("app.services.shot_director", "COMPOSITIONS")
EMOTIONAL_TONES = _try_import("app.services.shot_director", "EMOTIONAL_TONES")


def get_material_analyzer():
    """获取 MaterialAnalyzer 实例, 独立模式返回 None"""
    if MaterialAnalyzer:
        return MaterialAnalyzer()
    return None


def get_breath_detector():
    """BreathDetector — 优先本地导入"""
    from .breath_detector import BreathDetector
    return BreathDetector()


def get_kimi_vision_call():
    """Kimi Vision API 调用函数"""
    if chat_vision:
        return chat_vision
    logger.warning("Kimi Vision 不可用 — 请在父项目中运行")
    return None
