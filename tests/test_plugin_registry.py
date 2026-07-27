"""plugin_registry.py 测试 — 可插拔架构"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestPluginRegistry:
    def test_categories_exist(self):
        from clip_agent.plugin_registry import PLUGINS
        assert "tts" in PLUGINS
        assert "image_gen" in PLUGINS
        assert "subtitle" in PLUGINS
        assert "render" in PLUGINS

    def test_get_plugin(self):
        from clip_agent.plugin_registry import get_plugin
        p = get_plugin("tts")
        assert p is not None
        assert p.category == "tts"

    def test_get_plugin_by_engine(self):
        from clip_agent.plugin_registry import get_plugin
        p = get_plugin("render", "ffmpeg")
        assert p is not None
        assert p.engine == "ffmpeg"

    def test_register_new(self):
        from clip_agent.plugin_registry import register, get_plugin, PLUGINS
        register("tts", "TestTTS", "test_engine", True, "测试")
        p = get_plugin("tts", "test_engine")
        assert p is not None
        assert p.name == "TestTTS"

class TestPlugin:
    def test_fields(self):
        from clip_agent.plugin_registry import Plugin
        p = Plugin("测试", "tts", "test", True, "desc", {"key": "val"})
        assert p.name == "测试"
        assert p.available is True
        assert p.config == {"key": "val"}
