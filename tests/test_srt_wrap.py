"""句级SRT拆行单测(长句不拆会溢出画框·实测)"""
import os
from types import SimpleNamespace
from src.clip_agent.execution_engine import _write_srt_from_sentences


def _seg(text, start, dur):
    return SimpleNamespace(script_text=text, start_sec=start, duration_sec=dur)


def test_long_sentence_wrapped(tmp_path):
    """24字长句→拆成≤16字多行·时间均分"""
    p = str(tmp_path / "t.srt")
    _write_srt_from_sentences([_seg("唐" * 24, 0.0, 6.0)], p)
    content = open(p, encoding="utf-8").read()
    blocks = [b for b in content.strip().split("\n\n") if b.strip()]
    assert len(blocks) == 2
    assert "00:00:00,000 --> 00:00:03,000" in blocks[0]
    assert "00:00:03,000 --> 00:00:06,000" in blocks[1]
    assert len(blocks[0].splitlines()[2]) == 16


def test_short_sentence_single_line(tmp_path):
    p = str(tmp_path / "t.srt")
    _write_srt_from_sentences([_seg("左下角囤券", 2.0, 2.5)], p)
    content = open(p, encoding="utf-8").read()
    assert content.count("左下角囤券") == 1
    assert "00:00:02,000 --> 00:00:04,500" in content


def test_empty_text_skipped(tmp_path):
    p = str(tmp_path / "t.srt")
    _write_srt_from_sentences([_seg("", 0, 1), _seg("有效句", 1, 2)], p)
    assert "有效句" in open(p, encoding="utf-8").read()
