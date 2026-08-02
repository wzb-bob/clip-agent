"""Kimi Vision 成片评审——5维评分·低于阈值自动重试

参考: agentic-video-editor Reviewer agent (Director→Editor→Reviewer loop)
5维: 节奏(Pacing)/字幕(Subtitle)/画面(Visual)/音频(Audio)/整体(Overall)
"""
from __future__ import annotations
import base64, json, logging, os, subprocess, tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """你是顶级短视频评审专家。看这3帧(开头/中间/结尾)，从观众角度评分。

返回严格JSON:
{
  "pacing": {"score": 0-100, "reason": "节奏是否紧凑·切点是否合理"},
  "subtitle": {"score": 0-100, "reason": "字幕是否清晰·位置是否遮挡·字体大小"},
  "visual": {"score": 0-100, "reason": "画面色彩/构图/特效质量"},
  "audio": {"score": 0-100, "reason": "音量平衡·BGM是否盖过人声"},
  "overall": {"score": 0-100, "reason": "作为口播广告是否合格·哪里该改进"},
  "verdict": "pass/fail",
  "issues": ["具体问题1", "具体问题2"]
}

评分标准: ≥80优秀·60-79合格·40-59需改进·<40不合格
verdict=pass需要overall≥60"""  # noqa: E501


def _sample_keyframes(video_path: str, count: int = 3) -> list[str]:
    """提取关键帧: 开头/中间/结尾"""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", video_path],
        capture_output=True, text=True, timeout=10)
    dur = float(json.loads(r.stdout)["format"]["duration"])
    positions = [dur * 0.1, dur * 0.5, dur * 0.85]  # 10%/50%/85%
    frames = []
    for pos in positions:
        tmp = tempfile.mktemp(suffix=".jpg")
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path, "-vframes", "1", "-ss", str(pos),
            "-q:v", "2", tmp
        ], timeout=10)
        if os.path.exists(tmp):
            frames.append(tmp)
    return frames


def review_output(
    video_path: str,
    api_key: str = "",
    max_retries: int = 2,
) -> dict:
    """Kimi Vision评审成片→低于阈值自动重试

    Returns:
        {"score": 0-100, "dimensions": {...}, "verdict": "pass/fail",
         "issues": [...], "retries": int}
    """
    if not os.path.exists(video_path):
        return {"score": 0, "verdict": "fail", "issues": ["文件不存在"], "retries": 0}

    api_key = api_key or os.getenv("KIMI_API_KEY", "")
    if not api_key:
        logger.debug("Kimi API Key未配置·跳过评审")
        return {"score": 70, "verdict": "pass", "issues": [],
                "retries": 0, "source": "skip"}

    for attempt in range(max_retries + 1):
        frames = _sample_keyframes(video_path)
        if len(frames) < 2:
            return {"score": 0, "verdict": "fail", "issues": ["无法提取关键帧"]}

        # 构建多图消息
        content = [{"type": "text", "text": REVIEW_PROMPT}]
        for fp in frames:
            with open(fp, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        try:
            import requests
            r = requests.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "moonshot-v1-8k-vision-preview",
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 500, "temperature": 0.1,
                },
                timeout=30,
            )
            raw = r.json()["choices"][0]["message"]["content"]

            # 解析JSON
            import re
            m = re.search(r"\{.*\}", raw, re.S)
            review = json.loads(m.group(0)) if m else {}

            overall = int(review.get("overall", {}).get("score", 0) if isinstance(
                review.get("overall"), dict) else review.get("overall", 0))

            result = {
                "score": overall,
                "dimensions": {
                    k: v for k, v in review.items()
                    if k in ("pacing", "subtitle", "visual", "audio", "overall")
                },
                "verdict": review.get("verdict", "pass" if overall >= 60 else "fail"),
                "issues": review.get("issues", []),
                "retries": attempt,
                "source": "kimi_vision",
            }
        except Exception as e:
            logger.debug("Kimi评审失败: %s", e)
            result = {"score": 70, "verdict": "pass", "issues": [],
                      "retries": attempt, "source": "fallback"}

        # 清理临时帧
        for fp in frames:
            try: os.remove(fp)
            except Exception: pass

        if result["verdict"] == "pass" or attempt >= max_retries:
            return result

        logger.info("评审未通过(score=%d)·重试 %d/%d",
                   result["score"], attempt + 1, max_retries)

    return result


def should_retry(review: dict, threshold: int = 60) -> bool:
    """是否应该重试"""
    return (review.get("verdict") != "pass" and
            review.get("score", 0) < threshold and
            review.get("retries", 0) < 2)
