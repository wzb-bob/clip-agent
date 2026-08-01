"""素材质量门禁——按句上传模式的第一道防线

用户拍砸的素材: 拍黑了/拍糊了/没拍人脸/黑尾长。
全部离线检测(cv2+ffmpeg·不加依赖)·只报告不拦截(拦截是前端产品决策)。

阈值实测标定(2026-08·DJI口播+gblur对照):
  清晰素材 Laplacian方差 5800-7200 · σ5模糊≈450 · σ10模糊≈79
  → 模糊阈值400(只拦不可用级, 手机普通素材~1000-3000不误伤)
"""
from __future__ import annotations
import logging, os
import numpy as np

logger = logging.getLogger(__name__)

_BRIGHT_DARK = 35        # 均值亮度<35=过暗
_BRIGHT_OVER = 220       # 均值亮度>220=过曝
_BLUR_THR = 400.0        # Laplacian方差<400=模糊(实测标定)
_FACE_CASCADE = None     # 延迟加载


def _sample_frames_cv(video_path: str, count: int = 3) -> list:
    """cv2均匀抽帧(270x480小帧)"""
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    frames = []
    for i in range(count):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / count))
        ret, f = cap.read()
        if ret:
            frames.append(cv2.resize(f, (270, 480)))
    cap.release()
    return frames


def _check_brightness(frames: list) -> tuple[str | None, float]:
    """过暗/过曝。返回(issue_type|None, 均值亮度)"""
    if not frames:
        return None, 0.0
    import cv2
    mean = float(np.mean([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean() for f in frames]))
    if mean < _BRIGHT_DARK:
        return "too_dark", mean
    if mean > _BRIGHT_OVER:
        return "overexposed", mean
    return None, mean


def _check_blur(frames: list) -> tuple[str | None, float]:
    """模糊。返回(issue_type|None, Laplacian方差均值)"""
    if not frames:
        return None, 0.0
    import cv2
    var = float(np.mean([
        cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        for f in frames]))
    if var < _BLUR_THR:
        return "blurry", var
    return None, var


def _check_face(frames: list) -> tuple[str | None, int]:
    """无人脸。返回(issue_type|None, 有人脸的帧数)"""
    global _FACE_CASCADE
    import cv2
    if _FACE_CASCADE is None:
        _FACE_CASCADE = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    hits = 0
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        if len(_FACE_CASCADE.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))):
            hits += 1
    if hits == 0 and frames:
        return "no_face", 0
    return None, hits


def check_material(clip_path: str, need_face: bool = True) -> dict:
    """单素材质量检测。返回 {"pass","issues":[{"type","detail"}],"metrics"}"""
    issues, metrics = [], {}
    if not os.path.exists(clip_path):
        return {"pass": False, "issues": [{"type": "missing", "detail": "文件不存在"}],
                "metrics": {}}

    frames = _sample_frames_cv(clip_path, 3)
    if not frames:
        return {"pass": False, "issues": [{"type": "unreadable", "detail": "无法解码"}],
                "metrics": {}}

    t, v = _check_brightness(frames)
    metrics["brightness"] = round(v, 1)
    if t:
        issues.append({"type": t, "detail": f"均值亮度{v:.0f}(过暗<35/过曝>220)"})

    t, v = _check_blur(frames)
    metrics["blur_var"] = round(v, 1)
    if t:
        issues.append({"type": t, "detail": f"Laplacian方差{v:.0f}<{_BLUR_THR:.0f}"})

    if need_face:
        t, hits = _check_face(frames)
        metrics["face_frames"] = hits
        if t:
            issues.append({"type": t, "detail": "口播素材未检测到人脸"})

    # 黑尾(复用chatcut_vfx的blackdetect)
    try:
        from .chatcut_vfx import _content_duration, _probe_duration
        cd, total = _content_duration(clip_path), _probe_duration(clip_path)
        metrics["content_ratio"] = round(cd / total, 2) if total > 0 else 0
        if total > 0 and cd / total < 0.8:
            issues.append({"type": "black_tail",
                           "detail": f"有效内容仅{cd/total:.0%}(黑尾>{(1-cd/total):.0%})"})
    except Exception:
        pass

    return {"pass": not issues, "issues": issues, "metrics": metrics}


def check_sentence_materials(sentences: list, video_slots: dict) -> dict:
    """句级批量检测。talking句查人脸, broll句不查。
    sentences为空时直接按video_slots逐槽检测(execute_unified早期调用场景)。
    返回 {"per_sentence":{idx:report}, "bad":[idx], "pass_rate":0-1}"""
    per, bad = {}, []
    if sentences:
        items = [(i, getattr(s, 'index', i), getattr(s, 'is_broll', False))
                 for i, s in enumerate(sentences, 1)]
    else:
        items = [(i, idx, False) for i, idx in enumerate(sorted(video_slots), 1)]
    for i, idx, is_broll in items:
        vf = video_slots.get(idx) or video_slots.get(i)
        if not vf:
            continue
        r = check_material(vf, need_face=not is_broll)
        per[i] = r
        if not r["pass"]:
            bad.append(i)
    rate = (len(per) - len(bad)) / len(per) if per else 1.0
    return {"per_sentence": per, "bad": bad, "pass_rate": round(rate, 2)}


def verify_sentence_order(sentences: list, video_slots: dict,
                          sim_threshold: float = 0.4) -> dict:
    """顺序校验(重·默认关): 每句素材whisper转录vs句文本相似度
    相似度<threshold→疑似张冠李戴。返回 {"suspects":[{index,sim}],"checked":N}"""
    import difflib
    suspects, checked = [], 0
    try:
        import whisper
        model = whisper.load_model("small")
    except Exception as e:
        return {"suspects": [], "checked": 0, "error": f"whisper不可用: {e}"}

    for i, s in enumerate(sentences, 1):
        vf = video_slots.get(getattr(s, 'index', i)) or video_slots.get(i)
        text = getattr(s, 'text', '') or ''
        if not vf or not os.path.exists(vf) or not text:
            continue
        try:
            r = model.transcribe(vf, language="zh")
            heard = r.get("text", "").replace(" ", "")
            sim = difflib.SequenceMatcher(None, text, heard).ratio()
            checked += 1
            if sim < sim_threshold:
                suspects.append({"index": i, "sim": round(sim, 2),
                                 "expected": text[:15], "heard": heard[:15]})
        except Exception as e:
            logger.debug("顺序校验跳过句%d: %s", i, e)
    return {"suspects": suspects, "checked": checked}
