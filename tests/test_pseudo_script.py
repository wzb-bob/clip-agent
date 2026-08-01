"""伪脚本生成器单测(合成数据·不跑whisper)"""
from src.clip_agent.auto_pipeline import build_pseudo_script


def _u(segments, moments=None):
    """构造understand_audio风格的dict"""
    return {"transcript": "".join(s["text"] for s in segments),
            "segments": segments, "moments": moments or []}


def _seg(text, start, end, words=None):
    return {"text": text, "start": start, "end": end,
            "confidence": 0.9, "speed_cps": 4.0, "words": words or []}


def test_basic_pseudo_script():
    """两个whisper段→两句·真实时间戳保留"""
    ps = build_pseudo_script(_u([
        _seg("68块十只活虾", 0.0, 2.5),
        _seg("左下角囤券", 3.0, 5.0),
    ]))
    assert ps is not None
    assert len(ps["sentences"]) == 2
    assert ps["sentences"][0]["start_sec"] == 0.0
    assert ps["sentences"][0]["end_sec"] == 2.5
    assert ps["sentences"][1]["duration_sec"] == 2.0
    assert ps["source"] == "whisper_pseudo"
    assert "68块十只活虾" in ps["text"]


def test_empty_transcript_returns_none():
    """无语音内容→诚实失败None"""
    assert build_pseudo_script(_u([])) is None
    assert build_pseudo_script(_u([_seg("  ", 0, 1)])) is None


def test_emotion_from_moments():
    """能量峰值句→冲击·停顿句→悬念·无标注句→平实"""
    ps = build_pseudo_script(_u(
        [_seg("重磅消息", 0.0, 2.0), _seg("你听我说", 3.0, 5.0), _seg("随便看看", 6.0, 8.0)],
        moments=[{"at_sec": 1.0, "type": "emphasis", "energy": 0.9},
                 {"at_sec": 4.0, "type": "pause", "energy": 0}]))
    emos = [s["emotion"] for s in ps["sentences"]]
    assert emos == ["冲击", "悬念", "平实"]
    assert ps["sentences"][0]["intensity"] >= 8
    assert ps["key_moments"][0]["at_sec"] == 1.0


def test_long_segment_split_at_pause():
    """>8s长段在词间停顿处切开"""
    words = [{"word": str(i), "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(8)]
    words += [{"word": "停", "start": 5.0, "end": 5.3},   # 前一词end=3.9→gap 1.1s
              {"word": "后", "start": 5.4, "end": 5.7},
              {"word": "段", "start": 5.8, "end": 9.5}]
    ps = build_pseudo_script(_u([
        _seg("一二三四五六七八停后段", 0.0, 9.5, words=words)]))
    assert len(ps["sentences"]) == 2
    assert ps["sentences"][0]["end_sec"] == 3.9
    assert ps["sentences"][1]["start_sec"] == 5.0


def test_short_merged_into_next():
    """<1s短句并入相邻句"""
    ps = build_pseudo_script(_u([
        _seg("好", 0.0, 0.5),
        _seg("今天我们全场五折", 1.0, 3.5),
    ]))
    assert len(ps["sentences"]) == 1
    assert ps["sentences"][0]["text"].startswith("好")
    assert ps["sentences"][0]["end_sec"] == 3.5
