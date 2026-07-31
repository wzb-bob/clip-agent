"""whisper_srt_generator 纯函数单测(不加载whisper模型)"""
from src.clip_agent.whisper_srt_generator import (
    _group_words_to_lines, _strip_slate_words, _drop_isolated_fragments,
)


def _w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_no_word_split():
    """词内间隙≈0的"环境"不应被拆到两行, 应在词间停顿处断行"""
    # "今天给咱们展示一下我们店的环境跟我来" — 店(0.5s停顿)的环境(词内0间隙)
    words = [
        _w("今天", 0.0, 0.4), _w("给", 0.45, 0.6), _w("咱们", 0.62, 0.9),
        _w("展示", 0.92, 1.2), _w("一下", 1.22, 1.5), _w("我们", 1.52, 1.8),
        _w("店", 1.82, 2.0),
        _w("的", 2.6, 2.75),          # ← 0.6s停顿(短语边界)
        _w("环", 2.78, 2.9), _w("境", 2.90, 3.05),  # ← 词内0间隙
        _w("跟", 3.07, 3.2), _w("我", 3.22, 3.35), _w("来", 3.37, 3.6),
    ]
    groups = _group_words_to_lines(words, max_chars=8, min_ms=800)
    texts = [g["text"] for g in groups]
    assert not any(t.endswith("环") for t in texts), f"环境被拆: {texts}"
    assert not any(t.startswith("境") for t in texts), f"环境被拆: {texts}"
    assert "".join(texts) == "今天给咱们展示一下我们店的环境跟我来"  # 不丢字


def test_punctuation_break_still_works():
    """标点断行回归: 句末标点处应断行"""
    words = [
        _w("今天", 0.0, 0.4), _w("全场", 0.45, 0.8), _w("五折", 0.85, 1.2),
        _w("！", 1.2, 1.3),
        _w("快来", 2.0, 2.4), _w("抢购", 2.45, 2.8),
    ]
    groups = _group_words_to_lines(words, max_chars=18, min_ms=800)
    texts = [g["text"] for g in groups]
    assert texts == ["今天全场五折！", "快来抢购"]


def test_isolated_tail_dropped():
    """静音1.3s后的尾部孤立词"好"应被剔除"""
    words = [
        _w("跟", 0.0, 0.3), _w("我", 0.32, 0.5), _w("来", 0.52, 0.8),
        _w("好", 2.1, 2.6),   # ← 前面静音1.3s
    ]
    result = _drop_isolated_fragments(words)
    assert "".join(w["word"] for w in result) == "跟我来"


def test_isolated_mid_kept():
    """句中正常短词(间隙<0.8s)不应误删"""
    words = [
        _w("今天", 0.0, 0.4), _w("全场", 0.45, 0.8),
        _w("好", 1.0, 1.3),   # 间隙0.2s, 正常语流
    ]
    result = _drop_isolated_fragments(words)
    assert len(result) == 3


def test_slate_stripped():
    """开头"三二走"口令应被剔除, 返回slate_end>0"""
    words = [
        _w("三", 0.0, 0.4), _w("二", 0.45, 0.8), _w("走", 0.85, 1.2),
        _w("今天", 2.0, 2.4), _w("开业", 2.45, 2.8),
    ]
    kept, slate_end = _strip_slate_words(words)
    assert "".join(w["word"] for w in kept) == "今天开业"
    assert slate_end == 1.2


def test_no_slate_untouched():
    """正常开场白不应误判为口令"""
    words = [
        _w("今天", 0.0, 0.4), _w("给", 0.45, 0.6), _w("大家", 0.62, 0.95),
        _w("介绍", 1.0, 1.4), _w("三道", 1.45, 1.8), _w("菜", 1.85, 2.1),
    ]
    kept, slate_end = _strip_slate_words(words)
    assert kept == words
    assert slate_end == 0.0


def test_break_after_flag_preferred():
    """有break_after标记时, 即使时间戳连续(间隙=0)也在标记处断行"""
    # 模拟whisper连续时间戳 + LLM打标"环境"后断开
    words = [
        _w("今天", 0.0, 0.4), _w("给", 0.4, 0.6), _w("咱们", 0.6, 0.9),
        _w("展示", 0.9, 1.2), _w("一下", 1.2, 1.5), _w("我们", 1.5, 1.8),
        _w("店", 1.8, 2.0), _w("的", 2.0, 2.2),
        {**_w("环", 2.2, 2.4)}, {**_w("境", 2.4, 2.6), "break_after": True},
        _w("跟", 2.6, 2.8), _w("我", 2.8, 3.0), _w("来", 3.0, 3.3),
    ]
    groups = _group_words_to_lines(words, max_chars=15, min_ms=800)
    texts = [g["text"] for g in groups]
    assert not any(t.endswith("环") for t in texts), f"环境被拆: {texts}"
    assert texts[0] == "今天给咱们展示一下我们店的环境", f"未在标记处断行: {texts}"
