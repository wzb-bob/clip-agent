"""
节拍触发引擎 · 从 vfx-studio/beat_trigger_engine.dart 搬运

自动在音频节拍点触发视觉效果: 闪光/震动/变速/缩放脉冲/发光/色移/RGB分裂/故障

纯Python · 零外部依赖 · 可与任意音频分析后端对接
"""
from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 数据类型 (对齐 BeatOnset / BeatTrigger / BeatTriggerState)
# ══════════════════════════════════════════════════════════

class BeatTriggerType(Enum):
    flash = "flash"           # 白色/彩色闪光
    shake = "shake"           # 相机/画面震动
    speed_ramp = "speed_ramp" # 速度曲线
    zoom_pulse = "zoom_pulse" # 快速缩放脉冲
    glow_pulse = "glow_pulse" # 发光强度尖峰
    color_shift = "color_shift" # 色相/色度偏移
    rgb_split = "rgb_split"   # 色散尖峰
    glitch_hit = "glitch_hit" # 故障块爆发


@dataclass
class BeatOnset:
    """节拍检测点"""
    time_seconds: float
    energy: float
    is_downbeat: bool = False
    frequency: float = 0.0  # 主频 (kick~60, snare~200, hihat~8000)


@dataclass
class BeatTrigger:
    """节拍触发器配置"""
    type: BeatTriggerType
    intensity: float = 0.5       # 0-1
    duration_sec: float = 0.1     # 效果持续时长(秒)
    beat_interval: int = 1        # 每N拍触发一次 (1=每拍, 2=隔拍, 4=仅重拍)
    params: dict | None = None

    @classmethod
    def preset(cls, preset_name: str) -> BeatTrigger:
        """预设触发器 (对齐 BeatTrigger.preset)"""
        presets = {
            "heavy_drop":  cls(BeatTriggerType.shake,      0.8, 0.20, 1),
            "light_pulse": cls(BeatTriggerType.zoom_pulse, 0.3, 0.08, 2),
            "strobe_hit":  cls(BeatTriggerType.flash,      0.9, 0.05, 1),
            "glitch_beat": cls(BeatTriggerType.glitch_hit, 0.6, 0.12, 1),
            "warm_pulse":  cls(BeatTriggerType.glow_pulse, 0.4, 0.15, 2),
            "color_hit":   cls(BeatTriggerType.color_shift,0.5, 0.10, 4),
            "rgb_hit":     cls(BeatTriggerType.rgb_split,  0.6, 0.08, 1),
            "speed_curve": cls(BeatTriggerType.speed_ramp, 0.7, 0.25, 2),
        }
        return presets.get(preset_name, cls(BeatTriggerType.flash, 0.5, 0.1, 1))


@dataclass
class BeatTriggerState:
    """节拍触发器运行时状态"""
    time_sec: float
    beat: BeatOnset
    trigger: BeatTrigger
    elapsed_sec: float = 0.0

    @property
    def progress(self) -> float:
        """归一化进度 0→1"""
        if self.trigger.duration_sec <= 0:
            return 1.0
        return max(0.0, min(1.0, self.elapsed_sec / self.trigger.duration_sec))

    @property
    def envelope(self) -> float:
        """Attack/Decay 包络 (鼓点式: 快攻快衰减)"""
        p = self.progress
        if p > 0.5:
            return 2.0 * (1.0 - p)  # decay
        return 2.0 * p               # attack

    @property
    def is_active(self) -> bool:
        return self.elapsed_sec <= self.trigger.duration_sec


# ══════════════════════════════════════════════════════════
# BeatTriggerEngine (对齐 Dart BeatTriggerEngine)
# ══════════════════════════════════════════════════════════

class BeatTriggerEngine:
    """节拍触发引擎"""

    def __init__(self):
        self._triggers: list[BeatTrigger] = []
        self._beat_map: list[BeatOnset] = []
        self._active_states: list[BeatTriggerState] = []
        self._fired_beats: set[int] = set()  # 已触发的拍索引(防重复)

    # ── 配置 ──

    def configure(self, triggers: list[BeatTrigger]) -> None:
        self._triggers.clear()
        self._triggers.extend(triggers)
        self._fired_beats.clear()

    def add_trigger(self, trigger: BeatTrigger) -> None:
        self._triggers.append(trigger)

    def clear(self) -> None:
        self._triggers.clear()
        self._active_states.clear()
        self._fired_beats.clear()

    def set_beat_map(self, beats: list[BeatOnset]) -> None:
        self._beat_map.clear()
        self._beat_map.extend(beats)
        self._fired_beats.clear()

    # ── 主循环: 每帧调用 ──

    def update(self, current_time_sec: float) -> list[BeatTriggerState]:
        """更新引擎到当前时间, 返回所有活跃触发状态"""
        # 清理过期状态
        self._active_states = [s for s in self._active_states if s.is_active]

        # 检测新节拍穿越 (50ms窗口)
        for idx, beat in enumerate(self._beat_map):
            if idx in self._fired_beats:
                continue
            if beat.time_seconds <= current_time_sec and \
               beat.time_seconds > current_time_sec - 0.05:
                self._fired_beats.add(idx)
                self._fire_triggers(beat)

        # 更新已激活状态的 elapsed
        for i, state in enumerate(self._active_states):
            self._active_states[i] = BeatTriggerState(
                time_sec=current_time_sec,
                beat=state.beat,
                trigger=state.trigger,
                elapsed_sec=current_time_sec - state.time_sec + state.elapsed_sec,
            )

        return list(self._active_states)

    def _fire_triggers(self, beat: BeatOnset) -> None:
        """在指定节拍上触发所有匹配的触发器"""
        try:
            beat_idx = self._beat_map.index(beat)
        except ValueError:
            return

        for trigger in self._triggers:
            # 间隔检查
            beats_from_downbeat = beat_idx % (trigger.beat_interval * 4)
            if beats_from_downbeat % trigger.beat_interval != 0:
                continue

            # 重拍增强 (强拍强度×1.3)
            effective_intensity = trigger.intensity
            if beat.is_downbeat:
                effective_intensity = min(1.0, trigger.intensity * 1.3)

            self._active_states.append(BeatTriggerState(
                time_sec=beat.time_seconds,
                beat=beat,
                trigger=BeatTrigger(
                    type=trigger.type,
                    intensity=effective_intensity,
                    duration_sec=trigger.duration_sec,
                    beat_interval=trigger.beat_interval,
                    params=trigger.params,
                ),
                elapsed_sec=0.0,
            ))

    # ── 渲染参数 (供外部的视频渲染器使用) ──

    @property
    def current_effect_params(self) -> dict[str, float]:
        """获取当前帧的所有合成效果参数"""
        params: dict[str, float] = {}

        for state in self._active_states:
            if not state.is_active:
                continue
            env = state.envelope * state.trigger.intensity

            match state.trigger.type:
                case BeatTriggerType.flash:
                    params["flash_opacity"] = params.get("flash_opacity", 0) + env
                case BeatTriggerType.shake:
                    params["shake_amount"] = params.get("shake_amount", 0) + env * 8
                case BeatTriggerType.speed_ramp:
                    params["speed_multiplier"] = params.get("speed_multiplier", 1.0) + env * 0.5
                case BeatTriggerType.zoom_pulse:
                    params["zoom_offset"] = params.get("zoom_offset", 0) + env * 0.15
                case BeatTriggerType.glow_pulse:
                    params["bloom_boost"] = params.get("bloom_boost", 0) + env * 0.4
                case BeatTriggerType.color_shift:
                    params["hue_shift"] = params.get("hue_shift", 0) + env * 30
                case BeatTriggerType.rgb_split:
                    params["rgb_split_amount"] = params.get("rgb_split_amount", 0) + env * 6
                case BeatTriggerType.glitch_hit:
                    params["glitch_intensity"] = params.get("glitch_intensity", 0) + env * 0.5

        return params

    @property
    def shake_offset(self) -> tuple[float, float]:
        """获取当前帧的震动偏移 (x, y) 像素"""
        sx, sy = 0.0, 0.0
        for state in self._active_states:
            if not state.is_active:
                continue
            env = state.envelope * state.trigger.intensity
            seed = state.beat.time_seconds * 1000
            angle = (seed % 360) * math.pi / 180
            sx += math.cos(angle) * env * 8
            sy += math.sin(angle) * env * 8
        return sx, sy

    # ── FFmpeg滤镜生成 ⚠️ DEPRECATED ──

    def to_ffmpeg_chain(self, input_label: str = "0", output_label: str = "v") -> str:
        """⚠️ 已弃用: geq闪白+静态crop震动效果粗糙。使用chatcut_vfx的eq/noise/vignette替代。"""
        params = self.current_effect_params
        filters = []

        # 闪光
        if params.get("flash_opacity", 0) > 0.01:
            opacity = min(params["flash_opacity"], 0.8)
            filters.append(
                f"[{input_label}]geq=r='r(X,Y)+{opacity*255}*(1-r(X,Y)/255)':"
                f"g='g(X,Y)+{opacity*255}*(1-g(X,Y)/255)':"
                f"b='b(X,Y)+{opacity*255}*(1-b(X,Y)/255)':eval=frame[flash_out]"
            )
            input_label = "flash_out"

        # 震动 (通过随机裁剪模拟)
        if params.get("shake_amount", 0) > 0.5:
            amount = int(min(params["shake_amount"], 16))
            filters.append(
                f"[{input_label}]crop=iw-{amount*2}:ih-{amount*2}:{amount}:{amount},"
                f"scale=iw:ih[shake_out]"
            )
            input_label = "shake_out"

        # 缩放脉冲
        if params.get("zoom_offset", 0) > 0.01:
            zoom = 1.0 + params["zoom_offset"]
            filters.append(
                f"[{input_label}]scale=iw*{zoom:.2f}:ih*{zoom:.2f},"
                f"crop=iw/{zoom:.2f}:ih/{zoom:.2f}[zoom_out]"
            )
            # 简化: zoompan 不支持动态参数, 使用 scale 近似
            # filters.append(f"[{input_label}]zoompan=z='min(zoom+0.0015,1.1)':d=1[zoom_out]")
            # input_label = "zoom_out"

        # 色移 (色相旋转)
        if params.get("hue_shift", 0) > 0.5:
            hue = params["hue_shift"]
            filters.append(f"[{input_label}]hue=h={hue}[hue_out]")
            input_label = "hue_out"

        if not filters:
            return f"[{input_label}]copy[{output_label}]"

        filters.append(f"[{input_label}]copy[{output_label}]")
        return ";".join(filters)


# ══════════════════════════════════════════════════════════
# 预设库 (对齐 BeatTriggerPresets)
# ══════════════════════════════════════════════════════════

class BeatTriggerPresets:
    """节拍触发预设库"""

    @staticmethod
    def douyin_hot() -> list[BeatTrigger]:
        """抖音爆款"""
        return [
            BeatTrigger.preset("strobe_hit"),
            BeatTrigger.preset("rgb_hit"),
            BeatTrigger.preset("light_pulse"),
        ]

    @staticmethod
    def drill_impact() -> list[BeatTrigger]:
        """Drill/Trap 重击"""
        return [
            BeatTrigger.preset("heavy_drop"),
            BeatTrigger.preset("glitch_beat"),
        ]

    @staticmethod
    def melodic_subtle() -> list[BeatTrigger]:
        """旋律说唱·细腻"""
        return [
            BeatTrigger.preset("warm_pulse"),
            BeatTrigger.preset("speed_curve"),
        ]

    @staticmethod
    def party_hype() -> list[BeatTrigger]:
        """派对高能"""
        return [
            BeatTrigger.preset("strobe_hit"),
            BeatTrigger.preset("color_hit"),
            BeatTrigger.preset("heavy_drop"),
        ]

    @staticmethod
    def minimal_clean() -> list[BeatTrigger]:
        """极简干净"""
        return [BeatTrigger.preset("light_pulse")]

    @staticmethod
    def for_genre(genre: str) -> list[BeatTrigger]:
        """按音乐风格匹配预设"""
        mapping = {
            "trap": BeatTriggerPresets.drill_impact,
            "drill": BeatTriggerPresets.drill_impact,
            "melodic": BeatTriggerPresets.melodic_subtle,
            "emo": BeatTriggerPresets.melodic_subtle,
            "rage": BeatTriggerPresets.party_hype,
            "hype": BeatTriggerPresets.party_hype,
            "boom_bap": BeatTriggerPresets.minimal_clean,
        }
        factory = mapping.get(genre, BeatTriggerPresets.douyin_hot)
        return factory()


# ══════════════════════════════════════════════════════════
# 音频分析工具 (简版Onset检测·无scipy依赖)
# ══════════════════════════════════════════════════════════

def detect_beats_simple(
    audio_path: str,
    sensitivity: float = 0.5,
    brutality: float = 0.5,
    min_bpm: float = 60,
    max_bpm: float = 200,
) -> list[BeatOnset]:
    """
    简易节拍检测·FFmpeg音频能量分析

    使用 FFmpeg 提取RMS能量曲线→峰值检测→BPM推算→节拍网格
    零外部依赖 (不依赖 librosa/scipy)

    Args:
        audio_path: 音频/视频文件路径
        sensitivity: 灵敏度 0.3=激进 1.5=保守
        brutality: 0=宽松(段落边界) 1=严格(节拍锁定)
        min_bpm: 最小BPM
        max_bpm: 最大BPM

    Returns:
        检测到的节拍列表
    """
    import subprocess, json, tempfile

    # Step 1: FFmpeg 提取RMS能量曲线 (每秒30次采样)
    try:
        proc = subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", audio_path,
            "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
            "-f", "null", "-"
        ], capture_output=True, text=True, timeout=120)
    except Exception as e:
        logger.warning(f"节拍检测失败(FFmpeg): {e}")
        return []

    # Step 2: 解析RMS值
    rms_values = []
    for line in proc.stderr.splitlines():
        if "RMS_level" in line:
            try:
                val = float(line.split("=")[-1].strip())
                if val > -100:  # 过滤静音
                    rms_values.append(val)
            except ValueError:
                continue

    if len(rms_values) < 10:
        return []

    # Step 3: 峰值检测
    # 将RMS转换为0-1能量值
    if not rms_values:
        return []
    max_rms = max(rms_values)
    min_rms = min(rms_values)
    if max_rms == min_rms:
        return []

    energy = [(v - min_rms) / (max_rms - min_rms) for v in rms_values]

    # 自适应阈值
    threshold = sensitivity * 0.3
    window_size = max(3, int(len(energy) * 0.02))  # ~20ms窗口

    peaks = []
    for i in range(window_size, len(energy) - window_size):
        window = energy[i - window_size:i + window_size + 1]
        if energy[i] > threshold and energy[i] == max(window):
            peaks.append(i)

    if len(peaks) < 2:
        return []

    # Step 4: BPM推算 (峰值间隔平均)
    sample_rate = 30  # astats reset间隔 ≈ 1/30s
    intervals = []
    for i in range(1, len(peaks)):
        dt = (peaks[i] - peaks[i - 1]) / sample_rate
        if 60 / max_bpm <= dt <= 60 / min_bpm:
            intervals.append(dt)

    if intervals:
        avg_interval = sum(intervals) / len(intervals)
        detected_bpm = 60 / avg_interval
    else:
        detected_bpm = 120  # 默认

    # Step 5: 构建节拍列表
    beats = []
    for i, peak_idx in enumerate(peaks):
        time_sec = peak_idx / sample_rate
        is_downbeat = (i % 4 == 0)  # 4/4拍，每4拍=强拍
        beats.append(BeatOnset(
            time_seconds=time_sec,
            energy=energy[peak_idx],
            is_downbeat=is_downbeat,
            frequency=60 if is_downbeat else 200,  # 近似: 强拍低频
        ))

    return beats
