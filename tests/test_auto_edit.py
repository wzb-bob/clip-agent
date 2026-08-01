"""auto_edit 段决策单测(不跑真渲染)"""
from src.clip_agent.auto_pipeline import _insert_broll, build_pseudo_script


def _s(i, dur=3.0):
    return {"index": i, "text": f"句{i}", "start_sec": (i-1)*3.0, "end_sec": (i-1)*3.0+dur,
            "duration_sec": dur, "emotion": "平实", "intensity": 3}


def test_insert_broll_midpoint(monkeypatch):
    """B-roll插在中点·时长=min(3,有效内容)"""
    monkeypatch.setattr("src.clip_agent.chatcut_vfx._content_duration", lambda p: 5.0)
    out = _insert_broll([_s(1), _s(2), _s(3), _s(4)], ["broll.mp4"])
    assert len(out) == 5
    assert out[2]["is_broll"] is True
    assert out[2]["duration_sec"] == 3.0
    assert out[2]["material_file"] == "broll.mp4"


def test_insert_broll_too_short_skipped(monkeypatch):
    """B-roll有效内容<1s→不插"""
    monkeypatch.setattr("src.clip_agent.chatcut_vfx._content_duration", lambda p: 0.5)
    out = _insert_broll([_s(1), _s(2)], ["broll.mp4"])
    assert len(out) == 2


def test_insert_broll_none():
    assert len(_insert_broll([_s(1)], [])) == 1


def test_pseudo_to_sentence_fields():
    """伪脚本句字段能直接驱动auto_edit(字段完整性)"""
    ps = build_pseudo_script({"transcript": "68块", "segments": [
        {"text": "68块", "start": 0.0, "end": 2.0, "words": []}], "moments": []})
    s = ps["sentences"][0]
    for field in ("index", "text", "duration_sec", "emotion", "intensity"):
        assert field in s
