"""
Whisper→SRT字幕生成器 v1 · 彻底解决字幕问题

不再依赖剪映会员的智能包装——直接在生成草稿时产出SRT字幕文件。
Whisper word-level timestamps → 智能分组 → SRT格式 → 烧录或嵌入草稿
"""
from __future__ import annotations
import logging, os, re, tempfile, time
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

        # 🆕 开机口令剔除: "三二走/三二一/开拍"等倒数不进字幕
        words, slate_end = _strip_slate_words(words)
        if slate_end > 0:
            logger.info("检测到开机口令, 已剔除 (%.2fs前)", slate_end)
        if not words:
            logger.warning("剔除口令后无剩余词")
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

        # 🆕 短语边界打标: LLM标记意群边界, 断行不拆词(失败静默跳过)
        words = _mark_phrase_breaks(words)

        # 🆕 孤立残词过滤: 长静音后的短碎片(如结尾"好")不进字幕
        words = _drop_isolated_fragments(words)
        if not words:
            logger.warning("过滤残词后无剩余词")
            return None

        # 智能分组: 每行最多max_chars_per_line字, 标点/停顿处断行
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


# 开机口令模式: 倒数/打板类, 只在开场几秒内匹配
_SLATE_PATTERNS = [
    re.compile(r"三\s*[,，]?\s*二\s*[,，]?\s*[一幺走]"),   # 三二一/三二走
    re.compile(r"3\s*2\s*1"),                            # 321
    re.compile(r"开拍"),
    re.compile(r"[aA]ction"),
    re.compile(r"准备\s*[,，]?\s*开始"),
]

# 断行标点
_BREAK_PUNCT = ("。", "！", "？", ".", "!", "?", "，", ",")


def _strip_slate_words(words: list[dict], window_s: float = 3.0) -> tuple[list[dict], float]:
    """剔除开场window_s内的开机口令词。返回(剩余词, 口令结束时间·0=未检出)"""
    if not words:
        return words, 0.0
    head_end = words[0]["start"] + window_s
    head = [w for w in words if w["start"] < head_end]
    if not head:
        return words, 0.0

    head_text = "".join(w["word"] for w in head)
    for pat in _SLATE_PATTERNS:
        m = pat.search(head_text)
        if not m:
            continue
        # 字符区间→词下标: 剔除完全落在匹配区间内的词
        lo, hi = m.span()
        kept_head, slate_end = [], 0.0
        pos = 0
        for w in head:
            w_lo, w_hi = pos, pos + len(w["word"])
            pos = w_hi
            if w_lo >= lo and w_hi <= hi:
                slate_end = max(slate_end, w["end"])
            else:
                kept_head.append(w)
        return kept_head + words[len(head):], slate_end
    return words, 0.0


def _drop_isolated_fragments(words: list[dict], gap_threshold_s: float = 0.8,
                             max_frag_chars: int = 2) -> list[dict]:
    """剔除长静音后的短残词(如结尾孤立的"好")"""
    if len(words) < 2:
        return words
    # 从尾部找最后一个 ≥gap_threshold_s 的间隙
    frag_start = len(words) - 1
    while frag_start > 0 and \
            words[frag_start]["start"] - words[frag_start - 1]["end"] < gap_threshold_s:
        frag_start -= 1
    if frag_start == 0:
        return words  # 没找到符合条件的静音间隙
    frag = words[frag_start:]
    frag_chars = sum(len(w["word"]) for w in frag)
    if 0 < frag_chars <= max_frag_chars:
        dropped = "".join(w["word"] for w in frag)
        logger.info("剔除尾部孤立残词: %s", dropped)
        return words[:frag_start]
    return words


def _make_group(line_words: list[dict]) -> dict:
    return {
        "start": line_words[0]["start"],
        "end": line_words[-1]["end"],
        "text": "".join(w["word"] for w in line_words),
    }


def _best_break_index(line_words: list[dict], min_gap_s: float = 0.05) -> int | None:
    """选断点: ①LLM短语标记(取行内最后一个) ②最大词间停顿 ③None=硬切"""
    for i in range(len(line_words) - 1, 0, -1):
        if line_words[i - 1].get("break_after"):
            return i
    best_i, best_gap = None, min_gap_s
    for i in range(1, len(line_words)):
        gap = line_words[i]["start"] - line_words[i - 1]["end"]
        if gap > best_gap:
            best_gap, best_i = gap, i
    return best_i


def _llm_phrase_marks(text: str) -> str | None:
    """LLM在短语边界插入｜。优先父项目gateway, 独立模式直连Kimi。失败返回None"""
    system = "你是中文分词专家。只返回加标记后的文本, 不要解释。"
    user = f"在下面中文口播文本的短语/意群边界处插入符号｜(不增删改任何字, 只加标记):\n{text}"
    try:
        from ._imports import chat_via_gateway, get_model_name
        if chat_via_gateway:
            model = get_model_name("deepseek") or "deepseek-v4-flash"
            r = chat_via_gateway(provider="deepseek", model=model, system=system,
                                 user=user, temperature=0.1, max_tokens=800)
            return r.get("content", "") if isinstance(r, dict) else str(r)
    except Exception:
        pass
    try:
        key = os.getenv("KIMI_API_KEY")
        if not key:
            from dotenv import load_dotenv
            for p in [".env", "../.env", "c:/Users/wangzibo/enterprise-agent-content/.env"]:
                if os.path.exists(p):
                    load_dotenv(p)
                    key = os.getenv("KIMI_API_KEY")
                    if key:
                        break
        if not key:
            return None
        import requests
        r = requests.post("https://api.moonshot.cn/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "moonshot-v1-8k", "temperature": 0.1, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}]}, timeout=30)
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def _mark_phrase_breaks(words: list[dict]) -> list[dict]:
    """可选增强: LLM短语边界打标(break_after), 断行不拆词。失败静默返回原词表"""
    text = "".join(w["word"] for w in words)
    if len(text) < 10:
        return words
    marked = _llm_phrase_marks(text)
    if not marked:
        return words
    marked = marked.strip()
    if marked.replace("｜", "").replace(" ", "") != text:
        logger.debug("短语打标对齐失败, 跳过")
        return words
    # 标记字符位置集合(不计空格)
    breaks, pos = set(), 0
    for ch in marked:
        if ch == "｜":
            breaks.add(pos)
        elif ch.strip():
            pos += 1
    # 位置→词边界: 落在词内的吸附到该词末尾
    out, cum = [], 0
    for w in words:
        w_lo = cum
        cum += len(w["word"])
        nw = dict(w)
        if any(w_lo < b <= cum for b in breaks):
            nw["break_after"] = True
        out.append(nw)
    logger.info("短语打标: %d个边界", len(breaks))
    return out


def _group_words_to_lines(words: list[dict], max_chars: int, min_ms: int) -> list[dict]:
    """将词列表智能分组为字幕行: 标点优先, 超字数时在最大停顿处断行"""
    if not words:
        return []
    groups = []
    current = [words[0]]

    for w in words[1:]:
        # 超字数: 优先短语标记/停顿处断行, 都不行则硬切(不丢词)
        while sum(len(x["word"]) for x in current) + len(w["word"]) > max_chars and current:
            bi = _best_break_index(current)
            if bi:
                groups.append(_make_group(current[:bi]))
                current = current[bi:]
            else:
                groups.append(_make_group(current))
                current = []
        current.append(w)

        # 标点处断行(时长够才断)
        if w["word"] in _BREAK_PUNCT and len(current) >= 2:
            duration_ms = (current[-1]["end"] - current[0]["start"]) * 1000
            if duration_ms >= min_ms:
                groups.append(_make_group(current))
                current = []

    if current:
        groups.append(_make_group(current))

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
