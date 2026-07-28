"""
Whisper→SRT字幕生成器 v1 · 彻底解决字幕问题

不再依赖剪映会员的智能包装——直接在生成草稿时产出SRT字幕文件。
Whisper word-level timestamps → 智能分组 → SRT格式 → 烧录或嵌入草稿
"""
from __future__ import annotations
import logging, os, tempfile, time
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_srt_from_video(video_path: str, output_path: str = "",
                            max_chars_per_line: int = 18,
                            min_duration_ms: int = 800,
                            expected_script: str = "") -> str | None:
    """
    从视频文件生成SRT字幕。

    Args:
        video_path: 口播视频路径
        output_path: SRT输出路径(默认和视频同目录)
        max_chars_per_line: 每行最大字数(短视频建议15-20)
        min_duration_ms: 每段最小显示时长(ms)

    Returns:
        SRT文件路径, None=失败
    """
    vp = Path(video_path)
    if not vp.exists():
        return None

    out = Path(output_path) if output_path else vp.with_suffix(".srt")

    try:
        import whisper

        t0 = time.time()
        model = whisper.load_model("small")
        result = model.transcribe(str(vp), word_timestamps=True)
        elapsed = time.time() - t0

        # 提取词级时间戳
        words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                word_text = w.get("word", "").strip()
                if word_text:
                    words.append({
                        "word": word_text,
                        "start": w.get("start", 0),
                        "end": w.get("end", 0),
                    })

        if not words:
            logger.warning("Whisper未提取到词级数据")
            return None

        # 🆕 转录修正: DeepSeek对齐预期脚本
        if expected_script:
            try:
                from .transcript_corrector import correct_transcript, align_transcript_to_timestamps
                whisper_full = "".join(w["word"] for w in words)
                corrected = correct_transcript(whisper_full, expected_script)
                if corrected and len(corrected) > 10:
                    words = align_transcript_to_timestamps(corrected, words)
                    logger.info("转录修正: DeepSeek对齐完成")
            except Exception:
                pass

        # 智能分组: 每行最多max_chars_per_line字, 在标点处断行
        groups = _group_words_to_lines(words, max_chars_per_line, min_duration_ms)

        # 生成SRT
        srt_lines = []
        for i, g in enumerate(groups, 1):
            start_ts = _sec_to_srt(g["start"])
            end_ts = _sec_to_srt(g["end"])
            srt_lines.append(str(i))
            srt_lines.append(f"{start_ts} --> {end_ts}")
            srt_lines.append(g["text"])
            srt_lines.append("")

        out.write_text("\n".join(srt_lines), encoding="utf-8")
        logger.info("SRT生成: %d条·%d词·%.1fs", len(groups), len(words), elapsed)
        return str(out)

    except Exception as e:
        logger.warning("SRT生成失败: %s", e)
        return None


def _group_words_to_lines(words: list[dict], max_chars: int, min_ms: int) -> list[dict]:
    """将词列表智能分组为字幕行"""
    groups = []
    current = {"words": [], "start": words[0]["start"], "end": 0}

    for w in words:
        current_text = "".join(g["word"] for g in current["words"])
        if len(current_text) + len(w["word"]) > max_chars and current["words"]:
            # 当前行满了，保存并开始新行
            duration_ms = (current["words"][-1]["end"] - current["start"]) * 1000
            if duration_ms >= min_ms:
                groups.append({
                    "start": current["start"],
                    "end": current["words"][-1]["end"],
                    "text": "".join(g["word"] for g in current["words"]),
                })
            current = {"words": [w], "start": w["start"], "end": w["end"]}
        else:
            current["words"].append(w)
            current["end"] = w["end"]

        # 标点处强制断行
        if w["word"] in ("。", "！", "？", ".", "!", "?", "，", ","):
            duration_ms = (current["end"] - current["start"]) * 1000
            if duration_ms >= min_ms and len(current["words"]) >= 2:
                groups.append({
                    "start": current["start"],
                    "end": current["end"],
                    "text": "".join(g["word"] for g in current["words"]),
                })
                current = {"words": [], "start": current["end"], "end": current["end"]}

    # 最后一行
    if current["words"]:
        groups.append({
            "start": current["start"],
            "end": current["words"][-1]["end"],
            "text": "".join(g["word"] for g in current["words"]),
        })

    return groups


def _sec_to_srt(sec: float) -> str:
    """秒→SRT时间戳 HH:MM:SS,mmm"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def burn_srt_to_video(video_path: str, srt_path: str, output_path: str) -> str | None:
    """将SRT字幕烧录到视频中"""
    if not os.path.exists(srt_path):
        return None

    safe_srt = srt_path.replace("\\", "/")
    try:
        import subprocess
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path,
            "-vf", f"subtitles='{safe_srt}':force_style='FontSize=48,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,Outline=3,Shadow=2'",
            "-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","copy",
            output_path
        ], timeout=300)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except Exception as e:
        logger.warning("SRT烧录失败: %s", e)
    return None
