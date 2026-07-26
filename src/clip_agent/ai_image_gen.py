"""
AI图像生成桥 v1 · 脚本描述→B-roll画面

支持引擎:
  dashscope: 阿里云WAN/DashScope(需DASHSCOPE_API_KEY)
  placeholder: 返回文字描述(用户手动拍摄/找素材)
"""
from __future__ import annotations
import base64, json, logging, os, tempfile, time
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_broll_image(prompt: str, style: str = "realistic",
                         engine: str = "auto") -> dict:
    """
    从文字描述生成B-roll画面。

    Args:
        prompt: 画面描述,如"花雕酒浸泡的虾·暖光·特写"
        style: realistic/food/product/vlog
        engine: auto/dashscope/placeholder

    Returns:
        {"success": bool, "image_path": str, "engine": str, "prompt": str}
    """
    if engine == "auto":
        if os.getenv("DASHSCOPE_API_KEY"):
            engine = "dashscope"
        else:
            engine = "placeholder"

    if engine == "dashscope":
        return _gen_dashscope(prompt, style)
    else:
        return _gen_placeholder(prompt, style)


def _gen_dashscope(prompt: str, style: str) -> dict:
    """阿里云DashScope/WAN AI生图"""
    try:
        import urllib.request

        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            return _gen_placeholder(prompt, style)

        # DashScope text-to-image API
        data = json.dumps({
            "model": "wan2.1-t2i",
            "input": {
                "prompt": f"{prompt}, {style} style, high quality, 1080x1920 portrait",
            },
            "parameters": {
                "size": "1080*1920",
                "n": 1,
            },
        }).encode()

        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-DashScope-Async": "enable",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        task_id = result.get("output", {}).get("task_id", "")
        if task_id:
            # Poll for result
            for _ in range(10):
                time.sleep(2)
                req2 = urllib.request.Request(
                    f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    status = json.loads(resp2.read())
                if status.get("output", {}).get("task_status") == "SUCCEEDED":
                    img_url = status["output"]["results"][0]["url"]
                    # Download image
                    tmp = tempfile.mktemp(suffix=".jpg")
                    with urllib.request.urlopen(img_url, timeout=30) as img_resp:
                        with open(tmp, "wb") as f:
                            f.write(img_resp.read())
                    return {"success": True, "image_path": tmp, "engine": "dashscope", "prompt": prompt}

        return _gen_placeholder(prompt, style)

    except Exception as e:
        logger.debug("DashScope失败,降级: %s", e)
        return _gen_placeholder(prompt, style)


def _gen_placeholder(prompt: str, style: str) -> dict:
    """无AI生图时: 返回文字描述+建议"""
    # 生成纯色占位图(带文字提示)
    try:
        import subprocess, tempfile
        tmp = tempfile.mktemp(suffix=".jpg")
        safe_prompt = prompt[:40].replace("'", "")
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-f","lavfi","-i",f"color=c=gray@0.3:size=1080x1920:d=1,"
            f"drawtext=text='{safe_prompt}':fontsize=36:fontcolor=white:x=(w-tw)/2:y=h*0.4",
            "-frames:v","1", tmp,
        ], timeout=10)
        return {
            "success": True,
            "image_path": tmp,
            "engine": "placeholder",
            "prompt": prompt,
            "shooting_guide": f"📱 拍摄指导: {prompt}",
        }
    except Exception:
        return {"success": False, "engine": "placeholder", "prompt": prompt}


def generate_broll_batch(prompts: list[str], style: str = "realistic") -> list[dict]:
    """批量生成B-roll画面"""
    results = []
    for prompt in prompts:
        results.append(generate_broll_image(prompt, style))
    return results
