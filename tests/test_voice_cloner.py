"""voice_cloner.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestListVoices:
    def test_returns_list(self):
        from clip_agent.voice_cloner import list_voices
        voices = list_voices()
        assert len(voices) >= 2
        assert any(v["engine"] == "edgetts" for v in voices)

class TestSSMLEmphasis:
    def test_price_emphasis(self):
        from clip_agent.voice_cloner import _add_ssml_emphasis
        result = _add_ssml_emphasis("68块！十只活虾！")
        assert "<emphasis" in result
        assert "68块" in result

    def test_cta_speedup(self):
        from clip_agent.voice_cloner import _add_ssml_emphasis
        result = _add_ssml_emphasis("赶紧来。左下角团购。")
        assert "prosody" in result.lower()

    def test_plain_text_unchanged(self):
        from clip_agent.voice_cloner import _add_ssml_emphasis
        result = _add_ssml_emphasis("大家好我是老张。干餐饮十二年了。")
        assert "大家好" in result

class TestAutoSelectVoice:
    def test_script_types(self):
        from clip_agent.digital_human import _auto_select_voice
        assert "Yunxi" in _auto_select_voice("老板IP")
        assert "Xiaoxiao" in _auto_select_voice("团购售卖")
