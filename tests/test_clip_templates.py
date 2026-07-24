"""clip_templates.py 测试 — 3脚本策略·15剪同款模板（纯逻辑，无外部依赖）"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestScriptToTemplateMapping:
    def test_all_three_main_types_mapped(self):
        from clip_agent.clip_templates import SCRIPT_TO_TEMPLATE
        assert SCRIPT_TO_TEMPLATE["老板IP"] == "老板IP"
        assert SCRIPT_TO_TEMPLATE["团购售卖"] == "团购售卖"
        assert SCRIPT_TO_TEMPLATE["引流进店"] == "引流进店"

    def test_alias_types_mapped_correctly(self):
        from clip_agent.clip_templates import SCRIPT_TO_TEMPLATE
        assert SCRIPT_TO_TEMPLATE["product_intro"] == "团购售卖"
        assert SCRIPT_TO_TEMPLATE["company_intro"] == "老板IP"
        assert SCRIPT_TO_TEMPLATE["store_tour"] == "引流进店"
        assert SCRIPT_TO_TEMPLATE["daily_vlog"] == "老板IP"


class TestClipTemplatesDataIntegrity:
    @pytest.fixture
    def templates(self):
        from clip_agent.clip_templates import CLIP_TEMPLATES
        return CLIP_TEMPLATES

    def test_all_three_types_defined(self, templates):
        assert "老板IP" in templates
        assert "团购售卖" in templates
        assert "引流进店" in templates

    def test_each_template_has_required_fields(self, templates):
        required = ["name", "icon", "script_type", "desc", "creator_archetype",
                    "hook_strategy", "retention_timeline", "editing_dna",
                    "bgm_style", "default_bpm", "min_shots"]
        for key, tmpl in templates.items():
            for field in required:
                assert field in tmpl, f"{key} missing '{field}'"

    def test_hook_strategy_has_four_layers(self, templates):
        layers = ["visual_0s", "text_0s", "verbal_0s", "audio_0s"]
        for key, tmpl in templates.items():
            for layer in layers:
                assert layer in tmpl["hook_strategy"], f"{key} hook missing '{layer}'"

    def test_retention_timelines_have_action_and_detail(self, templates):
        for key, tmpl in templates.items():
            for i, point in enumerate(tmpl["retention_timeline"]):
                assert "at_sec" in point, f"{key} timeline[{i}] missing at_sec"
                assert "action" in point, f"{key} timeline[{i}] missing action"
                assert "detail" in point, f"{key} timeline[{i}] missing detail"

    def test_editing_dna_has_required_fields(self, templates):
        dna_fields = ["shot_duration", "broll_density", "text_density",
                      "preferred_camera", "color_filter", "transition",
                      "pace", "opening", "ending"]
        for key, tmpl in templates.items():
            for field in dna_fields:
                assert field in tmpl["editing_dna"], f"{key} dna missing '{field}'"

    def test_shot_duration_ranges_are_valid(self, templates):
        for key, tmpl in templates.items():
            sd = tmpl["editing_dna"]["shot_duration"]
            assert sd["min"] <= sd["typical"] <= sd["max"], \
                f"{key}: min({sd['min']}) <= typical({sd['typical']}) <= max({sd['max']}) violation"

    def test_min_shots_at_least_5(self, templates):
        for key, tmpl in templates.items():
            assert tmpl["min_shots"] >= 5, f"{key} min_shots too low: {tmpl['min_shots']}"


class TestPresetTemplates:
    @pytest.fixture
    def presets(self):
        from clip_agent.clip_templates import PRESET_TEMPLATES
        return PRESET_TEMPLATES

    def test_has_15_presets(self, presets):
        assert len(presets) == 15, f"Expected 15 presets, got {len(presets)}"

    def test_5_per_script_type(self, presets):
        from collections import Counter
        counts = Counter(p["script_type"] for p in presets.values())
        assert counts["老板IP"] == 5
        assert counts["团购售卖"] == 5
        assert counts["引流进店"] == 5

    def test_each_preset_has_required_fields(self, presets):
        required = ["name", "icon", "script_type", "desc", "shot_count",
                    "target_duration", "bgm", "filter", "text_animation",
                    "transition", "example_hook"]
        for key, p in presets.items():
            for field in required:
                assert field in p, f"preset {key} missing '{field}'"

    def test_preset_keys_follow_naming_convention(self, presets):
        for key in presets:
            assert key.startswith(("ip_", "sale_", "traffic_")), \
                f"preset key '{key}' doesn't follow naming convention"

    def test_target_durations_are_reasonable(self, presets):
        for key, p in presets.items():
            assert 15 <= p["target_duration"] <= 65, \
                f"{key} target_duration {p['target_duration']}s out of range"


class TestListTemplates:
    def test_returns_three_templates(self):
        from clip_agent.clip_templates import list_templates
        result = list_templates()
        assert len(result) == 3

    def test_each_has_required_keys(self):
        from clip_agent.clip_templates import list_templates
        for t in list_templates():
            for k in ["key", "name", "icon", "script_type", "desc", "min_shots"]:
                assert k in t


class TestGetTemplate:
    def test_exact_key_match(self):
        from clip_agent.clip_templates import get_template
        t = get_template("老板IP")
        assert t is not None
        assert t["name"] == "老板IP·人物故事"

    def test_alias_key_match(self):
        from clip_agent.clip_templates import get_template
        t = get_template("product_intro")
        assert t is not None
        assert t["script_type"] == "团购售卖"

    def test_unknown_key_falls_back_to_老板IP(self):
        from clip_agent.clip_templates import get_template
        t = get_template("完全不存在的类型")
        assert t is not None
        assert t["script_type"] == "老板IP"


class TestAutoSelectTemplate:
    def test_keyword_match_团购(self):
        from clip_agent.clip_templates import auto_select_template
        result = auto_select_template([], "想做一个团购促销视频")
        assert result == "团购售卖"

    def test_keyword_match_引流(self):
        from clip_agent.clip_templates import auto_select_template
        result = auto_select_template([], "想引流到店，展示排队火爆")
        assert result == "引流进店"

    def test_keyword_match_story(self):
        from clip_agent.clip_templates import auto_select_template
        result = auto_select_template([], "讲讲我的创业故事")
        assert result == "老板IP"

    def test_material_type_character_only(self):
        from clip_agent.clip_templates import auto_select_template
        result = auto_select_template(["人物"])
        assert result == "老板IP"

    def test_material_type_both_then_团购(self):
        from clip_agent.clip_templates import auto_select_template
        result = auto_select_template(["人物", "产品"])
        assert result == "团购售卖"

    def test_empty_defaults_to_团购(self):
        from clip_agent.clip_templates import auto_select_template
        result = auto_select_template([], "")
        assert result == "团购售卖"


class TestListPresetTemplates:
    def test_returns_all_15_when_no_filter(self):
        from clip_agent.clip_templates import list_preset_templates
        result = list_preset_templates()
        assert len(result) == 15

    def test_filter_by_script_type(self):
        from clip_agent.clip_templates import list_preset_templates
        result = list_preset_templates("老板IP")
        assert len(result) == 5
        assert all(t["script_type"] == "老板IP" for t in result)


class TestGetPresetTemplate:
    def test_existing_key(self):
        from clip_agent.clip_templates import get_preset_template
        t = get_preset_template("ip_story_beginning")
        assert t is not None
        assert t["name"] == "创业初心"

    def test_missing_key(self):
        from clip_agent.clip_templates import get_preset_template
        t = get_preset_template("not_exists")
        assert t is None


class TestBuildEditingPrompt:
    def test_returns_non_empty_string(self):
        from clip_agent.clip_templates import build_editing_prompt
        result = build_editing_prompt("老板IP")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_key_sections(self):
        from clip_agent.clip_templates import build_editing_prompt
        result = build_editing_prompt("团购售卖")
        assert "剪辑策略" in result
        assert "4层钩子" in result
        assert "留存动作点" in result
        assert "蒙太奇" in result

    def test_includes_creator_archetype(self):
        from clip_agent.clip_templates import build_editing_prompt
        result = build_editing_prompt("团购售卖")
        assert "Hormozi" in result

    def test_unknown_key_falls_back_to_老板IP(self):
        from clip_agent.clip_templates import build_editing_prompt
        result = build_editing_prompt("不存在")
        # get_template("不存在") → falls back to 老板IP → valid prompt
        assert "老板IP" in result
        assert len(result) > 100


class TestVisualStrategies:
    def test_three_strategies_defined(self):
        from clip_agent.clip_templates import VISUAL_STRATEGIES
        assert "good_presence" in VISUAL_STRATEGIES
        assert "script_reading" in VISUAL_STRATEGIES
        assert "mixed" in VISUAL_STRATEGIES

    def test_broll_ratios_sum_to_logic(self):
        from clip_agent.clip_templates import VISUAL_STRATEGIES
        # script_reading (all broll) should be 1.0
        assert VISUAL_STRATEGIES["script_reading"].broll_ratio == 1.0
        # good_presence (minimal broll) should be < 0.5
        assert VISUAL_STRATEGIES["good_presence"].broll_ratio < 0.5


class TestBgmRules:
    def test_default_values(self):
        from clip_agent.clip_templates import BGM_RULES
        assert BGM_RULES["volume_ratio"] == 0.33
        assert BGM_RULES["ducking"] is True
        assert BGM_RULES["ducking_ratio"] == 0.25
