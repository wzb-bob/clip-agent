"""
产品图→AI带货视频 v1 · 猪脚AI启发

输入: 产品图片 + 价格 + 卖点
输出: 短视频(图片Ken Burns动画 + TTS语音 + 字幕)
"""
from __future__ import annotations
import logging, os, subprocess, tempfile, time
from pathlib import Path

logger = logging.getLogger(__name__)


def create_product_video(
    product_image: str,
    price: str,
    selling_points: list[str],
    output_path: str = "",
    voice: str = "zh-CN-XiaoxiaoNeural",
) -> dict:
    """
    产品图→AI带货视频。

    Args:
        product_image: 产品图片路径
        price: 价格文字("68块!")
        selling_points: 卖点列表(["十只活虾","干煸技术","花雕酒泡8小时"])
        output_path: 输出路径
        voice: TTS语音

    Returns:
        {"success": bool, "video_path": str, "duration": float}
    """
    vp = Path(product_image)
    if not vp.exists():
        return {"success": False, "error": "图片不存在"}

    try:
        # 1. 生成口播脚本
        points_text = "。".join(selling_points)
        script = f"{price}！{points_text}！左下角团购已上线！"

        # 2. TTS语音
        import asyncio, edge_tts
        async def gen_tts():
            tts = tempfile.mktemp(suffix=".mp3")
            await edge_tts.Communicate(script, voice).save(tts)
            return tts
        tts_path = asyncio.run(gen_tts())

        # 3. 获取语音时长
        import json
        r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",tts_path],
                         capture_output=True, text=True, timeout=10)
        duration = float(json.loads(r.stdout)["format"]["duration"])

        # 4. 图片Ken Burns动画+语音+字幕
        out = output_path or str(vp.parent / f"带货_{vp.stem}.mp4")
        vf = (
            f"scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"zoompan=z='1.03+0.03*sin(on*0.05)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
            f"fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.5}:d=0.5,"
            f"drawtext=text='{price}':fontsize=72:fontcolor=red@0.95:"
            f"x=(w-tw)/2:y=h*0.3:enable='between(t,0,{duration})':"
            f"bordercolor=black@0.5:borderw=3"
        )
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-loop","1","-i", str(vp),
            "-i", tts_path,
            "-vf", vf,
            "-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","aac","-b:a","192k",
            "-t", str(duration),
            "-pix_fmt","yuv420p",
            out
        ], timeout=60)

        try: os.remove(tts_path)
        except: pass

        return {"success": os.path.exists(out), "video_path": out, "duration": duration}
    except Exception as e:
        return {"success": False, "error": str(e)}
