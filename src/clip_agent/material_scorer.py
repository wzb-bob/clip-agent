"""素材评分系统——技术质量+内容匹配+多样性·自动择优

参考: BRISQUE无参考VQA + clipforge RMS能量评分 + Video Review OS质量门禁
实现: 纯cv2+numpy·零新依赖·CPU可用
"""
from __future__ import annotations
import logging, os
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

# 镜头类型→素材槽映射
SHOT_TO_SLOT = {
    "特写": "product", "近景": "talking", "中近景": "talking",
    "中景": "broll", "全景": "broll", "远景": "broll",
    "俯拍": "product",
}


def _sample_frames(video_path: str, count: int = 5) -> list:
    """均匀抽帧"""
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


def _score_technical(frames: list) -> tuple[float, dict]:
    """技术质量: 锐度(50%) + 亮度适宜(30%) + 对比度(20%) → 0-1分"""
    if not frames:
        return 0.0, {}
    import cv2
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]

    # 锐度: Laplacian方差·归一化(清晰素材~6000→1.0)
    lap_vars = [cv2.Laplacian(g, cv2.CV_64F).var() for g in grays]
    avg_lap = float(np.mean(lap_vars))
    sharpness = min(1.0, avg_lap / 4000.0)  # 4000=基准清晰度

    # 亮度: 均值在80-180最佳
    means = [float(np.mean(g)) for g in grays]
    avg_mean = float(np.mean(means))
    if 80 <= avg_mean <= 180:
        brightness = 1.0
    elif avg_mean < 80:
        brightness = max(0.0, avg_mean / 80.0)
    else:
        brightness = max(0.0, 1.0 - (avg_mean - 180) / 75.0)

    # 对比度: std在30-80最佳
    stds = [float(np.std(g)) for g in grays]
    avg_std = float(np.mean(stds))
    contrast = min(1.0, avg_std / 50.0) if avg_std < 50 else max(0.0, 1.0 - (avg_std - 50) / 80.0)

    score = sharpness * 0.5 + brightness * 0.3 + contrast * 0.2
    return round(score, 3), {
        "sharpness": round(sharpness, 2), "brightness": round(brightness, 2),
        "contrast": round(contrast, 2), "lap_var": round(avg_lap, 1),
        "mean_brightness": round(avg_mean, 1), "mean_contrast": round(avg_std, 1),
    }


def _score_content_match(shot_json: list, material_type: str) -> float:
    """内容匹配: shot要求的镜头类型 vs 素材实际类型 → 0-1分"""
    if not shot_json:
        return 0.6  # 无分镜·默认中等匹配

    # 统计shot需要的素材类型
    needed_slots: dict[str, int] = {}
    for s in shot_json:
        slot = SHOT_TO_SLOT.get(s.get("shot_type", ""), "talking")
        needed_slots[slot] = needed_slots.get(slot, 0) + 1

    # 单素材: 按需要最多槽位类型匹配
    if material_type == "talking":
        return min(1.0, needed_slots.get("talking", 0) / max(1, len(shot_json)) * 2.5)
    elif material_type == "product":
        return min(1.0, needed_slots.get("product", 0) / max(1, len(shot_json)) * 3.0)
    elif material_type == "broll":
        return min(1.0, needed_slots.get("broll", 0) / max(1, len(shot_json)) * 2.0)
    return 0.5


def score_materials(
    materials: dict[str, str],          # {slot_type: file_path}
    shot_json: list | None = None,
    duration_needed: float = 10.0,
) -> dict:
    """批量评分 → 每个素材0-1分·排序·选最优

    Returns:
        {"scores": {slot: {score,technical,content_match,metrics}},
         "best": {slot: path},
         "ranking": [{slot,score,path}, ...]}
    """
    results: dict = {"scores": {}, "best": {}, "ranking": []}

    for slot, path in materials.items():
        if not path or not os.path.exists(path):
            continue
        frames = _sample_frames(path, 5)
        tech_score, tech_metrics = _score_technical(frames)

        # 内容匹配
        match_score = _score_content_match(shot_json or [], slot)

        # 时长适配: 口播时长/需要时长
        try:
            import subprocess, json
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", path],
                capture_output=True, text=True, timeout=10)
            dur = float(json.loads(r.stdout)["format"]["duration"])
            dur_fit = min(1.0, dur / max(1.0, duration_needed))
        except Exception:
            dur = 5.0
            dur_fit = 0.5

        # 综合评分
        overall = round(tech_score * 0.4 + match_score * 0.35 + dur_fit * 0.25, 3)

        results["scores"][slot] = {
            "score": overall, "technical": tech_score,
            "content_match": round(match_score, 2),
            "duration_fit": round(dur_fit, 2),
            "duration_sec": round(dur, 1),
            "metrics": tech_metrics,
        }
        results["ranking"].append({"slot": slot, "score": overall, "path": path})

    # 排序·选最优
    results["ranking"].sort(key=lambda x: x["score"], reverse=True)
    # 每个槽位取最高分
    seen_slots = set()
    for item in results["ranking"]:
        if item["slot"] not in seen_slots:
            results["best"][item["slot"]] = item["path"]
            seen_slots.add(item["slot"])

    return results


def score_single(video_path: str, shot_type: str = "talking") -> dict:
    """单个视频评分·快速评估"""
    frames = _sample_frames(video_path, 5)
    tech_score, metrics = _score_technical(frames)

    # 检测人脸
    import cv2
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    has_face = False
    for f in frames:
        gray = cv2.cvtColor(cv2.resize(f, (540, 960)), cv2.COLOR_BGR2GRAY)
        if len(face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))):
            has_face = True
            break

    return {
        "score": round(tech_score, 3),
        "technical": metrics,
        "has_face": has_face,
        "shot_type": shot_type,
        "usable": tech_score > 0.3 and (shot_type != "talking" or has_face),
    }
