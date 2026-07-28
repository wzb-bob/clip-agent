"""coze_pipeline.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestGetAvailableTools:
    def test_returns_list(self):
        from clip_agent.coze_pipeline import get_available_tools
        tools = get_available_tools()
        assert len(tools) >= 5
        assert any(t["name"] == "audio_to_subtitle" for t in tools)

class TestGetChannelStatus:
    def test_channel_status(self):
        from clip_agent.coze_pipeline import get_channel_status
        status = get_channel_status()
        assert "channel_1_jianying" in status
        assert status["channel_1_jianying"]["available"] is True
        assert "channel_2_coze" in status

class TestFallbackToJianying:
    def test_no_talking_video(self):
        from clip_agent.coze_pipeline import _fallback_to_jianying
        result = _fallback_to_jianying("68块！十只活虾！", "", [], "")
        assert result["channel"] == "jianying"
