"""execution_engine.py 测试 — 6阶段执行管线"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestExecutionJob:
    def test_default_values(self):
        from clip_agent.execution_engine import ExecutionJob
        job = ExecutionJob(
            job_id="test-001",
            script_text="测试脚本内容",
            script_type="老板IP",
            audio_slots={},
            video_slots={},
        )
        assert job.job_id == "test-001"
        assert job.script_text == "测试脚本内容"
        assert job.script_type == "老板IP"
        assert job.status == "pending"
        assert job.progress_pct == 0.0
        assert job.sentences == []
        assert job.errors == []
        assert job.draft_path == ""

    def test_audio_video_slots(self):
        from clip_agent.execution_engine import ExecutionJob
        job = ExecutionJob(
            job_id="test-002",
            script_text="hello",
            script_type="团购售卖",
            audio_slots={0: "/audio/a.mp3"},
            video_slots={0: "/video/a.mp4", 1: "/video/b.mp4"},
        )
        assert 0 in job.audio_slots
        assert 1 in job.video_slots


class TestChangyiExecutionEngine:
    def test_init(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine
        engine = ChangyiExecutionEngine()
        assert engine.jobs == {}

    def test_parse_script_empty_text(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
        engine = ChangyiExecutionEngine()
        job = ExecutionJob(job_id="test", script_text="", script_type="老板IP",
                          audio_slots={}, video_slots={})
        result = engine.parse_script(job)
        assert result.errors

    def test_parse_script_too_short(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
        engine = ChangyiExecutionEngine()
        job = ExecutionJob(job_id="test", script_text="ab", script_type="老板IP",
                          audio_slots={}, video_slots={})
        result = engine.parse_script(job)
        assert result.errors

    def test_parse_script_with_valid_text(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
        engine = ChangyiExecutionEngine()
        job = ExecutionJob(
            job_id="test",
            script_text="大家好，我是做小龙虾的老王。今天给大家看看我们的虾有多新鲜。",
            script_type="老板IP",
            audio_slots={}, video_slots={},
        )
        result = engine.parse_script(job)
        assert result.status in ("parsing", "pending")

    def test_validate_slots_no_slots(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
        engine = ChangyiExecutionEngine()
        job = ExecutionJob(job_id="test", script_text="hello world test",
                          script_type="老板IP", audio_slots={}, video_slots={})
        engine.parse_script(job)
        result = engine.validate_slots(job)
        assert result.status == "enhancing"

    def test_run_quality_gates(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
        engine = ChangyiExecutionEngine()
        job = ExecutionJob(job_id="test", script_text="hello world test string",
                          script_type="老板IP", audio_slots={}, video_slots={})
        engine.parse_script(job)
        engine.validate_slots(job)
        result = engine.run_quality_gates(job)
        assert hasattr(result, 'quality_report')
        assert 'score' in result.quality_report
        assert 'passed' in result.quality_report

    def test_execute_full_pipeline(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
        engine = ChangyiExecutionEngine()
        job = ExecutionJob(
            job_id="test-pipeline",
            script_text="大家好，我是老张。今天给大家看看我们的招牌菜。",
            script_type="老板IP",
            audio_slots={}, video_slots={},
        )
        result = engine.execute(job, stop_on_error=False)
        assert result.status in ("done", "failed")

    def test_execute_with_stop_on_error_empty_script(self):
        from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
        engine = ChangyiExecutionEngine()
        job = ExecutionJob(job_id="test", script_text="", script_type="老板IP",
                          audio_slots={}, video_slots={})
        result = engine.execute(job, stop_on_error=True)
        assert result.errors


class TestQuickExecute:
    def test_returns_execution_job(self):
        from clip_agent.execution_engine import quick_execute
        result = quick_execute(
            script_text="测试脚本内容，这是一个测试。",
            script_type="老板IP",
        )
        from clip_agent.execution_engine import ExecutionJob
        assert isinstance(result, ExecutionJob)
        assert result.script_type == "老板IP"

    def test_with_slots(self):
        from clip_agent.execution_engine import quick_execute
        result = quick_execute(
            script_text="测试脚本内容。",
            script_type="团购售卖",
            audio_slots={0: "/test/audio.mp3"},
            video_slots={0: "/test/video.mp4"},
        )
        assert result.audio_slots == {0: "/test/audio.mp3"}
