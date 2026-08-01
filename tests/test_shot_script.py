"""shot契约单测"""
from src.clip_agent.shot_script import (
    ShotScript, parse_shot_script, shots_to_sentences, shot_effects, _est_duration,
)

GW_SHOTS = [
    {"start_sec": 0, "end_sec": 3, "shot_type": "近景", "camera_move": "推镜",
     "script_text": "68一份!", "action": "手指镜头", "emotion": "冲击",
     "duration_ms": 3000, "transition": "cut", "overlay_text": ""},
    {"start_sec": 3, "end_sec": 8, "shot_type": "特写", "camera_move": "固定",
     "script_text": "凌晨四点挑的活虾", "action": "展示虾", "emotion": "信任",
     "duration_ms": 5000, "transition": "dissolve", "overlay_text": "只只满黄"},
]


def test_parse_gateway_format():
    ss = parse_shot_script("68一份! 凌晨四点挑的活虾", "团购售卖", GW_SHOTS)
    assert ss.source == "shot_json"
    assert len(ss.shots) == 2
    s0 = ss.shots[0]
    assert s0.duration_sec == 3.0 and s0.shot_type == "近景" and s0.emotion == "冲击"
    assert ss.shots[1].overlay_text == "只只满黄"


def test_fallback_without_shot_json():
    ss = parse_shot_script("68块十只活虾。左下角囤券。", "团购售卖")
    assert ss.source == "text_fallback"
    assert len(ss.shots) == 2
    assert ss.shots[0].duration_sec > 0


def test_duration_fallback_to_estimate():
    sj = [{"script_text": "今天全场五折", "duration_ms": 0, "start_sec": 0, "end_sec": 0}]
    ss = parse_shot_script("今天全场五折", "团购售卖", sj)
    assert ss.shots[0].duration_sec == _est_duration("今天全场五折")


def test_empty_shot_json_falls_back():
    ss = parse_shot_script("只有文本。没有分镜。", "老板IP", [])
    assert ss.source == "text_fallback"


def test_shots_to_sentences_contract():
    ss = parse_shot_script("68一份! 凌晨四点挑的活虾", "团购售卖", GW_SHOTS)
    sents = shots_to_sentences(ss)
    assert len(sents) == 2
    assert sents[0].index == 1 and sents[0].text == "68一份!"
    assert sents[0].duration_sec == 3.0 and sents[0].is_broll is False


def test_shot_effects_mapping():
    ss = parse_shot_script("x", "团购售卖", GW_SHOTS)
    fx = shot_effects(ss)
    assert fx[1]["shader"] == "bleach_bypass"   # 冲击
    assert fx[1].get("xfade") is None            # cut不进xfade
    assert fx[1]["text_size"] == 64              # 近景
    assert fx[2]["shader"] == "bright_grade"     # 信任
    assert fx[2]["xfade"] == "dissolve"
    assert fx[2]["overlay_text"] == "只只满黄"
    assert fx[2]["text_size"] == 72              # 特写


def test_est_duration():
    assert _est_duration("一" * 45) == 10.0
    assert _est_duration("短") == 1.5
