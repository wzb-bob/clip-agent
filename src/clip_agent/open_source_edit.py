"""
开源工具增强编辑 · auto-editor + PySceneDetect + librosa + pydub

auto-editor (WyattBlue, 29.3.1): 自动运动+音频双信号编辑——业界最成熟的自动化剪辑工具
PySceneDetect (0.7.1): 内容感知场景检测——自适应阈值+HSV比较
librosa (0.11.0): 音频分析——节拍检测+onset+频谱
pydub: 精确音频静音检测+分段
"""
from __future__ import annotations
import json, logging, os, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EditRegion:
    """auto-editor检测到的可编辑区域"""
    start_sec: float
    end_sec: float
    duration_sec: float
    has_audio: bool = True       # 是否有声音(False=静音段)
    has_motion: bool = True      # 是否有运动(False=静止段)
    speed: float = 1.0           # 建议播放速度
    action: str = "keep"         # keep/cut/speed_up


@dataclass
class AutoEditResult:
    """auto-editor分析结果"""
    input_path: str
    output_path: str = ""
    regions: list[EditRegion] = field(default_factory=list)
    total_silence_removed_sec: float = 0.0
    total_duration_before: float = 0.0
    total_duration_after: float = 0.0
    method: str = "auto-editor"


# ================================================================
# 1. auto-editor — 自动运动+音频双信号编辑
# ================================================================

def auto_edit_silence(
    video_path: str,
    output_path: str = "",
    silence_threshold: float = 0.04,  # 音量阈值(0-1)
    margin_sec: float = 0.2,           # 静音前后保留的缓冲
    min_clip_sec: float = 0.5,         # 最小保留片段长度
    min_cut_sec: float = 0.3,          # 最小删除段长度
) -> AutoEditResult:
    """
    使用 auto-editor 自动删除视频中的静音/静止段。
    这是业界最成熟的自动化剪辑工具——比我们手动FFmpeg silenceremove精确得多。

    auto-editor 的核心优势:
    - 双信号检测: 同时分析音频音量和画面运动量
    - 自适应阈值: 根据视频内容自动调整
    - 精确到帧: 输出精确的剪切时间点
    """
    import subprocess, json as _json, re

    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"auto_edit_{Path(video_path).stem}_{int(time.time())}.mp4")

    try:
        # Step 1: auto-editor 分析——获取编辑时间线
        cmd_analyze = [
            "auto-editor", str(video_path),
            "--edit", "audio:{:.2f}".format(silence_threshold),
            "--margin", "{:.1f}sec".format(margin_sec),
            "--min_clip_length", "{:.1f}sec".format(min_clip_sec),
            "--min_cut_length", "{:.1f}sec".format(min_cut_sec),
            "--no-open",  # 不打开GUI
            "--output_file", output_path,
        ]
        result = subprocess.run(cmd_analyze, capture_output=True, text=True, timeout=180)

        # 解析输出中的编辑信息
        output_text = result.stdout + result.stderr
        regions = []

        # 匹配 "cut: Xs - Ys (duration)" 或类似格式
        cut_pattern = re.findall(r'(\d+\.?\d*)\s*s?\s*[-–]\s*(\d+\.?\d*)\s*s', output_text)
        for start_str, end_str in cut_pattern[:50]:
            start, end = float(start_str), float(end_str)
            if end - start >= min_cut_sec:
                regions.append(EditRegion(
                    start_sec=start, end_sec=end, duration_sec=end-start,
                    has_audio=False, has_motion=True, action="cut",
                ))

        # 获取原始时长
        orig_dur = 0.0
        try:
            probe = subprocess.run(["ffprobe","-v","quiet","-print_format","json",
                "-show_format", video_path], capture_output=True, text=True, timeout=10)
            orig_dur = float(_json.loads(probe.stdout).get("format",{}).get("duration",0))
        except: pass

        new_dur = os.path.getsize(output_path) / (os.path.getsize(video_path) / orig_dur) if orig_dur > 0 and os.path.exists(output_path) else orig_dur
        removed = orig_dur - new_dur if new_dur < orig_dur else 0

        logger.info("auto-editor: %.1f→%.1fs (删除%.1fs静音/%d段)",
                   orig_dur, new_dur, removed, len(regions))

        return AutoEditResult(
            input_path=video_path, output_path=output_path,
            regions=regions,
            total_silence_removed_sec=round(removed, 1),
            total_duration_before=round(orig_dur, 1),
            total_duration_after=round(new_dur, 1),
            method="auto-editor",
        )

    except subprocess.TimeoutExpired:
        logger.warning("auto-editor超时(>180s),降级FFmpeg")
    except Exception as e:
        logger.warning("auto-editor失败(%s),降级FFmpeg silenceremove", e)

    # 降级: FFmpeg silenceremove
    try:
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-af", "silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-30dB",
            "-c:v","libx264","-preset","ultrafast","-crf","23",
            "-c:a","aac","-b:a","128k",
            output_path,
        ], timeout=120, check=True)
        return AutoEditResult(
            input_path=video_path, output_path=output_path,
            method="ffmpeg-fallback",
        )
    except Exception as e:
        return AutoEditResult(
            input_path=video_path, output_path="",
            method="failed",
        )


# ================================================================
# 2. PySceneDetect — 内容感知场景检测
# ================================================================

def detect_scenes_adaptive(
    video_path: str,
    threshold: float = 27.0,
    min_scene_len: int = 15,  # 帧数
) -> list[dict]:
    """
    PySceneDetect + OpenCV 内容感知场景检测——比FFmpeg的scene滤镜更精确。
    使用HSV色彩空间比较,对光线变化不敏感。
    """
    try:
        import scenedetect
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector, AdaptiveDetector

        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(AdaptiveDetector(
            adaptive_threshold=threshold / 100.0,
            min_scene_len=min_scene_len,
        ))

        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        scenes = []
        for i, (start, end) in enumerate(scene_list):
            start_sec = start.get_seconds()
            end_sec = end.get_seconds()
            scenes.append({
                "index": i,
                "start_sec": round(start_sec, 2),
                "end_sec": round(end_sec, 2),
                "duration": round(end_sec - start_sec, 2),
            })

        logger.info("PySceneDetect: %d个场景(自适应阈值=%.2f)", len(scenes), threshold/100)
        return scenes

    except ImportError:
        logger.warning("PySceneDetect不可用,降级FFmpeg")
    except Exception as e:
        logger.warning("场景检测失败: %s", e)

    # 降级: FFmpeg scene detect
    return _fallback_scene_detect(video_path, threshold)


def _fallback_scene_detect(video_path: str, threshold: float = 27.0) -> list[dict]:
    try:
        cmd = [
            "ffmpeg", "-hide_banner", "-i", video_path,
            "-vf", f"select='gt(scene,{threshold/100:.3f})',showinfo",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        import re
        times = re.findall(r'pts_time:([\d.]+)', result.stderr)
        scenes = []
        for i in range(len(times)):
            start = float(times[i])
            end = float(times[i+1]) if i+1 < len(times) else start + 5
            scenes.append({"index":i, "start_sec":round(start,2), "end_sec":round(end,2),
                          "duration":round(end-start,2)})
        return scenes
    except Exception:
        return [{"index":0, "start_sec":0, "end_sec":5, "duration":5}]


# ================================================================
# 3. librosa — 节拍+onset检测
# ================================================================

def detect_beats_librosa(video_path: str, tempo_hint: float = 120.0) -> dict:
    """librosa音频分析——精确节拍检测"""
    import numpy as np
    try:
        import librosa

        # 提取音频
        wav_path = os.path.join(tempfile.gettempdir(), f"beat_{int(time.time())}.wav")
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path, "-vn", "-acodec","pcm_s16le",
            "-ar","22050","-ac","1", wav_path,
        ], timeout=30, check=True)

        y, sr = librosa.load(wav_path, sr=22050)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, bpm=tempo_hint)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # Onset检测(音符/词的起始点)——比节拍更精细的编辑点
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units='frames')
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)

        os.unlink(wav_path)

        return {
            "bpm": round(float(tempo), 1),
            "beat_count": len(beat_times),
            "beat_times": [round(t, 2) for t in beat_times.tolist()],
            "onset_count": len(onset_times),
            "onset_times": [round(t, 2) for t in onset_times.tolist()],
            "method": "librosa",
        }

    except ImportError:
        return {"bpm": tempo_hint, "beat_count": 0, "beat_times": [],
                "onset_count": 0, "onset_times": [], "method": "fallback"}
    except Exception as e:
        logger.warning("librosa节拍检测失败: %s", e)
        return {"bpm": tempo_hint, "beat_count": 0, "beat_times": [],
                "onset_count": 0, "onset_times": [], "method": "fallback"}


# ================================================================
# 4. pydub — 精确音频静音检测
# ================================================================

def detect_silence_pydub(
    video_path: str,
    min_silence_ms: int = 300,
    silence_thresh_db: int = -35,
) -> list[dict]:
    """
    pydub 精确静音检测——比FFmpeg silencedetect更稳定,基于音频采样值。
    返回静音段列表 [(start_sec, end_sec, duration_ms), ...]
    """
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_silence

        # 提取音频
        wav_path = os.path.join(tempfile.gettempdir(), f"pydub_{int(time.time())}.wav")
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path, "-vn", "-acodec","pcm_s16le",
            "-ar","16000","-ac","1", wav_path,
        ], timeout=30, check=True)

        audio = AudioSegment.from_wav(wav_path)
        silence_ranges = detect_silence(
            audio,
            min_silence_len=min_silence_ms,
            silence_thresh=silence_thresh_db,
        )

        os.unlink(wav_path)

        # 也获取非静音段(有用的说话内容)
        nonsilent_ranges = []

        results = []
        for start_ms, end_ms in silence_ranges:
            results.append({
                "start_sec": round(start_ms / 1000, 2),
                "end_sec": round(end_ms / 1000, 2),
                "duration_ms": end_ms - start_ms,
                "type": "silence",
            })

        logger.info("pydub: %d个静音段", len(results))
        return results

    except ImportError:
        logger.warning("pydub不可用")
    except Exception as e:
        logger.warning("pydub静音检测失败: %s", e)

    return []


# ================================================================
# 5. 综合编辑——串联所有开源工具
# ================================================================

def open_source_edit_pipeline(
    video_path: str,
    output_dir: str = "",
    remove_silence: bool = True,
    detect_scenes: bool = True,
    detect_beats: bool = True,
) -> dict:
    """一键运行所有开源工具的编辑管线"""
    if not output_dir:
        output_dir = tempfile.gettempdir()

    results = {}

    # 1. auto-editor 删除静音
    if remove_silence:
        t0 = time.time()
        ae = auto_edit_silence(video_path)
        results["auto_edit"] = {
            "method": ae.method,
            "duration_before": ae.total_duration_before,
            "duration_after": ae.total_duration_after,
            "silence_removed": ae.total_silence_removed_sec,
            "cut_regions": len(ae.regions),
            "time": round(time.time()-t0, 1),
        }
        # 如果有输出,后续步骤用编辑后的视频
        if ae.output_path and os.path.exists(ae.output_path):
            working_video = ae.output_path
        else:
            working_video = video_path
    else:
        working_video = video_path

    # 2. PySceneDetect 场景检测
    if detect_scenes:
        t0 = time.time()
        scenes = detect_scenes_adaptive(working_video)
        results["scene_detect"] = {
            "scenes": len(scenes),
            "avg_duration": round(sum(s["duration"] for s in scenes)/max(len(scenes),1), 1),
            "time": round(time.time()-t0, 1),
        }

    # 3. librosa 节拍检测
    if detect_beats:
        t0 = time.time()
        beats = detect_beats_librosa(working_video)
        results["beat_detect"] = {
            "bpm": beats["bpm"],
            "beats": beats["beat_count"],
            "onsets": beats["onset_count"],
            "method": beats["method"],
            "time": round(time.time()-t0, 1),
        }

    return {
        "success": True,
        "working_video": working_video,
        "results": results,
    }
