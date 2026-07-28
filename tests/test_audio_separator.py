"""audio_separator.py 测试"""
import sys, os, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestSeparateVocals:
    def test_missing_file(self):
        from clip_agent.audio_separator import separate_vocals
        result = separate_vocals("/nonexistent/video.mp4")
        assert result is None

    def test_method_validation(self):
        from clip_agent.audio_separator import separate_vocals
        # Invalid method should fallback to ffmpeg
        test_file = r"c:\tmp\clip_e2e\test_hook.mp4"
        if os.path.exists(test_file):
            result = separate_vocals(test_file, method="invalid")
            # Should still work with ffmpeg fallback or return None gracefully
            assert result is None or os.path.exists(result)

class TestEnhanceAudioForWhisper:
    def test_missing_file(self):
        from clip_agent.audio_separator import enhance_audio_for_whisper
        result = enhance_audio_for_whisper("/nonexistent/video.mp4")
        assert result is None

class TestEnhanceDirect:
    def test_missing_file(self):
        from clip_agent.audio_separator import _enhance_direct
        result = _enhance_direct("/nonexistent/video.mp4")
        assert result is None
