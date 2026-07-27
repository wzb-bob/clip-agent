"""report_generator.py 测试"""
import sys, tempfile, os
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestGenerateHTMLReport:
    def test_generates_file(self):
        from clip_agent.report_generator import generate_html_report
        # Mock a job object
        job = MagicMock()
        job.sentences = []
        job.enhancement_report = {"semantic": {}, "video": {}, "director_plan": {}, "aesthetic": {}}
        job.status = "done"

        with tempfile.TemporaryDirectory() as tmp:
            path = generate_html_report(job, tmp)
            assert os.path.exists(path)
            content = Path(path).read_text(encoding="utf-8")
            assert "出片报告" in content
            assert "<html" in content.lower()

    def test_with_segments(self):
        from clip_agent.report_generator import generate_html_report
        seg = MagicMock()
        seg.is_broll = False
        seg.start_sec = 0.0
        seg.duration_sec = 2.5
        seg.required_shot = "CU"
        seg.text = "68块！"
        seg.text_overlay = "68块!"

        job = MagicMock()
        job.sentences = [seg]
        job.enhancement_report = {
            "semantic": {"engine": "deepseek", "emotional_arc": "冲击→展示"},
            "video": {"engine": "kimi_k2.6"},
            "director_plan": {"editing_style": "快节奏", "color_grade": "vivid", "bgm": "电子"},
            "aesthetic": {"score": 95, "error_count": 0, "warning_count": 0, "info_count": 0},
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = generate_html_report(job, tmp)
            assert os.path.exists(path)
            content = Path(path).read_text(encoding="utf-8")
            assert "68块!" in content
            assert "deepseek" in content
