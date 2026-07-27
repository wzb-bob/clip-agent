"""
字幕烧录 · ASS格式 · FFmpeg原生支持

ASS格式比SRT更可靠:
- 原生支持样式(字号/颜色/边框/阴影)
- 不需force_style参数(避免Windows兼容问题)
- FFmpeg ass滤镜处理中文字体更稳定
"""
from __future__ import annotations
import logging, os, subprocess, tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def burn_subtitles(video_path: str, segments: list[dict], output_path: str,
                   font_size: int = 56) -> str | None:
    if not segments:
        return None

    # 1. 生成ASS字幕文件
    ass_path = tempfile.mktemp(suffix=".ass")
    _generate_ass(segments, ass_path, font_size)

    # 2. FFmpeg ass滤镜烧录
    tmp = tempfile.mktemp(suffix=".mp4")
    safe_ass = ass_path.replace("\\", "/")
    try:
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-vf", f"ass='{safe_ass}'",
            "-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","copy",
            tmp
        ], timeout=120)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, output_path)
            return output_path
    except Exception as e:
        logger.warning("ASS字幕烧录失败: %s", e)
    finally:
        for f in [ass_path, tmp]:
            try: os.remove(f)
            except: pass
    return None


def _generate_ass(segments: list[dict], output_path: str, font_size: int):
    """生成ASS字幕文件·带完整样式头"""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,{font_size},&H00FFFFFF,&H000000FF,&H80000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,2,50,50,30,1

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
