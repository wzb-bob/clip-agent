"""
MLT 剪辑引擎 · melt CLI 封装

替换 FFmpeg 多Pass 管线为 MLT 多轨时间线:
  Track 0: 口播主画面
  Track 1: B-roll 画中画 (composite)
  Track 2: 文字叠加 (pango + affine 关键帧动画)
  Track 3: BGM (mix + volume 闪避)

用法:
  engine = MltEngine()
  cmd = engine.build_timeline(plan, materials)
  output = engine.render(cmd)

依赖: Shotcut 便携版 (提供 melt.exe)
  MELT_PATH = ~/shotcut/Shotcut/melt.exe 或自动检测
"""
from __future__ import annotations
import os, subprocess, logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── melt 路径检测 ──

def _find_melt() -> str:
    """自动检测 melt 位置(跨平台: Windows便携版/安装版·Mac .app·Linux PATH)"""
    import shutil
    # PATH优先(brew/apt安装的直接可用)
    on_path = shutil.which("melt") or shutil.which("melt.exe")
    if on_path:
        return on_path
    candidates = [
        # Windows
        os.path.expanduser("~/shotcut/Shotcut/melt.exe"),
        "C:/Program Files/Shotcut/melt.exe",
        os.path.expanduser("~/Desktop/Shotcut/melt.exe"),
        # macOS (Shotcut.app)
        "/Applications/Shotcut.app/Contents/MacOS/melt",
        os.path.expanduser("~/Applications/Shotcut.app/Contents/MacOS/melt"),
        # Linux
        "/usr/bin/melt",
        "/usr/local/bin/melt",
        os.path.expanduser("~/shotcut/Shotcut/melt"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return "melt"  # 兜底交给系统报错

MELT = _find_melt()


# ══════════════════════════════════════════════════════════
# 效果映射表
# ══════════════════════════════════════════════════════════

# 调色 → frei0r 滤镜
COLOR_EFFECTS = {
    "vivid_pop":     "frei0r.brightness brightness=0.05:contrast=1.1",
    "film_warm":     "frei0r.curves curve_r='0/0 0.3/0.35 0.7/0.72 1/1':curve_b='0/0 0.5/0.48 1/0.95'",
    "clean_bright":  "frei0r.brightness brightness=0.08:contrast=1.05",
    "warm_boost":    "frei0r.brightness brightness=0.05:contrast=1.05",
    "warm_grade":    "frei0r.brightness brightness=0.03:contrast=1.03",
    "bleach_bypass": "frei0r.brightness brightness=0.02:contrast=1.15",
    "cool_metal":    "frei0r.brightness brightness=-0.02:contrast=1.12",
}

# 转场映射
TRANSITIONS = {
    "fade":     "luma",
    "cut":      "luma",
    "crossfade":"mix",
    "slideleft":"composite",
}


@dataclass
class MltResult:
    success: bool
    output_path: str = ""
    melt_cmd: str = ""
    duration_ms: float = 0.0
    error: str = ""


class MltEngine:
    """MLT 时间线引擎 · melt CLI 封装

    注意: Windows上pango中文渲染依赖fontconfig, 可能不可用。
    降级方案: 用FFmpeg预渲染PNG文字→qimage叠加。
    """

    def __init__(self, melt_path: str = "", width: int = 1080, height: int = 1920, fps: int = 30):
        self.melt = melt_path or MELT
        self.width = width
        self.height = height
        self.fps = fps
        self._use_pango = self._check_pango()

    @property
    def profile(self) -> str:
        """MLT profile 字符串"""
        return f"atsc_1080p_{self.fps}" if self.width == 1920 else ""

    def verify(self) -> bool:
        """验证 melt 可用"""
        try:
            r = subprocess.run([self.melt, "-version"], capture_output=True, text=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return False

    def build_timeline(self, plan, materials: dict, output_path: str) -> str:
        """
        将 VFX 计划转为 melt 命令行。

        materials: {
            "talking": "口播.mp4",            # 口播主视频
            "broll": ["空镜1.mp4", ...],      # B-roll 素材
            "bgm": "bgm.mp3",                 # 背景音乐(可选)
            "product": ["产品.mp4"],           # 产品特写(可选)
        }
        返回: melt 命令字符串
        """
        parts = [self.melt]

        # ── Track 0: 口播主画面 ──
        talking = materials.get("talking", "")
        if talking and os.path.exists(talking):
            parts.append(f'"{talking}"')

            # 全局调色
            color_name = self._color_for_category(getattr(plan, 'category', '团购售卖'))
            if color_name in COLOR_EFFECTS:
                parts.append(f"-attach {COLOR_EFFECTS[color_name]}")

            # 暗角(老板IP)
            if getattr(plan, 'category', '') == "老板IP":
                parts.append("-attach frei0r.vignette radius=0.8:softness=0.5:opacity=0.5")
        else:
            parts.append("color:black")

        # ── Track 1: B-roll 画中画 ──
        brolls = materials.get("broll", [])
        for i, br in enumerate(brolls):
            if os.path.exists(br):
                parts.append(f"-track")
                parts.append(f'"{br}"')
                parts.append("-transition composite")
                # 右上角小窗: 65%/8%位置, 33%x19%大小
                parts.append(f"geometry=65%/8%:33%x19%:100%")

        # ── Track 2: 文字叠加(PNG模板·FFmpeg后处理·比melt qimage快50倍) ──
        # PNG文字由FFmpeg在渲染后叠加·这里只收集文字数据
        text_items = self._build_text_items(plan)
        self._text_overlays = text_items  # 存下来供外部使用

        # ── Track 3: BGM(音量闪避·长度=视频) ──
        bgm = materials.get("bgm", "")
        if bgm and os.path.exists(bgm):
            total_dur = sum(s.get("duration", 2.0) for s in (getattr(plan, 'segments_vfx', []) or []))
            total_frames = max(int(total_dur * 30), 30)
            parts.append(f'-track "{bgm}" out={total_frames}')
            vol_keyframes = self._build_bgm_ducking(plan)
            if vol_keyframes:
                parts.append(f"-attach volume gain=\"{vol_keyframes}\"")
            parts.append("-transition mix")
            parts.append("start=-8db:end=-8db")

        # ── Consumer: 输出 MP4(长度=口播轨) ──
        parts.append("-consumer")
        parts.append(f'avformat:"{output_path}"')
        parts.append("vcodec=libx264")
        parts.append("acodec=aac")
        parts.append("ab=192k")
        parts.append("crf=18")
        parts.append("preset=fast")
        parts.append("progressive=1")
        parts.append("real_time=-2")
        parts.append("terminate_on_pause=1")

        return " ".join(parts)

    def render(self, cmd: str, timeout: int = 600) -> MltResult:
        """执行 melt 命令·返回结果"""
        import time
        t0 = time.time()

        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=os.getcwd()
            )
            elapsed = (time.time() - t0) * 1000

            # 解析输出路径
            output_path = ""
            if "avformat:" in cmd:
                import re
                m = re.search(r'avformat:"([^"]+)"', cmd)
                if m:
                    output_path = m.group(1)

            if proc.returncode == 0 and output_path and os.path.exists(output_path):
                return MltResult(success=True, output_path=output_path,
                                melt_cmd=cmd, duration_ms=elapsed)
            else:
                return MltResult(success=False, melt_cmd=cmd,
                                duration_ms=elapsed,
                                error=proc.stderr[:500] if proc.stderr else f"exit={proc.returncode}")
        except subprocess.TimeoutExpired:
            return MltResult(success=False, melt_cmd=cmd, error="渲染超时")
        except Exception as e:
            return MltResult(success=False, melt_cmd=cmd, error=str(e)[:500])

    def overlay_text_pngs(self, video_path: str, output_path: str) -> bool:
        """FFmpeg叠加PNG文字(MLT渲染后调用)"""
        if not getattr(self, '_text_overlays', None):
            return False
        import subprocess
        pngs = []
        for td in self._text_overlays:
            png = td.get("png", "")
            if png and os.path.exists(png):
                pngs.append(png)
        if not pngs:
            return False

        # 逐个叠加·根据文字类型决定位置(hook上方·CTA底部)
        current = video_path
        for i, td in enumerate(self._text_overlays):
            png = td.get("png", "")
            if not png or not os.path.exists(png):
                continue
            role = "hook" if "price_" in os.path.basename(png) else "cta"
            # hook在上方5%(避免遮挡人脸)·CTA在底部85%
            y_pos = "0.05" if role == "hook" else "0.85"
            tmp = output_path.replace('.mp4', f'_ov{i}.mp4')
            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                   "-i", current, "-i", png,
                   "-filter_complex", f"[0:v][1:v]overlay=(W-w)/2:(H-h)*{y_pos}:eval=init[out]",
                   "-map", "[out]", "-map", "0:a:0?",
                   "-c:v", "libx264", "-preset", "fast", "-crf", "18", tmp]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if os.path.exists(tmp) and os.path.getsize(tmp) > 500:
                    current = tmp
            except Exception:
                pass

        if current != video_path:
            try:
                import shutil
                shutil.move(current, output_path)
            except Exception:
                pass
            return os.path.exists(output_path) and os.path.getsize(output_path) > 500
        return False

    def render_with_fallback(self, plan, materials: dict, output_path: str) -> MltResult:
        """
        MLT渲染(调色·转场) → FFmpeg叠加PNG文字 → 失败 → melt直接
        """
        # Level 1: MLT渲染(无文字·快速)
        cmd = self.build_timeline(plan, materials, output_path)
        result = self.render(cmd)
        if result.success:
            # 叠加PNG文字
            png_output = output_path.replace('.mp4', '_text.mp4')
            if self.overlay_text_pngs(result.output_path, png_output):
                result.output_path = png_output
            return result
            return result

        # Level 2: melt 最小模式(单轨·无反效果)
        talking = materials.get("talking", "")
        if talking and os.path.exists(talking):
            simple_cmd = f'{self.melt} "{talking}" -consumer avformat:"{output_path}" vcodec=libx264 acodec=aac crf=18'
            result2 = self.render(simple_cmd)
            if result2.success:
                result2.error = f"降级: MLT完整模式失败({result.error[:100]})"
                return result2

        return result  # 失败,让上层降到FFmpeg

    # ── 内部辅助 ──

    def _check_pango(self) -> bool:
        """检测pango中文渲染是否可用·不可用则降级到PNG文字"""
        try:
            import tempfile, subprocess
            test_out = os.path.join(tempfile.gettempdir(), "_mlt_pango_test.mp4")
            cmd = f'{self.melt} color:red out=5 -track "pango:测试" out=5 -transition composite -consumer avformat:"{test_out}" vcodec=libx264 crf=18 real_time=-2'
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return proc.returncode == 0 and os.path.exists(test_out) and os.path.getsize(test_out) > 500
        except Exception:
            return False

    @staticmethod
    def _render_text_png(text: str, output_path: str, font_size: int = 48, color: str = "white"):
        """用PIL渲染中文文字PNG(独立于系统字体·始终可用)"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGBA", (800, 200), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # 跨平台字体候选: Windows(WINDIR自适应)/Mac/Linux
            _windir = os.environ.get("WINDIR", "C:/Windows").replace("\\", "/")
            font = None
            for fp in [f"{_windir}/Fonts/simhei.ttf", f"{_windir}/Fonts/msyh.ttc",
                       "/System/Library/Fonts/PingFang.ttc",
                       "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                       "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, font_size)
                    break
            if font is None:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            # 裁剪到文字大小
            img = Image.new("RGBA", (tw + 40, th + 20), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((20, 10), text, fill=color, font=font)
            img.save(output_path, "PNG")
            return True
        except ImportError:
            return False

    @staticmethod
    def _color_for_category(category: str) -> str:
        return {"团购售卖":"vivid_pop", "老板IP":"film_warm", "引流进店":"clean_bright"}.get(category, "vivid_pop")

    def _build_text_items(self, plan) -> list[dict]:
        """从 VFX plan 提取文字叠加项·使用PNG模板(Windows pango中文不可用)"""
        items = []
        try:
            from .template_gen import get_template_gen
            tgen = get_template_gen()
        except ImportError:
            tgen = None
        segs = getattr(plan, 'segments_vfx', []) or []
        accum = 0.0
        trans_dur = 0.3

        for i, seg in enumerate(segs):
            text = seg.get("text", "")
            role = seg.get("role", "")
            dur = seg.get("duration", 2.0)

            if not text:
                accum += dur - (trans_dur if i < len(segs)-1 else 0)
                continue

            start_frame = int(accum * 30)
            end_frame = int((accum + dur) * 30)

            # 生成PNG模板·替代pango(Windows中文不可用)
            png = ""
            if tgen:
                try:
                    if role == "hook": png = tgen.price(text)
                    elif role == "cta": png = tgen.cta(text)
                except Exception: pass

            if role == "hook":
                anim = f"{start_frame}=50%,130%:40%x14%:0%;{start_frame+12}~=50%,12%:40%x14%:100%;{end_frame-12}~=50%,12%:40%x14%:100%;{end_frame}=50%,130%:40%x14%:0%"
                items.append({"text": text, "size": 64,
                    "position": "30%/12%:40%x14%:100%", "animation": anim, "png": png})
            elif role == "cta":
                anim = f"{start_frame}=10%,82%:60%x14%:0%;{start_frame+10}~=10%,82%:60%x14%:100%;{end_frame-10}~=10%,82%:60%x14%:100%;{end_frame}=10%,82%:60%x14%:0%"
                items.append({"text": text, "size": 44,
                    "position": "20%/82%:60%x14%:100%", "animation": anim, "png": png})
            elif role == "body":
                # 字幕式·底部居中·淡入淡出(短)
                if len(text) > 3:  # 至少4个字才显示
                    anim = f"{start_frame+5}=10%,88%:80%x10%:0%;{start_frame+10}~=10%,88%:80%x10%:100%;{end_frame-15}~=10%,88%:80%x10%:100%;{end_frame-5}=10%,88%:80%x10%:0%"
                    items.append({"text": text, "size": 28,
                        "position": "10%/88%:80%x10%:100%", "animation": anim})

            accum += dur - (trans_dur if i < len(segs)-1 else 0)

        return items

    def _build_bgm_ducking(self, plan) -> str:
        """生成BGM音量闪避关键帧(有文字/口播时BGM降低)"""
        segs = getattr(plan, 'segments_vfx', []) or []
        if not segs:
            return ""
        total_frames = int(sum(s.get("duration",2) for s in segs) * 30)
        keyframes = []
        accum = 0.0
        for i, seg in enumerate(segs):
            dur = seg.get("duration", 2.0)
            role = seg.get("role", "")
            start_f = int(accum * 30)
            end_f = int((accum + dur) * 30)
            if role in ("hook", "cta", "body"):
                # 有内容段: BGM降低
                keyframes.append(f"{start_f}=-3db")
                keyframes.append(f"{start_f+3}=-8db")
                keyframes.append(f"{end_f-3}=-8db")
                keyframes.append(f"{end_f}=-3db")
            accum += dur
        if keyframes:
            keyframes.insert(0, "0=-3db")
            keyframes.append(f"{total_frames}=-3db")
        return ";".join(keyframes) if keyframes else ""

    @staticmethod
    def _pango_producer(text_def: dict) -> str:
        """生成文字producer——PNG优先·pango降级"""
        png = text_def.get("png", "")
        if png and os.path.exists(png):
            return f'"{png}"'
        text = text_def["text"].replace('"', '\\"')
        size = text_def.get("size", 48)
        span = f"<span font='Sans {size}' foreground='white'>{text}</span>"
        return f'pango:"{span}"'


# ══════════════════════════════════════════════════════════
# 便捷函数
# ══════════════════════════════════════════════════════════

def mlt_verify() -> bool:
    """检查 MLT 是否可用"""
    return MltEngine().verify()


def mlt_clip(talking: str, script: str = "", output: str = "",
             broll: list = None, bgm: str = "",
             category: str = "团购售卖") -> MltResult:
    """一行出片——MLT 版本"""
    if not output:
        output = str(Path(talking).parent / f"mlt_{Path(talking).stem}.mp4")

    from .chatcut_vfx import VfxPlan
    plan = VfxPlan(success=True, category=category, segments_vfx=[
        {"role":"hook","text":script[:15] if script else "","duration":2.0},
        {"role":"body","text":"","duration":3.0},
        {"role":"cta","text":"囤券" if "囤" in script else "","duration":2.0},
    ])

    engine = MltEngine()
    materials = {"talking": talking}
    if broll: materials["broll"] = [b for b in broll if os.path.exists(b)]
    if bgm: materials["bgm"] = bgm

    return engine.render_with_fallback(plan, materials, output)
