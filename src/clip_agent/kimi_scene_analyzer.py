"""
Kimi Vision 场景分析 · 关键帧→画面描述

轻量级视频理解: 提取关键帧→Kimi K2.6描述画面内容
不需要分镜数据, 直接理解"画面里有什么"
"""
from __future__ import annotations
import base64, json, logging, os, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SceneDescription:
    """单帧的画面理解"""
    at_sec: float
    description: str           # "一位厨师正在大火翻炒小龙虾，锅中油光四溅..."


def analyze_video_scenes(video_path: str, frame_count: int = 3) -> list[SceneDescription]:
    """
    从视频中提取关键帧 → Kimi Vision 描述画面内容。

    轻量替代 analyze_video_chain() — 不需要分镜数据。
    """
    vp = Path(video_path)
    if not vp.exists():
        return []

    key = os.getenv("KIMI_API_KEY", "")
    if not key:
        logger.debug("KIMI_API_KEY 未配置")
        return []

    try:
        # 1. 获取视频时长
        r = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json","-show_format", str(vp)],
            capture_output=True, text=True, timeout=10,
        )
        duration = float(json.loads(r.stdout).get("format", {}).get("duration", 0))
        if duration <= 0:
            return []

        # 2. 在时长均匀分布的N个位置提取关键帧
        frames = []
        for i in range(frame_count):
            at_sec = duration * (i + 1) / (frame_count + 1)
            tmp = tempfile.mktemp(suffix=".jpg")
            subprocess.run([
                "ffmpeg","-y","-hide_banner","-loglevel","error",
                "-ss", str(at_sec), "-i", str(vp),
                "-vframes","1", "-q:v","2", tmp,
            ], timeout=15)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                with open(tmp, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                frames.append({"at_sec": round(at_sec, 1), "b64": b64, "tmp": tmp})

        if not frames:
            return []

        # 3. 批量发送给 Kimi Vision
        from ._imports import chat_vision
        if not chat_vision:
            chat_vision_fn = _try_kimi_direct
        else:
            chat_vision_fn = chat_vision

        results = []
        for f in frames:
            desc = _describe_frame(f["b64"], f["at_sec"], chat_vision_fn, key)
            if desc:
                results.append(SceneDescription(at_sec=f["at_sec"], description=desc))

        # 清理
        for f in frames:
            try: os.remove(f["tmp"])
            except: pass

        return results

    except Exception as e:
        logger.warning("Kimi场景分析失败: %s", e)
        return []


def _describe_frame(b64: str, at_sec: float, vision_fn, api_key: str) -> str:
    """调用Kimi Vision描述单帧画面"""
    try:
        # Try imported vision function first
        if vision_fn and vision_fn is not _try_kimi_direct:
            result = vision_fn(b64, f"描述这个短视频画面的内容(10字以内): 人物/产品/环境/动作")
            if isinstance(result, dict):
                return result.get("content", "")[:80]
            return str(result)[:80]

        # Direct Kimi API call
        return _try_kimi_direct(b64, api_key)
    except Exception as e:
        logger.debug("帧描述失败@%.1fs: %s", at_sec, e)
        return ""


def _try_kimi_direct(b64: str, api_key: str) -> str:
    """直接调用 Kimi Vision API (不依赖 gateway_client)"""
    try:
        import urllib.request

        data = json.dumps({
            "model": "moonshot-v1-32k-vision-preview",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": "描述这个短视频画面的内容(15字以内): 人物/产品/环境/动作"},
                ]
            }],
            "max_tokens": 100,
            "temperature": 0.1,
        }).encode()

        req = urllib.request.Request(
            "https://api.moonshot.cn/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"]
            return content.strip()[:80]
    except Exception as e:
        logger.debug("Kimi直接调用失败: %s", e)
        return ""


def quick_scene_description(video_path: str) -> str:
    """快速获取视频场景描述 (单帧)"""
    scenes = analyze_video_scenes(video_path, frame_count=1)
    if scenes:
        return scenes[0].description
    return ""
