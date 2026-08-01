"""素材质量门禁单测+e2e(lavfi生成异常素材)"""
import shutil
import subprocess

import numpy as np
import pytest

from src.clip_agent.material_checker import (
    _check_brightness, _check_blur, check_material, check_sentence_materials,
)

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None,
                                reason="ffmpeg不可用")


# ── 纯函数(合成帧) ──

def _cv_frame(gray_level, noise=20):
    import cv2
    img = np.random.normal(gray_level, noise, (480, 270)).clip(0, 255).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_brightness_dark():
    t, v = _check_brightness([_cv_frame(20)])
    assert t == "too_dark" and v < 35


def test_brightness_over():
    t, v = _check_brightness([_cv_frame(235)])
    assert t == "overexposed"


def test_brightness_normal():
    t, v = _check_brightness([_cv_frame(120)])
    assert t is None


def test_blur_detection():
    """纯色帧(方差≈0)→模糊; 噪声帧→不模糊"""
    import cv2
    flat = np.full((480, 270, 3), 128, np.uint8)
    t, v = _check_blur([flat])
    assert t == "blurry" and v < 400
    t2, v2 = _check_blur([_cv_frame(120, noise=60)])
    assert t2 is None and v2 >= 400


# ── e2e: lavfi生成异常素材 ──

def _mkclip(path, vf=None, dur=2.0):
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "lavfi", "-i", f"testsrc2=size=270x480:rate=30:duration={dur}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}"]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", path]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("mc")
    normal = str(d / "normal.mp4"); _mkclip(normal)
    dark = str(d / "dark.mp4"); _mkclip(dark, vf="eq=brightness=-0.8")
    blurry = str(d / "blurry.mp4"); _mkclip(blurry, vf="gblur=sigma=10")
    return {"normal": normal, "dark": dark, "blurry": blurry}


def test_e2e_normal_passes(clips):
    r = check_material(clips["normal"], need_face=False)
    assert r["pass"], r["issues"]


def test_e2e_dark_detected(clips):
    r = check_material(clips["dark"], need_face=False)
    assert not r["pass"]
    assert any(i["type"] == "too_dark" for i in r["issues"])


def test_e2e_blurry_detected(clips):
    r = check_material(clips["blurry"], need_face=False)
    assert not r["pass"]
    assert any(i["type"] == "blurry" for i in r["issues"])


def test_e2e_no_face_testsrc(clips):
    """testsrc2无人脸→need_face时报no_face"""
    r = check_material(clips["normal"], need_face=True)
    assert any(i["type"] == "no_face" for i in r["issues"])


def test_e2e_missing_file():
    r = check_material("D:/no_such.mp4")
    assert not r["pass"] and r["issues"][0]["type"] == "missing"


def test_batch_empty_sentences_uses_slots(clips):
    """sentences为空→按slots逐槽检测(execute_unified早期场景)"""
    r = check_sentence_materials([], {1: clips["normal"], 2: clips["dark"]})
    assert r["bad"] == [2]
    assert r["pass_rate"] == 0.5


# ── 真实人脸(skipif桌面素材不在) ──

@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg不可用")
def test_real_face_detected():
    import os
    real = "C:/Users/wangzibo/Desktop/测试视频/sentence_clips/s1.mp4"
    if not os.path.exists(real):
        pytest.skip("桌面真实素材不在")
    r = check_material(real, need_face=True)
    assert not any(i["type"] == "no_face" for i in r["issues"])
