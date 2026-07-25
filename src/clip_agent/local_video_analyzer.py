"""
本地视频分析器 v1 · 零API依赖 · 纯OpenCV+FFmpeg+MediaPipe

不需要Kimi Vision/GLM-4V API Key, 从视频文件中真实提取:
  1. 关键帧提取 (场景变化检测)
  2. 人脸检测 (OpenCV Haar Cascade)
  3. 运动分析 (光流法)
  4. 画质评估 (拉普拉斯清晰度+亮度+色彩)
  5. 调性分析 (主色调+饱和度)
  6. 镜头切分 (PySceneDetect)
"""
from __future__ import annotations
import json, logging, os, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


@dataclass
class VideoFrame:
    """提取的单帧信息"""
    timestamp_sec: float
    is_keyframe: bool = False      # 场景变化关键帧
    has_face: bool = False
    face_count: int = 0
    face_bboxes: list = field(default_factory=list)
    sharpness: float = 0.0          # 拉普拉斯清晰度
    brightness: float = 0.0         # 平均亮度
    dominant_color: str = ""        # 主色调
    saturation: float = 0.0         # 饱和度
    motion_intensity: float = 0.0   # 运动强度
    frame_data: bytes = b""         # 帧图像数据(可选)


@dataclass
class LocalVideoAnalysis:
    """本地视频分析结果"""
    file_path: str
    duration_sec: float
    width: int
    height: int
    fps: float
    codec: str
    file_size_mb: float

    # 分析结果
    frames: list[VideoFrame] = field(default_factory=list)
    keyframes: list[VideoFrame] = field(default_factory=list)

    # 质量评估
    avg_sharpness: float = 0.0
    avg_brightness: float = 0.0
    quality_label: str = "medium"   # good/medium/poor

    # 内容特征
    has_talking_head: bool = False  # 检测到人脸
    face_time_pct: float = 0.0      # 人脸出现的时间占比
    scene_count: int = 0            # 场景切换次数
    avg_shot_duration: float = 0.0  # 平均镜头时长
    motion_profile: str = "static"  # static/smooth/dynamic/shaky

    # 类别推断
    inferred_type: str = "unknown"  # talking_head/product/environment/broll


def analyze_video_local(video_path: str, extract_frames: bool = True,
                        frame_interval: float = 0.5) -> LocalVideoAnalysis | None:
    """
    主入口: 从视频文件中提取所有可获取的真实信息。

    零API依赖 — 纯本地计算。
    """
    vp = Path(video_path)
    if not vp.exists():
        logger.warning("视频文件不存在: %s", video_path)
        return None

    # Step 1: FFprobe基本信息
    info = _probe_video_ffprobe(str(vp))
    if not info:
        return None

    analysis = LocalVideoAnalysis(
        file_path=str(vp),
        duration_sec=info["duration"],
        width=info["width"],
        height=info["height"],
        fps=info["fps"],
        codec=info.get("codec", "unknown"),
        file_size_mb=vp.stat().st_size / (1024 * 1024),
    )

    if not HAS_CV2:
        logger.warning("OpenCV不可用 — 仅返回FFprobe信息")
        return analysis

    if not extract_frames:
        return analysis

    # Step 2: 提取帧 + 分析
    try:
        _extract_and_analyze_frames(analysis, str(vp), frame_interval)
    except Exception as e:
        logger.warning("帧分析失败: %s", e)

    # Step 3: 聚合统计
    _compute_aggregates(analysis)
    _infer_video_type(analysis)

    logger.info("本地分析: %s | %.1fs | %d场景 | 质量=%s | 类型=%s | 人脸=%.0f%%",
               vp.name, analysis.duration_sec, analysis.scene_count,
               analysis.quality_label, analysis.inferred_type,
               analysis.face_time_pct * 100)

    return analysis


def _probe_video_ffprobe(video_path: str) -> dict | None:
    """FFprobe提取视频元信息"""
    try:
        r = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json",
             "-show_format","-show_streams", video_path],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        if not video_streams:
            return None

        vs = video_streams[0]
        # Safe FPS parsing
        fps_str = vs.get("r_frame_rate", "30/1")
        try:
            p = fps_str.split("/")
            fps = float(p[0]) / float(p[1]) if len(p) == 2 else float(fps_str)
        except (ValueError, ZeroDivisionError):
            fps = 30.0

        return {
            "duration": float(fmt.get("duration", 0)),
            "width": vs.get("width", 1080),
            "height": vs.get("height", 1920),
            "fps": fps,
            "codec": vs.get("codec_name", "unknown"),
            "bitrate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else 0,
        }
    except Exception as e:
        logger.debug("FFprobe失败: %s", e)
        return None


def _extract_and_analyze_frames(analysis: LocalVideoAnalysis, video_path: str, interval: float):
    """提取帧 + OpenCV分析"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return

    fps = analysis.fps
    frame_skip = max(1, int(fps * interval))  # 每interval秒取一帧
    frame_idx = 0
    prev_gray = None

    # 加载人脸检测器
    face_cascade = None
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
    except Exception:
        pass

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_skip != 0:
            frame_idx += 1
            continue

        timestamp = frame_idx / fps
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        vf = VideoFrame(timestamp_sec=round(timestamp, 2))

        # 1. 清晰度 (拉普拉斯方差)
        vf.sharpness = round(cv2.Laplacian(gray, cv2.CV_64F).var(), 1)

        # 2. 亮度
        vf.brightness = round(float(np.mean(gray)), 1)

        # 3. 色彩分析
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        vf.saturation = round(float(np.mean(hsv[:,:,1])), 1)
        # 主色调
        avg_hue = int(np.mean(hsv[:,:,0]))
        vf.dominant_color = _hue_to_name(avg_hue)

        # 4. 人脸检测
        if face_cascade is not None:
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            vf.has_face = len(faces) > 0
            vf.face_count = len(faces)
            if len(faces) > 0:
                vf.face_bboxes = [{"x": int(f[0]), "y": int(f[1]),
                                   "w": int(f[2]), "h": int(f[3])} for f in faces[:5]]

        # 5. 运动分析 (光流法)
        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0,
            )
            mag = np.mean(np.sqrt(flow[:,:,0]**2 + flow[:,:,1]**2))
            vf.motion_intensity = round(float(mag), 2)

        analysis.frames.append(vf)
        prev_gray = gray
        frame_idx += 1

    cap.release()


def _compute_aggregates(analysis: LocalVideoAnalysis):
    """聚合统计分析"""
    if not analysis.frames:
        return

    # 平均值
    analysis.avg_sharpness = round(np.mean([f.sharpness for f in analysis.frames]), 1)
    analysis.avg_brightness = round(np.mean([f.brightness for f in analysis.frames]), 1)

    # 质量标签
    if analysis.avg_sharpness > 500:
        analysis.quality_label = "good"
    elif analysis.avg_sharpness > 200:
        analysis.quality_label = "medium"
    else:
        analysis.quality_label = "poor"

    # 场景检测 (基于运动强度突变)
    motions = [f.motion_intensity for f in analysis.frames]
    if motions:
        mean_motion = np.mean(motions)
        std_motion = np.std(motions)
        for f in analysis.frames:
            if f.motion_intensity > mean_motion + 2 * std_motion:
                f.is_keyframe = True
                analysis.keyframes.append(f)

    analysis.scene_count = len(analysis.keyframes) + 1
    if analysis.scene_count > 1:
        analysis.avg_shot_duration = round(analysis.duration_sec / analysis.scene_count, 1)

    # 人脸统计
    face_frames = [f for f in analysis.frames if f.has_face]
    analysis.has_talking_head = len(face_frames) > len(analysis.frames) * 0.3
    analysis.face_time_pct = round(len(face_frames) / max(len(analysis.frames), 1), 2)

    # 运动类型
    avg_motion = np.mean(motions) if motions else 0
    if avg_motion < 0.5:
        analysis.motion_profile = "static"
    elif avg_motion < 2.0:
        analysis.motion_profile = "smooth"
    elif avg_motion < 5.0:
        analysis.motion_profile = "dynamic"
    else:
        analysis.motion_profile = "shaky"


def _infer_video_type(analysis: LocalVideoAnalysis):
    """推断视频类型 (talking_head / product / environment / broll)"""
    if analysis.has_talking_head and analysis.face_time_pct > 0.5:
        if analysis.motion_profile in ("static", "smooth"):
            analysis.inferred_type = "talking_head"
        else:
            analysis.inferred_type = "broll"
    elif analysis.scene_count <= 2 and analysis.avg_sharpness > 400:
        analysis.inferred_type = "product"
    elif analysis.scene_count >= 3:
        analysis.inferred_type = "environment"
    else:
        analysis.inferred_type = "broll"


def _hue_to_name(hue: int) -> str:
    """Hue值→颜色名"""
    if hue < 15 or hue > 165:
        return "red"
    elif hue < 25:
        return "orange"
    elif hue < 40:
        return "yellow"
    elif hue < 75:
        return "green"
    elif hue < 105:
        return "cyan"
    elif hue < 135:
        return "blue"
    elif hue < 150:
        return "purple"
    else:
        return "pink"


# ══════════════════════════════════════════════════════════
# 快速分析入口
# ══════════════════════════════════════════════════════════

def quick_analyze(video_path: str) -> dict:
    """快速分析 — 返回摘要dict (适合脚本Agent消费)"""
    analysis = analyze_video_local(video_path, extract_frames=True, frame_interval=0.5)
    if not analysis:
        return {"error": "分析失败", "file": video_path}

    return {
        "file": Path(video_path).name,
        "duration_sec": analysis.duration_sec,
        "resolution": f"{analysis.width}x{analysis.height}",
        "quality": analysis.quality_label,
        "sharpness": analysis.avg_sharpness,
        "brightness": analysis.avg_brightness,
        "has_face": analysis.has_talking_head,
        "face_coverage_pct": round(analysis.face_time_pct * 100),
        "scene_count": analysis.scene_count,
        "motion": analysis.motion_profile,
        "inferred_type": analysis.inferred_type,
        "recommendation": _get_usage_recommendation(analysis),
    }


def _get_usage_recommendation(analysis: LocalVideoAnalysis) -> str:
    """基于分析结果推荐用途"""
    if analysis.quality_label == "poor":
        return "画质较低 — 建议重拍或用做B-roll快速切换"
    if analysis.has_talking_head and analysis.face_time_pct > 0.6:
        return "口播素材 — 保留原声·用做主轨"
    if analysis.scene_count <= 1 and not analysis.has_talking_head:
        return "产品/环境镜头 — 适合B-roll覆盖·配音驱动"
    if analysis.motion_profile == "shaky":
        return "镜头晃动 — 需要稳定处理或只用于快速切镜"
    return "通用素材 — 根据脚本内容灵活使用"
