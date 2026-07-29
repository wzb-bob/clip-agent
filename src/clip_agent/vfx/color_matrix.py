"""
颜色矩阵工具 · 从 vfx-studio SimpleEffectRenderer 搬运

5x4颜色矩阵运算 → FFmpeg colorchannelmixer 参数
来源: d:/vfx-studio/lib/src/engine/simple_effect_renderer.dart

FFmpeg的colorchannelmixer就是5x4矩阵的直接应用。
这些算法可用于生成比eq更精细的调色效果。
"""
from __future__ import annotations
import math


# ══════════════════════════════════════════════════════════
# 基础矩阵 (对齐 SimpleEffectRenderer._identityMatrix 等)
# ══════════════════════════════════════════════════════════

def identity_matrix() -> list[float]:
    """5x4单位矩阵: 输出=输入"""
    return [
        1, 0, 0, 0, 0,  # R通道
        0, 1, 0, 0, 0,  # G通道
        0, 0, 1, 0, 0,  # B通道
        0, 0, 0, 1, 0,  # A通道
    ]


def contrast_matrix(contrast: float) -> list[float]:
    """对比度矩阵 (对齐 _contrastMatrix)

    contrast=0: 全灰
    contrast=1: 原始
    contrast>1: 增强对比
    """
    t = (1.0 - contrast) / 2.0
    return [
        contrast, 0, 0, 0, t,
        0, contrast, 0, 0, t,
        0, 0, contrast, 0, t,
        0, 0, 0, 1, 0,
    ]


def brightness_matrix(brightness: float) -> list[float]:
    """亮度矩阵——给所有通道加偏移"""
    return [
        1, 0, 0, 0, brightness,
        0, 1, 0, 0, brightness,
        0, 0, 1, 0, brightness,
        0, 0, 0, 1, 0,
    ]


def saturation_matrix(saturation: float) -> list[float]:
    """饱和度矩阵 (标准601亮度权重)

    saturation=0: 灰度
    saturation=1: 原始
    saturation>1: 增强饱和
    """
    sr = (1 - saturation) * 0.299
    sg = (1 - saturation) * 0.587
    sb = (1 - saturation) * 0.114
    return [
        sr + saturation, sg,            sb,            0, 0,
        sr,              sg + saturation, sb,           0, 0,
        sr,              sg,            sb + saturation, 0, 0,
        0,               0,              0,             1, 0,
    ]


def hue_matrix(angle_deg: float) -> list[float]:
    """色相旋转矩阵 (对齐 _hueMatrix)

    angle_deg: 色相旋转角度(度), 0=不变, 180=反相色
    """
    rad = math.radians(angle_deg)
    c = math.cos(rad)
    s = math.sin(rad)

    # 标准601亮度权重
    rw, gw, bw = 0.299, 0.587, 0.114

    return [
        rw + c*(1-rw) + s*(-rw),     gw + c*(-gw) + s*(-gw),      bw + c*(-bw) + s*(1-bw),      0, 0,
        rw + c*(-rw) + s*0.143,      gw + c*(1-gw) + s*0.140,     bw + c*(-bw) + s*(-0.283),    0, 0,
        rw + c*(-rw) + s*(-(1-rw)),  gw + c*(-gw) + s*rw,         bw + c*(1-bw) + s*bw,         0, 0,
        0,                           0,                            0,                            1, 0,
    ]


def sepia_matrix(intensity: float = 1.0) -> list[float]:
    """怀旧棕褐矩阵"""
    base = [
        0.393, 0.769, 0.189, 0, 0,
        0.349, 0.686, 0.168, 0, 0,
        0.272, 0.534, 0.131, 0, 0,
        0,     0,     0,     1, 0,
    ]
    if intensity >= 1.0:
        return base
    return lerp_matrix(identity_matrix(), base, intensity)


def bleach_bypass_matrix(intensity: float = 0.7) -> list[float]:
    """漂白留银矩阵 (低饱和+高对比)"""
    desat = saturation_matrix(0.2)
    contrast = contrast_matrix(1.3)
    bypass = multiply_matrix(desat, contrast)
    return lerp_matrix(identity_matrix(), bypass, intensity)


def vignette_matrix(intensity: float = 0.5) -> list[float]:
    """暗角矩阵 (降低边缘亮度)"""
    return [
        1-intensity*0.3, 0, 0, 0, -intensity*0.05,
        0, 1-intensity*0.3, 0, 0, -intensity*0.05,
        0, 0, 1-intensity*0.3, 0, -intensity*0.05,
        0, 0, 0, 1, 0,
    ]


# ══════════════════════════════════════════════════════════
# 矩阵运算 (对齐 SimpleEffectRenderer._multiplyMatrix 等)
# ══════════════════════════════════════════════════════════

def multiply_matrix(a: list[float], b: list[float]) -> list[float]:
    """两个5x4矩阵相乘 (4行×5列 × 4行×5列 = 4行×5列)"""
    result = [0.0] * 20
    for row in range(4):
        for col in range(5):
            idx = row * 5 + col
            for k in range(5):
                a_idx = row * 5 + k
                b_idx = (k if k < 4 else 4) * 5 + col
                if k < 4:
                    result[idx] += a[a_idx] * b[b_idx]
            if col == 4:
                result[idx] += a[row * 5 + 4]
    return result


def lerp_matrix(a: list[float], b: list[float], t: float) -> list[float]:
    """矩阵线性插值 (对齐 _lerpMatrix)"""
    return [a[i] + (b[i] - a[i]) * t for i in range(20)]


# ══════════════════════════════════════════════════════════
# 输出: 转为 FFmpeg colorchannelmixer 参数
# ══════════════════════════════════════════════════════════

def to_ffmpeg(matrix: list[float]) -> str:
    """将20元素5x4矩阵转为FFmpeg滤镜参数

    colorchannelmixer只支持3x4(无alpha)或4x4矩阵, 不支持第5列偏移。
    偏移量(亮度变化)通过eq=brightness=单独处理。
    """
    assert len(matrix) == 20, f"Expected 20 elements, got {len(matrix)}"
    # 取3x4子矩阵(RGB通道×4系数)
    # 矩阵布局: row0=R(rr,rg,rb,ra,roff) row1=G(...) row2=B(...) row3=A(...)
    rr, rg, rb, ra, roff = matrix[0:5]
    gr, gg, gb, ga, goff = matrix[5:10]
    br, bg, bb, ba, boff = matrix[10:15]
    # 平均偏移量→eq brightness
    avg_off = (roff + goff + boff) / 3.0
    mixer = f"colorchannelmixer=rr={rr:.4f}:rg={rg:.4f}:rb={rb:.4f}:ra={ra:.4f}" \
            f":gr={gr:.4f}:gg={gg:.4f}:gb={gb:.4f}:ga={ga:.4f}" \
            f":br={br:.4f}:bg={bg:.4f}:bb={bb:.4f}:ba={ba:.4f}"
    if abs(avg_off) > 0.001:
        return f"{mixer},eq=brightness={avg_off:.4f}"
    return mixer


# ══════════════════════════════════════════════════════════
# 预设调色方案 (组合多个矩阵)
# ══════════════════════════════════════════════════════════

def cinematic_warm(intensity: float = 0.7) -> str:
    """电影暖色调: 低饱和+暖色相偏移+暗角+对比"""
    sat = saturation_matrix(0.85)
    hue = hue_matrix(8)      # +8度→偏暖
    cont = contrast_matrix(1.08)
    m = multiply_matrix(sat, hue)
    m = multiply_matrix(m, cont)
    m = lerp_matrix(identity_matrix(), m, intensity)
    return to_ffmpeg(m)


def vivid_pop(intensity: float = 0.8) -> str:
    """鲜艳弹出: 高饱和+微对比"""
    sat = saturation_matrix(1.2)
    cont = contrast_matrix(1.05)
    m = multiply_matrix(sat, cont)
    m = lerp_matrix(identity_matrix(), m, intensity)
    return to_ffmpeg(m)


def cool_metal(intensity: float = 0.7) -> str:
    """冷金属: 低饱和+冷色相+高对比"""
    sat = saturation_matrix(0.8)
    hue = hue_matrix(-10)    # -10度→偏冷
    cont = contrast_matrix(1.12)
    m = multiply_matrix(sat, hue)
    m = multiply_matrix(m, cont)
    m = lerp_matrix(identity_matrix(), m, intensity)
    return to_ffmpeg(m)


def clean_bright(intensity: float = 0.5) -> str:
    """干净明亮: 微提亮+微饱和"""
    bright = brightness_matrix(0.03)
    sat = saturation_matrix(1.05)
    m = multiply_matrix(bright, sat)
    m = lerp_matrix(identity_matrix(), m, intensity)
    return to_ffmpeg(m)


# ══════════════════════════════════════════════════════════
# 预设映射 (与现有eq预设对应)
# ══════════════════════════════════════════════════════════

COLOR_MATRIX_PRESETS = {
    "warm_boost":    cinematic_warm(0.7),
    "film_warm":     cinematic_warm(0.9),
    "vivid_pop":     vivid_pop(0.8),
    "cool_metal":    cool_metal(0.7),
    "clean_bright":  clean_bright(0.5),
    "bleach_bypass": to_ffmpeg(bleach_bypass_matrix(0.7)),
    "sepia":         to_ffmpeg(sepia_matrix(0.8)),
    "neutral":       to_ffmpeg(identity_matrix()),
}
