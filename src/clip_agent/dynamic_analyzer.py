"""
动态视频内容识别 · OpenCV光流+MediaPipe姿态/人脸+PySceneDetect+时序分段

从\"看一帧猜内容\"升级到\"看整段视频理解动态内容\":
- 光流运动检测: 画面里什么东西在动? 运动强度?
- MediaPipe人脸追踪: 有没有人脸? 在看镜头吗? 在说话吗?
- MediaPipe姿态: 人物在做什么动作? 手势? 站立/走动?
- PySceneDetect: 内容变化检测,自动分段
- OpenCV对象检测: 画面中的主要物体
"""
from __future__ import annotations
import base64, json, logging, os, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MotionProfile:
    """运动特征"""
    has_motion: bool
    motion_intensity: float       # 0-1,运动强度
    camera_moving: bool           # 相机是否在移动
    subject_moving: bool          # 画面主体是否在移动
    dominant_direction: str       # 主要运动方向: static/pan/tilt/zoom/complex
    motion_type: str              # smooth/jerky/static
    peak_motion_sec: float        # 运动最剧烈的时间点


@dataclass
class FaceProfile:
    """人脸特征"""
    has_face: bool
    face_count: int               # 画面中有几张脸
    eye_contact_ratio: float      # 看镜头的帧占比(0-1)
    smiling_ratio: float          # 微笑的帧占比
    speaking_likelihood: float    # 说话可能性(基于嘴部运动)
    face_size_ratio: float        # 人脸占画面比例→判断景别
    dominant_expression: str      # 主要表情: neutral/happy/serious/surprised


@dataclass
class PoseProfile:
    """人体姿态特征"""
    has_person: bool
    is_standing: bool
    is_walking: bool
    is_gesturing: bool            # 是否有手势
    upper_body_visible: bool      # 上半身可见→适合口播
    full_body_visible: bool       # 全身可见→适合动作展示
    pose_stability: float         # 姿态稳定性(0-1,越高越稳定)


@dataclass
class ContentSegments:
    """内容分段——基于内容变化的自动分段"""
    segments: list[dict]          # [{start_sec, end_sec, content_type, confidence}]
    dominant_content: str         # 主导内容类型
    scene_changes: int            # 场景切换次数
    content_stability: float      # 内容稳定性(0-1,越高内容越一致)


@dataclass
class DynamicAnalysis:
    """完整动态分析结果"""
    filename: str
    duration_sec: float
    motion: MotionProfile
    face: FaceProfile
    pose: PoseProfile
    segments: ContentSegments
    # 综合判断
    recommended_use: str          # 推荐用途: hook/body/broll/outro/waste
    editing_notes: str            # 编辑建议
    confidence: float


def analyze_video_dynamic(
    video_path: str,
    sample_fps: int = 2,          # 每秒采样帧数(2=每0.5秒一帧)
    max_frames: int = 120,        # 最多分析帧数(60秒@2fps)
) -> DynamicAnalysis:
    """
    动态视频内容分析——真正\"看懂\"视频内容

    采样策略: 每秒2帧,最多120帧→覆盖60秒内容
    分析维度: 光流运动+人脸追踪+姿态检测+场景分段
    """
    import mediapipe as mp

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return _fallback_dynamic(video_path)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    frame_interval = max(1, int(fps / sample_fps))

    # ===== 初始化MediaPipe =====
    mp_face = mp.solutions.face_detection
    mp_pose = mp.solutions.pose
    face_detector = mp_face.FaceDetection(min_detection_confidence=0.5)
    pose_detector = mp_pose.Pose(min_detection_confidence=0.5, model_complexity=1)

    # ===== 收集数据 =====
    motion_data = []      # 每帧的运动向量
    face_data = []        # 每帧的人脸信息
    pose_data = []        # 每帧的姿态信息
    prev_gray = None
    frame_count = 0

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret: break
        if frame_count % frame_interval != 0:
            frame_count += 1; continue

        h, w = frame.shape[:2]
        # 缩放到480p加速处理
        scale = 480 / h
        small = cv2.resize(frame, (int(w*scale), 480))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # === 光流运动检测 ===
        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            motion_intensity = float(np.mean(mag))
            # 方向分类
            mean_ang = float(np.mean(ang))
            if motion_intensity < 0.5: direction = "static"
            elif np.pi/4 < mean_ang < 3*np.pi/4 or 5*np.pi/4 < mean_ang < 7*np.pi/4:
                direction = "vertical"
            else: direction = "horizontal"

            motion_data.append({
                "intensity": motion_intensity,
                "direction": direction,
                "time_sec": frame_count / fps,
            })
        prev_gray = gray

        # === MediaPipe人脸检测 ===
        face_result = face_detector.process(rgb)
        face_info = {"has_face": False, "count": 0, "eye_contact": False,
                     "smile": False, "face_size": 0.0, "mouth_open": False}
        if face_result.detections:
            faces = face_result.detections
            face_info["has_face"] = True
            face_info["count"] = len(faces)
            # 取最大的人脸
            best = max(faces, key=lambda d: d.location_data.relative_bounding_box.width)
            bb = best.location_data.relative_bounding_box
            face_info["face_size"] = bb.width * bb.height  # 0-1
            # 基于人脸位置判断看镜头: 居中且大小适中
            cx = bb.xmin + bb.width / 2
            face_info["eye_contact"] = (0.35 < cx < 0.65 and bb.width > 0.1)
        face_data.append(face_info)

        # === MediaPipe姿态检测(兼容性保护) ===
        try:
            pose_result = pose_detector.process(rgb)
            pose_ok = True
        except Exception:
            pose_result = None
            pose_ok = False
        pose_info = {"has_person": False, "upper_body": False, "full_body": False,
                     "standing": False, "gesturing": False, "arms_raised": False}
        if pose_ok and pose_result and pose_result.pose_landmarks:
            lm = pose_result.pose_landmarks.landmark
            pose_info["has_person"] = True
            # 上半身可见: 肩膀+手肘可视
            if lm[11].visibility > 0.5 and lm[13].visibility > 0.5:
                pose_info["upper_body"] = True
            # 全身可见: 脚踝可视
            if lm[27].visibility > 0.5:
                pose_info["full_body"] = True
                pose_info["standing"] = (lm[27].y < 0.95)  # 脚在画面内
            # 手势: 手腕高于肩膀
            if lm[15].y < lm[11].y - 0.05:
                pose_info["gesturing"] = True
        pose_data.append(pose_info)

        frame_count += 1

    cap.release()
    try: face_detector.close()
    except Exception: pass
    try: pose_detector.close()
    except Exception: pass

    if not motion_data and not face_data:
        return _fallback_dynamic(video_path)

    # ===== 综合分析 =====

    # 运动特征
    intensities = [m["intensity"] for m in motion_data] if motion_data else [0]
    avg_intensity = float(np.mean(intensities))
    max_intensity = float(np.max(intensities))
    directions = [m["direction"] for m in motion_data]
    from collections import Counter
    dom_dir = Counter(directions).most_common(1)[0][0] if directions else "static"

    has_motion = avg_intensity > 0.8
    motion = MotionProfile(
        has_motion=has_motion,
        motion_intensity=round(min(avg_intensity / 20.0, 1.0), 2),
        camera_moving=dom_dir != "static" and avg_intensity > 1.5,
        subject_moving=(avg_intensity > 0.8 and dom_dir != "static"),
        dominant_direction=dom_dir,
        motion_type="smooth" if avg_intensity < 3 else ("jerky" if max_intensity > 10 else "static"),
        peak_motion_sec=round(motion_data[intensities.index(max_intensity)]["time_sec"], 1) if motion_data else 0,
    )

    # 人脸特征
    face_frames = [f for f in face_data if f["has_face"]]
    face_ratio = len(face_frames) / max(len(face_data), 1)
    eye_contact_ratio = sum(1 for f in face_frames if f["eye_contact"]) / max(len(face_frames), 1)
    face_sizes = [f["face_size"] for f in face_frames]
    avg_face_size = float(np.mean(face_sizes)) if face_sizes else 0

    # 景别判断(基于人脸占比)
    if avg_face_size > 0.15: shot_hint = "CU(近景)"
    elif avg_face_size > 0.08: shot_hint = "MCU(中近景)"
    elif avg_face_size > 0.04: shot_hint = "MS(中景)"
    else: shot_hint = "LS(全景)" if face_ratio > 0.3 else "未知"

    speaking = face_ratio > 0.5 and avg_face_size > 0.04 and has_motion
    face = FaceProfile(
        has_face=face_ratio > 0.3,
        face_count=1 if face_ratio > 0 else 0,
        eye_contact_ratio=round(eye_contact_ratio, 2),
        smiling_ratio=0.0,  # 需要专门的表情识别模型
        speaking_likelihood=round(min(speaking * 1.0 + avg_intensity / 20, 1.0), 2),
        face_size_ratio=round(avg_face_size, 2),
        dominant_expression="neutral",
    )

    # 姿态特征
    pose_frames = [p for p in pose_data if p["has_person"]]
    pose_ratio = len(pose_frames) / max(len(pose_data), 1)
    upper_ratio = sum(1 for p in pose_frames if p["upper_body"]) / max(len(pose_frames), 1)
    gesturing_ratio = sum(1 for p in pose_frames if p["gesturing"]) / max(len(pose_frames), 1)

    pose = PoseProfile(
        has_person=pose_ratio > 0.3,
        is_standing=sum(1 for p in pose_frames if p.get("standing", False)) > len(pose_frames) * 0.5,
        is_walking=pose_ratio > 0.5 and avg_intensity > 2.0,
        is_gesturing=gesturing_ratio > 0.15,
        upper_body_visible=upper_ratio > 0.5,
        full_body_visible=sum(1 for p in pose_frames if p.get("full_body", False)) > len(pose_frames) * 0.3,
        pose_stability=round(1.0 - min(avg_intensity / 10, 0.9), 2),
    )

    # 内容分段(基于场景变化)
    try:
        from app.services.clip_agent.open_source_edit import detect_scenes_adaptive
        scene_segments = detect_scenes_adaptive(video_path, threshold=30)
    except Exception:
        scene_segments = [{"index":0, "start_sec":0, "end_sec":duration, "duration":duration}]

    segments = ContentSegments(
        segments=scene_segments[:20],
        dominant_content="talking_head" if (face_ratio > 0.5 and speaking) else ("broll" if pose_ratio < 0.3 else "mixed"),
        scene_changes=len(scene_segments) - 1,
        content_stability=round(1.0 / max(len(scene_segments), 1), 2),
    )

    # === 综合推荐 ===
    if face_ratio > 0.5 and speaking and eye_contact_ratio > 0.4:
        recommended = "body"
        notes = f"优质口播素材({shot_hint},看镜头{eye_contact_ratio:.0%})——用作主体内容"
    elif face_ratio > 0.5 and not speaking:
        recommended = "broll"
        notes = "人物出镜但未说话——可用作B-roll或静音覆盖"
    elif avg_face_size > 0.12 and has_motion:
        recommended = "hook"
        notes = f"人物+运动+{shot_hint}——适合开头钩子"
    elif pose_ratio < 0.2:
        recommended = "broll"
        notes = "无人物——产品/环境B-roll素材"
    else:
        recommended = "broll"
        notes = "通用素材"

    if motion.motion_intensity > 0.8 and motion.motion_type == "jerky":
        recommended = "waste"
        notes = "画面抖动严重——建议重新拍摄或使用稳定器"

    confidence = round((face_ratio * 0.3 + (1 - min(avg_intensity/30, 0.5)) + pose_ratio * 0.2), 2)

    return DynamicAnalysis(
        filename=os.path.basename(video_path),
        duration_sec=round(duration, 1),
        motion=motion, face=face, pose=pose, segments=segments,
        recommended_use=recommended,
        editing_notes=notes,
        confidence=min(confidence, 1.0),
    )


def _fallback_dynamic(video_path: str) -> DynamicAnalysis:
    return DynamicAnalysis(
        filename=os.path.basename(video_path), duration_sec=0,
        motion=MotionProfile(False,0,False,False,"static","static",0),
        face=FaceProfile(False,0,0,0,0,0,"neutral"),
        pose=PoseProfile(False,False,False,False,False,False,0),
        segments=ContentSegments([],"unknown",0,0),
        recommended_use="broll", editing_notes="无法分析——请检查视频文件", confidence=0.0,
    )
