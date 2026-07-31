"""
PNG模板生成器 · PIL渲染·圆角·半透明·不依赖系统字体

用法:
  from .template_gen import TemplateGen
  gen = TemplateGen()
  price_png = gen.price("68块!")
"""
from __future__ import annotations
import os, logging
from pathlib import Path

logger = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).parent / "templates" / "png"

class TemplateGen:
    def __init__(self):
        self._font_paths = [
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ]

    def _get_font(self, size: int):
        from PIL import ImageFont
        for fp in self._font_paths:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    def _save(self, img, name: str) -> str:
        out = str(TEMPLATES_DIR / f"{name}.png")
        os.makedirs(str(TEMPLATES_DIR), exist_ok=True)
        img.save(out, "PNG")
        return out

    def price(self, text: str) -> str:
        from PIL import Image, ImageDraw
        font = self._get_font(80)
        img = Image.new("RGBA", (1000, 300), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        # 大圆角40px(Kimi A/B验证最优)
        draw.rounded_rectangle([0,0,990,290], radius=40, fill=(220,20,60,230))
        draw.rounded_rectangle([3,3,987,287], radius=38, outline=(255,255,255,60), width=2)
        bbox = draw.textbbox((0,0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x, y = (1000-tw)//2, (300-th)//2-8
        # 粗阴影8px多方向(Kimi A/B验证最优)
        for dx, dy in [(-8,-8),(-8,8),(8,-8),(8,8),(-8,0),(8,0),(0,-8),(0,8)]:
            draw.text((x+dx, y+dy), text, fill=(0,0,0,160), font=font)
        draw.text((x, y), text, fill="white", font=font)
        return self._save(img, f"price_{hash(text)&0xffff}")

    def cta(self, text: str) -> str:
        from PIL import Image, ImageDraw
        font = self._get_font(60)
        dummy = ImageDraw.Draw(Image.new("RGBA",(1,1)))
        bbox = dummy.textbbox((0,0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        w, h = tw+160, th+60
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0,0,w-4,h-4], radius=h//2, fill=(220,20,60,240))
        x, y = (w-tw)//2, (h-th)//2-5
        for dx, dy in [(-2,-2),(2,-2),(-2,2),(2,2)]:
            draw.text((x+dx, y+dy), text, fill=(0,0,0,200), font=font)
        draw.text((x, y), text, fill="white", font=font)
        return self._save(img, f"cta_{hash(text)&0xffff}")

    def hook_label(self, text: str) -> str:
        from PIL import Image, ImageDraw
        font = self._get_font(48)
        dummy = ImageDraw.Draw(Image.new("RGBA",(1,1)))
        bbox = dummy.textbbox((0,0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        w, h = tw+80, th+30
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0,0,w,h], radius=20, fill=(0,0,0,160))
        draw.text((40, 15), text, fill="white", font=font)
        return self._save(img, f"hook_{hash(text)&0xffff}")

    def location_tag(self, text: str) -> str:
        from PIL import Image, ImageDraw
        font = self._get_font(40)
        txt = f"📍 {text}" if "📍" not in text else text
        dummy = ImageDraw.Draw(Image.new("RGBA",(1,1)))
        bbox = dummy.textbbox((0,0), txt, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        w, h = tw+60, th+24
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0,0,w,h], radius=16, fill=(255,255,255,210))
        draw.text((30, 12), txt, fill="black", font=font)
        return self._save(img, f"loc_{hash(text)&0xffff}")

_gen = None
def get_template_gen():
    global _gen
    if _gen is None: _gen = TemplateGen()
    return _gen
