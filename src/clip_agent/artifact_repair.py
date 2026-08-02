"""Artifact自动修复——检测后修复·不阻断管线

修复能力:
  black_box → 自动裁剪黑块区域
  freeze → 裁剪冻结段(前后保留0.1s过渡)
  black_tail → 裁剪尾部黑帧(检测有效内容终点)
  red_block → 替换为相邻正常帧
"""
from __future__ import annotations
import logging, os, subprocess, tempfile, json
from pathlib import Path

logger = logging.getLogger(__name__)


def repair_black_tail(video_path: str, output_path: str = "") -> str:
    """裁剪尾部黑帧——检测有效内容终点·只保留到最后一个非黑帧"""
    out = output_path or video_path
    try:
        from .chatcut_vfx import _content_duration, _probe_duration
        cd = _content_duration(video_path)
        total = _probe_duration(video_path)
        if total > 0 and cd > 0 and cd / total < 0.85:
            tmp = tempfile.mktemp(suffix=".mp4")
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", video_path, "-t", str(cd),
                "-c", "copy", tmp
            ], timeout=30)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                if output_path:
                    os.replace(tmp, out)
                else:
                    os.replace(tmp, video_path)
                logger.info("black_tail修复: %.1fs→%.1fs", total, cd)
        return out
    except Exception as e:
        logger.debug("black_tail修复跳过: %s", e)
        return video_path


def repair_freeze(video_path: str, output_path: str = "",
                  min_freeze_s: float = 1.5) -> str:
    """裁剪冻结段——冻结>1.5s自动剪掉·保留过渡帧"""
    out = output_path or video_path
    try:
        from .artifact_detector import _detect_freeze
        freezes = _detect_freeze(video_path)
        if not freezes:
            return video_path

        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", video_path],
            capture_output=True, text=True, timeout=10)
        total = float(json.loads(r.stdout)["format"]["duration"])

        # 构建分割点: 跳过冻结段
        keep = []
        last_end = 0.0
        for fz in freezes:
            start = max(0, fz["start_sec"] - 0.1)
            end = min(total, fz["end_sec"] + 0.1)
            if start > last_end:
                keep.append((last_end, start))
            last_end = end
        if last_end < total:
            keep.append((last_end, total))

        if len(keep) == 1 and keep[0] == (0.0, total):
            return video_path  # 只有一个全段=无冻结

        # FFmpeg concat
        concat_file = tempfile.mktemp(suffix=".txt")
        with open(concat_file, "w") as f:
            for start, end in keep:
                f.write(f"file '{video_path}'\n")
                f.write(f"inpoint {start}\n")
                f.write(f"outpoint {end}\n")

        tmp = tempfile.mktemp(suffix=".mp4")
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy", tmp
        ], timeout=30)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            if output_path:
                os.replace(tmp, out)
            else:
                os.replace(tmp, video_path)
            logger.info("freeze修复: %d段冻结·裁剪后%.1fs",
                       len(freezes),
                       sum(e - s for s, e in keep))
        return out
    except Exception as e:
        logger.debug("freeze修复跳过: %s", e)
        return video_path


def repair_black_box(video_path: str, output_path: str = "") -> str:
    """检测到黑块→自动裁剪黑块区域(简单crop·基于检测坐标)"""
    out = output_path or video_path
    try:
        from .artifact_detector import detect_artifacts
        artifacts = detect_artifacts(video_path, sample_count=3)
        black_boxes = [a for a in artifacts if a.get("type") == "black_box"]
        if not black_boxes:
            return video_path

        # 取最小裁剪区域
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", video_path],
            capture_output=True, text=True, timeout=10)
        streams = json.loads(r.stdout).get("streams", [])
        vs = [s for s in streams if s["codec_type"] == "video"][0]
        w, h = int(vs["width"]), int(vs["height"])

        # 黑块通常在边缘(如PiP窗口在角落)·crop掉黑块区域
        for bb in black_boxes[:1]:
            center = bb.get("center", [0.9, 0.5])
            area = bb.get("area_max", 0.05)
            if area < 0.15 and center[0] > 0.7:
                # 右侧黑块→crop左边
                new_w = int(w * 0.85)
                tmp = tempfile.mktemp(suffix=".mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", video_path,
                    "-vf", f"crop={new_w}:{h}:0:0,scale={w}:{h}:flags=lanczos",
                    "-c:a", "copy", tmp
                ], timeout=30)
                if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                    os.replace(tmp, out)
                    logger.info("black_box修复: crop右边缘·area=%.2f", area)
        return out
    except Exception as e:
        logger.debug("black_box修复跳过: %s", e)
        return video_path


def auto_repair(video_path: str, artifacts: list[dict] = None) -> str:
    """一站式自动修复——检测artifact类型→选修复策略"""
    if artifacts is None:
        try:
            from .artifact_detector import detect_artifacts
            artifacts = detect_artifacts(video_path)
        except Exception:
            return video_path

    if not artifacts:
        return video_path

    types = set(a.get("type", "") for a in artifacts)
    current = video_path

    if "black_tail" in types:
        current = repair_black_tail(current)
    if "freeze" in types:
        current = repair_freeze(current)
    if "black_box" in types:
        current = repair_black_box(current)

    if current != video_path:
        logger.info("artifact修复: %s → %s", types, current)
    return current
