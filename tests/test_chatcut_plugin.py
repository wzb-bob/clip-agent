"""chatcut_plugin.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestGetChatcutStatus:
    def test_returns_status(self):
        from clip_agent.chatcut_plugin import get_chatcut_status
        status = get_chatcut_status()
        assert status["name"] == "ChatCut剪辑插件"
        assert status["total_tools"] == 8
        assert status["ported"] == 7

class TestChatcutTools:
    def test_all_tools_listed(self):
        from clip_agent.chatcut_plugin import CHATCUT_TOOLS
        assert len(CHATCUT_TOOLS) == 8
        for name in ["audio_to_subtitle","video_trim","concat_videos",
                     "compile_video_audio","add_subtitle","audio_separate",
                     "add_text","video_super_resolution"]:
            assert name in CHATCUT_TOOLS

class TestRunChatcutWorkflow:
    def test_missing_video(self):
        from clip_agent.chatcut_plugin import run_chatcut_workflow
        result = run_chatcut_workflow("/nonexistent/video.mp4")
        assert result["success"] is False
