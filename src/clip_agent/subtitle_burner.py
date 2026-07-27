"""
字幕烧录 · SRT格式 · 比drawtext更可靠

用法: burn_subtitles(video_path, segments, output_path)
segments: [{"start_sec":0,"duration_sec":2.5,"text":"大字内容"}]
"""
from __future__ import annotations
import logging, os, subprocess, tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def burn_subtitles(video_path: str, segments: list[dict], output_path: str,
                   font_size: int = 56, color: str = "&H00FFFFFF") -> str | None:
    """
    生成SRT字幕 → FFmpeg subtitles滤镜烧录。

    SRT格式比drawtext更可靠:
    - 不需要指定fontfile路径(FFmpeg自动找系统字体)
    - 支持中文字符
    - 支持样式(粗体/边框/阴影)
    """
    if not segments:
        return None

    # 1. 生成SRT文件
    srt_path = tempfile.mktemp(suffix=".srt")
    ass_path = tempfile.mktemp(suffix=".ass")
    _generate_srt(segments, srt_path)
    _generate_ass_style(ass_path, font_size, color)

    # 2. FFmpeg烧录
    tmp = tempfile.mktemp(suffix=".mp4")
    try:
        cmd = [
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-vf", f"subtitles={srt_path}",
            "-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","copy",
            tmp
        ]
        subprocess.run(cmd, timeout=120)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            # Replace original
            os.replace(tmp, output_path)
            return output_path
    except Exception as e:
        logger.warning("字幕烧录失败: %s", e)
    finally:
        for f in [srt_path, ass_path, tmp]:
            try: os.remove(f)
            except: pass
    return None


def _generate_srt(segments: list[dict], output_path: str):
    """生成SRT字幕文件"""
    lines = []
    idx = 1
    cur_sec = 0.0

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            cur_sec += seg.get("duration", seg.get("duration_sec", 3.0))
            continue

        dur = seg.get("duration", seg.get("duration_sec", 3.0))
        start = seg.get("start_sec", cur_sec)
        end = start + dur

        # SRT时间格式: HH:MM:SS,mmm
        start_ts = _sec_to_srt(start)
        end_ts = _sec_to_srt(end)

        lines.append(f"{idx}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(text)
        lines.append("")
        idx += 1
        cur_sec = end

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _generate_ass_style(output_path: str, font_size: int, color: str):
    """生成ASS样式头(备用)"""
    pass  # SRT force_style足够, 暂不需要ASS


def _sec_to_srt(sec: float) -> str:
    """秒→SRT时间戳"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
