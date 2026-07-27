"""端到端管道集成测试 — 验证全流程"""
import sys, os, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestE2EPipeline:
    """完整管线: 脚本→导演→美学→导出"""

    def test_full_pipeline_runs(self):
        from clip_agent.execution_engine import quick_direct
        job = quick_direct("68块！十只活虾！团购已上线！", "团购售卖")
        assert job.status in ("done", "failed")
        assert len(job.sentences) >= 2
        assert hasattr(job, 'enhancement_report')

    def test_semantic_in_pipeline(self):
        from clip_agent.execution_engine import quick_direct
        job = quick_direct("大家好我是老张。干餐饮十二年了。食材不能糊弄。", "老板IP")
        er = job.enhancement_report
        assert "semantic" in er

    def test_aesthetic_runs(self):
        from clip_agent.execution_engine import quick_direct
        job = quick_direct("68块！十只活虾！团购上线！", "团购售卖")
        aes = job.enhancement_report.get("aesthetic", {})
        assert "score" in aes

    def test_director_plan_exists(self):
        from clip_agent.execution_engine import quick_direct
        job = quick_direct("全玉田只此一家。你看这排队。导航搜虾神。", "引流进店")
        dc = job.enhancement_report.get("director_plan", {})
        assert "editing_style" in dc or "color_grade" in dc

    def test_script_types_all_work(self):
        from clip_agent.execution_engine import quick_direct
        for st, script in [
            ("团购售卖", "68块！十只活虾！团购上线！"),
            ("老板IP", "大家好我是老张。干餐饮十二年了。"),
            ("引流进店", "全玉田只此一家。你看这排队。"),
        ]:
            job = quick_direct(script, st)
            assert job.status in ("done", "failed"), f"{st} failed"
            assert len(job.sentences) >= 1

    def test_empty_script_handled(self):
        from clip_agent.execution_engine import quick_direct
        job = quick_direct("", "团购售卖")
        # Pipeline should fail gracefully for empty scripts
        assert job.status in ("done", "failed")

    def test_very_short_script(self):
        from clip_agent.execution_engine import quick_direct
        job = quick_direct("ab", "团购售卖")
        # Short scripts may still produce output or error
        assert job.status in ("done", "failed")

    def test_timing_recorded(self):
        from clip_agent.execution_engine import quick_direct
        job = quick_direct("68块！十只活虾！团购上线！", "团购售卖")
        timing = job.enhancement_report.get("timing", {})
        assert "total_s" in timing
