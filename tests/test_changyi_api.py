"""changyi_api.py 测试 — 统一API"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestChangyiAPI:
    def test_init(self):
        from clip_agent.changyi_api import ChangyiAPI
        api = ChangyiAPI()
        assert api is not None

    def test_diagnose(self):
        from clip_agent.changyi_api import ChangyiAPI
        api = ChangyiAPI()
        result = api.diagnose()
        assert result.mode == "diagnose"
        assert "health" in result.data
        assert "plugins" in result.data

    def test_plugins(self):
        from clip_agent.changyi_api import ChangyiAPI
        api = ChangyiAPI()
        plugins = api.plugins()
        assert "tts" in plugins
        assert "render" in plugins

    def test_voices(self):
        from clip_agent.changyi_api import ChangyiAPI
        api = ChangyiAPI()
        voices = api.voices()
        assert len(voices) >= 2

    def test_detect_type(self):
        from clip_agent.changyi_api import ChangyiAPI
        api = ChangyiAPI()
        assert api._detect_type("68块！十只活虾！") == "团购售卖"
        assert api._detect_type("大家好我是老张干餐饮十二年了") == "老板IP"
        assert api._detect_type("全玉田只此一家导航搜虾神") == "引流进店"
        assert api._detect_type("普通文本") == "团购售卖"

    def test_clip_minimal(self):
        from clip_agent.changyi_api import ChangyiAPI
        api = ChangyiAPI()
        result = api.clip("68块！十只活虾！", "团购售卖")
        assert result.mode == "clip"
        assert isinstance(result.success, bool)
        assert result.elapsed > 0

class TestAPIResult:
    def test_fields(self):
        from clip_agent.changyi_api import APIResult
        r = APIResult(True, "clip", {"key": "val"}, elapsed=1.5)
        assert r.success is True
        assert r.mode == "clip"
        assert r.data["key"] == "val"
        assert r.elapsed == 1.5

    def test_error(self):
        from clip_agent.changyi_api import APIResult
        r = APIResult(False, "clip", error="测试错误")
        assert r.success is False
        assert r.error == "测试错误"
