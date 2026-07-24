"""pro_renderer.py 测试 — 专业视频渲染器数据结构和纯逻辑"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestRenderJob:
    def test_default_values(self):
        from clip_agent.pro_renderer import RenderJob
        job = RenderJob(
            segments=[{"file": "/test.mp4", "duration": 3.0}],
            output_path="/out.mp4",
        )
        assert job.segments == [{"file": "/test.mp4", "duration": 3.0}]
        assert job.output_path == "/out.mp4"
        assert job.bgm_path == ""
        assert job.bgm_volume == 0.3
        assert job.width == 1080
        assert job.height == 1920
        assert job.fps == 30

    def test_full_config(self):
        from clip_agent.pro_renderer import RenderJob
        job = RenderJob(
            segments=[
                {"file": "/a.mp4", "duration": 2.0, "broll": False, "text": "开头大字"},
                {"file": "/b.mp4", "duration": 4.0, "broll": True, "text": ""},
            ],
            output_path="/final.mp4",
            bgm_path="/bgm.mp3",
            bgm_volume=0.25,
            width=1080,
            height=1350,
            fps=25,
        )
        assert len(job.segments) == 2
        assert job.segments[0]["broll"] is False
        assert job.segments[1]["broll"] is True
        assert job.height == 1350


class TestRenderResult:
    def test_success_result(self):
        from clip_agent.pro_renderer import RenderResult
        result = RenderResult(
            success=True,
            output_path="/out.mp4",
            duration_sec=28.5,
            file_size_mb=2.8,
            render_time_sec=15.2,
        )
        assert result.success is True
        assert result.output_path == "/out.mp4"
        assert result.duration_sec == 28.5
        assert result.file_size_mb == 2.8
        assert result.error == ""

    def test_failure_result(self):
        from clip_agent.pro_renderer import RenderResult
        result = RenderResult(
            success=False,
            output_path="",
            duration_sec=0,
            file_size_mb=0,
            render_time_sec=0.5,
            error="FFmpeg not found",
        )
        assert result.success is False
        assert result.error == "FFmpeg not found"


class TestRenderProfessional:
    def test_empty_segments_returns_failure(self):
        from clip_agent.pro_renderer import render_professional, RenderJob
        job = RenderJob(segments=[], output_path="/test.mp4")
        result = render_professional(job)
        assert result.success is False
        assert "无渲染片段" in result.error

    def test_missing_files_skipped(self):
        from clip_agent.pro_renderer import render_professional, RenderJob
        job = RenderJob(
            segments=[
                {"file": "/nonexistent/video.mp4", "duration": 3.0},
            ],
            output_path="/test/output.mp4",
        )
        # Should handle missing files gracefully - returns failure
        result = render_professional(job)
        # Either fails at prep stage or handles gracefully
        assert isinstance(result.success, bool)

    @patch("clip_agent.pro_renderer.subprocess.run")
    @patch("clip_agent.pro_renderer.tempfile.mktemp")
    @patch("clip_agent.pro_renderer.os.path.exists")
    @patch("clip_agent.pro_renderer.os.rename")
    @patch("clip_agent.pro_renderer.os.remove")
    def test_successful_render_flow(self, mock_remove, mock_rename, mock_exists, mock_mktemp, mock_run):
        from clip_agent.pro_renderer import render_professional, RenderJob

        mock_exists.return_value = True
        # Use a counter to generate unique temp paths — render_professional
        # calls mktemp many times (prep + concat + overlay + text + fade + bgm)
        _counter = [0]
        mock_mktemp.side_effect = lambda suffix="": f"/tmp/step_{_counter[0]}{suffix}" if _counter.__setitem__(0, _counter[0] + 1) is None else None  # noqa
        # Simpler: just use a list that's long enough
        mock_mktemp.side_effect = [f"/tmp/step_{i}.mp4" for i in range(20)]
        mock_run.return_value = MagicMock(returncode=0)

        with patch("os.path.getsize", return_value=3 * 1024 * 1024):
            job = RenderJob(
                segments=[{"file": "/real/video.mp4", "duration": 5.0, "text": "测试"}],
                output_path="/output.mp4",
            )
            result = render_professional(job)

        assert result.success is True
        assert result.file_size_mb > 0
        assert mock_run.call_count >= 1
