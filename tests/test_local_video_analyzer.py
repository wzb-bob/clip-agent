"""local_video_analyzer.py 测试 — 本地视频分析"""
import sys, os, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestProbeVideo:
    def test_missing_file(self):
        from clip_agent.local_video_analyzer import _probe_video_ffprobe
        result = _probe_video_ffprobe("/nonexistent/video.mp4")
        assert result is None

    def test_valid_video(self):
        """Use our test video from earlier"""
        test_video = r"c:\tmp\clip_test\test_hook.mp4"
        if not os.path.exists(test_video):
            return  # Skip if test files don't exist

        from clip_agent.local_video_analyzer import _probe_video_ffprobe
        result = _probe_video_ffprobe(test_video)
        assert result is not None
        assert result["duration"] > 0
        assert result["width"] == 1080
        assert result["height"] == 1920


class TestAnalyzeVideoLocal:
    def test_missing_file(self):
        from clip_agent.local_video_analyzer import analyze_video_local
        result = analyze_video_local("/nonexistent/video.mp4")
        assert result is None

    def test_basic_info_no_frames(self):
        """Test without frame extraction (faster)"""
        test_video = r"c:\tmp\clip_test\test_hook.mp4"
        if not os.path.exists(test_video):
            return

        from clip_agent.local_video_analyzer import analyze_video_local
        result = analyze_video_local(test_video, extract_frames=False)
        assert result is not None
        assert result.duration_sec > 0
        assert result.width == 1080
        assert result.file_size_mb > 0

    def test_with_frame_extraction(self):
        """Full analysis with OpenCV"""
        test_video = r"c:\tmp\clip_test\test_hook.mp4"
        if not os.path.exists(test_video):
            return

        from clip_agent.local_video_analyzer import analyze_video_local
        result = analyze_video_local(test_video, extract_frames=True, frame_interval=0.5)
        assert result is not None
        # 3 second video at 0.5s interval = ~6 frames
        if result.frames:
            assert len(result.frames) >= 3
            assert result.frames[0].sharpness > 0
            assert result.frames[0].brightness > 0


class TestQuickAnalyze:
    def test_returns_summary(self):
        test_video = r"c:\tmp\clip_test\test_hook.mp4"
        if not os.path.exists(test_video):
            return

        from clip_agent.local_video_analyzer import quick_analyze
        result = quick_analyze(test_video)
        assert "error" not in result
        assert result["resolution"] == "1080x1920"
        assert result["duration_sec"] > 0
        assert "recommendation" in result
        assert result["quality"] in ("good", "medium", "poor")


class TestHueToName:
    def test_colors(self):
        from clip_agent.local_video_analyzer import _hue_to_name
        assert _hue_to_name(0) == "red"
        assert _hue_to_name(30) == "yellow"
        assert _hue_to_name(60) == "green"
        assert _hue_to_name(120) == "blue"


class TestInferVideoType:
    def test_talking_head(self):
        from clip_agent.local_video_analyzer import LocalVideoAnalysis, _infer_video_type
        analysis = LocalVideoAnalysis(
            file_path="", duration_sec=10, width=1080, height=1920, fps=30, codec="h264",
            file_size_mb=1.0, has_talking_head=True, face_time_pct=0.8,
            motion_profile="static",
        )
        _infer_video_type(analysis)
        assert analysis.inferred_type == "talking_head"

    def test_product(self):
        from clip_agent.local_video_analyzer import LocalVideoAnalysis, _infer_video_type
        analysis = LocalVideoAnalysis(
            file_path="", duration_sec=5, width=1080, height=1920, fps=30, codec="h264",
            file_size_mb=1.0, has_talking_head=False, face_time_pct=0,
            scene_count=1, avg_sharpness=600, motion_profile="static",
        )
        _infer_video_type(analysis)
        assert analysis.inferred_type == "product"
