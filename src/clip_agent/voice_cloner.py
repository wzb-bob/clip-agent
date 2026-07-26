"""
声音克隆器 v1 · Index-TTS(优先)→EdgeTTS(降级)

用户录30秒语音 → 克隆声线 → 所有脚本用'自己的声音'配音
这是实体店老板最需要的: 不用自己录口播·但声音是自己的
"""
from __future__ import annotations
import logging, os, subprocess, tempfile, time
from pathlib import Path

logger = logging.getLogger(__name__)

# TTS engines in priority order
AVAILABLE_ENGINES = []


def _check_index_tts() -> bool:
    """检查Index-TTS是否可用"""
    try:
        import importlib
        importlib.import_module("indextts")
        return True
    except ImportError:
        return False


HAS_INDEX_TTS = _check_index_tts()


def clone_voice(reference_audio: str, voice_name: str = "") -> str | None:
    """
    从参考音频克隆声音 → 返回voice_id供后续使用。

    Args:
        reference_audio: 30秒参考语音文件
        voice_name: 声音名称(默认用文件名)

    Returns:
        voice_id: 供generate_speech使用, None=失败
    """
    if not HAS_INDEX_TTS:
        logger.warning("Index-TTS未安装 — 降级EdgeTTS")
        return None

    vp = Path(reference_audio)
    if not vp.exists():
        return None

    name = voice_name or vp.stem
    try:
        # Index-TTS voice cloning
        from indextts import VoiceCloner
        cloner = VoiceCloner()
        voice_path = cloner.clone(
            reference_audio=str(vp),
            voice_name=name,
        )
        logger.info("声音克隆: %s → %s", vp.name, name)
        return voice_path or name
    except Exception as e:
        logger.warning("声音克隆失败: %s", e)
        return None


def generate_speech(
    text: str,
    voice_id: str = "",
    engine: str = "auto",
    speed: float = 1.0,
) -> str:
    """
    用指定声音生成语音。

    Args:
        text: 要朗读的文本
        voice_id: clone_voice返回的ID, 为空则用EdgeTTS默认音
        engine: "auto"(自动选择)/"indextts"/"edgetts"
        speed: 语速(0.5-2.0)

    Returns:
        mp3文件路径, ""=失败
    """
    # 自动选择引擎: Index-TTS > EdgeTTS
    if engine == "auto":
        if HAS_INDEX_TTS and voice_id:
            engine = "indextts"
        else:
            engine = "edgetts"

    if engine == "indextts" and HAS_INDEX_TTS and voice_id:
        return _speak_indextts(text, voice_id, speed)
    else:
        return _speak_edgetts(text, speed)


def _speak_indextts(text: str, voice_id: str, speed: float) -> str:
    """Index-TTS语音合成"""
    try:
        from indextts import VoiceSynthesizer
        synth = VoiceSynthesizer()
        tmp = tempfile.mktemp(suffix=".mp3")
        synth.synthesize(
            text=text,
            voice=voice_id,
            output_path=tmp,
            speed=speed,
        )
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            return tmp
    except Exception as e:
        logger.warning("Index-TTS合成失败: %s", e)
    return ""


def _speak_edgetts(text: str, speed: float = 1.0) -> str:
    """EdgeTTS语音合成 — 带SSML语调增强"""
    try:
        import asyncio
        import edge_tts

        async def _gen():
            tmp = tempfile.mktemp(suffix=".mp3")
            rate = f"{'+' if speed > 1 else ''}{int((speed-1)*100)}%" if speed != 1 else "+0%"

            # 🆕 SSML增强: 感叹句加强调·问句升调·价格数字加重
            ssml_text = _add_ssml_emphasis(text)

            communicate = edge_tts.Communicate(
                ssml_text, "zh-CN-XiaoxiaoNeural",
                rate=rate,
            )
            await communicate.save(tmp)
            return tmp

        return asyncio.run(_gen())
    except Exception as e:
        logger.warning("EdgeTTS失败: %s", e)
        return ""


def _add_ssml_emphasis(text: str) -> str:
    """为文本加SSML语调标记 — 让机械音更自然"""
    import re

    # 1. 数字+块/元 → 加重读出
    text = re.sub(r'(\d+)\s*块', r'<emphasis level="strong">\1块</emphasis>', text)
    text = re.sub(r'(\d+)\s*元', r'<emphasis level="strong">\1元</emphasis>', text)

    # 2. 感叹句 → 升调
    sentences = re.split(r'([。！？!?\n])', text)
    result = []
    for i, part in enumerate(sentences):
        if part in ('！', '!', '？', '?'):
            result.append(part)
        elif part.strip():
            # 加停顿和语调
            if any(kw in part for kw in ["!", "！", "块", "元", "只此", "第一", "最好"]):
                result.append(f'<prosody rate="fast" pitch="high">{part.strip()}</prosody>')
            elif any(kw in part for kw in ["?", "？"]):
                result.append(f'<prosody pitch="high">{part.strip()}</prosody>')
            elif any(kw in part for kw in ["来", "赶紧", "快", "左下", "团购"]):
                result.append(f'<prosody rate="+10%">{part.strip()}</prosody>')
            else:
                result.append(part.strip())

    text = "".join(result)

    # Wrap in SSML
    if "<" in text:
        text = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">{text}</speak>'

    return text


def list_voices() -> list[dict]:
    """列出可用的声音"""
    voices = []
    # EdgeTTS voices
    voices.append({
        "id": "edgetts:zh-CN-XiaoxiaoNeural",
        "name": "晓晓(女·标准)",
        "engine": "edgetts",
        "type": "builtin",
    })
    voices.append({
        "id": "edgetts:zh-CN-YunxiNeural",
        "name": "云希(男·标准)",
        "engine": "edgetts",
        "type": "builtin",
    })
    if HAS_INDEX_TTS:
        voices.append({
            "id": "indextts:clone",
            "name": "声音克隆(需先录30秒参考音)",
            "engine": "indextts",
            "type": "clone",
        })
    return voices
