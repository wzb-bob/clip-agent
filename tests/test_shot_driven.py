"""shot驱动剪辑单测(分镜意图→segments_vfx覆盖)"""
from src.clip_agent.shot_script import parse_shot_script, shot_effects


def _apply_fx(segments_vfx, fx_map):
    """复刻_render_unified_vfx里的shot覆盖逻辑(抽出便于单测)"""
    for sv in segments_vfx:
        fx = fx_map.get(sv.get("index", -1) + 1)
        if not fx:
            continue
        if fx.get("xfade"):
            sv["xfade"] = fx["xfade"]
        if fx.get("shader") and not any(f.get("shader") == fx["shader"] for f in sv["filters"]):
            sv["filters"].insert(0, {"type": "color", "shader": fx["shader"]})
        if fx.get("text_size"):
            sv["text_size"] = fx["text_size"]
        if fx.get("overlay_text"):
            sv["text"] = fx["overlay_text"]
            sv["text_y_frac"] = 0.25
    return segments_vfx


def _mk_segments(n=2):
    return [{"index": i, "filters": [], "text": ""} for i in range(n)]


GW_SHOTS = [
    {"start_sec": 0, "end_sec": 3, "shot_type": "近景", "camera_move": "推镜",
     "script_text": "68一份!", "action": "", "emotion": "冲击",
     "duration_ms": 3000, "transition": "cut", "overlay_text": ""},
    {"start_sec": 3, "end_sec": 8, "shot_type": "特写", "camera_move": "固定",
     "script_text": "凌晨四点挑的活虾", "action": "", "emotion": "信任",
     "duration_ms": 5000, "transition": "dissolve", "overlay_text": "只只满黄"},
]


def test_transition_applied():
    ss = parse_shot_script("x", "团购售卖", GW_SHOTS)
    segs = _apply_fx(_mk_segments(2), shot_effects(ss))
    assert segs[0].get("xfade") is None          # cut不进xfade
    assert segs[1]["xfade"] == "dissolve"


def test_emotion_shader_inserted_front():
    ss = parse_shot_script("x", "团购售卖", GW_SHOTS)
    segs = _apply_fx(_mk_segments(2), shot_effects(ss))
    assert segs[0]["filters"][0]["shader"] == "bleach_bypass"
    assert segs[1]["filters"][0]["shader"] == "bright_grade"


def test_shot_type_text_size():
    ss = parse_shot_script("x", "团购售卖", GW_SHOTS)
    segs = _apply_fx(_mk_segments(2), shot_effects(ss))
    assert segs[0]["text_size"] == 64   # 近景
    assert segs[1]["text_size"] == 72   # 特写


def test_overlay_text_with_safe_position():
    ss = parse_shot_script("x", "团购售卖", GW_SHOTS)
    segs = _apply_fx(_mk_segments(2), shot_effects(ss))
    assert segs[1]["text"] == "只只满黄"
    assert segs[1]["text_y_frac"] == 0.25   # 避开底部字幕
    assert segs[0]["text"] == ""            # 无overlay不动


def test_no_duplicate_shader():
    ss = parse_shot_script("x", "团购售卖", GW_SHOTS)
    segs = _mk_segments(2)
    segs[0]["filters"].append({"type": "color", "shader": "bleach_bypass"})
    segs = _apply_fx(segs, shot_effects(ss))
    assert len([f for f in segs[0]["filters"] if f["shader"] == "bleach_bypass"]) == 1
