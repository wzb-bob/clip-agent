"""自主引擎7阶段质量门禁单测(每个gate好/坏case)"""
import os
import pytest
from src.clip_agent.openmontage_pipeline import (
    _gate_material_integrity, _gate_audio_quality, _gate_subtitle,
    _gate_rhythm, _gate_broll, _gate_brand_safety, _gate_export_review,
    run_auto_quality_gates,
)


def _pseudo(durs=(2.0, 3.0, 2.5)):
    sents, t = [], 0.0
    for i, d in enumerate(durs, 1):
        sents.append({"index": i, "text": f"句{i}", "start_sec": t, "end_sec": t + d,
                      "duration_sec": d})
        t += d
    return {"sentences": sents, "text": "。 ".join(s["text"] for s in sents)}


# ① 素材完整性
def test_material_integrity_bad():
    r = _gate_material_integrity({"video_path": "D:/no_such_file.mp4"})
    assert not r["passed"] and r["issues"]


# ② 音频质量
def test_audio_quality_good():
    r = _gate_audio_quality({"pseudo_script": _pseudo(), "expected_duration": 7.5})
    assert r["passed"]


def test_audio_quality_empty():
    r = _gate_audio_quality({"pseudo_script": {"sentences": []}})
    assert not r["passed"]


def test_audio_quality_big_gap():
    p = _pseudo()
    p["sentences"][1]["start_sec"] += 15  # 句间断裂15s
    p["sentences"][1]["end_sec"] += 15
    p["sentences"][2]["start_sec"] += 15
    p["sentences"][2]["end_sec"] += 15
    r = _gate_audio_quality({"pseudo_script": p})
    assert not r["passed"] and any("断裂" in i for i in r["issues"])


# ③ 字幕准确性
def test_subtitle_overlap():
    p = _pseudo()
    p["sentences"][0]["end_sec"] += 1.0  # 与下句重叠
    r = _gate_subtitle({"pseudo_script": p})
    assert not r["passed"]


def test_subtitle_too_long():
    p = _pseudo()
    p["sentences"][1]["text"] = "长" * 25
    r = _gate_subtitle({"pseudo_script": p})
    assert not r["passed"] and any("20" in i for i in r["issues"])


# ④ 剪辑节奏
def test_rhythm_good():
    assert _gate_rhythm({"pseudo_script": _pseudo()})["passed"]


def test_rhythm_too_long_segment():
    r = _gate_rhythm({"pseudo_script": _pseudo((2.0, 10.0, 2.0))})
    assert not r["passed"] and any("超长" in i for i in r["issues"])


# ⑤ B-roll匹配
def test_broll_missing_file():
    r = _gate_broll({"broll_videos": ["D:/no_broll.mp4"]})
    assert not r["passed"]


def test_broll_none_ok():
    assert _gate_broll({"broll_videos": []})["passed"]


# ⑥ 品牌安全
def test_brand_safety_no_output():
    """无成片→无法检·算过(成片验收会拦)"""
    r = _gate_brand_safety({"output_path": "D:/no_out.mp4"})
    assert r["passed"]


# ⑦ 成片验收
def test_export_review_missing():
    r = _gate_export_review({"output_path": "D:/no_out.mp4", "expected_duration": 10})
    assert not r["passed"]


def test_export_review_real_file(tmp_path):
    f = tmp_path / "out.mp4"
    f.write_bytes(b"x" * 200_000)
    r = _gate_export_review({"output_path": str(f), "expected_duration": 0})
    assert r["passed"]


# 汇总
def test_run_all_gates_shape():
    r = run_auto_quality_gates({"video_path": "D:/no.mp4", "pseudo_script": _pseudo(),
                                "output_path": "D:/no.mp4", "expected_duration": 7.5,
                                "broll_videos": []})
    assert len(r["gates"]) == 7
    assert not r["passed_all"]  # 素材/成片不存在必挂
    assert 0 <= r["score"] <= 100
