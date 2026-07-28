"""
着色器目录 · 56个GLSL着色器元数据
从 vfx-studio/shader_effect_engine.dart + shader_library.dart 搬运
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field

SHADER_DIR = Path(__file__).parent / "shaders"

# ===== 着色器分类（对齐 FlowVid 的 _RenderCategory） =====

SHADER_CATEGORIES: dict[str, list[str]] = {
    "spatial": [  # 空间效果·模糊/变形
        "gaussian_blur", "directional_blur", "radial_blur", "tilt_shift",
        "bloom", "glow",
    ],
    "color": [  # 调色效果·颜色校正
        "invert", "sepia", "bleach_bypass", "color_balance",
        "hue_saturation", "channel_mixer", "gradient_map",
        "curves", "posterize", "threshold",
    ],
    "texture": [  # 纹理叠加·胶片/噪点
        "film_grain", "noise", "scanlines", "vhs_noise", "bad_tv",
        "halftone",
    ],
    "distortion": [  # 变形效果·镜头/扭曲
        "chromatic_aberration", "lens_distortion", "lens_flare", "light_leak",
        "bulge", "twirl", "ripple", "wave_distort", "kaleidoscope", "mirror",
        "prism", "rays", "echo", "pixel_sort",
    ],
    "glitch": [  # 故障效果
        "glitch_blocks", "data_glitch", "rgb_shift",
    ],
    "composite": [  # 合成效果·叠加/边框
        "vignette", "frame_blend", "edge_detect", "find_edges", "emboss",
    ],
    "transition": [  # 转场效果
        "crossfade", "dissolve", "push", "slide", "wipe", "radial_wipe",
        "zoom_transition", "page_curl",
    ],
    "dynamic": [  # 动态效果·时间相关
        "strobe", "speed_ramp", "time_displacement", "venetian_blinds",
    ],
}


@dataclass
class ShaderDef:
    """单个着色器定义"""
    name: str
    category: str
    file: str
    desc: str = ""
    params: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    # params: {name: (default, min, max)}


# ===== 56个着色器全量注册（从 shader_effect_engine.dart 搬运） =====

_SHADERS: dict[str, ShaderDef] = {
    # ── 空间效果 ──
    "gaussian_blur": ShaderDef("gaussian_blur", "spatial", "gaussian_blur.frag",
        "高斯模糊·可调半径", {"uRadius": (3.0, 0.5, 20.0), "uIntensity": (1.0, 0.0, 1.0)}),
    "directional_blur": ShaderDef("directional_blur", "spatial", "directional_blur.frag",
        "方向模糊·运动感", {"uAngle": (0.0, 0.0, 360.0), "uLength": (10.0, 1.0, 50.0), "uIntensity": (1.0, 0.0, 1.0)}),
    "radial_blur": ShaderDef("radial_blur", "spatial", "radial_blur.frag",
        "径向模糊·变焦感", {"uCenterX": (0.5, 0.0, 1.0), "uCenterY": (0.5, 0.0, 1.0), "uStrength": (0.1, 0.0, 1.0)}),
    "tilt_shift": ShaderDef("tilt_shift", "spatial", "tilt_shift.frag",
        "移轴模糊·微缩模型效果", {"uFocusY": (0.5, 0.0, 1.0), "uFocusWidth": (0.15, 0.02, 0.5), "uBlurSize": (15.0, 1.0, 40.0)}),
    "bloom": ShaderDef("bloom", "spatial", "bloom.frag",
        "泛光·高亮溢出", {"uThreshold": (0.8, 0.0, 1.0), "uIntensity": (0.5, 0.0, 2.0), "uRadius": (3.0, 1.0, 10.0)}),
    "glow": ShaderDef("glow", "spatial", "glow.frag",
        "发光·柔和光晕", {"uIntensity": (0.5, 0.0, 1.5), "uRadius": (5.0, 1.0, 15.0), "uColorR": (1.0, 0.0, 1.0), "uColorG": (1.0, 0.0, 1.0), "uColorB": (1.0, 0.0, 1.0)}),

    # ── 调色效果 ──
    "invert": ShaderDef("invert", "color", "invert.frag",
        "反相", {"uIntensity": (1.0, 0.0, 1.0)}),
    "sepia": ShaderDef("sepia", "color", "sepia.frag",
        "怀旧棕褐", {"uIntensity": (1.0, 0.0, 1.0)}),
    "bleach_bypass": ShaderDef("bleach_bypass", "color", "bleach_bypass.frag",
        "漂白留银·电影感", {"uIntensity": (0.7, 0.0, 1.0)}),
    "color_balance": ShaderDef("color_balance", "color", "color_balance.frag",
        "色彩平衡·阴影/中间调/高光", {"uShadowR": (0.0, -1.0, 1.0), "uShadowG": (0.0, -1.0, 1.0), "uShadowB": (0.0, -1.0, 1.0), "uMidR": (0.0, -1.0, 1.0), "uMidG": (0.0, -1.0, 1.0), "uMidB": (0.0, -1.0, 1.0), "uHighlightR": (0.0, -1.0, 1.0), "uHighlightG": (0.0, -1.0, 1.0), "uHighlightB": (0.0, -1.0, 1.0)}),
    "hue_saturation": ShaderDef("hue_saturation", "color", "hue_saturation.frag",
        "色相饱和度", {"uHue": (0.0, -180.0, 180.0), "uSaturation": (0.0, -1.0, 1.0), "uLightness": (0.0, -1.0, 1.0)}),
    "channel_mixer": ShaderDef("channel_mixer", "color", "channel_mixer.frag",
        "通道混合器·黑白/色调分离", {"uRR": (1.0, 0.0, 2.0), "uRG": (0.0, 0.0, 2.0), "uRB": (0.0, 0.0, 2.0), "uGR": (0.0, 0.0, 2.0), "uGG": (1.0, 0.0, 2.0), "uGB": (0.0, 0.0, 2.0), "uBR": (0.0, 0.0, 2.0), "uBG": (0.0, 0.0, 2.0), "uBB": (1.0, 0.0, 2.0)}),
    "gradient_map": ShaderDef("gradient_map", "color", "gradient_map.frag",
        "渐变映射·风格化调色", {"uIntensity": (1.0, 0.0, 1.0)}),
    "curves": ShaderDef("curves", "color", "curves.frag",
        "曲线调整·对比度", {"uContrast": (0.0, -1.0, 1.0), "uBrightness": (0.0, -1.0, 1.0)}),
    "posterize": ShaderDef("posterize", "color", "posterize.frag",
        "色调分离·海报化", {"uLevels": (8.0, 2.0, 32.0)}),
    "threshold": ShaderDef("threshold", "color", "threshold.frag",
        "阈值·黑白极简", {"uThreshold": (0.5, 0.0, 1.0)}),

    # ── 纹理叠加 ──
    "film_grain": ShaderDef("film_grain", "texture", "film_grain.frag",
        "胶片颗粒·复古电影感", {"uIntensity": (0.15, 0.0, 1.0), "uSize": (1.5, 0.5, 5.0)}),
    "noise": ShaderDef("noise", "texture", "noise.frag",
        "噪点叠加", {"uIntensity": (0.2, 0.0, 1.0)}),
    "scanlines": ShaderDef("scanlines", "texture", "scanlines.frag",
        "扫描线·CRT老电视", {"uIntensity": (0.5, 0.0, 1.0), "uLineWidth": (2.0, 1.0, 8.0)}),
    "vhs_noise": ShaderDef("vhs_noise", "texture", "vhs_noise.frag",
        "VHS噪点·录像带质感", {"uIntensity": (0.3, 0.0, 1.0)}),
    "bad_tv": ShaderDef("bad_tv", "texture", "bad_tv.frag",
        "坏电视·信号干扰+雪花+偏移", {"uIntensity": (0.4, 0.0, 1.0)}),
    "halftone": ShaderDef("halftone", "texture", "halftone.frag",
        "半色调·漫画网点", {"uDotSize": (4.0, 1.0, 15.0), "uAngle": (45.0, 0.0, 360.0)}),

    # ── 变形效果 ──
    "chromatic_aberration": ShaderDef("chromatic_aberration", "distortion", "chromatic_aberration.frag",
        "色散·RGB通道分离", {"uIntensity": (3.0, 0.0, 15.0), "uAngle": (0.0, 0.0, 360.0)}),
    "lens_distortion": ShaderDef("lens_distortion", "distortion", "lens_distortion.frag",
        "镜头畸变·桶形/枕形", {"uDistortion": (0.1, -0.5, 0.5), "uEdgeDarkening": (0.3, 0.0, 1.0)}),
    "lens_flare": ShaderDef("lens_flare", "distortion", "lens_flare.frag",
        "镜头光晕·逆光效果", {"uBrightness": (1.5, 0.0, 3.0), "uBias": (0.5, 0.0, 1.0)}),
    "light_leak": ShaderDef("light_leak", "distortion", "light_leak.frag",
        "漏光·胶片边缘渗光", {"uIntensity": (0.3, 0.0, 1.0)}),
    "bulge": ShaderDef("bulge", "distortion", "bulge.frag",
        "凸起膨胀·哈哈镜", {"uRadius": (0.3, 0.05, 0.8), "uStrength": (0.3, -0.5, 0.5)}),
    "twirl": ShaderDef("twirl", "distortion", "twirl.frag",
        "旋转扭曲·漩涡", {"uRadius": (0.4, 0.05, 0.8), "uAngle": (2.0, -10.0, 10.0)}),
    "ripple": ShaderDef("ripple", "distortion", "ripple.frag",
        "波纹·水面效果", {"uFrequency": (20.0, 5.0, 60.0), "uAmplitude": (0.02, 0.0, 0.1)}),
    "wave_distort": ShaderDef("wave_distort", "distortion", "wave_distort.frag",
        "波浪扭曲", {"uAmplitude": (0.02, 0.0, 0.1), "uFrequency": (15.0, 1.0, 50.0), "uSpeed": (1.0, 0.0, 5.0)}),
    "kaleidoscope": ShaderDef("kaleidoscope", "distortion", "kaleidoscope.frag",
        "万花筒·对称反射", {"uSegments": (6.0, 2.0, 16.0), "uAngle": (0.0, 0.0, 360.0)}),
    "mirror": ShaderDef("mirror", "distortion", "mirror.frag",
        "镜像·水平/垂直翻转拼接", {"uAxis": (0.0, 0.0, 1.0), "uOffset": (0.5, 0.0, 1.0)}),
    "prism": ShaderDef("prism", "distortion", "prism.frag",
        "棱镜·三棱镜色散", {"uIntensity": (0.5, 0.0, 1.0), "uAngle": (0.0, 0.0, 360.0)}),
    "rays": ShaderDef("rays", "distortion", "rays.frag",
        "放射光线·丁达尔", {"uIntensity": (0.5, 0.0, 1.5), "uAngle": (0.0, 0.0, 360.0)}),
    "echo": ShaderDef("echo", "distortion", "echo.frag",
        "残影·拖尾", {"uIntensity": (0.3, 0.0, 1.0), "uDecay": (0.7, 0.3, 0.95)}),
    "pixel_sort": ShaderDef("pixel_sort", "distortion", "pixel_sort.frag",
        "像素排序·数据腐蚀", {"uIntensity": (0.5, 0.0, 1.0), "uThreshold": (0.5, 0.0, 1.0)}),

    # ── 故障效果 ──
    "glitch_blocks": ShaderDef("glitch_blocks", "glitch", "glitch_blocks.frag",
        "故障块·画面撕裂", {"uIntensity": (0.4, 0.0, 1.0), "uBlockSize": (20.0, 4.0, 80.0)}),
    "data_glitch": ShaderDef("data_glitch", "glitch", "data_glitch.frag",
        "数据故障·像素偏移+色彩分离", {"uIntensity": (0.3, 0.0, 1.0)}),
    "rgb_shift": ShaderDef("rgb_shift", "glitch", "rgb_shift.frag",
        "RGB偏移·通道位移", {"uShiftX": (4.0, 0.0, 20.0), "uShiftY": (2.0, 0.0, 20.0)}),

    # ── 合成效果 ──
    "vignette": ShaderDef("vignette", "composite", "vignette.frag",
        "暗角·边缘压暗", {"uIntensity": (0.5, 0.0, 1.0), "uRoundness": (0.5, 0.0, 1.0)}),
    "frame_blend": ShaderDef("frame_blend", "composite", "frame_blend.frag",
        "帧混合·抽帧+重叠", {"uBlendFrames": (3.0, 1.0, 8.0), "uOpacity": (0.5, 0.0, 1.0)}),
    "edge_detect": ShaderDef("edge_detect", "composite", "edge_detect.frag",
        "边缘检测·Sobel", {"uThreshold": (0.1, 0.0, 1.0), "uIntensity": (1.0, 0.0, 2.0)}),
    "find_edges": ShaderDef("find_edges", "composite", "find_edges.frag",
        "寻边·线条提取", {"uIntensity": (1.0, 0.0, 2.0)}),
    "emboss": ShaderDef("emboss", "composite", "emboss.frag",
        "浮雕·凹凸感", {"uIntensity": (1.0, 0.0, 2.0), "uAngle": (135.0, 0.0, 360.0)}),

    # ── 转场效果 ──
    "crossfade": ShaderDef("crossfade", "transition", "crossfade.frag",
        "交叉淡入淡出", {"uProgress": (0.5, 0.0, 1.0)}),
    "dissolve": ShaderDef("dissolve", "transition", "dissolve.frag",
        "溶解·噪点擦除", {"uProgress": (0.5, 0.0, 1.0), "uNoiseScale": (5.0, 1.0, 20.0)}),
    "push": ShaderDef("push", "transition", "push.frag",
        "推入·画面平推", {"uProgress": (0.5, 0.0, 1.0), "uDirection": (0.0, 0.0, 3.0)}),
    "slide": ShaderDef("slide", "transition", "slide.frag",
        "滑入·从边缘滑入", {"uProgress": (0.5, 0.0, 1.0), "uDirection": (0.0, 0.0, 3.0)}),
    "wipe": ShaderDef("wipe", "transition", "wipe.frag",
        "擦除·线性擦除", {"uProgress": (0.5, 0.0, 1.0), "uAngle": (0.0, 0.0, 360.0), "uFeather": (0.1, 0.0, 0.5)}),
    "radial_wipe": ShaderDef("radial_wipe", "transition", "radial_wipe.frag",
        "径向擦除·时钟式", {"uProgress": (0.5, 0.0, 1.0), "uFeather": (0.05, 0.0, 0.3)}),
    "zoom_transition": ShaderDef("zoom_transition", "transition", "zoom_transition.frag",
        "缩放转场·推拉切换", {"uProgress": (0.5, 0.0, 1.0), "uZoom": (3.0, 1.0, 10.0)}),
    "page_curl": ShaderDef("page_curl", "transition", "page_curl.frag",
        "翻页·纸张翻卷", {"uProgress": (0.5, 0.0, 1.0), "uAngle": (45.0, 0.0, 360.0)}),

    # ── 动态效果 ──
    "strobe": ShaderDef("strobe", "dynamic", "strobe.frag",
        "频闪·节奏闪烁", {"uFrequency": (4.0, 0.5, 30.0), "uIntensity": (0.8, 0.0, 1.0)}),
    "speed_ramp": ShaderDef("speed_ramp", "dynamic", "speed_ramp.frag",
        "变速·时间重映射", {"uSpeed": (1.0, 0.1, 5.0), "uRampPosition": (0.5, 0.0, 1.0)}),
    "time_displacement": ShaderDef("time_displacement", "dynamic", "time_displacement.frag",
        "时间置换·像素时间偏移", {"uIntensity": (0.3, 0.0, 1.0)}),
    "venetian_blinds": ShaderDef("venetian_blinds", "dynamic", "venetian_blinds.frag",
        "百叶窗·条纹切换", {"uProgress": (0.5, 0.0, 1.0), "uStrips": (20.0, 4.0, 60.0), "uDirection": (0.0, 0.0, 1.0)}),
}


# ===== 查询API =====

def get_shader(name: str) -> ShaderDef | None:
    """按名称查询着色器"""
    return _SHADERS.get(name)


def list_shaders(category: str = "") -> list[ShaderDef]:
    """列出所有着色器，可选按分类过滤"""
    if category and category in SHADER_CATEGORIES:
        return [s for s in _SHADERS.values() if s.category == category]
    return list(_SHADERS.values())


def list_categories() -> list[str]:
    """列出所有着色器分类"""
    return list(SHADER_CATEGORIES.keys())


def get_shaders_by_category() -> dict[str, list[ShaderDef]]:
    """按分类返回着色器字典"""
    result: dict[str, list[ShaderDef]] = {}
    for cat, names in SHADER_CATEGORIES.items():
        result[cat] = [s for n in names if (s := _SHADERS.get(n))]
    return result


class ShaderCatalog:
    """着色器目录·单例"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def count(self) -> int:
        return len(_SHADERS)

    @property
    def categories(self) -> list[str]:
        return list(SHADER_CATEGORIES.keys())

    def __getitem__(self, name: str) -> ShaderDef | None:
        return _SHADERS.get(name)

    def __iter__(self):
        return iter(_SHADERS.values())

    def __contains__(self, name: str) -> bool:
        return name in _SHADERS

    def for_category(self, category: str) -> list[ShaderDef]:
        names = SHADER_CATEGORIES.get(category, [])
        return [s for n in names if (s := _SHADERS.get(n))]
