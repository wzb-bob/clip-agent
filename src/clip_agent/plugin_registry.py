"""
可插拔架构 v1 · ComfyKit模式 · 能力可替换

Pixelle-Video的ComfyKit启发: 每个能力(TTS/生图/字幕)是独立插件
改能力=换插件·不改代码。全模块共享同一注册表。
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    """一个可替换的能力插件"""
    name: str
    category: str          # tts/image_gen/subtitle/render
    engine: str            # indextts/edgetts/dashscope/flux/custom
    available: bool
    description: str
    config: dict = field(default_factory=dict)


# 全局插件注册表
PLUGINS: dict[str, list[Plugin]] = {
    "tts": [],
    "image_gen": [],
    "subtitle": [],
    "render": [],
}


def register(category: str, name: str, engine: str, available: bool,
             description: str = "", config: dict = None):
    """注册一个插件"""
    plugin = Plugin(
        name=name, category=category, engine=engine,
        available=available, description=description,
        config=config or {},
    )
    if category not in PLUGINS:
        PLUGINS[category] = []
    PLUGINS[category].append(plugin)
    return plugin


def get_plugin(category: str, engine: str = "") -> Plugin | None:
    """获取指定目录的最佳可用插件"""
    plugins = PLUGINS.get(category, [])
    if engine:
        for p in plugins:
            if p.engine == engine and p.available:
                return p
    # 返回第一个可用的
    for p in plugins:
        if p.available:
            return p
    return None


# ══════════════════════════════════════════════════════════
# 注册所有可用插件
# ══════════════════════════════════════════════════════════

# TTS engines
try:
    import edge_tts
    register("tts", "EdgeTTS", "edgetts", True, "微软Edge免费TTS·多语言·无需Key")
except ImportError:
    register("tts", "EdgeTTS", "edgetts", False, "需安装: pip install edge-tts")

try:
    import indextts
    register("tts", "Index-TTS", "indextts", True, "声音克隆·录30秒→模仿声线")
except ImportError:
    register("tts", "Index-TTS", "indextts", False, "需安装: pip install indextts")

# Image generation engines
dashscope_ok = bool(__import__("os").getenv("DASHSCOPE_API_KEY"))
register("image_gen", "DashScope/WAN", "dashscope", dashscope_ok,
         "阿里云AI生图·文字→画面" if dashscope_ok else "需DASHSCOPE_API_KEY")

register("image_gen", "Placeholder", "placeholder", True,
         "无AI生图·返回文字描述·用户手动拍摄")

# Subtitle engines
register("subtitle", "FFmpeg Drawtext", "ffmpeg", True,
         "逐词动画字幕·打字机效果·黑边描边")

register("subtitle", "HTML Template", "html", False,
         "HTML/CSS模板渲染·高级样式·需headless浏览器")

# Render engines
register("render", "FFmpeg v2", "ffmpeg", True,
         "模糊背景·Lanczos缩放·xfade转场·自适应时长")


def print_plugins():
    """打印所有已注册插件"""
    for category, plugins in PLUGINS.items():
        print(f"[{category}]")
        for p in plugins:
            icon = "✅" if p.available else "❌"
            print(f"  {icon} {p.name:20s} | {p.engine:15s} | {p.description}")
