"""
数字人口播生成器 v1 · 照片+脚本→AI口播视频

独立模块 — 不依赖剪辑管线。输入一张照片和一段文案, 输出数字人说话视频。

模式:
  simple: OpenCV脸检测+Ken Burns动画+EdgeTTS语音 (轻量·秒级)
  advanced: SadTalker/Wav2Lip唇形同步 (需额外安装, 生产级)

用法:
  from .digital_human import create_talking_video
  result = create_talking_video("老板照片.jpg", "68块！十只活虾！...", mode="simple")
  → 输出: 口播视频.mp4 + 可送入剪辑管线
"""
from __future__ import annotations
import logging, os, subprocess, tempfile, time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


@dataclass
class DigitalHumanResult:
    """数字人视频生成结果"""
    success: bool
    video_path: str            # 生成的口播视频
    audio_path: str            # 生成的语音文件
    duration_sec: float
    mode: str                  # simple/advanced
    face_detected: bool
    error: str = ""


# ══════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════

def create_talking_video(
    photo_path: str,
    script_text: str,
    output_path: str = "",
    mode: str = "simple",
    voice: str = "",  # 空=按脚本类型自动选择
    width: int = 1080,
    height: int = 1920,
) -> DigitalHumanResult:
    """
    创建数字人口播视频。

    Args:
        photo_path: 人物照片路径
        script_text: 口播脚本文案
        output_path: 输出视频路径(默认自动生成)
        mode: "simple"(轻量动画) / "advanced"(唇形同步·需SadTalker)
        voice: EdgeTTS语音角色
        width, height: 视频分辨率

    Returns:
        DigitalHumanResult
    """
    vp = Path(photo_path)
    if not vp.exists():
        return DigitalHumanResult(False, "", "", 0, mode, False, "照片文件不存在")

    t0 = time.time()
    output = output_path or str(vp.parent / f"digital_human_{int(time.time())}.mp4")

    # 自动选声线
    if not voice:
        voice = _auto_select_voice(script_type)

    # Step 1: 生成语音
    audio_path = _generate_speech(script_text, voice)
    if not audio_path:
        return DigitalHumanResult(False, "", "", 0, mode, False, "语音生成失败")

    # 获取语音时长
    audio_dur = _get_audio_duration(audio_path)
    if audio_dur <= 0:
        audio_dur = len(script_text) * 0.25  # 估算

    # Step 2: 人脸检测
    face_detected = False
    face_bbox = None
    if HAS_CV2:
        face_bbox = _detect_face(str(vp))
        face_detected = face_bbox is not None

    # Step 3: 生成视频
    if mode == "advanced":
        success = _generate_lip_sync(str(vp), audio_path, output, width, height)
    else:
        success = _generate_simple_animation(str(vp), audio_path, output, width, height, audio_dur, face_bbox)

    elapsed = time.time() - t0
    logger.info("数字人: %s | %.1fs | 人脸=%s | 模式=%s",
               "✅" if success else "❌", elapsed, face_detected, mode)

    return DigitalHumanResult(
        success=success,
        video_path=output if success else "",
        audio_path=audio_path,
        duration_sec=audio_dur,
        mode=mode,
        face_detected=face_detected,
    )


# ══════════════════════════════════════════════════════════
# 内部实现
# ══════════════════════════════════════════════════════════

def _auto_select_voice(script_type: str) -> str:
    """脚本类型→最优声线"""
    voices = {
        "老板IP": "zh-CN-YunxiNeural",       # 男声·温暖可信
        "团购售卖": "zh-CN-XiaoxiaoNeural",   # 女声·活泼有冲击力
        "引流进店": "zh-CN-YunxiNeural",      # 男声·亲切自然
    }
    return voices.get(script_type, "zh-CN-XiaoxiaoNeural")


def _generate_speech(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> str:
    """语音合成 — 克隆声音优先→EdgeTTS降级"""
    try:
        from .voice_cloner import generate_speech as gen_speech
        # 尝试用克隆声音
        result = gen_speech(text, voice_id=voice, engine="auto")
        if result:
            return result
    except Exception:
        pass

    # EdgeTTS降级
    try:
        import asyncio
        import edge_tts

        async def _gen():
            tmp = tempfile.mktemp(suffix=".mp3")
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(tmp)
            return tmp

        return asyncio.run(_gen())
    except Exception as e:
        logger.warning("TTS失败: %s", e)
        return ""


def _get_audio_duration(audio_path: str) -> float:
    """FFprobe获取音频时长"""
    try:
        import json
        r = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json","-show_format", audio_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(json.loads(r.stdout).get("format", {}).get("duration", 0))
    except Exception:
        return 0


def _detect_face(photo_path: str):
    """人脸检测 — MediaPipe优先→OpenCV降级"""
    # Try MediaPipe (more accurate)
    try:
        import mediapipe as mp
        mp_face = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        img = cv2.imread(photo_path)
        if img is None:
            return None
        h, w = img.shape[:2]
        results = mp_face.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        if results.detections:
            det = results.detections[0]
            bbox = det.location_data.relative_bounding_box
            return {
                "x": int(bbox.xmin * w),
                "y": int(bbox.ymin * h),
                "w": int(bbox.width * w),
                "h": int(bbox.height * h),
            }
        mp_face.close()
    except ImportError:
        pass
    except Exception:
        pass

    # OpenCV Haar Cascade fallback
    try:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        img = cv2.imread(photo_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))
        if len(faces) > 0:
            x, y, w, h = faces[0]
            return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    except Exception:
        pass
    return None


def _generate_simple_animation(
    photo_path: str, audio_path: str, output: str,
    width: int, height: int, duration: float, face_bbox: dict = None,
) -> bool:
    """
    轻量动画模式:
    1. 人脸居中·放大裁剪(有脸) / 全图Ken Burns(无脸)
    2. 缓慢推进(模拟呼吸感)
    3. 叠加音频
    """
    try:
        if face_bbox:
            # 有人脸 → 裁剪到人脸区域+边距·居中放大
            fx, fy, fw, fh = face_bbox["x"], face_bbox["y"], face_bbox["w"], face_bbox["h"]
            # 人脸中心+50%边距
            cx, cy = fx + fw/2, fy + fh/2
            crop_w, crop_h = int(fw * 2.5), int(fh * 3.0)
            crop_x = max(0, int(cx - crop_w/2))
            crop_y = max(0, int(cy - crop_h/2))
            zoom_end = 1.08  # gentle zoom
            # 美颜: 轻度磨皮(smartblur)+提亮+暖色
            vf = (
                f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
                f"smartblur=lr=1.5:ls=0.8,"
                f"eq=brightness=0.03:contrast=1.02:saturation=1.05,"
                f"scale={width}:{height}:flags=lanczos,"
                f"zoompan=z='min(zoom+0.0003,{zoom_end})':d=1:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps=30,"
                f"fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.5}:d=0.5"
            )
        else:
            # 无脸 → 全图Ken Burns
            zoom_end = 1.1
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"zoompan=z='min(zoom+0.0003,{zoom_end})':d=1:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps=30,"
                f"fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.5}:d=0.5"
            )

        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-loop","1","-i", photo_path,
            "-i", audio_path,
            "-vf", vf,
            "-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","aac","-b:a","192k",
            "-t", str(duration),
            "-pix_fmt","yuv420p",
            output
        ], timeout=60)

        return os.path.exists(output) and os.path.getsize(output) > 0
    except Exception as e:
        logger.warning("简单动画失败: %s", e)
        return False


def _generate_lip_sync(photo_path: str, audio_path: str, output: str, width: int, height: int) -> bool:
    """
    高级唇形同步模式 — 依赖 SadTalker 或 Wav2Lip。

    安装: pip install sadtalker (需要PyTorch)
    当前为stub — 返回False触发降级。
    """
    try:
        # 尝试导入SadTalker
        import sadtalker
        logger.info("SadTalker可用 — 唇形同步模式")
        # SadTalker调用(需要模型文件...)
        # sadtalker.generate(photo_path, audio_path, output)
        return False  # stub: 需要模型下载配置
    except ImportError:
        logger.info("SadTalker未安装 — 降级简单动画")
        return False


# ══════════════════════════════════════════════════════════
# 集成入口: 数字人→剪辑管线
# ══════════════════════════════════════════════════════════

def create_and_clip(
    photo_path: str,
    script_text: str,
    script_type: str = "老板IP",
    output_dir: str = "",
    broll_videos: list[str] = None,
) -> dict:
    """
    一站式: 数字人生成 + 剪辑管线 = 完整成片。

    独立流程 — 不嵌入execution_engine。分两步:
    Step1: 照片→TTS→数字人动画视频
    Step2: 数字人视频→剪辑管线(加B-roll/字幕/BGM)

    容错: Step1成功但Step2失败→仍返回数字人视频
    """
    # Step 1: 数字人视频 (独立·不依赖剪辑管线)
    dh_result = create_talking_video(photo_path, script_text, mode="simple")
    if not dh_result.success:
        return {"success": False, "error": dh_result.error, "stage": "digital_human_failed"}

    # Step 2: 送入剪辑管线 (可选·失败不影响Step1产出)
    clip_success = False
    sentence_count = 0
    outdir = output_dir or str(Path(photo_path).parent / f"output_{int(time.time())}")

    try:
        from .execution_engine import quick_direct
        os.makedirs(outdir, exist_ok=True)

        video_slots = {1: dh_result.video_path}
        if broll_videos:
            for i, vf in enumerate(broll_videos):
                if os.path.exists(vf):
                    video_slots[i + 2] = vf

        job = quick_direct(
            script_text=script_text,
            script_type=script_type,
            audio_slots={1: dh_result.video_path},
            video_slots=video_slots,
            output_dir=outdir,
        )
        clip_success = job.status == "done"
        sentence_count = len(job.sentences)

        if clip_success:
            try:
                from .feedback_loop import learn_from_success
                quality = job.quality_report.get("score", 7)
                learn_from_success(script_type, "digital_human", "warm", "auto", quality)
            except Exception:
                pass
    except Exception as e:
        logger.warning("剪辑管线失败(数字人视频仍可用): %s", e)

    return {
        "success": dh_result.success,
        "clip_success": clip_success,
        "digital_human_video": dh_result.video_path,
        "edited_video": outdir if clip_success else dh_result.video_path,
        "duration": dh_result.duration_sec,
        "face_detected": dh_result.face_detected,
        "sentence_count": sentence_count,
        "stage": "complete" if clip_success else "digital_human_only",
    }
