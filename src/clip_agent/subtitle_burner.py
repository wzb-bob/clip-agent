"""
字幕烧录 · SRT格式 · FFmpeg subtitles滤镜

改用SRT替代ASS: Windows上ASS滤镜路径解析有bug(original_size)。
SRT+force_style参数更可靠。
"""
from __future__ import annotations
import logging, os, subprocess, tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def burn_subtitles(video_path: str, segments: list[dict], output_path: str,
                   font_size: int = 20) -> str | None:
    if not segments:
        return None

    # 生成SRT字幕
    srt_path = tempfile.mktemp(suffix=".srt")
    _generate_srt(segments, srt_path)

    # FFmpeg subtitles滤镜(比ass滤镜Windows兼容性好)
    tmp = tempfile.mktemp(suffix=".mp4")
    safe_srt = srt_path.replace("\\", "/")
    try:
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-vf", f"subtitles='{safe_srt}':force_style='FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'",
            "-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","copy",
            tmp
        ], timeout=120)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, output_path)
            return output_path
    except Exception as e:
        logger.debug("字幕烧录跳过: %s", e)
    finally:
        for f in [srt_path, tmp]:
            try: os.remove(f)
            except: pass
    return None


def _generate_srt(segments: list[dict], output_path: str):
    """生成SRT字幕文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, s in enumerate(segments):
            start_sec = s.get("start_sec", s.get("start", 0))
            dur = s.get("duration_sec", s.get("duration", 2))
            end_sec = start_sec + dur
            text = s.get("text", s.get("text_overlay", ""))
            if not text:
                continue
            f.write(f"{i+1}\n")
            f.write(f"{_fmt_time(start_sec)} --> {_fmt_time(end_sec)}\n")
            f.write(f"{text}\n\n")


def _fmt_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _generate_ass(segments: list[dict], output_path: str, font_size: int):
    """生成ASS字幕文件·带完整样式头"""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,{font_size},&H00FFFFFF,&H000000FF,&H80000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,2,50,50,30,1
Style: SimHei,SimHei,{font_size},&H00FFFFFF,&H000000FF,&H80000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,2,50,50,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    cur_sec = 0.0

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            cur_sec += seg.get("duration", seg.get("duration_sec", 3.0))
            continue

        dur = seg.get("duration", seg.get("duration_sec", 3.0))
        start = seg.get("start_sec", cur_sec)
        end = start + dur

        start_ts = _sec_to_ass(start)
        end_ts = _sec_to_ass(end)

        # ASS事件行
        lines.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}")
        cur_sec = end

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _sec_to_ass(sec: float) -> str:
    """秒→ASS时间戳 H:MM:SS.cc"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
