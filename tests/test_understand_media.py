"""understand_media构造崩溃回归(TypeError: duration_sec必填)

此前 understand_media() 入口必崩——MediaUnderstanding(file_path=...)缺必填参数,
意味着这个入口从未被成功调用过(无测试覆盖的断头路)。
"""
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None,
                                reason="ffmpeg不可用")


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    d = tmp_path_factory.mktemp("um")
    p = str(d / "c.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=270x480:rate=30:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p,
    ], check=True, capture_output=True, timeout=60)
    return p


def test_understand_media_no_typeerror(clip):
    """入口不崩·返回带duration的MediaUnderstanding"""
    from src.clip_agent.media_understanding import understand_media
    mu = understand_media(clip, use_ai=False)
    assert mu is not None
    assert mu.duration_sec > 0
    assert mu.file_path == clip
