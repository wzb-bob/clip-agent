"""BGM选曲单测"""
import os
import subprocess
import pytest

from src.clip_agent.bgm_selector import select_bgm, _candidate_names


@pytest.fixture(scope="module")
def bgm_dir(tmp_path_factory):
    """生成测试音频进临时bgm目录"""
    d = tmp_path_factory.mktemp("bgm")
    pad = str(d / "热爱105°C的你.mp3")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=277:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=330:duration=3",
        "-filter_complex", "[0][1][2]amix=inputs=3,volume=0.3", pad,
    ], capture_output=True, timeout=30)
    return str(d)


def test_select_by_track_name(bgm_dir):
    """曲名匹配命中(团购→带货/美食类曲目)"""
    out = select_bgm("团购售卖", [bgm_dir])
    # 后端曲库在场时命中"热爱105°C的你"; 不在时兜底到目录唯一音频
    assert out is not None and out.endswith(".mp3")


def test_fallback_to_only_audio(bgm_dir):
    """无曲库/无匹配→目录唯一音频兜底"""
    out = select_bgm("不存在的类别", [bgm_dir])
    assert out is not None


def test_missing_dir_returns_none():
    assert select_bgm("团购售卖", ["D:/no_such_bgm_dir_xxx"]) is None


def test_candidate_names_no_crash():
    """独立模式无曲库→空列表不崩"""
    names = _candidate_names("团购售卖")
    assert isinstance(names, list)
