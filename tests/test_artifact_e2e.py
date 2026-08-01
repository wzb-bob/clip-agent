"""artifact_detector 端到端回归(CI可跑·ffmpeg现场生成样本)

自省制度化: 检测类代码先立真实样本验收——
此前真实样本在桌面(机器相关), 这里用lavfi现场生成等价场景:
红块遮挡/黑窗/全屏黑段/冻结/干净 五连
"""
import shutil
import subprocess

import pytest

from src.clip_agent.artifact_detector import detect_artifacts

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None,
                                reason="ffmpeg不可用")

_SIZE = "270x480"


def _run(args):
    r = subprocess.run(args, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr[-300:] if isinstance(r.stderr, str) else r.stderr


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    d = tmp_path_factory.mktemp("e2e")
    out = {}

    # 干净版: testsrc2噪声图案(无纯色块·持续运动)
    out["clean"] = str(d / "clean.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
          "-i", f"testsrc2=size={_SIZE}:rate=30:duration=4",
          "-pix_fmt", "yuv420p", out["clean"]])

    # 红块版: 上半屏纯红(v1 hook遮挡场景)
    out["red"] = str(d / "red.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
          "-i", f"testsrc2=size={_SIZE}:rate=30:duration=4",
          "-vf", "drawbox=x=0:y=0:w=270:h=200:color=red@1:t=fill",
          "-pix_fmt", "yuv420p", out["red"]])

    # 黑窗版: 右上角黑块120x100(v1 PiP黑窗场景·压缩边缘有振铃故取大块)
    out["blackbox"] = str(d / "blackbox.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
          "-i", f"testsrc2=size={_SIZE}:rate=30:duration=4",
          "-vf", "drawbox=x=140:y=30:w=120:h=100:color=black@1:t=fill",
          "-pix_fmt", "yuv420p", out["blackbox"]])

    # 黑屏段版: 前2s正常+后1.5s全黑(v3 B-roll黑尾场景)
    out["blackgap"] = str(d / "blackgap.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-f", "lavfi", "-i", f"testsrc2=size={_SIZE}:rate=30:duration=2",
          "-f", "lavfi", "-i", f"color=black:size={_SIZE}:rate=30:duration=1.5",
          "-filter_complex", "[0][1]concat=n=2:v=1[v]", "-map", "[v]",
          "-pix_fmt", "yuv420p", out["blackgap"]])

    # 冻结版: 单帧循环到3s(画面卡死场景·循环动图不算冻结)
    tiny = str(d / "tiny.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
          "-i", f"testsrc2=size={_SIZE}:rate=30",
          "-frames:v", "1", "-pix_fmt", "yuv420p", tiny])
    out["freeze"] = str(d / "freeze.mp4")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1",
          "-i", tiny, "-t", "3", "-pix_fmt", "yuv420p", out["freeze"]])

    return out


def _types(report):
    return {a["type"] for a in report.get("artifacts", [])}


def test_e2e_clean(samples):
    r = detect_artifacts(samples["clean"])
    assert r["clean"], f"干净版误报: {r['artifacts']}"


def test_e2e_red_block(samples):
    r = detect_artifacts(samples["red"])
    assert not r["clean"]
    assert "saturated_block" in _types(r)


def test_e2e_black_box(samples):
    r = detect_artifacts(samples["blackbox"])
    assert not r["clean"]
    assert "black_box" in _types(r)


def test_e2e_black_gap(samples):
    r = detect_artifacts(samples["blackgap"])
    assert not r["clean"]
    assert "black_gap" in _types(r)


def test_e2e_freeze(samples):
    r = detect_artifacts(samples["freeze"])
    assert not r["clean"]
    assert "freeze" in _types(r)
