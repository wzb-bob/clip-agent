"""成片artifact确定性检测——补Kimi视觉盲区

实测: Kimi逐帧评估漏报大红块遮挡(v1 hook)和B-roll PiP黑块。
LLM对"策略匹配度"敏感,对大面积纯色块不敏感——这类缺陷用纯CV检测更可靠。

原理: 抽帧→缩到160x284→16px网格算块方差→低方差块按颜色连通→
     连通区>15%画面且跨≥2帧持续出现→判定artifact
豁免: 肤色/天空蓝/低饱和自然色不误报;只报黑色块和高饱和色块
"""
from __future__ import annotations
import logging, os, subprocess, tempfile
import numpy as np

logger = logging.getLogger(__name__)

_FRAME_W, _FRAME_H = 160, 284   # 检测用小帧(快)
_BLOCK = 16                     # 网格块边长(px)
_STD_THR = 8.0                  # 块内标准差阈值·低于=平坦
_COLOR_DIST = 35.0              # 相邻块颜色距离阈值·低于=同一连通区
_AREA_THR = 0.15                # 连通区面积占比阈值
_MIN_FRAMES = 2                 # 至少持续帧数


def _extract_small_frames(video_path: str, count: int) -> list[np.ndarray]:
    """均匀抽count帧并缩小"""
    import json as _json
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_format", video_path],
                           capture_output=True, text=True, timeout=15)
        dur = float(_json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return []
    frames = []
    tmp = tempfile.mkdtemp(prefix="ad_")
    for i in range(count):
        t = dur * (i + 0.5) / count
        fp = os.path.join(tmp, f"f{i}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t),
                        "-i", video_path, "-frames:v", "1",
                        "-vf", f"scale={_FRAME_W}:{_FRAME_H}", fp],
                       capture_output=True, timeout=30)
        if os.path.exists(fp):
            from PIL import Image
            frames.append(np.asarray(Image.open(fp).convert("RGB")))
    return frames


def _flat_grid(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """16px网格→(平坦掩码, 块均色)"""
    gh, gw = _FRAME_H // _BLOCK, _FRAME_W // _BLOCK
    flat = np.zeros((gh, gw), dtype=bool)
    means = np.zeros((gh, gw, 3))
    for gy in range(gh):
        for gx in range(gw):
            cell = img[gy*_BLOCK:(gy+1)*_BLOCK, gx*_BLOCK:(gx+1)*_BLOCK].astype(float)
            # 空间平坦度: 每通道单独算空间std取最大(纯色块跨通道差大但空间std=0)
            flat[gy, gx] = cell.std(axis=(0, 1)).max() < _STD_THR
            means[gy, gx] = cell.mean(axis=(0, 1))
    return flat, means


def _dark_grid(img: np.ndarray) -> np.ndarray:
    """死平暗块掩码: mean<60 且 std<3
    失败overlay的黑窗核心是绝对死平的(编码合成区无传感器噪声);
    自然暗部(木质顶棚等)必有纹理/噪声(std≥12)——实测可分"""
    gh, gw = _FRAME_H // _BLOCK, _FRAME_W // _BLOCK
    dark = np.zeros((gh, gw), dtype=bool)
    for gy in range(gh):
        for gx in range(gw):
            cell = img[gy*_BLOCK:(gy+1)*_BLOCK, gx*_BLOCK:(gx+1)*_BLOCK].astype(float)
            if cell.mean(axis=(0, 1)).max() < 60 and cell.std(axis=(0, 1)).max() < 3:
                dark[gy, gx] = True
    return dark


def _mask_regions(mask: np.ndarray):
    """纯掩码BFS连通区(暗块专用·不需要颜色距离)"""
    gh, gw = mask.shape
    seen = np.zeros_like(mask)
    for sy in range(gh):
        for sx in range(gw):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            stack, cells = [(sy, sx)], []
            seen[sy, sx] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((0,1),(0,-1),(1,0),(-1,0)):
                    ny, nx = y+dy, x+dx
                    if (0 <= ny < gh and 0 <= nx < gw
                            and mask[ny, nx] and not seen[ny, nx]):
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            yield {"area": len(cells) / (gh * gw),
                   "cx": np.mean([x for _, x in cells]) / gw,
                   "cy": np.mean([y for y, _ in cells]) / gh}


def _iter_regions(flat: np.ndarray, means: np.ndarray):
    """平坦块按颜色连通, 迭代返回所有连通区(面积占比/均色/质心)"""
    gh, gw = flat.shape
    seen = np.zeros_like(flat)
    for sy in range(gh):
        for sx in range(gw):
            if not flat[sy, sx] or seen[sy, sx]:
                continue
            # BFS: 颜色相近的平坦块
            stack, cells = [(sy, sx)], []
            base_color = means[sy, sx]
            seen[sy, sx] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((0,1),(0,-1),(1,0),(-1,0)):
                    ny, nx = y+dy, x+dx
                    if (0 <= ny < gh and 0 <= nx < gw and flat[ny, nx]
                            and not seen[ny, nx]
                            and np.linalg.norm(means[ny, nx] - base_color) < _COLOR_DIST):
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            area = len(cells) / (gh * gw)
            color = np.mean([means[y, x] for y, x in cells], axis=0)
            cy = np.mean([y for y, _ in cells]) / gh
            cx = np.mean([x for _, x in cells]) / gw
            yield {"area": area, "color": color, "cx": cx, "cy": cy}


def _is_suspicious_color(rgb: np.ndarray) -> str | None:
    """黑色块或亮高饱和色块→类型; 自然色(肤色/暗色场景/低饱和)→None豁免"""
    r, g, b = rgb
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 45:
        return "black_box"                     # 纯黑块(PiP空窗/渲染失败)
    if mx - mn > 70 and mx > 180:              # 亮且高饱和(设计色块特征)
        # 肤色豁免: R>G>B且差距温和
        if r > g > b and (r - b) < 110 and g > 80:
            return None
        return "saturated_block"               # 亮高饱和色块(大红遮挡等)
    return None


def detect_artifacts(video_path: str, sample_count: int = 5,
                     area_threshold: float = _AREA_THR,
                     min_frames: int = _MIN_FRAMES) -> dict:
    """检测成片中的大面积纯色遮挡artifact。返回检测报告dict"""
    frames = _extract_small_frames(video_path, sample_count)
    if not frames:
        return {"clean": None, "error": "帧提取失败", "artifacts": []}

    hits = []
    for idx, img in enumerate(frames):
        flat, means = _flat_grid(img)
        for region in _iter_regions(flat, means):
            atype = _is_suspicious_color(region["color"])
            if not atype or atype == "black_box":
                continue  # 黑块走专用暗块检测(边缘混合·平坦阈值不适用)
            if region["area"] < area_threshold:
                continue
            hits.append({"frame": idx, "type": atype, "area": round(region["area"], 2),
                         "color": [int(c) for c in region["color"]],
                         "center": [round(region["cx"], 2), round(region["cy"], 2)]})
        # 死平暗块(黑窗)检测: ≥3个连通死平块(>50%=夜景内容豁免)
        for region in _mask_regions(_dark_grid(img)):
            if 0.018 <= region["area"] <= 0.5:
                hits.append({"frame": idx, "type": "black_box",
                             "area": round(region["area"], 2), "color": [0, 0, 0],
                             "center": [round(region["cx"], 2), round(region["cy"], 2)]})

    # 持续性: 同类型+质心相近(±0.15)的命中聚类, ≥min_frames帧才确认
    confirmed = []
    used = [False] * len(hits)
    for i, h in enumerate(hits):
        if used[i]:
            continue
        group = [h]
        used[i] = True
        for j in range(i + 1, len(hits)):
            if used[j] or hits[j]["type"] != h["type"]:
                continue
            if (abs(hits[j]["center"][0] - h["center"][0]) < 0.15
                    and abs(hits[j]["center"][1] - h["center"][1]) < 0.15):
                group.append(hits[j])
                used[j] = True
        if len(group) >= min_frames:
            confirmed.append({
                "type": h["type"], "frames": [g["frame"] for g in group],
                "area_max": max(g["area"] for g in group), "color": h["color"],
                "center": h["center"],
            })

    # 冻结检测(2fps差分·独立通道)
    try:
        for r in _detect_freeze(video_path):
            confirmed.append({"type": "freeze", **r})
    except Exception as e:
        logger.debug("冻结检测跳过: %s", e)

    if confirmed:
        logger.warning("artifact检出: %s", confirmed)
    return {"clean": not confirmed, "checked_frames": len(frames), "artifacts": confirmed}


# ══════════════════════════════════════════════════════════
# 冻结检测: 相邻帧差分持续近零=画面卡死(v3实测7.2-7.6s冻结)
# ══════════════════════════════════════════════════════════

def _freeze_runs(diffs: list[float], fps: float,
                 diff_thr: float = 0.3, min_freeze_s: float = 1.5) -> list[dict]:
    """相邻帧差分序列→冻结区间(纯函数·可单测)
    diffs[i]=第i帧与第i+1帧的差分均值·diffs<t thr视为静止"""
    min_frames = max(1, int(min_freeze_s * fps))
    runs = []
    start = None
    for i, d in enumerate(diffs):
        if d < diff_thr:
            if start is None:
                start = i
        else:
            if start is not None and i - start >= min_frames:
                runs.append({"start": round(start / fps, 1),
                             "end": round((i + 1) / fps, 1)})
            start = None
    if start is not None and len(diffs) - start >= min_frames:
        runs.append({"start": round(start / fps, 1),
                     "end": round(len(diffs) / fps, 1)})
    return runs


def _detect_freeze(video_path: str, fps: float = 2.0,
                   max_dur: float = 120.0) -> list[dict]:
    """2fps抽小帧→相邻差分→冻结段; 同通道顺带检测全屏黑段(black_gap)"""
    import json as _json
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_format", video_path],
                           capture_output=True, text=True, timeout=15)
        dur = min(float(_json.loads(r.stdout)["format"]["duration"]), max_dur)
    except Exception:
        return []
    tmp = tempfile.mkdtemp(prefix="fz_")
    pat = os.path.join(tmp, "f%04d.jpg").replace("\\", "/")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-t", str(dur), "-i", video_path,
                    "-vf", f"fps={fps},scale={_FRAME_W}:{_FRAME_H}",
                    "-q:v", "5", pat],
                   capture_output=True, timeout=120)
    from PIL import Image
    frames = sorted(f for f in os.listdir(tmp) if f.endswith(".jpg"))
    diffs, brightness, prev = [], [], None
    for f in frames:
        img = np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), dtype=float)
        brightness.append(float(img.mean()))
        if prev is not None:
            diffs.append(float(np.abs(img - prev).mean()))
        prev = img
    return _freeze_runs(diffs, fps) + _black_gaps(brightness, fps)


def _black_gaps(brightness: list[float], fps: float,
                dark_thr: float = 5.0, min_s: float = 0.5) -> list[dict]:
    """全屏亮度持续<dark_thr(≥min_s秒)→black_gap
    v3实测: B-roll素材黑尾播进成片0.5s——冻结(≥1.5s)和黑窗(<50%画面)都漏检"""
    min_frames = max(1, int(min_s * fps))
    runs, start = [], None
    for i, b in enumerate(brightness):
        if b < dark_thr:
            if start is None:
                start = i
        else:
            if start is not None and i - start >= min_frames:
                runs.append({"type": "black_gap", "start": round(start / fps, 1),
                             "end": round(i / fps, 1)})
            start = None
    if start is not None and len(brightness) - start >= min_frames:
        runs.append({"type": "black_gap", "start": round(start / fps, 1),
                     "end": round(len(brightness) / fps, 1)})
    return runs


def detect_freeze_artifacts(video_path: str) -> dict:
    """独立入口: 只查冻结"""
    runs = _detect_freeze(video_path)
    return {"clean": not runs, "artifacts": [
        {"type": "freeze", **r} for r in runs]}
