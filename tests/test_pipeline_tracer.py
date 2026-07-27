"""pipeline_tracer.py 测试"""
import sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestPipelineTrace:
    def test_basic_flow(self):
        from clip_agent.pipeline_tracer import PipelineTrace
        trace = PipelineTrace("test-job-001")
        trace.stage("parse", "input", "output", 100, True)
        trace.stage("direct", "input2", "output2", 50, False)
        assert len(trace.stages) == 2
        assert trace.stages[0]["success"] is True
        assert trace.stages[1]["success"] is False

    def test_summary(self):
        from clip_agent.pipeline_tracer import PipelineTrace
        trace = PipelineTrace("test-002")
        trace.stage("semantic", "", "deepseek", 200, True)
        summary = trace.summary()
        assert "test-002" in summary
        assert "semantic" in summary
        assert "deepseek" in summary

    def test_save(self):
        from clip_agent.pipeline_tracer import PipelineTrace
        trace = PipelineTrace("test-003")
        trace.stage("render", "", "done", 50, True)
        path = trace.save()
        assert os.path.exists(path)
        # Cleanup
        os.remove(path)
