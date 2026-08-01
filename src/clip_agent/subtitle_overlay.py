"""
字幕图片叠加 · PNG渲染·比FFmpeg文字滤镜更可靠

不依赖FFmpeg drawtext/subtitles/ass滤镜
用PIL渲染文字到透明PNG→FFmpeg overlay叠加
"""
from __future__ import annotations
import logging, os, tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def render_text_to_png(text: str, width: int, height: int,
                       font_size: int = 56) -> str | None:
    """将文字渲染为透明PNG图片"""
    if not HAS_PIL:
        return None

    try:
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 尝试加载中文字体
        font = None
        # 跨平台: Windows(WINDIR自适应)/Mac/Linux
        _windir = os.environ.get("WINDIR", "C:/Windows").replace("\\", "/")
        candidates = [
            f"{_windir}/Fonts/simhei.ttf",
            f"{_windir}/Fonts/msyh.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        for fp in candidates:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, font_size)
                    break
                except Exception:
                    continue

        if font is None:
            font = ImageFont.load_default()

        # 文字居中·黑边描边
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (width - tw) // 2
        y = height * 0.65  # 下方1/3处

        # 描边(画4个偏移的黑色文字)
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2)]:
            draw.text((x+dx, y+dy), text, font=font, fill=(0,0,0,180))
        # 主体白色
        draw.text((x, y), text, font=font, fill=(255,255,255,240))

        tmp = tempfile.mktemp(suffix=".png")
        img.save(tmp, "PNG")
        return tmp
    except Exception as e:
        logger.warning("PNG字幕渲染失败: %s", e)
        return None


def burn_png_subtitle(video_path: str, text: str, output_path: str,
                      font_size: int = 56) -> str | None:
    """在视频上叠加文字PNG（比FFmpeg滤镜更可靠）"""
    try:
        import subprocess, json

        # 获取视频尺寸
        r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_streams",video_path],
                         capture_output=True, text=True, timeout=10)
        vs = [s for s in json.loads(r.stdout).get("streams",[]) if s.get("codec_type")=="video"][0]
        w, h = vs["width"], vs["height"]

        png_path = render_text_to_png(text, w, h, font_size)
        if not png_path:
            return None

        tmp = tempfile.mktemp(suffix=".mp4")
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path, "-i", png_path,
            "-filter_complex", "[0:v][1:v]overlay=0:0",
            "-c:v","libx264","-preset","fast","-crf","18",
            "-c:a","copy",
            tmp
        ], timeout=120)

        try: os.remove(png_path)
        except: pass

        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, output_path)
            return output_path
    except Exception as e:
        logger.warning("PNG叠加失败: %s", e)
    return None
