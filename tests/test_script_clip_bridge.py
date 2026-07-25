"""script_clip_bridge.py 测试 — 脚本→剪辑联通桥"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestBridgeConfig:
    def test_default_values(self):
        from clip_agent.script_clip_bridge import BridgeConfig
        bc = BridgeConfig(script_type="老板IP", template_key="test", color_grade="warm", bgm_genre="温暖")
        assert bc.script_type == "老板IP"
        assert bc.bgm_volume == 0.3
        assert bc.script_text == ""
        assert bc.sentences == []
        assert bc.shot_map == []


class TestScriptToClipConfig:
    def test_all_three_types_have_config(self):
        from clip_agent.script_clip_bridge import SCRIPT_TO_CLIP_CONFIG
        for st in ["老板IP", "团购售卖", "引流进店"]:
            assert st in SCRIPT_TO_CLIP_CONFIG
            cfg = SCRIPT_TO_CLIP_CONFIG[st]
            assert "template_key" in cfg
            assert "color_grade" in cfg
            assert "bgm_genre" in cfg
            assert "broll_density" in cfg

    def test_color_grades_are_valid(self):
        from clip_agent.script_clip_bridge import SCRIPT_TO_CLIP_CONFIG
        valid = {"warm", "vivid", "bright", "cool", "cinematic", "neutral"}
        for st, cfg in SCRIPT_TO_CLIP_CONFIG.items():
            assert cfg["color_grade"] in valid, f"{st} color_grade invalid"


class TestBridgeScriptToClip:
    def test_minimal_input(self):
        from clip_agent.script_clip_bridge import bridge_script_to_clip
        bridge = bridge_script_to_clip({"script_type": "老板IP", "script_text": "大家好"})
        assert bridge.script_type == "老板IP"
        assert bridge.template_key == "ip_story_beginning"
        assert bridge.color_grade == "warm"
        assert bridge.script_text == "大家好"

    def test_defaults_to_团购售卖(self):
        from clip_agent.script_clip_bridge import bridge_script_to_clip
        bridge = bridge_script_to_clip({})
        assert bridge.script_type == "团购售卖"
        assert bridge.template_key == "sale_price_first"

    def test_with_shotlist(self):
        from clip_agent.script_clip_bridge import bridge_script_to_clip
        script_output = {
            "script_type": "团购售卖",
            "script_text": "68块！十只活虾！",
            "shot_list": {
                "shots": [
                    {"shot_id": 1, "label": "产品特写", "required_material": "product_closeup",
                     "shot_type": "CU", "duration_sec": 2.0, "camera_move": "static",
                     "text_overlay": "68块!", "text_position": "center", "broll_overlay": False},
                    {"shot_id": 2, "label": "口播", "required_material": "talking_head",
                     "shot_type": "MS", "duration_sec": 5.0, "camera_move": "static",
                     "text_overlay": "", "broll_overlay": False},
                ]
            }
        }
        bridge = bridge_script_to_clip(script_output)
        assert len(bridge.shot_map) == 2
        assert bridge.shot_map[0]["required_material"] == "product_closeup"
        assert bridge.shot_map[0]["required_shot"] == "CU"
        assert bridge.shot_map[1]["required_material"] == "talking_head"

    def test_with_retention_timeline(self):
        from clip_agent.script_clip_bridge import bridge_script_to_clip
        script_output = {
            "script_type": "引流进店",
            "retention_timeline": [
                {"at_sec": 0, "action": "稀缺钩子", "detail": "门头全景"},
                {"at_sec": 3, "action": "证明1", "detail": "独家工艺"},
            ]
        }
        bridge = bridge_script_to_clip(script_output)
        assert len(bridge.retention_timeline) == 2
        assert bridge.retention_timeline[0]["at_sec"] == 0

    def test_with_hook_strategy(self):
        from clip_agent.script_clip_bridge import bridge_script_to_clip
        script_output = {
            "script_type": "团购售卖",
            "hook_strategy": {
                "text_0s": "68块！",
                "visual_0s": "产品特写CU",
                "verbal_0s": "68块！十只活虾！",
                "audio_0s": "鼓点BGM淡入",
            }
        }
        bridge = bridge_script_to_clip(script_output)
        assert bridge.hook_strategy["text"] == "68块！"
        assert bridge.hook_strategy["animation"] == "fade_in"  # "冲击" not in verbal

    def test_parses_sentences_from_script_text(self):
        from clip_agent.script_clip_bridge import bridge_script_to_clip
        script_output = {
            "script_type": "老板IP",
            "script_text": "大家好。我是做小龙虾的老王。今天给大家看看我们的虾。",
        }
        bridge = bridge_script_to_clip(script_output)
        assert len(bridge.sentences) >= 2


class TestAutoAssignMaterials:
    def test_simple_sequential(self):
        from clip_agent.script_clip_bridge import _auto_assign_materials
        shot_map = [
            {"required_material": "product_closeup"},
            {"required_material": "talking_head"},
        ]
        files = ["产品特写.mp4", "口播.mp4"]
        result = _auto_assign_materials(shot_map, files)
        assert len(result) == 2

    def test_empty_inputs(self):
        from clip_agent.script_clip_bridge import _auto_assign_materials
        assert _auto_assign_materials([], []) == []
        assert _auto_assign_materials([{"required_material": "product"}], []) == []


class TestMapFunctions:
    def test_map_retention_empty(self):
        from clip_agent.script_clip_bridge import _map_retention_to_broll_points
        assert _map_retention_to_broll_points([]) == []

    def test_map_hook_empty(self):
        from clip_agent.script_clip_bridge import _map_hook_to_text_overlay
        assert _map_hook_to_text_overlay({}) == {"text": "", "visual": "", "audio": "", "verbal": "", "animation": "fade_in", "font_size": 72, "color": "#FFD700"}
