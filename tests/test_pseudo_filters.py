"""伪脚本开机口令/尾部残词过滤单测(字幕三修在自主引擎的复用)"""
from src.clip_agent.auto_pipeline import build_pseudo_script


def _u(segments, moments=None):
    return {"transcript": "".join(s["text"] for s in segments),
            "segments": segments, "moments": moments or []}


def _seg(text, start, end):
    return {"text": text, "start": start, "end": end, "confidence": 0.9,
            "speed_cps": 4.0, "words": []}


def test_slate_sentence_dropped():
    """"三二走"开头句被剔除(实测A5_0086场景)"""
    ps = build_pseudo_script(_u([
        _seg("三二走", 0.0, 2.76),
        _seg("今天给咱们展示一下店里的环境", 2.76, 6.2),
    ]))
    assert len(ps["sentences"]) == 1
    assert "三二走" not in ps["text"]
    assert ps["sentences"][0]["text"].startswith("今天")


def test_slate_partial_stripped():
    """口令+正文混合句→只裁口令"""
    ps = build_pseudo_script(_u([
        _seg("三二一开机今天我们开业了", 0.0, 3.0),
        _seg("欢迎大家", 4.0, 5.5),
    ]))
    assert "三二一" not in ps["sentences"][0]["text"]
    assert "今天" in ps["sentences"][0]["text"]


def test_tail_fragment_dropped():
    """长静音后的"好"残句被剔除"""
    ps = build_pseudo_script(_u([
        _seg("今天给咱们展示一下店里的环境", 0.0, 4.0),
        _seg("好", 5.5, 6.0),  # 间隔1.5s·2字以内
    ]))
    assert len(ps["sentences"]) == 1


def test_tail_normal_kept():
    """正常结尾句(间隔短/时长正常)保留"""
    ps = build_pseudo_script(_u([
        _seg("今天给咱们展示一下店里的环境", 0.0, 4.0),
        _seg("跟我来看看", 4.2, 6.0),  # 间隔0.2s·1.8s
    ]))
    assert len(ps["sentences"]) == 2
