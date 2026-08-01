"""_srt_to_drawtext字体路径回归(豆腐块bug)

此前 _srt_to_drawtext 对_find_font()已转义的路径二次转义→字体加载失败→
SRT字幕全程豆腐块·被segment drawtext掩盖, body段清空后才暴露(实测v3帧)
"""
from src.clip_agent.chatcut_vfx import _srt_to_drawtext, _find_font


def test_font_not_double_escaped(tmp_path):
    srt = tmp_path / "t.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n测试字幕\n", encoding="utf-8")
    font = _find_font()
    if not font:
        import pytest; pytest.skip("无系统字体")
    vf = _srt_to_drawtext(str(srt), font, 1080, 1920)
    # 字体路径必须原样出现(不被二次转义成 C/\: 的畸形)
    assert f"fontfile='{font}'" in vf
    assert "/\\:" not in vf.split("fontfile=")[1][:40]


def test_srt_entries_parsed(tmp_path):
    srt = tmp_path / "t.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n第一句\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\n第二句\n", encoding="utf-8")
    vf = _srt_to_drawtext(str(srt), _find_font() or "sans", 1080, 1920)
    assert "第一句" in vf and "第二句" in vf
    assert "between(t,0.0,2.0)" in vf or "between(t,0,2)" in vf
