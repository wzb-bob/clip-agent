"""
GLSL着色器渲染器 · FFmpeg filter_complex 映射 + OpenGL 备用路径

将56个GLSL着色器翻译为FFmpeg可用滤镜命令。
对于无FFmpeg等价物的着色器，标记为需要OpenGL渲染路径。
"""
from __future__ import annotations
import subprocess, tempfile, logging, os
from pathlib import Path
from dataclasses import dataclass, field
from .shader_catalog import get_shader, ShaderDef

logger = logging.getLogger(__name__)

SHADER_DIR = Path(__file__).parent / "shaders"


# ══════════════════════════════════════════════════════════
# FFmpeg滤镜映射表 (GLSL着色器 → ffmpeg filter_complex)
# ══════════════════════════════════════════════════════════

_FFMPEG_MAP: dict[str, str] = {
    # 空间效果
    "gaussian_blur": "smartblur=luma_radius={radius}:luma_strength={intensity}",
    "directional_blur": "tmix=frames=3:weights=1 1 1",  # 近似方向模糊
    "bloom": "",  # 需要 multi-input: split→blur→blend
    "glow": "",  # 同上
    # 调色效果
    "invert": "negate",
    "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "bleach_bypass": "eq=saturation=0.3:contrast=1.3:brightness=0.05",
    "color_balance": "",  # 需要独立 RGB 通道调整
    "hue_saturation": "hue=h={hue}:s={saturation}",
    "curves": "eq=contrast={contrast}:brightness={brightness}",
    "posterize": "pp=posterize:{levels}",
    "threshold": "format=gray,geq=lum_expr='if(gt(lum(X,Y),{threshold}*255),255,0)'",
    # 纹理叠加
    "film_grain": "noise=alls={intensity}:allf=t",
    "noise": "noise=alls={intensity}:allf=t",
    "vignette": "vignette=PI/4",
    # 变形
    "chromatic_aberration": "",
    "lens_distortion": "lenscorrection=cx=0.5:cy=0.5:k1={distortion}:k2=0",
    "mirror": "hflip",  # 简化版
    "kaleidoscope": "",
    # 复合
    "edge_detect": "edgedetect=low={threshold}:high={threshold}*2",
    "emboss": "edgedetect+negate",
    # 转场
    "crossfade": "xfade=transition=fade:duration=0.5:offset={offset}",
    "dissolve": "xfade=transition=dissolve:duration=0.5:offset={offset}",
    "push": "xfade=transition=slideleft:duration=0.3:offset={offset}",
    "slide": "xfade=transition=slideright:duration=0.3:offset={offset}",
    "wipe": "xfade=transition=wiperight:duration=0.3:offset={offset}",
    # 动态
    "strobe": "",
    "speed_ramp": "setpts={speed}*PTS",
}


def _build_bloom_chain(input_label: str, output_label: str,
                        threshold: float = 0.8, intensity: float = 0.5, radius: int = 5) -> str:
    """构建Bloom滤镜链 (split→blur→extract→overlay)"""
    return (
        f"[{input_label}]split[base][glow_src];"
        f"[glow_src]boxblur={radius}:2,"
        f"geq=lum_expr='if(gt(lum(X,Y),{threshold}*255),lum(X,Y)*{intensity},0)'[glow];"
        f"[base][glow]blend=all_mode=screen:all_opacity={intensity}[{output_label}]"
    )


def _build_glow_chain(input_label: str, output_label: str,
                       intensity: float = 0.5, radius: int = 10) -> str:
    """构建Glow滤镜链"""
    return (
        f"[{input_label}]split[base_g][glow_g];"
        f"[glow_g]boxblur={radius}:2,"
        f"geq=r='r(X,Y)*{intensity}':g='g(X,Y)*{intensity}':b='b(X,Y)*{intensity}'[glow_out];"
        f"[base_g][glow_out]blend=all_mode=addition[{output_label}]"
    )


def _build_ca_chain(input_label: str, output_label: str, intensity: float = 3.0) -> str:
    """构建色散滤镜链 (RGB通道分离+偏移)"""
    return (
        f"[{input_label}]split[ca_r][ca_g][ca_b];"
        f"[ca_r]geq=r='r(X-{intensity},Y)':g='g(X,Y)':b='b(X,Y)'[r_shift];"
        f"[ca_b]geq=r='r(X,Y)':g='g(X,Y)':b='b(X+{intensity},Y)'[b_shift];"
        f"[r_shift][ca_g]blend=all_mode=addition:all_opacity=0.5[mid];"
        f"[mid][b_shift]blend=all_mode=addition:all_opacity=0.5[{output_label}]"
    )


# ══════════════════════════════════════════════════════════
# GlslRenderer
# ══════════════════════════════════════════════════════════

@dataclass
class RenderResult:
    success: bool
    output_path: str = ""
    filter_used: str = ""
    error: str = ""
    duration_ms: float = 0.0


class GlslRenderer:
    """GLSL着色器渲染器·双路径: FFmpeg滤镜映射 + OpenGL备用"""

    def __init__(self):
        self._ffmpeg_available: bool | None = None

    @property
    def ffmpeg_ok(self) -> bool:
        if self._ffmpeg_available is None:
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
                self._ffmpeg_available = True
            except Exception:
                self._ffmpeg_available = False
        return self._ffmpeg_available

    def apply_shader(
        self,
        video_path: str,
        shader_name: str,
        output_path: str = "",
        params: dict | None = None,
    ) -> RenderResult:
        """
        对视频应用指定着色器。

        Args:
            video_path: 输入视频路径
            shader_name: 着色器名称 (如 'bloom', 'chromatic_aberration')
            output_path: 输出路径 (默认: 输入名_shader名.mp4)
            params: 着色器参数覆盖 (默认使用shader定义中的值)

        Returns:
            RenderResult with output path and status
        """
        import time
        t0 = time.time()

        shader = get_shader(shader_name)
        if not shader:
            return RenderResult(success=False, error=f"未知着色器: {shader_name}")

        if not output_path:
            in_path = Path(video_path)
            output_path = str(in_path.parent / f"{in_path.stem}_{shader_name}.mp4")

        # 合并参数
        final_params: dict[str, float] = {}
        for pname, (default, _min, _max) in shader.params.items():
            final_params[pname] = default
        if params:
            final_params.update(params)

        # 尝试FFmpeg路径
        try:
            result = self._apply_via_ffmpeg(video_path, output_path, shader, final_params)
            result.duration_ms = (time.time() - t0) * 1000
            return result
        except Exception as e:
            return RenderResult(
                success=False,
                error=f"渲染失败: {str(e)[:200]}",
                duration_ms=(time.time() - t0) * 1000,
            )

    def _apply_via_ffmpeg(
        self, video_path: str, output_path: str,
        shader: ShaderDef, params: dict[str, float],
    ) -> RenderResult:
        """FFmpeg滤镜映射路径"""
        filter_str = self._build_filter(shader, params)

        if not filter_str:
            return RenderResult(
                success=False,
                error=f"着色器 '{shader.name}' 需要OpenGL渲染路径 (无FFmpeg等价滤镜)",
                filter_used="opengl_required",
            )

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vf", filter_str,
            "-c:a", "copy",
            output_path,
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            return RenderResult(
                success=False,
                filter_used=filter_str,
                error=f"FFmpeg错误: {proc.stderr[:300]}",
            )

        return RenderResult(
            success=True,
            output_path=output_path,
            filter_used=filter_str,
        )

    def _build_filter(self, shader: ShaderDef, params: dict[str, float]) -> str:
        """根据着色器类型构建FFmpeg滤镜字符串"""
        name = shader.name

        # 特殊多滤镜链
        if name == "bloom":
            return _build_bloom_chain(
                "0", "v",
                threshold=params.get("uThreshold", 0.8),
                intensity=params.get("uIntensity", 0.5),
                radius=int(params.get("uRadius", 5)),
            )
        elif name == "glow":
            return _build_glow_chain(
                "0", "v",
                intensity=params.get("uIntensity", 0.5),
                radius=int(params.get("uRadius", 10)),
            )
        elif name == "chromatic_aberration":
            return _build_ca_chain(
                "0", "v",
                intensity=params.get("uIntensity", 3.0),
            )

        # 简单映射
        template = _FFMPEG_MAP.get(name, "")
        if not template:
            return ""

        # 填充参数
        param_map = {
            "intensity": params.get("uIntensity", 1.0),
            "radius": params.get("uRadius", 5.0),
            "threshold": params.get("uThreshold", 0.5),
            "contrast": params.get("uContrast", 0.0),
            "brightness": params.get("uBrightness", 0.0),
            "hue": params.get("uHue", 0.0),
            "saturation": params.get("uSaturation", 0.0),
            "levels": int(params.get("uLevels", 8)),
            "speed": params.get("uSpeed", 1.0),
            "distortion": params.get("uDistortion", 0.1),
            "offset": params.get("offset", 1.0),
            "angle": params.get("uAngle", 0.0),
        }
        # 安全填充——只替换模板中存在的变量
        result = template
        for k, v in param_map.items():
            placeholder = '{' + k + '}'
            if placeholder in result:
                result = result.replace(placeholder, str(v))
            # 为整数参数提供整数版本
            placeholder_d = '{' + k + ':d}'
            if placeholder_d in result:
                result = result.replace(placeholder_d, str(int(v)))

        return result

    def get_shader_capabilities(self) -> dict[str, bool]:
        """返回所有着色器的可用性 (True=FFmpeg可用, False=需OpenGL)"""
        caps = {}
        for name in _FFMPEG_MAP:
            caps[name] = bool(_FFMPEG_MAP[name])
        # 特殊链式滤镜
        caps["bloom"] = True
        caps["glow"] = True
        caps["chromatic_aberration"] = True
        return caps

    def apply_chain(
        self,
        video_path: str,
        shader_chain: list[tuple[str, dict | None]],
        output_path: str = "",
    ) -> RenderResult:
        """
        应用效果链（多个着色器按顺序叠加）。

        Args:
            video_path: 输入视频
            shader_chain: [(着色器名, 参数字典), ...]
            output_path: 输出路径
        """
        import time
        t0 = time.time()

        if not shader_chain:
            return RenderResult(success=False, error="空效果链")

        if not output_path:
            in_path = Path(video_path)
            chain_name = "_".join(s[0] for s in shader_chain[:3])
            output_path = str(in_path.parent / f"{in_path.stem}_{chain_name}.mp4")

        # 构建复合滤镜链
        filters = []
        current_label = "0"
        temp_files = []

        for i, (shader_name, params) in enumerate(shader_chain):
            shader = get_shader(shader_name)
            if not shader:
                continue

            final_params = {}
            for pname, (default, _min, _max) in shader.params.items():
                final_params[pname] = default
            if params:
                final_params.update(params)

            filter_str = self._build_filter(shader, final_params)
            if not filter_str:
                continue

            next_label = f"v{i}" if i < len(shader_chain) - 1 else "v"
            filters.append(filter_str.replace("[0]", f"[{current_label}]").replace("[v]", f"[{next_label}]"))
            current_label = next_label

        if not filters:
            return RenderResult(success=False, error="无可用的FFmpeg滤镜")

        combined_filter = ";".join(filters)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vf", combined_filter,
            "-c:a", "copy",
            output_path,
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            return RenderResult(success=False, filter_used=combined_filter,
                              error=f"FFmpeg错误: {proc.stderr[:300]}")

        return RenderResult(success=True, output_path=output_path,
                          filter_used=combined_filter,
                          duration_ms=(time.time() - t0) * 1000)


# ══════════════════════════════════════════════════════════
# 便捷函数
# ══════════════════════════════════════════════════════════

_renderer: GlslRenderer | None = None

def _get_renderer() -> GlslRenderer:
    global _renderer
    if _renderer is None:
        _renderer = GlslRenderer()
    return _renderer


def apply_shader_to_video(video_path: str, shader_name: str,
                           output_path: str = "", **params) -> RenderResult:
    """便捷函数: 应用单个着色器"""
    return _get_renderer().apply_shader(video_path, shader_name, output_path,
                                         params if params else None)


def apply_effect_chain(video_path: str,
                        shader_chain: list[tuple[str, dict | None]],
                        output_path: str = "") -> RenderResult:
    """便捷函数: 应用效果链"""
    return _get_renderer().apply_chain(video_path, shader_chain, output_path)
