"""
媒体深度理解引擎 v1 · 音频+视频+文本 跨模态理解

真正的"理解"而非"检测":
  1. Whisper全转录 → 说了什么·哪里强调·语速变化
  2. 音频能量分析 → 情绪峰值·自然停顿·节奏
  3. 视频帧理解 → 场景描述·动作识别 (OpenCV本地)
  4. DeepSeek跨模态 → 文本+音频+视频 语义对齐

输入: 视频文件 + 脚本文本
输出: 完整的媒体理解 — 每时刻在发生什么·该插什么画面
"""
from __future__ import annotations
import json, logging, os, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


@dataclass
class AudioMoment:
    """音频中的一个关键时刻"""
    timestamp_sec: float
    type: str                # emphasis/ pause/ speed_change/ emotion_peak
    word: str = ""
    energy: float = 0.0       # 归一化能量
    detail: str = ""


@dataclass
class VisualMoment:
    """视频中的一个关键时刻"""
    timestamp_sec: float
    type: str                # face_appears/ scene_change/ motion_peak/ product_closeup
    description: str = ""
    confidence: float = 0.0


@dataclass
class MediaUnderstanding:
    """完整的媒体理解结果"""
    file_path: str
    duration_sec: float

    # 音频理解
    transcript: str = ""                    # 完整转录文本
    transcript_segments: list[dict] = field(default_factory=list)  # [{start, end, text, confidence}]
    audio_moments: list[AudioMoment] = field(default_factory=list)

    # 视频理解
    visual_moments: list[VisualMoment] = field(default_factory=list)
    scene_descriptions: list[dict] = field(default_factory=list)  # [{at_sec, description}]

    # 跨模态对齐
    alignment: list[dict] = field(default_factory=list)  # [{at_sec, audio_context, visual_context, suggestion}]

    # 编辑建议
    edit_suggestions: list[dict] = field(default_factory=list)


# ══════════════════════════════════════════════════════════
# 音频理解: Whisper转录 + librosa能量分析
# ══════════════════════════════════════════════════════════

def understand_audio(video_path: str) -> dict:
    """
    深度音频理解: 转录+语速+能量+情绪峰值

    返回:
      transcript: 完整文本
      segments: [{start, end, text, confidence, speed_cps, energy}]
      moments: [{at_sec, type, word, energy, detail}]
    """
    result = {"transcript": "", "segments": [], "moments": []}
    vp = Path(video_path)
    if not vp.exists():
        return result

    # 1. Whisper转录 (词级时间戳)
    try:
        import whisper
        model = whisper.load_model("small")
        whisper_result = model.transcribe(str(vp), word_timestamps=True)

        result["transcript"] = whisper_result.get("text", "").strip()

        for seg in whisper_result.get("segments", []):
            words = seg.get("words", [])
            seg_text = seg.get("text", "").strip()
            seg_dur = seg.get("end", 0) - seg.get("start", 0)
            word_count = len(words)

            # 语速 (字/秒)
            speed = round(word_count / max(seg_dur, 0.1), 1) if seg_dur > 0 else 0

            # Include word-level timestamps for frame-precise editing
            word_list = [
                {"word": w.get("word","").strip(), "start": round(w.get("start",0), 2), "end": round(w.get("end",0), 2)}
                for w in words
            ]
            result["segments"].append({
                "start": round(seg.get("start", 0), 2),
                "end": round(seg.get("end", 0), 2),
                "text": seg_text,
                "confidence": round(seg.get("confidence", 0), 2),
                "speed_cps": speed,
                "word_count": word_count,
                "words": word_list,
            })
    except Exception as e:
        logger.warning("Whisper转录失败: %s", e)

    # 2. librosa音频能量+节奏分析
    if HAS_LIBROSA:
        try:
            y, sr = librosa.load(str(vp), sr=22050, mono=True)
            if len(y) > 0:
                # 能量包络
                hop = 512
                energy = np.array([
                    np.sum(np.abs(y[i:i+hop])**2)
                    for i in range(0, len(y)-hop, hop)
                ])
                if len(energy) > 0:
                    energy = energy / (np.max(energy) + 1e-10)
                    times = np.arange(len(energy)) * hop / sr

                    # 找能量峰值 (>mean+1.5std = 情绪强调)
                    threshold = np.mean(energy) + 1.5 * np.std(energy)
                    for i in range(1, len(energy) - 1):
                        if energy[i] > threshold and energy[i] > energy[i-1] and energy[i] > energy[i+1]:
                            result["moments"].append({
                                "at_sec": round(float(times[i]), 2),
                                "type": "emphasis",
                                "energy": round(float(energy[i]), 2),
                                "detail": "音频强调/情绪峰值",
                            })

                    # 找静音段 (<mean*0.3 = 自然停顿)
                    silence_thresh = np.mean(energy) * 0.3
                    in_silence = False
                    silence_start = 0
                    for i in range(len(energy)):
                        if energy[i] < silence_thresh and not in_silence:
                            silence_start = times[i]
                            in_silence = True
                        elif energy[i] >= silence_thresh and in_silence:
                            gap = times[i] - silence_start
                            if 0.3 <= gap <= 2.0:  # 300ms-2s是有效停顿
                                result["moments"].append({
                                    "at_sec": round(float(silence_start + gap/2), 2),
                                    "type": "pause",
                                    "energy": 0,
                                    "detail": f"自然停顿{int(gap*1000)}ms",
                                })
                            in_silence = False

                    # 语速变化检测
                    if len(result["segments"]) >= 2:
                        speeds = [s["speed_cps"] for s in result["segments"] if s["speed_cps"] > 0]
                        if speeds:
                            avg_speed = np.mean(speeds)
                            for seg in result["segments"]:
                                if seg["speed_cps"] > avg_speed * 1.5:
                                    result["moments"].append({
                                        "at_sec": seg["start"],
                                        "type": "speed_change",
                                        "energy": 0,
                                        "detail": f"语速加快({seg['speed_cps']}字/秒 vs 平均{avg_speed:.1f})",
                                    })
        except Exception as e:
            logger.debug("librosa分析跳过: %s", e)

    return result


# ══════════════════════════════════════════════════════════
# 视频理解: OpenCV帧分析 + 场景描述
# ══════════════════════════════════════════════════════════

def understand_video(video_path: str, frame_interval: float = 0.5) -> dict:
    """
    视频深度理解: 帧分析+场景描述+关键时刻

    返回:
      moments: [{at_sec, type, description, confidence}]
      scene_descriptions: [{at_sec, description}]
    """
    result = {"moments": [], "scene_descriptions": []}

    try:
        from .local_video_analyzer import analyze_video_local
        analysis = analyze_video_local(video_path, extract_frames=True, frame_interval=frame_interval)
        if not analysis:
            return result

        # 从LocalVideoAnalysis提取关键时刻
        for f in analysis.frames:
            desc_parts = []

            if f.is_keyframe:
                result["moments"].append({
                    "at_sec": f.timestamp_sec,
                    "type": "scene_change",
                    "description": "场景切换/镜头变化",
                    "confidence": 0.8,
                })

            if f.face_count > 0:
                result["moments"].append({
                    "at_sec": f.timestamp_sec,
                    "type": "face_appears",
                    "description": f"检测到{f.face_count}个人脸",
                    "confidence": 0.7,
                })

            # 场景描述
            if f.brightness > 0:
                quality = "清晰" if f.sharpness > 500 else ("一般" if f.sharpness > 200 else "模糊")
                desc_parts = [
                    f"{f.dominant_color}色调",
                    quality,
                    "有人脸" if f.has_face else "无人脸",
                    "静态" if f.motion_intensity < 0.5 else "动态",
                ]
                result["scene_descriptions"].append({
                    "at_sec": f.timestamp_sec,
                    "description": "·".join(desc_parts),
                })

        # 运动峰值
        if analysis.frames:
            motions = [f.motion_intensity for f in analysis.frames if f.motion_intensity > 0]
            if motions:
                thresh = np.mean(motions) + 2 * np.std(motions)
                for f in analysis.frames:
                    if f.motion_intensity > thresh:
                        result["moments"].append({
                            "at_sec": f.timestamp_sec,
                            "type": "motion_peak",
                            "description": f"运动强度突增(强度{f.motion_intensity:.1f})",
                            "confidence": 0.6,
                        })

    except Exception as e:
        logger.debug("视频理解跳过: %s", e)

    return result


# ══════════════════════════════════════════════════════════
# 跨模态理解: DeepSeek语义对齐
# ══════════════════════════════════════════════════════════

CROSS_MODAL_PROMPT = """你是视频剪辑导演。下面是一个短视频的完整信息,请做跨模态理解和对齐。

## 脚本内容
{script_text}

## 音频转录(Whisper)
{transcript}

## 音频关键时刻
{audio_moments}

## 视频关键时刻
{visual_moments}

## 视频场景描述
{scene_descriptions}

## 任务
1. 将脚本语义与音频转录对齐——找出每句话实际在什么时候说的
2. 分析说话人的情绪变化——哪里激动、哪里平静、哪里慢下来强调
3. 为每个B-roll段落推荐具体的插入时机和画面内容
4. 找出音频中的"金句"时刻(适合放大文字/加特效的瞬间)

输出格式(JSON):
{{
  "alignment": [
    {{"at_sec": 0.0, "script_line": "68块!", "audio_text": "68块!", "emotion": "excited", "suggestion": "大字弹出+鼓点BGM"}}
  ],
  "emotional_curve": "激动的报价→展示工艺的自信→亲切的CTA",
  "golden_moments": [{{"at_sec": 0.5, "reason": "价格冲击", "effect": "大字弹出+画面缩放"}}],
  "broll_suggestions": [{{"at_sec": 3.0, "duration": 2.0, "visual": "厨房干煸过程", "reason": "正在说工艺,展示制作画面"}}]
}}

只返回JSON。不要markdown。"""


def cross_modal_align(
    script_text: str,
    transcript: str,
    audio_moments: list[dict],
    visual_moments: list[dict],
    scene_descriptions: list[dict],
) -> dict:
    """
    DeepSeek跨模态理解: 将音频+视频+文本对齐

    这是真正的"理解"层——不是单独检测特征,而是让AI理解整个场景。
    """
    try:
        from ._imports import chat_via_gateway, get_model_name
        if not chat_via_gateway:
            logger.warning("gateway_client不可用 — 跳过跨模态理解")
            return {"alignment": [], "emotional_curve": "", "golden_moments": [], "broll_suggestions": []}

        prompt = CROSS_MODAL_PROMPT.format(
            script_text=script_text[:500],
            transcript=transcript[:500],
            audio_moments=json.dumps(audio_moments[:20], ensure_ascii=False),
            visual_moments=json.dumps(visual_moments[:15], ensure_ascii=False),
            scene_descriptions=json.dumps(scene_descriptions[:10], ensure_ascii=False),
        )

        model = get_model_name("deepseek") or "deepseek-v4-flash"
        result = chat_via_gateway(
            provider="deepseek", model=model,
            system="你是视频剪辑导演。只返回JSON。不要markdown。",
            user=prompt, temperature=0.1, max_tokens=2000,
        )

        content = result.get("content", "") if isinstance(result, dict) else str(result)

        import re
        from .semantic_engine import _repair_json
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            raw = _repair_json(json_match.group(0))
            return json.loads(raw)

    except Exception as e:
        logger.warning("跨模态理解失败: %s", e)

    return {"alignment": [], "emotional_curve": "", "golden_moments": [], "broll_suggestions": []}


# ══════════════════════════════════════════════════════════
# 统一入口
# ══════════════════════════════════════════════════════════

def understand_media(video_path: str, script_text: str = "",
                     use_ai: bool = True) -> MediaUnderstanding:
    """
    统一入口: 深度理解一个视频文件。

    输出完整的MediaUnderstanding — 包含音频理解、视频理解、跨模态对齐。
    """
    vp = Path(video_path)
    # 基础信息(先probe时长·dataclass必填)
    duration = 0.0
    try:
        from .local_video_analyzer import _probe_video_ffprobe
        info = _probe_video_ffprobe(str(vp))
        if info:
            duration = float(info.get("duration", 0))
    except Exception:
        pass
    result = MediaUnderstanding(file_path=str(vp), duration_sec=duration)

    t0 = time.time()

    # 1. 音频理解
    audio = understand_audio(str(vp))
    result.transcript = audio["transcript"]
    result.transcript_segments = audio["segments"]
    for m in audio["moments"]:
        result.audio_moments.append(AudioMoment(
            timestamp_sec=m["at_sec"], type=m["type"],
            energy=m.get("energy", 0), detail=m.get("detail", ""),
        ))

    # 2. 视频理解
    video = understand_video(str(vp))
    for m in video["moments"]:
        result.visual_moments.append(VisualMoment(
            timestamp_sec=m["at_sec"], type=m["type"],
            description=m.get("description", ""),
            confidence=m.get("confidence", 0),
        ))
    result.scene_descriptions = video["scene_descriptions"]

    # 3. 跨模态对齐 (DeepSeek — 真正的理解)
    if use_ai and script_text:
        cross = cross_modal_align(
            script_text, result.transcript,
            audio["moments"], video["moments"], video["scene_descriptions"],
        )
        result.alignment = cross.get("alignment", [])
        result.edit_suggestions = cross.get("broll_suggestions", [])

        if cross.get("golden_moments"):
            for gm in cross["golden_moments"]:
                result.audio_moments.append(AudioMoment(
                    timestamp_sec=gm["at_sec"], type="golden_moment",
                    detail=f"{gm.get('reason','')} → {gm.get('effect','')}",
                ))

    elapsed = time.time() - t0
    logger.info("媒体理解完成: %s | %.1fs | 音频事件=%d | 视频事件=%d | 跨模态对齐=%d",
               vp.name, elapsed, len(result.audio_moments),
               len(result.visual_moments), len(result.alignment))

    return result


def understand_and_suggest(video_path: str, script_text: str = "") -> dict:
    """
    快速入口: 理解视频 → 返回编辑建议列表

    适合集成到执行管线中。
    """
    understanding = understand_media(video_path, script_text, use_ai=True)

    # 聚合所有编辑建议
    suggestions = []

    # 音频自然停顿 → B-roll插入点
    pauses = [m for m in understanding.audio_moments if m.type == "pause"]
    for p in pauses[:5]:
        suggestions.append({
            "at_sec": p.timestamp_sec,
            "action": "broll_insert",
            "reason": f"自然停顿·{p.detail}",
            "source": "audio",
        })

    # 音频强调 → 文字特效点
    emphases = [m for m in understanding.audio_moments if m.type == "emphasis"]
    for e in emphases[:3]:
        suggestions.append({
            "at_sec": e.timestamp_sec,
            "action": "text_emphasis",
            "reason": f"情绪强调·能量{e.energy:.2f}",
            "source": "audio",
        })

    # 金句时刻 → 大字+特效
    golden = [m for m in understanding.audio_moments if m.type == "golden_moment"]
    for g in golden:
        suggestions.append({
            "at_sec": g.timestamp_sec,
            "action": "golden_moment_effect",
            "reason": g.detail,
            "source": "cross_modal",
        })

    # 跨模态对齐的编辑建议
    for es in understanding.edit_suggestions[:5]:
        suggestions.append({
            "at_sec": es.get("at_sec", 0),
            "action": "cross_modal_broll",
            "reason": es.get("reason", ""),
            "visual": es.get("visual", ""),
            "source": "cross_modal",
        })

    suggestions.sort(key=lambda s: s["at_sec"])

    return {
        "file": Path(video_path).name,
        "duration_sec": understanding.duration_sec,
        "transcript": understanding.transcript[:200],
        "suggestions": suggestions,
        "emotional_curve": "",
        "alignment": understanding.alignment[:10],
    }
