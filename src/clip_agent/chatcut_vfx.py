"""
ChatCut VFX 增强层 · 长益三类脚本专属剪辑风格

不再套通用预设。每类脚本有确定的剪辑策略:
  团购售卖 → 价格冲击·紧迫感·食物光泽
  老板IP   → 故事感·信任·真实颗粒
  引流进店 → 氛围诱惑·排队稀缺·地点引导

10行业自动适配色调(通过 detect_industry)，
但剪辑策略由脚本类别决定——这是跨行业的铁律。
"""
from __future__ import annotations
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 三类脚本 = 三套剪辑策略 (跨10行业通用)
# ══════════════════════════════════════════════════════════

CATEGORY_STYLE = {
    # 只用eq调色+vignette暗角+noise颗粒——三种100%可靠的FFmpeg滤镜
    "团购售卖": {
        "label": "鲜艳冲击型",
        "global_color": "warm_boost",     # eq: 暖色增强·食物更有食欲
        "global_texture": "none",         # 干净·不分散注意力
        "hook_effects": ["warm_boost"],             # 钩子=暖色
        "body_effects": ["warm_grade"],             # 主体=暖色调
        "broll_effects": ["bloom_light", "slow_zoom"], # B-roll=柔光+慢缩
        "cta_effects": ["pulse_ring"],              # CTA=脉冲圈(drawbox,无字体依赖)
        "transition": "crossfade",        # 交叉淡入
    },
    "老板IP": {
        "label": "故事质感型",
        "global_color": "film_warm",      # eq: 胶片暖色·怀旧真实
        "global_texture": "film_grain_light", # noise: 胶片颗粒·增加质感
        "hook_effects": ["vignette_soft"],          # 钩子=暗角·聚焦人脸
        "body_effects": ["film_grain_light"],       # 主体=轻颗粒
        "broll_effects": ["crossfade_slow"],        # B-roll=慢淡入
        "cta_effects": ["glow_warm"],               # CTA=暖光引导(boxblur+blend)
        "transition": "crossfade",        # 交叉淡入
    },
    "引流进店": {
        "label": "明亮引导型",
        "global_color": "bright_clean",   # eq: 明亮干净·展示环境
        "global_texture": "none",         # 无颗粒·保持清晰
        "hook_effects": ["speed_ramp"],             # 钩子=变速(setpts)
        "body_effects": ["bright_grade", "stabilize"], # 主体=明亮+防抖
        "broll_effects": ["bloom_light", "glow_warm"], # B-roll=柔光+暖光
        "cta_effects": ["pulse_ring"],              # CTA=脉冲圈
        "transition": "crossfade",        # 交叉淡入
    },
}


# ══════════════════════════════════════════════════════════
# 行业色调微调 (可选·叠加在脚本类别之上)
# ══════════════════════════════════════════════════════════

INDUSTRY_COLOR_TWEAK = {
    "餐饮": {"warmth": 0.08, "saturation": 0.10, "contrast": 0.05},   # 食物要暖·饱和
    "美容": {"warmth": -0.02, "saturation": -0.05, "contrast": 0.02},  # 干净·低饱和
    "汽修": {"warmth": 0.00, "saturation": -0.10, "contrast": 0.15},   # 金属感·高对比
    "建材": {"warmth": 0.03, "saturation": 0.00, "contrast": 0.10},    # 质感·对比
    "零售": {"warmth": 0.02, "saturation": 0.05, "contrast": 0.05},    # 活泼
    "教育": {"warmth": 0.00, "saturation": 0.00, "contrast": 0.08},    # 干净·清晰
    "健身": {"warmth": -0.05, "saturation": -0.10, "contrast": 0.20},  # 冷峻·高对比
    "宠物": {"warmth": 0.10, "saturation": 0.05, "contrast": 0.00},    # 温暖·柔和
    "家政": {"warmth": 0.05, "saturation": 0.00, "contrast": 0.00},    # 温和
    "摄影": {"warmth": 0.00, "saturation": -0.05, "contrast": 0.12},   # 专业·中性
}


# ══════════════════════════════════════════════════════════
# 效果 → FFmpeg滤镜 实际映射 (不是描述, 是可执行的命令)
# ══════════════════════════════════════════════════════════

def _effect_to_ffmpeg(effect_name: str, in_label: str = "0", out_label: str = "v") -> str:
    """
    将效果名转为可执行的 FFmpeg 滤镜片段。

    这是整个模块最关键的映射表——每个效果都有确定的 FFmpeg 实现。
    """
    ffmpeg_map = {
        # ── 价格冲击类 ──
        "price_pop": (
            f"[{in_label}]drawtext=fontfile=/Windows/Fonts/simhei.ttf:"
            "text='':fontsize=72:fontcolor=red@0.9:"
            "x=(w-text_w)/2:y=h*0.25-th:enable='between(t,0,2)'[{out_label}]"
        ),
        "flash": (
            f"[{in_label}]geq=r='r(X,Y)+40*(1-gt(t,0.08))':"
            f"g='g(X,Y)+40*(1-gt(t,0.08))':"
            f"b='b(X,Y)+40*(1-gt(t,0.08))':eval=frame[{out_label}]"
        ),
        "red_flash": (
            f"[{in_label}]geq=r='r(X,Y)+50*(1-gt(t,0.1))':"
            f"g='g(X,Y)':b='b(X,Y)':eval=frame[{out_label}]"
        ),

        # ── 调色类 ──
        # 以下使用eq滤镜替代不存在的colorbalance滤镜(BugFix#1)
        "warm_boost": (
            f"[{in_label}]eq=saturation=1.2:brightness=0.05:contrast=1.05:gamma=1.03[{out_label}]"
        ),
        "warm_grade": (
            f"[{in_label}]eq=saturation=1.15:brightness=0.03:contrast=1.03[{out_label}]"
        ),
        "film_warm": (
            f"[{in_label}]eq=saturation=0.85:brightness=0.02:contrast=1.1:gamma=1.08[{out_label}]"
        ),
        "bright_clean": (
            f"[{in_label}]eq=saturation=1.0:brightness=0.08:contrast=1.08:gamma=0.95[{out_label}]"
        ),
        "bright_grade": (
            f"[{in_label}]eq=saturation=1.0:brightness=0.05:contrast=1.05[{out_label}]"
        ),

        # ── 纹理类 ──
        "film_grain_light": (
            f"[{in_label}]noise=alls=8:allf=t,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)'[{out_label}]"
        ),

        # ── 柔光/发光 ──
        "bloom_light": (
            f"[{in_label}]split[bg][fg];"
            f"[bg]boxblur=5:2,eq=brightness=0.1[bg_blur];"
            f"[bg_blur][fg]blend=all_mode=screen:all_opacity=0.3[{out_label}]"
        ),
        "glow_warm": (
            f"[{in_label}]split[base][glow];"
            f"[glow]boxblur=10:2,geq=r='r(X,Y)*1.3':g='g(X,Y)*1.1':b='b(X,Y)*0.9'[glow_out];"
            f"[base][glow_out]blend=all_mode=screen:all_opacity=0.25[{out_label}]"
        ),

        # ── 暗角 ──
        "vignette_soft": (
            f"[{in_label}]vignette=PI/4:aspect=0.75[{out_label}]"
        ),

        # ── 变速类 ──
        "slow_zoom": (
            f"[{in_label}]zoompan=z='min(zoom+0.0008,1.03)':d=1:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s=1080x1920[{out_label}]"
        ),
        "speed_ramp": (
            f"[{in_label}]setpts=0.8*PTS[{out_label}]"
        ),

        # ── 脉冲类 ──
        "zoom_pulse": (
            f"[{in_label}]zoompan=z='1+0.02*sin(2*PI*on*0.02)':d=1:s=1080x1920[{out_label}]"
        ),
        "pulse_ring": (
            f"[{in_label}]drawbox=x=iw*0.1:y=ih*0.7:w=iw*0.8:h=4:"
            f"color=red@0.6:t=fill,"
            f"drawbox=x=iw*0.1:y=ih*0.7:w=iw*0.8:h=4:"
            f"color=white@0.8:t=fill[{out_label}]"
        ),

        # ── 故障类 ──
        "glitch_intro": (
            f"[{in_label}]geq=r='r(X+2*sin(PI*t*10),Y)':"
            f"g='g(X,Y)':b='b(X-2*sin(PI*t*10),Y)'[{out_label}]"
        ),

        # ── 万花筒(轻) ──
        "kaleidoscope_light": (
            f"[{in_label}]hflip,blend=all_mode=average[{out_label}]"
        ),

        # ── 十字淡入 ──
        "crossfade_slow": (
            f"[{in_label}]fade=in:st=0:d=0.5[{out_label}]"
        ),

        # ── 定位标记 ──
        "location_pin": (
            f"[{in_label}]drawtext=fontfile=/Windows/Fonts/simhei.ttf:"
            f"text='📍':fontsize=48:fontcolor=white@0.9:"
            f"x=iw*0.05:y=ih*0.85[{out_label}]"
        ),

        # ── 稳定(轻微去抖) ──
        "stabilize": (
            f"[{in_label}]deshake[{out_label}]"
        ),
    }

    return ffmpeg_map.get(effect_name, f"[{in_label}]copy[{out_label}]")


# ══════════════════════════════════════════════════════════
# 主函数: 为时间线生成可执行的FFmpeg滤镜链
# ══════════════════════════════════════════════════════════

@dataclass
class VfxPlan:
    """VFX执行计划——不是描述, 是可执行的FFmpeg命令片段"""
    success: bool
    category: str = "团购售卖"
    category_label: str = ""
    beat_count: int = 0
    bpm: float = 120.0

    # 全局滤镜(应用于整个合成后视频)
    global_vf: str = ""

    # 段级滤镜: [{label_in, label_out, vf, duration}]
    segments_vfx: list[dict] = field(default_factory=list)

    # 转场滤镜: [{from_label, to_label, vf, duration}]
    transitions: list[dict] = field(default_factory=list)

    error: str = ""


def build_vfx_plan(
    timeline,           # FourCategoryTimeline
    video_path: str,
    category: str = "团购售卖",   # 脚本类别——决定剪辑策略
    industry: str = "",          # 行业(可选)——微调色调
) -> VfxPlan:
    """
    为ChatCut时间线生成VFX执行计划。

    category: "团购售卖" | "老板IP" | "引流进店"
    industry: 10行业之一(可选, 用于微调色调)

    返回的 VfxPlan 包含可直接拼接的 FFmpeg 滤镜片段。
    """
    # 获取类别策略
    style = CATEGORY_STYLE.get(category, CATEGORY_STYLE["团购售卖"])

    # 行业色调微调
    tweak = INDUSTRY_COLOR_TWEAK.get(industry, {})

    # ── 节拍检测 ──
    try:
        from .vfx.beat_trigger import detect_beats_simple, BeatOnset, BeatTriggerEngine, BeatTriggerPresets
        beats = detect_beats_simple(video_path)
    except Exception:
        beats = []

    if not beats:
        duration = sum(getattr(s, 'duration_sec', 2) for s in (timeline.segments if hasattr(timeline, 'segments') else []))
        duration = max(duration, 10)
        beats = [BeatOnset(t, 0.8, t % 2 == 0) for t in [i * 0.5 for i in range(int(duration * 2))]]

    # 配置节拍引擎
    engine = BeatTriggerEngine()
    engine.configure(BeatTriggerPresets.for_genre(
        "hype" if style["beat_preset"] == "douyin_hot" else
        "melodic" if style["beat_preset"] == "melodic_subtle" else
        "hype"
    ))
    engine.set_beat_map(beats)

    # ── 逐段构建滤镜 ──
    segments = timeline.segments if hasattr(timeline, 'segments') else []
    seg_vfx_list = []
    accum_time = 0.0

    for i, seg in enumerate(segments):
        dur = getattr(seg, 'duration_sec', 2.0)
        seg_end = accum_time + dur
        engine.update(seg_end)

        role = _guess_role(i, len(segments), seg)

        # 选择该角色的效果列表
        effect_names = style.get(f"{role}_effects", style.get("body_effects", []))

        # 为每个效果生成FFmpeg滤镜
        cur_label = str(i)  # 使用段索引作为输入标签
        seg_filters = []
        for fx_name in effect_names:
            vf = _effect_to_ffmpeg(fx_name, cur_label, f"s{i}_{fx_name}")
            if f"copy[{fx_name}]" not in vf:  # 跳过无实际效果的
                seg_filters.append(vf)

        seg_vfx_list.append({
            "index": i,
            "role": role,
            "duration": dur,
            "start_sec": getattr(seg, 'start_sec', 0),
            "filters": seg_filters,
            "transition": style.get("transition", "crossfade"),
        })
        accum_time = seg_end

    # ── 全局滤镜(最终调色) ──
    global_vf = _build_global_color_filter(style["global_color"], tweak)

    return VfxPlan(
        success=True,
        category=category,
        category_label=style["label"],
        beat_count=len(beats),
        bpm=_estimate_bpm(beats),
        global_vf=global_vf,
        segments_vfx=seg_vfx_list,
    )


# ══════════════════════════════════════════════════════════
# 渲染集成: 生成最终FFmpeg命令
# ══════════════════════════════════════════════════════════

def render_with_vfx(
    vfx_plan: VfxPlan,
    segment_files: list[tuple[str, float]],    # [(文件路径, 段时长), ...]
    audio_path: str = "",
    output_path: str = "",
    width: int = 1080,
    height: int = 1920,
) -> tuple[bool, str]:
    """
    执行VFX渲染——生成并运行FFmpeg命令。

    segment_files: [(视频文件路径, 该段时长秒), ...]
    返回: (成功, 输出路径或错误信息)
    """
    import subprocess, os

    if not segment_files:
        return False, "无素材文件"

    if not output_path:
        output_path = str(Path(segment_files[0][0]).parent / "vfx_output.mp4")

    # 构建filter_complex
    filter_parts = []
    concat_labels = []

    for i, ((file_path, duration), seg_vfx) in enumerate(
        zip(segment_files, vfx_plan.segments_vfx)
    ):
        label_in = str(i)
        label_out = f"seg{i}"

        # 段级滤镜链
        current_label = label_in
        for j, vf in enumerate(seg_vfx.get("filters", [])):
            # 把 vf 中的标签替换为当前链
            adjusted = vf.replace(f"[{label_in}]", f"[{current_label}]")
            # 替换输出标签为临时标签
            tmp_label = f"tmp{i}_{j}"
            adjusted = adjusted.replace(f"[s{i}_", f"[tmp{i}_")
            filter_parts.append(adjusted)
            current_label = f"tmp{i}_" + adjusted.split("[")[-1].split("]")[0]

        # 段裁剪+时长
        filter_parts.append(
            f"[{current_label}]trim=duration={duration},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[{label_out}]"
        )
        concat_labels.append(label_out)

    # 拼接
    concat_inputs = "".join(f"[{l}]" for l in concat_labels)
    n = len(segment_files)
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[v_raw]")

    # 全局调色
    if vfx_plan.global_vf:
        filter_parts.append(
            vfx_plan.global_vf.replace("[0]", "[v_raw]").replace("[v]", "[v_final]")
        )
        video_out = "v_final"
    else:
        filter_parts.append(f"[v_raw]copy[v_final]")
        video_out = "v_final"

    filter_complex = ";".join(filter_parts)

    # FFmpeg命令
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for file_path, _ in segment_files:
        cmd.extend(["-i", file_path])
    if audio_path and os.path.exists(audio_path):
        cmd.extend(["-i", audio_path])

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", f"[{video_out}]",
    ])
    if audio_path and os.path.exists(audio_path):
        cmd.extend(["-map", f"{len(segment_files)}:a:0"])
    cmd.extend([
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        output_path,
    ])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode == 0 and os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            logger.info(f"VFX渲染完成: {size_mb:.1f}MB → {output_path}")
            return True, output_path
        else:
            return False, f"FFmpeg错误: {proc.stderr[:300]}"
    except Exception as e:
        return False, str(e)[:200]


# ══════════════════════════════════════════════════════════
# 辅助
# ══════════════════════════════════════════════════════════

def _guess_role(idx: int, total: int, seg) -> str:
    if idx == 0:
        return "hook"
    if idx == total - 1:
        return "cta"
    if getattr(seg, 'is_broll', False):
        return "broll"
    return "body"


def _build_global_color_filter(color_name: str, tweak: dict) -> str:
    """根据颜色名+行业微调构建全局调色滤镜"""
    warmth = tweak.get("warmth", 0)
    saturation = tweak.get("saturation", 0)
    contrast = tweak.get("contrast", 0)

    base_filters = {
        "warm_boost": f"eq=saturation={1.2+saturation}:brightness=0.05:contrast={1.05+contrast}:gamma={1.03+warmth}",
        "film_warm": f"eq=saturation={0.85+saturation}:brightness=0.02:contrast={1.1+contrast}:gamma={1.08+warmth}",
        "bright_clean": f"eq=saturation={1.0+saturation}:brightness=0.08:contrast={1.08+contrast}:gamma=0.95",
        "none": "copy",
    }
    vf = base_filters.get(color_name, "copy")
    if vf == "copy":
        return ""
    return f"[0]{vf}[v]"


def _estimate_bpm(beats: list) -> float:
    if len(beats) < 2:
        return 120.0
    intervals = []
    for i in range(1, min(len(beats), 30)):
        dt = beats[i].time_seconds - beats[i - 1].time_seconds
        if 0.2 <= dt <= 2.0:
            intervals.append(dt)
    return round(60.0 / (sum(intervals) / len(intervals)), 1) if intervals else 120.0


# ══════════════════════════════════════════════════════════
# 兼容旧接口
# ══════════════════════════════════════════════════════════

def enhance_timeline(timeline, video_path: str, preset=None, script_category: str = "团购售卖"):
    """兼容旧 call 的包装器。preset 参数忽略, 改用 script_category。"""
    return build_vfx_plan(timeline, video_path, script_category)


class VfxPreset:
    """兼容旧代码的枚举占位"""
    douyin_hot = "douyin_hot"
    cinematic = "cinematic"
    gritty_drill = "gritty_drill"
    warm_story = "warm_story"
    clean_business = "clean_business"
    retro_vhs = "retro_vhs"


def get_category_style(category: str) -> dict:
    """查询某类脚本的剪辑策略"""
    return CATEGORY_STYLE.get(category, CATEGORY_STYLE["团购售卖"])


def list_categories() -> list[dict]:
    """列出所有三类脚本的剪辑策略摘要"""
    return [
        {"category": cat, "label": s["label"],
         "hook": s["hook_effects"], "cta": s["cta_effects"]}
        for cat, s in CATEGORY_STYLE.items()
    ]
