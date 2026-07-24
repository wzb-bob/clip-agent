"""
专业级音视频处理 · 降噪+音量归一化+变速+分屏+水印+画中画
全部基于 FFmpeg,无外部依赖
"""
from __future__ import annotations
import logging, os, subprocess, tempfile, time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ================================================================
# 1. 音频降噪 + 音量归一化
# ================================================================

def audio_denoise(
    video_path: str, output_path: str = "",
    strength: float = 0.5,       # 0-1 降噪强度
) -> dict:
    """FFmpeg音频降噪——afftdn + 高通滤波"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"denoise_{Path(video_path).stem}_{int(time.time())}.mp4")
    try:
        # afftdn=FFT降噪, highpass=去掉低频噪声(空调/风声)
        noise_reduction = min(max(strength, 0.01), 0.97)
        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-af", f"afftdn=nr={noise_reduction:.2f}:nf=-25,highpass=f=80",
            "-c:v","copy",
            "-c:a","aac","-b:a","192k",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path, "strength": strength}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def audio_normalize(
    video_path: str, output_path: str = "",
    target_level: float = -16.0,  # LUFS目标响度(行业标准: -16 for TV, -14 for streaming)
) -> dict:
    """音量归一化到行业标准响度——loudnorm EBU R128"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"norm_{Path(video_path).stem}_{int(time.time())}.mp4")
    try:
        # 第一遍: 分析原始响度
        probe = subprocess.run([
            "ffmpeg","-i",video_path,
            "-af",f"loudnorm=I={target_level}:TP=-1.5:LRA=11:print_format=json",
            "-f","null","-",
        ], capture_output=True, text=True, timeout=30)

        # 第二遍: 应用归一化
        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-af", f"loudnorm=I={target_level}:TP=-1.5:LRA=11:linear=true",
            "-c:v","copy",
            "-c:a","aac","-b:a","192k",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path, "target_lufs": target_level}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 2. 变速——慢动作/快进 + 速度渐变
# ================================================================

def speed_ramp(
    video_path: str, output_path: str = "",
    speed_start: float = 0.5,    # 起始速度(0.5=2x慢动作)
    speed_end: float = 1.0,      # 结束速度(1.0=正常)
    duration_sec: float = 2.0,   # 变速过渡时长
) -> dict:
    """速度渐变——开头慢动作逐渐恢复正常,电影感转场"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"ramp_{Path(video_path).stem}_{int(time.time())}.mp4")

    # setpts变速 + 音频atempo
    speed_expr = f"if(lt(t,{duration_sec}), 1/({speed_start}+({speed_end-speed_start})*t/{duration_sec}), 1)"
    atempo_expr = f"if(lt(t,{duration_sec}), {speed_start}+({speed_end-speed_start})*t/{duration_sec}, 1)"

    try:
        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-filter_complex",
            f"[0:v]setpts={speed_expr}*PTS[v];[0:a]atempo={atempo_expr}[a]",
            "-map","[v]","-map","[a]",
            "-c:v","libx264","-preset","medium","-crf","23",
            "-c:a","aac","-b:a","192k",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path, "speed_range": f"{speed_start}-{speed_end}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def change_speed(
    video_path: str, output_path: str = "",
    speed: float = 1.5,          # 1.5x快进 / 0.5x慢动作
) -> dict:
    """恒定变速——整段快进或慢动作"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"speed{speed}x_{Path(video_path).stem}_{int(time.time())}.mp4")
    try:
        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-filter_complex",
            f"[0:v]setpts={1/speed}*PTS[v];[0:a]atempo={speed}[a]",
            "-map","[v]","-map","[a]",
            "-c:v","libx264","-preset","medium","-crf","23",
            "-c:a","aac","-b:a","192k",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path, "speed": speed}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 3. 分屏——左右对比/上下对比
# ================================================================

def split_screen(
    video1: str, video2: str, output_path: str = "",
    layout: str = "horizontal",  # horizontal=左右, vertical=上下, pip=画中画
) -> dict:
    """分屏对比——左右/上下并排两个视频"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"splitscreen_{int(time.time())}.mp4")

    try:
        if layout == "horizontal":
            # 左右分屏: 每个视频缩放到一半宽度
            vf = "[0:v]scale=540:1920,pad=1080:1920:0:0[left];[1:v]scale=540:1920,pad=1080:1920:540:0[right];[left][right]overlay=0:0"
        elif layout == "vertical":
            # 上下分屏
            vf = "[0:v]scale=1080:960,pad=1080:1920:0:0[top];[1:v]scale=1080:960,pad=1080:1920:0:960[bottom];[top][bottom]overlay=0:0"
        elif layout == "pip":
            # 画中画: video2在右下角
            vf = "[1:v]scale=360:640[pip];[0:v][pip]overlay=W-w-20:H-h-20"

        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video1, "-i", video2,
            "-filter_complex", vf,
            "-c:v","libx264","-preset","medium","-crf","23",
            "-c:a","aac","-b:a","128k",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path, "layout": layout}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 4. 水印
# ================================================================

def add_watermark(
    video_path: str, output_path: str = "",
    text: str = "@长益AI剪辑",
    position: str = "bottom-right",  # bottom-right/top-left/center
    font_size: int = 32,
    opacity: float = 0.5,
) -> dict:
    """添加文字水印"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"wm_{Path(video_path).stem}_{int(time.time())}.mp4")

    positions = {
        "bottom-right": "x=W-tw-20:y=H-th-20",
        "top-left": "x=20:y=20",
        "top-right": "x=W-tw-20:y=20",
        "bottom-left": "x=20:y=H-th-20",
        "center": "x=(W-tw)/2:y=(H-th)/2",
    }
    pos_expr = positions.get(position, positions["bottom-right"])

    try:
        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-vf", f"drawtext=text='{text}':fontsize={font_size}:fontcolor=white@{opacity}:{pos_expr}:bordercolor=black@0.3:borderw=1",
            "-c:v","libx264","-preset","ultrafast","-crf","23",
            "-c:a","copy",
            output_path,
        ]
        subprocess.run(cmd, timeout=60, check=True)
        return {"success": True, "output": output_path, "text": text}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 5. 视频质量增强
# ================================================================

def enhance_video(
    video_path: str, output_path: str = "",
    sharpen: float = 0.5,        # 锐化强度
    contrast: float = 1.1,       # 对比度
    saturation: float = 1.1,     # 饱和度
    brightness: float = 0.02,    # 亮度
) -> dict:
    """视频质量一键增强——锐化+对比度+饱和度"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"enhanced_{Path(video_path).stem}_{int(time.time())}.mp4")

    vf = (f"unsharp=luma_msize_x=3:luma_msize_y=3:luma_amount={sharpen},"
          f"eq=contrast={contrast}:saturation={saturation}:brightness={1+brightness}")

    try:
        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-vf", vf,
            "-c:v","libx264","-preset","medium","-crf","23",
            "-c:a","copy",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 6. 一键全流程——专业级后期处理
# ================================================================

def pro_post_process(
    video_path: str,
    output_dir: str = "",
    denoise: bool = True,
    normalize_audio: bool = True,
    enhance: bool = True,
    watermark_text: str = "",
) -> dict:
    """一键专业后期处理: 降噪→音量归一化→画质增强→加水印"""
    if not output_dir:
        output_dir = tempfile.gettempdir()

    working = video_path
    steps = []

    # 1. 降噪
    if denoise:
        r = audio_denoise(working)
        if r["success"]:
            working = r["output"]
            steps.append("denoise")

    # 2. 音量归一化
    if normalize_audio:
        r = audio_normalize(working)
        if r["success"]:
            working = r["output"]
            steps.append("normalize")

    # 3. 画质增强
    if enhance:
        r = enhance_video(working)
        if r["success"]:
            working = r["output"]
            steps.append("enhance")

    # 4. 水印
    if watermark_text:
        r = add_watermark(working, text=watermark_text)
        if r["success"]:
            working = r["output"]
            steps.append("watermark")

    return {
        "success": True,
        "output": working,
        "steps_applied": steps,
        "original": video_path,
    }
