"""自主编辑引擎 · 无脚本出片

任意视频 → media_understanding(Whisper+能量+帧分析)
  → 伪脚本(真实时间戳分句+能量情绪) → semantic_engine语义决策
  → render_with_vfx渲染 → openmontage质量门禁 → MP4

与ChatCut管线独立并存。LLM全走chat_via_gateway(独立模式降级关键词)。
"""
from __future__ import annotations
import logging, os, tempfile, time
from pathlib import Path

logger = logging.getLogger(__name__)

# 停顿阈值: 两句之间静音>0.8s视为分句点
_PAUSE_SPLIT_S = 0.8
# 段时长健康范围(过长的段在停顿处切开)
_MAX_SEG_S = 8.0
_MIN_SEG_S = 1.0


def build_pseudo_script(understanding) -> dict | None:
    """Whisper转录→伪脚本(分句+真实时间轴+能量情绪标签)

    Args:
        understanding: MediaUnderstanding(或understand_audio的dict)
    Returns:
        {"text","sentences":[{index,text,start_sec,end_sec,duration_sec,emotion,intensity}],
         "key_moments","source"} · 无语音内容返回None(诚实失败)
    """
    if hasattr(understanding, "transcript_segments"):
        audio_segs = understanding.transcript_segments or []
        moments = [{"at_sec": m.timestamp_sec, "type": m.type, "energy": m.energy}
                   for m in (understanding.audio_moments or [])]
    else:
        audio_segs = understanding.get("segments", []) or []
        moments = understanding.get("moments", []) or []

    # 无转录=无法自主编辑(诚实原则·不硬编)
    if not audio_segs or not any(s.get("text", "").strip() for s in audio_segs):
        logger.warning("无语音内容·无法自主编辑")
        return None

    # ── 分句: whisper段直接用, 过长段在词间停顿处切开, 过短段并入下一句 ──
    raw = []
    for s in audio_segs:
        text = s.get("text", "").strip()
        if not text:
            continue
        start, end = float(s.get("start", 0)), float(s.get("end", 0))
        if end - start > _MAX_SEG_S and s.get("words"):
            raw.extend(_split_long_segment(s, start, end))
        else:
            raw.append({"text": text, "start_sec": start, "end_sec": end})
    sentences = _merge_short(raw)

    # ── 字幕三修复用: 开机口令/尾部残词(句级判定) ──
    sentences = _drop_slate_sentence(sentences)
    sentences = _drop_tail_fragment(sentences)

    # ── 情绪标签: 音频moments按时间窗归属 ──
    for i, sent in enumerate(sentences):
        sent["index"] = i + 1
        sent["duration_sec"] = round(sent["end_sec"] - sent["start_sec"], 2)
        em, intensity = _emotion_for(sent, moments)
        sent["emotion"] = em
        sent["intensity"] = intensity

    key_moments = [{"at_sec": m["at_sec"], "type": m["type"],
                    "intensity": max(1, round(m.get("energy", 0) * 10))}
                   for m in moments if m.get("type") == "emphasis"]

    return {
        "text": "。".join(s["text"].rstrip("。!?!,,") for s in sentences) + "。",
        "sentences": sentences,
        "key_moments": key_moments,
        "source": "whisper_pseudo",
    }


def _split_long_segment(seg: dict, start: float, end: float) -> list[dict]:
    """过长段在词间>0.8s停顿处切开(无停顿则按词数均分)"""
    words = seg.get("words", [])
    chunks, cur_words, cur_start = [], [], start
    for j in range(1, len(words)):
        gap = words[j].get("start", 0) - words[j - 1].get("end", 0)
        if gap >= _PAUSE_SPLIT_S:
            text = "".join(w.get("word", "") for w in cur_words + [words[j - 1]]).strip()
            if text:
                chunks.append({"text": text, "start_sec": cur_start,
                               "end_sec": words[j - 1].get("end", cur_start)})
            cur_words, cur_start = [], words[j].get("start", cur_start)
        else:
            cur_words.append(words[j - 1])
    last_end = words[-1].get("end", end) if words else end
    text = "".join(w.get("word", "") for w in cur_words + ([words[-1]] if words else [])).strip()
    if text:
        chunks.append({"text": text, "start_sec": cur_start, "end_sec": last_end})
    return chunks or [{"text": seg["text"], "start_sec": start, "end_sec": end}]


def _merge_short(raw: list[dict]) -> list[dict]:
    """过短句(<1s)并入相邻句(保持时间连续)"""
    merged = []
    for r in raw:
        dur = r["end_sec"] - r["start_sec"]
        if dur < _MIN_SEG_S and merged:
            merged[-1]["text"] += r["text"]
            merged[-1]["end_sec"] = r["end_sec"]
        elif dur < _MIN_SEG_S and not merged:
            merged.append(dict(r))
        else:
            if merged and merged[-1]["end_sec"] - merged[-1]["start_sec"] < _MIN_SEG_S:
                merged[-1]["text"] += r["text"]
                merged[-1]["end_sec"] = r["end_sec"]
            else:
                merged.append(dict(r))
    return merged


def _drop_slate_sentence(sentences: list[dict]) -> list[dict]:
    """剔除开机口令句(前3s内命中口令模式)——复用whisper_srt_generator的模式表"""
    if not sentences:
        return sentences
    from .whisper_srt_generator import _SLATE_PATTERNS
    first = sentences[0]
    if first["start_sec"] < 3.0:
        for pat in _SLATE_PATTERNS:
            m = pat.search(first["text"])
            if m:
                # 口令覆盖整句→删句; 部分→裁掉口令段文字
                stripped = (first["text"][:m.start()] + first["text"][m.end():]).strip()
                logger.info("伪脚本: 剔除开机口令 %s", first["text"][:12])
                if stripped:
                    first["text"] = stripped
                else:
                    sentences = sentences[1:]
                break
    return sentences


def _drop_tail_fragment(sentences: list[dict]) -> list[dict]:
    """剔除尾部孤立残句(长静音后≤2字)——与字幕三修同规则"""
    if len(sentences) < 2:
        return sentences
    last, prev = sentences[-1], sentences[-2]
    gap = last["start_sec"] - prev["end_sec"]
    if gap >= 0.8 and len(last["text"]) <= 2:
        logger.info("伪脚本: 剔除尾部残句 %s", last["text"])
        return sentences[:-1]
    return sentences


def _emotion_for(sent: dict, moments: list[dict]) -> tuple[str, int]:
    """按时间窗内的音频moments推断情绪+强度"""
    t0, t1 = sent["start_sec"], sent["end_sec"]
    inside = [m for m in moments if t0 - 0.3 <= m.get("at_sec", -1) <= t1 + 0.3]
    emphasis = [m for m in inside if m.get("type") == "emphasis"]
    pauses = [m for m in inside if m.get("type") == "pause"]
    speedup = [m for m in inside if m.get("type") == "speed_change"]

    max_e = max((m.get("energy", 0) for m in emphasis), default=0)
    intensity = max(1, min(10, round(1 + max_e * 9)))

    if emphasis and max_e > 0.5:
        return "冲击", intensity
    if pauses:
        return "悬念", intensity
    if speedup:
        return "紧迫", intensity
    return "平实", intensity


# ══════════════════════════════════════════════════════════
# Phase 2: 语义驱动编辑
# ══════════════════════════════════════════════════════════

def _precut_sentences(video_path: str, sentences: list[dict],
                      tmpdir: str) -> list[str]:
    """按伪脚本真实时间戳把源视频切成逐句片段(重编码保精度)"""
    import subprocess
    clips = []
    for i, s in enumerate(sentences):
        out = os.path.join(tmpdir, f"sent_{i:03d}.mp4")
        dur = s["end_sec"] - s["start_sec"]
        r = subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{s['start_sec']:.2f}", "-t", f"{dur:.2f}",
            "-i", video_path,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-c:a", "aac", out,
        ], capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.exists(out):
            clips.append(out)
    return clips


def _insert_broll(sentences: list[dict], broll_videos: list[str]) -> list[dict]:
    """在中点(或首个长停顿)后插入一段B-roll·时长=min(3s,有效内容)"""
    if not broll_videos:
        return sentences
    from .chatcut_vfx import _content_duration
    bf = broll_videos[0]
    dur = min(3.0, _content_duration(bf) or 0)
    if dur < 1.0:
        return sentences
    mid = len(sentences) // 2
    broll_seg = {"index": -1, "text": "", "start_sec": 0, "end_sec": dur,
                 "duration_sec": dur, "emotion": "平实", "intensity": 3,
                 "is_broll": True, "material_file": bf}
    out = list(sentences)
    out.insert(mid, broll_seg)
    return out


def auto_edit(video_path: str, pseudo_script: dict,
              output_path: str, broll_videos: list[str] | None = None,
              script_type: str = "") -> dict:
    """伪脚本→语义决策→VFX渲染(复用句级联动渲染器)

    Returns: {"success","output","category","artifact_check","script_audio_match","error"}
    """
    from types import SimpleNamespace
    from .chatcut_plugin import _detect_category, _detect_industry
    from .execution_engine import _render_unified_vfx

    sentences = pseudo_script["sentences"]
    text = pseudo_script["text"]
    category = script_type or _detect_category(text)
    industry = _detect_industry(text, video_path)

    # B-roll插入(可选)
    work_sents = _insert_broll(sentences, broll_videos or [])

    # 预切逐句片段(口播句·B-roll句直接用素材)
    tmpdir = tempfile.mkdtemp(prefix="auto_")
    talking = [s for s in work_sents if not s.get("is_broll")]
    precut = _precut_sentences(video_path, talking, tmpdir)
    if len(precut) != len(talking):
        return {"success": False, "error": f"预切失败 {len(precut)}/{len(talking)}"}

    # 组装句级渲染输入(复用_render_unified_vfx·字幕SRT直出/音轨拼接/artifact检测)
    cut_iter = iter(precut)
    sent_objs, video_slots = [], {}
    for i, s in enumerate(work_sents, 1):
        if s.get("is_broll"):
            vf = s["material_file"]
        else:
            vf = next(cut_iter)
        video_slots[i] = vf
        sent_objs.append(SimpleNamespace(
            index=i, text=s["text"], duration_sec=s["duration_sec"],
            is_broll=bool(s.get("is_broll"))))

    ok, info = _render_unified_vfx(sent_objs, video_slots, category,
                                   industry, text, output_path)
    if not ok:
        return {"success": False, "error": info.get("error", "渲染失败")}
    return {"success": True, "output": info["output"], "category": category,
            "industry": industry,
            "artifact_check": info.get("artifact_check"),
            "script_audio_match": info.get("script_audio_match"),
            "planned_duration": round(sum(s["duration_sec"] for s in work_sents), 1),
            "size_mb": info.get("size_mb")}


# ══════════════════════════════════════════════════════════
# 顶层入口: 无脚本全自动出片(理解→伪脚本→编辑→质检≤3次回退)
# ══════════════════════════════════════════════════════════

def auto_pipeline(video_path: str, output_path: str = "",
                  broll_videos: list[str] | None = None,
                  script_type: str = "", max_retries: int = 3) -> dict:
    """任意视频→全自动出片。无语音内容诚实失败。"""
    from .media_understanding import understand_media
    from .openmontage_pipeline import run_auto_quality_gates

    t0 = time.time()
    vp = str(video_path)
    if not output_path:
        output_path = str(Path(vp).parent / f"auto_{Path(vp).stem}.mp4")
    os.makedirs(Path(output_path).parent, exist_ok=True)

    # Step 1: 全量理解(Whisper+能量+帧)
    understanding = understand_media(vp)

    # Step 2: 伪脚本
    pseudo = build_pseudo_script(understanding)
    if not pseudo:
        return {"success": False, "error": "无语音内容·无法自主编辑",
                "elapsed": round(time.time() - t0, 1)}

    # Step 3: 编辑+渲染(仅"可修复"的门禁失败才回退重渲: brand_safety可换风格修,
    # broll/素材类失败重渲无意义)
    result, last_gates = {}, None
    for attempt in range(1, max_retries + 1):
        result = auto_edit(vp, pseudo, output_path,
                           broll_videos=broll_videos, script_type=script_type)
        if not result["success"]:
            break
        # Step 4: 7阶段质量门禁
        gates = run_auto_quality_gates({
            "video_path": vp, "pseudo_script": pseudo,
            "output_path": result["output"],
            "expected_duration": result.get("planned_duration", 0),
            "broll_videos": broll_videos or [],
        })
        last_gates = gates
        if gates["passed_all"]:
            break
        failed_names = {g["gate"] for g in gates["gates"] if not g["passed"]}
        logger.warning("质量门禁未过(第%d次): %s", attempt, failed_names)
        if "brand_safety" not in failed_names:
            break  # 素材类失败重渲无用·直接报出
        if attempt < max_retries:
            script_type = "老板IP"  # 回退到最保守风格重渲
    else:
        pass

    result.setdefault("success", False)
    result["quality_gates"] = last_gates
    result["pseudo_script"] = {"text": pseudo["text"],
                               "sentences": len(pseudo["sentences"]),
                               "key_moments": len(pseudo["key_moments"])}
    result["elapsed"] = round(time.time() - t0, 1)
    return result
