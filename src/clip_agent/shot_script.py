"""Shot契约——脚本Agent分镜语言→剪辑引擎可执行结构

脚本Agent(gateway_client._generate_direct)已生成shot_json但被API丢弃。
本模块是剪辑侧的消费契约: 解析shot_json→句级渲染输入。
无shot_json时退化为按句拆分(现状·不回归)。
"""
from __future__ import annotations
import logging, re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# shot_type(中文景别)→文字规格(px)
SHOT_TEXT_SIZE = {"特写": 72, "近景": 64, "中景": 56, "全景": 44, "远景": 44}
# shot.emotion→效果着色器(与句级语义映射同族)
SHOT_EMOTION_SHADER = {
    "冲击": "bleach_bypass",   # 高对比
    "共鸣": "warm_grade",      # 暖色
    "信任": "bright_grade",    # 明亮
    "渴望": "vignette_soft",   # 暗角聚焦
    "紧迫": "warm_boost",      # 高能暖色
    "好奇": "vignette_soft",
}
_CHARS_PER_SEC = 4.5


@dataclass
class Shot:
    index: int
    script_text: str
    shot_type: str = "中景"
    camera_move: str = ""
    emotion: str = ""
    transition: str = ""
    overlay_text: str = ""
    duration_sec: float = 0.0
    action: str = ""


@dataclass
class ShotScript:
    script_text: str
    script_type: str
    shots: list[Shot] = field(default_factory=list)
    source: str = "text_fallback"      # shot_json / text_fallback


def _est_duration(text: str) -> float:
    chars = len(re.sub(r"[\s，。！？、,.!?~…·—\-「」『』\"'“”‘’:：;；()（）【】]", "", text))
    return round(max(1.5, chars / _CHARS_PER_SEC), 1)


def parse_shot_script(script_text: str, script_type: str = "团购售卖",
                      shot_json: list | None = None) -> ShotScript:
    """解析脚本+可选shot_json→ShotScript

    shot_json兼容gateway格式: {start_sec,end_sec,shot_type,camera_move,
      script_text,action,emotion,duration_ms,transition,overlay_text}
    无shot_json→按句拆分退化。
    """
    if shot_json:
        shots = []
        for i, sj in enumerate(shot_json, 1):
            text = (sj.get("script_text") or "").strip()
            dur = (sj.get("duration_ms", 0) or 0) / 1000.0
            if dur <= 0:
                dur = float(sj.get("end_sec", 0) - sj.get("start_sec", 0))
            if dur <= 0:
                dur = _est_duration(text)
            shots.append(Shot(
                index=i, script_text=text,
                shot_type=sj.get("shot_type") or "中景",
                camera_move=sj.get("camera_move") or "",
                emotion=sj.get("emotion") or "",
                transition=sj.get("transition") or "",
                overlay_text=sj.get("overlay_text") or "",
                duration_sec=round(dur, 1),
                action=sj.get("action") or "",
            ))
        if shots:
            return ShotScript(script_text=script_text, script_type=script_type,
                              shots=shots, source="shot_json")
        logger.warning("shot_json为空·退化按句拆分")

    # 退化: 按句拆分(现状)
    parts = [p.strip() for p in re.split(r"[。!！?？\n]+", script_text) if p.strip()]
    shots = [Shot(index=i, script_text=p, duration_sec=_est_duration(p))
             for i, p in enumerate(parts, 1)]
    return ShotScript(script_text=script_text, script_type=script_type,
                      shots=shots, source="text_fallback")


def shots_to_sentences(ss: ShotScript) -> list:
    """ShotScript→句级渲染输入(SimpleNamespace·兼容_render_unified_vfx)"""
    from types import SimpleNamespace
    return [SimpleNamespace(index=s.index, text=s.script_text,
                            duration_sec=s.duration_sec, is_broll=False)
            for s in ss.shots]


def shot_effects(ss: ShotScript) -> dict[int, dict]:
    """每镜的剪辑指令: {index: {"xfade","shader","text_size","overlay_text"}}"""
    out = {}
    for s in ss.shots:
        fx = {}
        if s.transition and s.transition != "cut":
            fx["xfade"] = s.transition
        shader = SHOT_EMOTION_SHADER.get(s.emotion)
        if shader:
            fx["shader"] = shader
        fx["text_size"] = SHOT_TEXT_SIZE.get(s.shot_type, 56)
        if s.overlay_text:
            fx["overlay_text"] = s.overlay_text
        out[s.index] = fx
    return out
