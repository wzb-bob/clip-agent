"""breath_detector.py 测试 — 气口检测器数据结构和纯逻辑部分"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestBreathPointDataclass:
    def test_default_values(self):
        from clip_agent.breath_detector import BreathPoint
        bp = BreathPoint(at_sec=1.5, score=0.8)
        assert bp.at_sec == 1.5
        assert bp.score == 0.8
        assert bp.sources == []
        assert bp.confidence == 0.5
        assert bp.duration_ms == 0
        assert bp.label == ""
        assert bp.gap_ms == 0
        assert bp.word_before == ""
        assert bp.word_after == ""

    def test_full_creation(self):
        from clip_agent.breath_detector import BreathPoint
        bp = BreathPoint(
            at_sec=3.2, score=0.95, sources=["word_gap", "silence"],
            confidence=0.8, duration_ms=450, label="句间停顿",
            gap_ms=450, word_before="好的", word_after="那么"
        )
        assert bp.at_sec == 3.2
        assert bp.sources == ["word_gap", "silence"]
        assert bp.confidence == 0.8
        assert bp.label == "句间停顿"


class TestBreathReportDataclass:
    def test_default_values(self):
        from clip_agent.breath_detector import BreathReport
        report = BreathReport()
        assert report.video_path == ""
        assert report.duration_sec == 0.0
        assert report.total_points == 0
        assert report.points == []
        assert report.best_cuts == []
        assert report.good_cuts == []
        assert report.sentence_breaks == []
        assert report.avg_gap_between_words_ms == 0
        assert report.breath_count == 0

    def test_with_data(self):
        from clip_agent.breath_detector import BreathReport, BreathPoint
        points = [BreathPoint(at_sec=1.0, score=0.9), BreathPoint(at_sec=2.0, score=0.5)]
        report = BreathReport(
            video_path="/test.mp4", duration_sec=30.0, total_points=2,
            points=points, best_cuts=[points[0]], good_cuts=points,
            avg_gap_between_words_ms=250, speech_rate_cps=3.5
        )
        assert report.video_path == "/test.mp4"
        assert len(report.points) == 2
        assert len(report.best_cuts) == 1
        assert report.speech_rate_cps == 3.5


class TestBreathDetectorConstants:
    def test_class_constants(self):
        from clip_agent.breath_detector import BreathDetector
        assert BreathDetector.SILENCE_THRESH_DB == -30
        assert BreathDetector.MIN_SILENCE_MS == 200
        assert BreathDetector.MIN_SENTENCE_GAP_MS == 400
        assert BreathDetector.MIN_WORD_GAP_MS == 100
        # Weights should sum to 1.0
        total = (BreathDetector.WEIGHT_SILENCE + BreathDetector.WEIGHT_WORD_GAP +
                 BreathDetector.WEIGHT_SHOT_BOUNDARY + BreathDetector.WEIGHT_MOTION_LOW +
                 BreathDetector.WEIGHT_BREATH)
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"

    def test_init_creates_detector(self):
        from clip_agent.breath_detector import BreathDetector
        detector = BreathDetector()
        assert detector is not None


class TestGetOptimalBrollPoints:
    def test_returns_empty_when_no_points(self):
        from clip_agent.breath_detector import BreathDetector, BreathReport
        report = BreathReport()
        detector = BreathDetector()
        result = detector.get_optimal_broll_points(report, count=3)
        assert result == []

    def test_selects_highest_scored_with_min_gap(self):
        from clip_agent.breath_detector import BreathDetector, BreathReport, BreathPoint
        detector = BreathDetector()
        report = BreathReport(
            good_cuts=[
                BreathPoint(at_sec=2.0, score=0.9),
                BreathPoint(at_sec=2.3, score=0.85),  # too close to 2.0
                BreathPoint(at_sec=5.0, score=0.7),
                BreathPoint(at_sec=8.0, score=0.6),
            ]
        )
        result = detector.get_optimal_broll_points(report, count=5, min_gap_sec=3.0)
        # 2.3 should be skipped (too close to 2.0)
        assert len(result) <= 3  # max 3 given gap constraint
        # Points should be sorted by time
        at_times = [p.at_sec for p in result]
        assert at_times == sorted(at_times)

    def test_falls_back_to_all_points_when_no_good_cuts(self):
        from clip_agent.breath_detector import BreathDetector, BreathReport, BreathPoint
        detector = BreathDetector()
        report = BreathReport(
            points=[
                BreathPoint(at_sec=1.0, score=0.5),
                BreathPoint(at_sec=2.0, score=0.4),
                BreathPoint(at_sec=3.0, score=0.3),
            ]
        )
        result = detector.get_optimal_broll_points(report, count=2, prefer_sentence_breaks=False)
        assert len(result) >= 1

    def test_prefer_sentence_breaks_flag(self):
        from clip_agent.breath_detector import BreathDetector, BreathReport, BreathPoint
        detector = BreathDetector()
        report = BreathReport(
            sentence_breaks=[BreathPoint(at_sec=3.0, score=0.7)],
            good_cuts=[BreathPoint(at_sec=1.0, score=0.9)],
        )
        # With prefer=True, should use sentence_breaks
        result = detector.get_optimal_broll_points(report, count=1, prefer_sentence_breaks=True)
        assert len(result) == 1
        assert result[0].at_sec == 3.0

    def test_respects_min_gap(self):
        from clip_agent.breath_detector import BreathDetector, BreathReport, BreathPoint
        detector = BreathDetector()
        report = BreathReport(
            good_cuts=[
                BreathPoint(at_sec=1.0, score=0.9),
                BreathPoint(at_sec=1.1, score=0.8),
                BreathPoint(at_sec=1.2, score=0.7),
            ],
            sentence_breaks=[  # need these as fallback when prefer_sentence_breaks=True
                BreathPoint(at_sec=1.0, score=0.9),
            ]
        )
        result = detector.get_optimal_broll_points(report, count=5, min_gap_sec=3.0)
        # With min_gap=3.0, only one point can be selected from such a tight cluster
        assert len(result) == 1
