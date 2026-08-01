"""脚本↔口播时长匹配 单测"""
from src.clip_agent.chatcut_plugin import estimate_reading_seconds, script_audio_verdict


def test_estimate_reading_seconds():
    """45字÷4.5字/s=10s·标点不计"""
    assert estimate_reading_seconds("一" * 45) == 10.0
    assert estimate_reading_seconds("一" * 20 + "，。！") == round(20 / 4.5, 1)


def test_verdict_match():
    r = script_audio_verdict(9.0, 10.0)
    assert r["verdict"] == "匹配"


def test_verdict_too_long():
    """32s脚本配8s口播(实测场景)→脚本过长+可执行hint"""
    r = script_audio_verdict(32.0, 8.0)
    assert r["verdict"] == "脚本过长"
    assert r["ratio"] == 4.0
    assert "≤36字" in r["hint"]


def test_verdict_too_short():
    r = script_audio_verdict(4.0, 10.0)
    assert r["verdict"] == "脚本过短"


def test_verdict_no_audio():
    assert script_audio_verdict(10.0, 0)["verdict"] == "未知"
