"""
VFX 渲染引擎 · 从 FlowVid (d:/vfx-studio) 搬运到 Python

56 GLSL着色器 + 节拍触发引擎 + 效果链渲染
纯Python实现·零Flutter依赖·可独立运行或集成到ChatCut
"""
from .shader_catalog import ShaderCatalog, SHADER_CATEGORIES, get_shader, list_shaders
from .glsl_renderer import GlslRenderer, apply_shader_to_video, apply_effect_chain
from .beat_trigger import BeatTriggerEngine, BeatTrigger, BeatTriggerType, BeatTriggerPresets
