"""artifact_detector 冻结检测单测"""
from src.clip_agent.artifact_detector import _freeze_runs


def test_freeze_detected():
    """2fps下3个连续静止差分(帧2-5冻结=1.0~3.0s)→检出"""
    diffs = [5.0, 5.0, 0.1, 0.1, 0.1, 5.0]
    runs = _freeze_runs(diffs, fps=2.0, min_freeze_s=1.5)
    assert runs == [{"start": 1.0, "end": 3.0}]


def test_short_still_not_freeze():
    """静止不足1.5s(正常停顿)→不报"""
    diffs = [5.0, 0.1, 0.1, 5.0, 5.0]
    assert _freeze_runs(diffs, fps=2.0, min_freeze_s=1.5) == []


def test_freeze_at_end():
    """冻结延续到片尾→检出"""
    diffs = [5.0, 0.1, 0.1, 0.1]
    runs = _freeze_runs(diffs, fps=2.0, min_freeze_s=1.5)
    assert runs == [{"start": 0.5, "end": 2.0}]


def test_no_freeze_all_motion():
    diffs = [3.0, 4.0, 2.5, 6.0]
    assert _freeze_runs(diffs, fps=2.0) == []


def test_multiple_freeze_runs():
    diffs = [0.1, 0.1, 0.1, 5.0, 0.1, 0.1, 0.1]
    runs = _freeze_runs(diffs, fps=2.0, min_freeze_s=1.5)
    assert len(runs) == 2


def test_black_gap_detected():
    """全屏黑0.5s+(2fps下≥1帧)→black_gap(v3黑屏段场景)"""
    from src.clip_agent.artifact_detector import _black_gaps
    brightness = [80.0, 80.0, 2.0, 1.0, 80.0, 80.0]
    runs = _black_gaps(brightness, fps=2.0, min_s=0.5)
    assert runs == [{"type": "black_gap", "start": 1.0, "end": 2.0}]


def test_brief_fade_not_black_gap():
    """短暂暗帧(<0.5s·正常转场)→不报(用4fps使最小帧数>1)"""
    from src.clip_agent.artifact_detector import _black_gaps
    brightness = [80.0, 3.0, 80.0, 80.0]
    assert _black_gaps(brightness, fps=4.0, min_s=0.5) == []


def test_normal_content_no_black_gap():
    from src.clip_agent.artifact_detector import _black_gaps
    assert _black_gaps([60.0, 45.0, 70.0, 30.0], fps=2.0) == []
