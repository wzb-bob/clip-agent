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
    """自动检测 melt.exe 位置"""
    candidates = [
        os.path.expanduser("~/shotcut/Shotcut/melt.exe"),
        "C:/Program Files/Shotcut/melt.exe",
        os.path.expanduser("~/Desktop/Shotcut/melt.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # 最后尝试 PATH
    return "melt"

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
    """MLT 时间线引擎 · melt CLI 封装"""

    def __init__(self, melt_path: str = "", width: int = 1080, height: int = 1920, fps: int = 30):
        self.melt = melt_path or MELT
        self.width = width
        self.height = height
        self.fps = fps

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

        # ── Track 2: 文字叠加 ──
        text_items = self._build_text_items(plan)
        for text_def in text_items:
            parts.append("-track")
            parts.append(self._pango_producer(text_def))
            # affine 关键帧动画
            if text_def.get("animation"):
                parts.append(f'-attach affine transition.geometry="{text_def["animation"]}"')
            parts.append("-transition composite")
            parts.append(f"geometry={text_def.get('position','10%/80%:80%x15%:100%')}")

        # ── Track 3: BGM ──
        bgm = materials.get("bgm", "")
        if bgm and os.path.exists(bgm):
            parts.append(f'-track "{bgm}"')
            parts.append("-transition mix")
            parts.append("start=-10db:end=-10db")

        # ── Consumer: 输出 MP4 ──
        parts.append("-consumer")
        parts.append(f'avformat:"{output_path}"')
        parts.append("vcodec=libx264")
        parts.append("acodec=aac")
        parts.append("ab=192k")
        parts.append("crf=18")
        parts.append("preset=fast")
        parts.append("progressive=1")
        parts.append("real_time=-2")

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

    def render_with_fallback(self, plan, materials: dict, output_path: str) -> MltResult:
        """
        MLT渲染 → 失败 → melt直接模式 → 失败 → FFmpeg(上层调用)
        """
        # Level 1: MLT完整管线
        cmd = self.build_timeline(plan, materials, output_path)
        result = self.render(cmd)
        if result.success:
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

    @staticmethod
    def _color_for_category(category: str) -> str:
        return {"团购售卖":"vivid_pop", "老板IP":"film_warm", "引流进店":"clean_bright"}.get(category, "vivid_pop")

    def _build_text_items(self, plan) -> list[dict]:
        """从 VFX plan 提取文字叠加项"""
        items = []
        segs = getattr(plan, 'segments_vfx', []) or []
        accum = 0.0
        trans_dur = 0.3

        for i, seg in enumerate(segs):
            text = seg.get("text", "")
            role = seg.get("role", "")
            dur = seg.get("duration", 2.0)

            if not text or role not in ("hook", "cta"):
                accum += dur - (trans_dur if i < len(segs)-1 else 0)
                continue

            # 帧号计算 (30fps)
            start_frame = int(accum * 30)
            end_frame = int((accum + dur) * 30)

            if role == "hook":
                # 价格弹出: 从下飞入
                anim = f"{start_frame}=50%,120%:80%x15%:0%;{start_frame+10}~=50%,15%:80%x15%:100%;{end_frame-10}~=50%,15%:80%x15%:100%;{end_frame}=50%,120%:80%x15%:0%"
                items.append({
                    "text": text,
                    "size": 56,
                    "position": "10%/15%:80%x15%:100%",
                    "animation": anim,
                })
            elif role == "cta":
                # CTA: 底部固定·淡入淡出
                anim = f"{start_frame}=10%,80%:80%x15%:0%;{start_frame+8}~=10%,80%:80%x15%:100%;{end_frame-8}~=10%,80%:80%x15%:100%;{end_frame}=10%,80%:80%x15%:0%"
                items.append({
                    "text": text,
                    "size": 48,
                    "position": "10%/80%:80%x15%:100%",
                    "animation": anim,
                })

            accum += dur - (trans_dur if i < len(segs)-1 else 0)

        return items

    @staticmethod
    def _pango_producer(text_def: dict) -> str:
        """生成 pango 文字 producer 字符串"""
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
