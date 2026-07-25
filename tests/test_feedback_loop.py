"""feedback_loop.py 测试 — 闭环反馈系统"""
import json, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFeedbackReport:
    def test_default_values(self):
        from clip_agent.feedback_loop import FeedbackReport
        r = FeedbackReport(feedback_id="fb_001", timestamp="2026-07-24T12:00:00")
        assert r.feedback_id == "fb_001"
        assert r.script_type == "团购售卖"
        assert r.shot_count_planned == 0
        assert r.clip_quality_score == 0.0
        assert r.optimization_hints == []

    def test_full_report(self):
        from clip_agent.feedback_loop import FeedbackReport
        r = FeedbackReport(
            feedback_id="fb_002", timestamp="2026-07-24T12:00:00",
            script_type="老板IP", shot_coverage_pct=85.0,
            clip_quality_score=7.5, clip_success=True,
            missing_material_types=["product_closeup"],
            optimization_hints=[{"target": "shotlist", "severity": "high", "hint": "减少镜头类型"}],
        )
        assert r.shot_coverage_pct == 85.0
        assert r.clip_quality_score == 7.5
        assert len(r.optimization_hints) == 1
        assert "product_closeup" in r.missing_material_types


class TestFeedbackStore:
    def test_save_and_load(self):
        from clip_agent.feedback_loop import FeedbackStore, FeedbackReport
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as tf:
            tmp_path = tf.name

        try:
            store = FeedbackStore(file_path=tmp_path)
            report = FeedbackReport(feedback_id="fb_test", timestamp="2026-07-24T12:00:00",
                                   script_type="团购售卖", clip_quality_score=8.5)
            assert store.save(report) is True

            records = store.load_all()
            assert len(records) == 1
            assert records[0]["feedback_id"] == "fb_test"
            assert records[0]["clip_quality_score"] == 8.5
        finally:
            os.unlink(tmp_path)

    def test_get_stats_empty(self):
        from clip_agent.feedback_loop import FeedbackStore
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as tf:
            tmp_path = tf.name
        try:
            store = FeedbackStore(file_path=tmp_path)
            stats = store.get_stats("团购售卖")
            assert stats["count"] == 0
        finally:
            os.unlink(tmp_path)

    def test_get_stats_with_data(self):
        from clip_agent.feedback_loop import FeedbackStore, FeedbackReport
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as tf:
            tmp_path = tf.name
        try:
            store = FeedbackStore(file_path=tmp_path)
            for i in range(3):
                r = FeedbackReport(feedback_id=f"fb_{i}", timestamp="2026-07-24T12:00:00",
                                  script_type="团购售卖", clip_quality_score=6.0 + i,
                                  clip_success=True)
                store.save(r)
            stats = store.get_stats("团购售卖")
            assert stats["count"] == 3
            assert stats["success_rate"] == 100.0
            assert stats["avg_quality_score"] == 7.0
        finally:
            os.unlink(tmp_path)


class TestGenerateFeedback:
    def test_basic_feedback(self):
        from clip_agent.feedback_loop import generate_feedback
        bridge_cfg = {
            "script_type": "老板IP", "script_text": "大家好",
            "shot_map": [{"required_material": "talking_head"}],
            "template_key": "ip_story_beginning",
            "color_grade": "warm", "bgm_genre": "温暖",
            "editing_style": "慢节奏", "hook_type": "price",
        }
        job_result = {
            "success": True, "total_duration": 15.0,
            "quality_score": 8.0, "sentence_count": 3,
            "editing_cuts": 5, "draft_path": "/tmp/draft",
            "sentences": [{"is_broll": False}, {"is_broll": True}],
        }
        report = generate_feedback(bridge_cfg, job_result, {"total": 2, "talking": 1, "broll": 1})
        assert report.feedback_id.startswith("fb_")
        assert report.script_type == "老板IP"
        assert report.clip_success is True
        assert report.clip_quality_score == 8.0
        assert len(report.optimization_hints) > 0

    def test_low_quality_generates_hints(self):
        from clip_agent.feedback_loop import generate_feedback
        bridge_cfg = {
            "script_type": "团购售卖",
            "shot_map": [
                {"required_material": "product_closeup"},
                {"required_material": "product_closeup"},
            ],
            "template_key": "sale_price_first",
            "color_grade": "vivid", "bgm_genre": "电子",
            "editing_style": "快节奏", "hook_type": "price",
        }
        job_result = {
            "success": True, "total_duration": 10.0,
            "quality_score": 3.0, "sentence_count": 2,
            "editing_cuts": 2, "draft_path": "/tmp/draft",
            "sentences": [{"is_broll": False}],
        }
        report = generate_feedback(bridge_cfg, job_result, {"total": 1, "talking": 0, "broll": 1})
        # Low quality + missing product → should have multiple high-severity hints
        high_hints = [h for h in report.optimization_hints if h["severity"] == "high"]
        assert len(high_hints) >= 1


class TestGetScriptOptimizationHints:
    def test_no_data(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as tf:
            tmp_path = tf.name
        try:
            with patch("clip_agent.feedback_loop.FEEDBACK_FILE", Path(tmp_path)):
                from clip_agent.feedback_loop import get_script_optimization_hints
                result = get_script_optimization_hints("老板IP")
                assert result["has_data"] is False
        finally:
            os.unlink(tmp_path)
