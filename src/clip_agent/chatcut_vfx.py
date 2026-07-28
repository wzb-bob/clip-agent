"""
ChatCut VFX 增强层 · 将vfx引擎注入ChatCut剪辑管线

从机械拼接升级为创意剪辑:
  节拍检测 → 效果分配 → 段级滤镜链 → 转场升级 → 最终渲染

用法:
  from clip_agent.chatcut_vfx import enhance_timeline, VfxPreset
  enhanced = enhance_timeline(timeline, video_path, VfxPreset.douyin_hot)
"""
from __future__ import annotations
import logging
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 创意预设
# ══════════════════════════════════════════════════════════

class VfxPreset(Enum):
    douyin_hot = "douyin_hot"         # 抖音爆款: 频闪+RGB+缩放脉冲
    cinematic = "cinematic"           # 电影感: 漂白银+胶片颗粒+暗角
    gritty_drill = "gritty_drill"     # Drill重击: 震动+故障+色散
    warm_story = "warm_story"         # 温暖叙事: 柔光+棕褐+慢节奏
    clean_business = "clean_business" # 干净商务: 微对比+去噪+无特效
    retro_vhs = "retro_vhs"           # 复古VHS: 噪点+扫描线+坏电视


# 预设 → (全局调色, 纹理叠加, 节拍预设)
PRESET_CONFIG: dict[VfxPreset, tuple[str, str, str]] = {
    VfxPreset.douyin_hot:      ("none",            "none",          "douyin_hot"),
    VfxPreset.cinematic:       ("bleach_bypass",   "film_grain",    "melodic_subtle"),
    VfxPreset.gritty_drill:    ("bleach_bypass",   "vhs_noise",     "drill_impact"),
    VfxPreset.warm_story:      ("sepia",           "film_grain",    "minimal_clean"),
    VfxPreset.clean_business:  ("color_balance",   "none",          "minimal_clean"),
    VfxPreset.retro_vhs:       ("posterize",       "vhs_noise",     "melodic_subtle"),
}


# 段角色 → 默认效果 (hook/body/broll/cta/outro)
SEGMENT_EFFECTS: dict[str, dict] = {
    "hook": {
        "color": "none",
        "texture": "none",
        "beat_triggers": ["strobe_hit", "rgb_hit"],
        "transition_in": "dissolve",
        "text_effect": "fly_in",
    },
    "body": {
        "color": "none",       # 由全局预设覆盖
        "texture": "none",     # 由全局预设覆盖
        "beat_triggers": ["light_pulse", "warm_pulse"],
        "transition_in": "crossfade",
        "text_effect": "fade_up",
    },
    "broll": {
        "color": "bleach_bypass",
        "texture": "film_grain",
        "beat_triggers": ["speed_curve"],
        "transition_in": "dissolve",
        "text_effect": "none",
    },
    "cta": {
        "color": "none",
        "texture": "none",
        "beat_triggers": ["heavy_drop", "color_hit"],
        "transition_in": "zoom_transition",
        "text_effect": "price_pop",
    },
    "outro": {
        "color": "vignette",
        "texture": "none",
        "beat_triggers": [],
        "transition_in": "crossfade",
        "text_effect": "fade_out",
    },
}


@dataclass
class VfxEnhanceResult:
    """VFX增强结果"""
    success: bool
    segments: list[dict] = field(default_factory=list)
    beat_count: int = 0
    bpm: float = 120.0
    preset: str = ""
    filter_chain: str = ""
    error: str = ""


# ══════════════════════════════════════════════════════════
# 核心: 将vfx引擎注入时间线
# ══════════════════════════════════════════════════════════

def enhance_timeline(
    timeline,  # FourCategoryTimeline
    video_path: str,
    preset: VfxPreset = VfxPreset.douyin_hot,
    script_category: str = "团购售卖",
) -> VfxEnhanceResult:
    """
    对ChatCut时间线进行VFX增强。

    Args:
        timeline: four_category_pipeline 返回的时间线对象
        video_path: 原始视频路径
        preset: 创意预设
        script_category: 脚本类别(影响段效果分配)

    Returns:
        VfxEnhanceResult 含增强后的segments和滤镜链
    """
    try:
        from .vfx.beat_trigger import (
            BeatTriggerEngine, BeatTrigger, BeatTriggerPresets,
            BeatOnset, detect_beats_simple,
        )
        from .vfx.shader_catalog import ShaderCatalog, SHADER_CATEGORIES
        from .vfx.glsl_renderer import GlslRenderer, _build_bloom_chain, _build_ca_chain
    except ImportError as e:
        return VfxEnhanceResult(success=False, error=f"vfx模块导入失败: {e}")

    # ── 1. 节拍检测 ──
    beats = detect_beats_simple(video_path)
    if not beats:
        # 无声视频: 使用5秒间隔假节拍
        duration = sum(getattr(s, 'duration_sec', 2) for s in (timeline.segments if hasattr(timeline, 'segments') else []))
        duration = max(duration, 10)
        beats = [BeatOnset(t, 0.8, t % 2 == 0) for t in [i * 0.5 for i in range(int(duration * 2))]]
        logger.info("无音频节拍: 使用假拍网格(%d拍)", len(beats))

    # 配置节拍引擎
    global_color, global_texture, beat_preset_name = PRESET_CONFIG[preset]
    beat_triggers = BeatTriggerPresets.for_genre(
        "trap" if preset == VfxPreset.gritty_drill else
        "melodic" if preset in (VfxPreset.warm_story, VfxPreset.retro_vhs) else
        "hype" if preset == VfxPreset.douyin_hot else
        "boom_bap"
    )
    engine = BeatTriggerEngine()
    engine.configure(beat_triggers)
    engine.set_beat_map(beats)

    # ── 2. 逐段增强 ──
    enhanced_segments = []
    segments = timeline.segments if hasattr(timeline, 'segments') else []

    accum_time = 0.0  # 累计时间(跟踪节拍位置)

    for i, seg in enumerate(segments):
        # 确定段角色
        role = _guess_role(i, len(segments), seg)
        effects = SEGMENT_EFFECTS.get(role, SEGMENT_EFFECTS["body"])

        # 段时长
        dur = getattr(seg, 'duration_sec', 2.0)
        seg_start = accum_time
        seg_end = accum_time + dur

        # 更新节拍引擎到段结束时间
        engine.update(seg_end)
        beat_params = engine.current_effect_params

        # 确定段的着色器链
        seg_color = effects["color"] if effects["color"] != "none" else global_color
        seg_texture = effects["texture"] if effects["texture"] != "none" else global_texture

        # 构建段级滤镜
        seg_filters = _build_segment_filters(
            seg_color, seg_texture, beat_params, role,
            effects.get("transition_in", "crossfade"),
            effects.get("text_effect", "none"),
        )

        enhanced = {
            "index": i,
            "role": role,
            "file": getattr(seg, 'material_file', ''),
            "duration": dur,
            "start_sec": getattr(seg, 'start_sec', 0),
            "text": getattr(seg, 'script_text', '')[:50] if hasattr(seg, 'script_text') else "",
            "is_broll": getattr(seg, 'is_broll', False),
            # VFX增强字段
            "filters": seg_filters,
            "color_grade": seg_color,
            "texture": seg_texture,
            "transition_in": effects.get("transition_in", "crossfade"),
            "text_effect": effects.get("text_effect", "none"),
            "beat_params": {k: round(v, 3) for k, v in beat_params.items()},
        }
        enhanced_segments.append(enhanced)
        accum_time = seg_end

    # ── 3. 构建全局滤镜链 ──
    global_filters = _build_global_filters(global_color, global_texture, beats)

    return VfxEnhanceResult(
        success=True,
        segments=enhanced_segments,
        beat_count=len(beats),
        bpm=_estimate_bpm(beats),
        preset=preset.value,
        filter_chain=global_filters,
    )


# ══════════════════════════════════════════════════════════
# 内部辅助
# ══════════════════════════════════════════════════════════

def _guess_role(idx: int, total: int, seg) -> str:
    """根据段位置和属性推测角色"""
    if idx == 0:
        return "hook"
    if idx == total - 1:
        return "cta"
    if getattr(seg, 'is_broll', False):
        return "broll"
    if idx >= total * 0.7:
        return "outro"
    return "body"


def _build_segment_filters(
    color: str,
    texture: str,
    beat_params: dict,
    role: str,
    transition: str,
    text_effect: str,
) -> dict:
    """为单个段构建FFmpeg滤镜参数"""
    filters = []

    # 调色
    if color and color != "none":
        from .vfx.shader_catalog import get_shader
        shader = get_shader(color)
        if shader:
            filters.append({"type": "color", "shader": color, "params": dict(shader.params)})

    # 纹理
    if texture and texture != "none":
        from .vfx.shader_catalog import get_shader
        shader = get_shader(texture)
        if shader:
            filters.append({"type": "texture", "shader": texture, "params": dict(shader.params)})

    # 节拍效果 (仅非零时添加)
    if beat_params.get("flash_opacity", 0) > 0.01:
        filters.append({"type": "beat", "effect": "flash", "intensity": round(beat_params["flash_opacity"], 2)})
    if beat_params.get("shake_amount", 0) > 0.5:
        filters.append({"type": "beat", "effect": "shake", "intensity": round(beat_params["shake_amount"], 1)})
    if beat_params.get("rgb_split_amount", 0) > 0.5:
        filters.append({"type": "beat", "effect": "rgb_split", "intensity": round(beat_params["rgb_split_amount"], 1)})
    if beat_params.get("bloom_boost", 0) > 0.01:
        filters.append({"type": "beat", "effect": "bloom", "intensity": round(beat_params["bloom_boost"], 2)})
    if beat_params.get("glitch_intensity", 0) > 0.01:
        filters.append({"type": "beat", "effect": "glitch", "intensity": round(beat_params["glitch_intensity"], 2)})

    # 转场
    if transition and transition != "crossfade":
        filters.append({"type": "transition", "effect": transition})

    # 文字效果
    if text_effect and text_effect != "none":
        filters.append({"type": "text", "effect": text_effect})

    return {
        "chain": filters,
        "role": role,
        "transition": transition,
    }


def _build_global_filters(global_color: str, global_texture: str, beats: list) -> str:
    """构建全局FFmpeg滤镜链(应用于整个合成后的视频)"""
    parts = []

    # 全局调色
    if global_color and global_color != "none":
        from .vfx.glsl_renderer import GlslRenderer
        r = GlslRenderer()
        filter_str = r._build_filter(
            type('s', (), {'name': global_color, 'params': {}})(),
            {},
        )
        if filter_str:
            parts.append(filter_str)

    # 全局纹理(如果无段级纹理)
    if global_texture and global_texture != "none":
        from .vfx.glsl_renderer import GlslRenderer
        r = GlslRenderer()
        filter_str = r._build_filter(
            type('s', (), {'name': global_texture, 'params': {}})(),
            {},
        )
        if filter_str:
            parts.append(filter_str)

    return ";".join(parts) if parts else ""


def _estimate_bpm(beats: list) -> float:
    """从节拍列表估算BPM"""
    if len(beats) < 2:
        return 120.0
    intervals = []
    for i in range(1, len(beats)):
        dt = beats[i].time_seconds - beats[i-1].time_seconds
        if 0.2 <= dt <= 2.0:  # 合理范围
            intervals.append(dt)
    if not intervals:
        return 120.0
    avg_interval = sum(intervals) / len(intervals)
    return round(60.0 / avg_interval, 1)


# ══════════════════════════════════════════════════════════
# 便捷函数: 直接生成增强版FFmpeg命令
# ══════════════════════════════════════════════════════════

def build_vfx_ffmpeg_command(
    enhanced_result: VfxEnhanceResult,
    input_files: list[str],
    output_path: str,
    width: int = 1080,
    height: int = 1920,
) -> list[str]:
    """
    从VfxEnhanceResult构建完整FFmpeg渲染命令。

    返回可直接subprocess.run的ffmpeg命令列表。
    """
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    # 输入文件
    for f in input_files:
        if Path(f).exists():
            cmd.extend(["-i", f])

    # 构建filter_complex
    filter_parts = []
    seg_count = len(enhanced_result.segments)

    for i, seg in enumerate(enhanced_result.segments):
        input_idx = i if i < len(input_files) else 0
        label_in = str(input_idx)
        label_out = f"s{i}"

        # 段级滤镜
        seg_filter = ""
        for f in seg.get("filters", {}).get("chain", []):
            if f["type"] == "color" and f.get("shader"):
                seg_filter += _shader_to_ffmpeg_filter(f["shader"], label_in, "tmp") + ";"
                label_in = "tmp"
            elif f["type"] == "beat" and f["effect"] == "flash":
                opacity = f["intensity"]
                seg_filter += f"[{label_in}]geq=r='r(X,Y)+{opacity*255}*(1-r(X,Y)/255)':g='g(X,Y)+{opacity*255}*(1-g(X,Y)/255)':b='b(X,Y)+{opacity*255}*(1-b(X,Y)/255)'[tmp];"
                label_in = "tmp"

        if seg_filter:
            filter_parts.append(seg_filter[:-1])  # 去掉末尾分号
        filter_parts.append(f"[{label_in}]trim=duration={seg['duration']},setpts=PTS-STARTPTS[{label_out}]")

    # 拼接所有段
    concat_inputs = "".join(f"[s{i}]" for i in range(seg_count))
    filter_parts.append(f"{concat_inputs}concat=n={seg_count}:v=1:a=1[v][a]")

    # 全局滤镜
    if enhanced_result.filter_chain:
        filter_parts.append(f"[v]{enhanced_result.filter_chain}[v]")

    cmd.extend(["-filter_complex", ";".join(filter_parts)])
    cmd.extend(["-map", "[v]", "-map", "[a]"])
    cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18"])
    cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    cmd.extend(["-pix_fmt", "yuv420p"])
    cmd.append(output_path)

    return cmd


def _shader_to_ffmpeg_filter(shader_name: str, in_label: str, out_label: str) -> str:
    """将着色器名转为FFmpeg滤镜片段(简化版)"""
    from .vfx.glsl_renderer import _FFMPEG_MAP
    template = _FFMPEG_MAP.get(shader_name, "")
    if not template:
        return f"[{in_label}]copy[{out_label}]"
    return f"[{in_label}]{template}[{out_label}]"


# ══════════════════════════════════════════════════════════
# 查询API
# ══════════════════════════════════════════════════════════

def list_presets() -> list[dict]:
    """列出所有VFX预设"""
    return [
        {"name": p.value, "color": PRESET_CONFIG[p][0], "texture": PRESET_CONFIG[p][1],
         "beat_style": PRESET_CONFIG[p][2]}
        for p in VfxPreset
    ]


def get_preset(name: str) -> VfxPreset | None:
    """按名称获取预设"""
    for p in VfxPreset:
        if p.value == name:
            return p
    return None
