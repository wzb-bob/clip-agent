"""digital_human.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestAutoSelectVoice:
    def test_boss_ip_gets_male(self):
        from clip_agent.digital_human import _auto_select_voice
        assert "Yunxi" in _auto_select_voice("老板IP")

    def test_sale_gets_female(self):
        from clip_agent.digital_human import _auto_select_voice
        assert "Xiaoxiao" in _auto_select_voice("团购售卖")

    def test_traffic_gets_male(self):
        from clip_agent.digital_human import _auto_select_voice
        assert "Yunxi" in _auto_select_voice("引流进店")

    def test_unknown_gets_default(self):
        from clip_agent.digital_human import _auto_select_voice
        assert "Xiaoxiao" in _auto_select_voice("未知类型")

class TestDigitalHumanResult:
    def test_fields(self):
        from clip_agent.digital_human import DigitalHumanResult
        r = DigitalHumanResult(True, "/tmp/v.mp4", "/tmp/a.mp3", 10.0, "simple", True)
        assert r.success is True
        assert r.duration_sec == 10.0
        assert r.face_detected is True

    def test_failure(self):
        from clip_agent.digital_human import DigitalHumanResult
        r = DigitalHumanResult(False, "", "", 0, "simple", False, "文件不存在")
        assert r.success is False
        assert r.error == "文件不存在"

class TestCreateTalkingVideo:
    def test_missing_photo(self):
        from clip_agent.digital_human import create_talking_video
        result = create_talking_video("/nonexistent/photo.jpg", "测试脚本")
        assert result.success is False
        assert "不存在" in result.error
