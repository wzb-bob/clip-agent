"""health.py 测试 — 系统健康检查（纯逻辑，无外部依赖）"""
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestHealthStatus:
    def test_dataclass_fields(self):
        from clip_agent.health import HealthStatus
        hs = HealthStatus(component="ffmpeg", healthy=True, detail="OK", latency_ms=5.0, version="7.0")
        assert hs.component == "ffmpeg"
        assert hs.healthy is True
        assert hs.detail == "OK"
        assert hs.latency_ms == 5.0
        assert hs.version == "7.0"

    def test_defaults(self):
        from clip_agent.health import HealthStatus
        hs = HealthStatus(component="test", healthy=False, detail="fail")
        assert hs.latency_ms == 0.0
        assert hs.version == ""


class TestCheckAll:
    def test_returns_expected_structure(self):
        from clip_agent.health import check_all
        result = check_all()
        assert "healthy" in result
        assert "checks" in result
        assert "timestamp" in result
        assert isinstance(result["checks"], dict)
        assert isinstance(result["healthy"], bool)

    def test_contains_all_components(self):
        from clip_agent.health import check_all
        result = check_all()
        expected = {"ffmpeg", "python_deps", "api_keys", "disk", "openmontage", "modules", "ai_services"}
        assert set(result["checks"].keys()) >= expected

    def test_each_check_has_required_fields(self):
        from clip_agent.health import check_all
        result = check_all()
        for name, check in result["checks"].items():
            if isinstance(check, dict):
                if "healthy" in check:
                    assert "detail" in check, f"{name} missing 'detail'"
                else:
                    # Nested (ai_services)
                    for sub in check.values():
                        assert "healthy" in sub
                        assert "detail" in sub


class TestCheckFfmpeg:
    def test_ffmpeg_found(self):
        with patch("clip_agent.health.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("clip_agent.health.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="ffmpeg version 7.0.1", stderr="")
                from clip_agent.health import _check_ffmpeg
                result = _check_ffmpeg()
                assert result["healthy"] is True
                assert "ffmpeg" in result["detail"]

    def test_ffmpeg_not_found(self):
        with patch("clip_agent.health.shutil.which", return_value=None):
            from clip_agent.health import _check_ffmpeg
            result = _check_ffmpeg()
            assert result["healthy"] is False
            assert "未安装" in result["detail"]

    def test_ffprobe_missing(self):
        with patch("clip_agent.health.shutil.which", side_effect=lambda x: x == "ffmpeg" and "/usr/bin/ffmpeg" or None):
            from clip_agent.health import _check_ffmpeg
            result = _check_ffmpeg()
            assert result["healthy"] is False


class TestCheckDeps:
    def test_all_deps_found(self):
        with patch("clip_agent.health.importlib.import_module"):
            from clip_agent.health import _check_deps
            result = _check_deps()
            assert result["healthy"] is True
            assert "全部" in result["detail"]

    def test_some_deps_missing(self):
        def mock_import(name, *args, **kwargs):
            if name in ("cv2", "whisper"):
                raise ImportError(f"No module named '{name}'")
        with patch("clip_agent.health.importlib.import_module", side_effect=mock_import):
            from clip_agent.health import _check_deps
            result = _check_deps()
            assert result["healthy"] is False
            assert "缺少" in result["detail"]
            assert "cv2" in result["detail"]
            assert "whisper" in result["detail"]


class TestCheckApiKeys:
    def test_some_keys_configured(self):
        with patch.dict("os.environ", {"KIMI_API_KEY": "kimi-key", "DEEPSEEK_API_KEY": "ds-key"}, clear=True):
            from clip_agent.health import _check_api_keys
            result = _check_api_keys()
            assert result["healthy"] is True
            assert "2/4" in result["detail"]

    def test_no_keys_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            from clip_agent.health import _check_api_keys
            result = _check_api_keys()
            assert result["healthy"] is False
            assert "无API Key" in result["detail"]


class TestCheckDisk:
    def test_sufficient_space(self):
        mock_usage = MagicMock()
        mock_usage.free = 10 * 1024**3  # 10GB
        with patch("clip_agent.health.shutil.disk_usage", return_value=mock_usage):
            from clip_agent.health import _check_disk
            result = _check_disk()
            assert result["healthy"] is True

    def test_low_space(self):
        mock_usage = MagicMock()
        mock_usage.free = 100 * 1024**2  # 100MB
        with patch("clip_agent.health.shutil.disk_usage", return_value=mock_usage):
            from clip_agent.health import _check_disk
            result = _check_disk()
            assert result["healthy"] is False
            assert "不足" in result["detail"]


class TestCheckOpenmontage:
    def test_not_installed(self):
        with patch("pathlib.Path.exists", return_value=False):
            from clip_agent.health import _check_openmontage
            result = _check_openmontage()
            assert result["healthy"] is False
            assert "未安装" in result["detail"]


class TestPrintHealthReport:
    def test_does_not_raise(self):
        from clip_agent.health import check_all
        result = check_all()
        # print_health_report should not raise
        from clip_agent.health import print_health_report
        try:
            print_health_report()
        except Exception as e:
            pytest.fail(f"print_health_report raised: {e}")
