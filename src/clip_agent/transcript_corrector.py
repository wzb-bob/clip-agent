"""
转录修正器 · DeepSeek对齐Whisper输出与预期脚本

问题: Whisper small模型中文准确度约70%
解决: 将Whisper转录+预期脚本→DeepSeek对齐修正→精确字幕文本
"""
from __future__ import annotations
import json, logging, re, time

logger = logging.getLogger(__name__)


def correct_transcript(
    whisper_text: str,
    expected_script: str,
    script_type: str = "老板IP",
) -> str | None:
    """
    DeepSeek修正Whisper转录。

    输入: Whisper粗转录 + 预期脚本文本
    输出: 修正后的精确转录(保持原始时间戳)
    """
    if not whisper_text or not expected_script:
        return None

    try:
        from ._imports import chat_via_gateway, get_model_name
        if not chat_via_gateway:
            return None

        prompt = f"""你是中文语音转录校对员。下面有两段文字:

## Whisper转录(可能有错误)
{whisper_text[:500]}

## 预期脚本(用户提供的文案)
{expected_script[:500]}

## 任务
1. 将Whisper转录与预期脚本对齐
2. 修正Whisper中的同音字错误(如"瞎吃"→"瞎吃","食之火"→"十只活")
3. 保持Whisper的实际语序(用户可能即兴发挥·不完全按脚本)
4. 输出修正后的完整转录文本

只返回修正后的文本。不要解释。"""

        model = get_model_name("deepseek") or "deepseek-v4-flash"
        result = chat_via_gateway(
            provider="deepseek", model=model,
            system="你是中文语音校对员。只返回修正后的文本。不要解释。",
            user=prompt, temperature=0.1, max_tokens=1000,
        )
        content = result.get("content", "") if isinstance(result, dict) else str(result)
        corrected = content.strip().strip('"').strip("'")

        if len(corrected) > 10 and len(corrected) < len(whisper_text) * 2:
            logger.info("转录修正: %d→%d字", len(whisper_text), len(corrected))
            return corrected

    except Exception as e:
        logger.debug("转录修正失败: %s", e)

    return None


def align_transcript_to_timestamps(
    corrected_text: str,
    word_timestamps: list[dict],
) -> list[dict]:
    """
    将修正后的文本对齐到原始时间戳。

    策略: 按字符比例分配时间戳(中文每个字用时相近)
    """
    if not corrected_text or not word_timestamps:
        return word_timestamps

    total_dur = word_timestamps[-1]["end"] - word_timestamps[0]["start"]
    chars = list(corrected_text.replace(" ", "").replace("\n", ""))
    char_dur = total_dur / max(len(chars), 1)

    result = []
    cur = word_timestamps[0]["start"]
    for i, ch in enumerate(chars):
        result.append({
            "word": ch,
            "start": round(cur, 2),
            "end": round(cur + char_dur, 2),
        })
        cur += char_dur

    return result
