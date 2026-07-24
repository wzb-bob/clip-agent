"""editing_rules.py 测试 — 15条精确编辑规则（纯逻辑，无外部依赖）"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestEditRuleDataIntegrity:
    """验证 EDITING_RULES 数据完整性和一致性"""

    @pytest.fixture
    def rules(self):
        from clip_agent.editing_rules import EDITING_RULES
        return EDITING_RULES

    def test_all_rules_have_unique_ids(self, rules):
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids)), f"重复rule_id: {[i for i in ids if ids.count(i) > 1]}"

    def test_all_rules_cover_three_script_types(self, rules):
        script_types = {r.script_type for r in rules}
        assert script_types >= {"老板IP", "团购售卖", "引流进店"}

    def test_all_rules_cover_four_roles(self, rules):
        for st in ["老板IP", "团购售卖", "引流进店"]:
            roles = {r.material_role for r in rules if r.script_type == st}
            # Each script type should have at least hook + body + outro
            assert "hook" in roles, f"{st} missing hook rule"
            assert "body" in roles, f"{st} missing body rule"
            assert "outro" in roles, f"{st} missing outro rule"

    def test_each_rule_has_required_fields(self, rules):
        for r in rules:
            assert r.rule_id, f"Rule missing rule_id"
            assert r.script_type, f"{r.rule_id} missing script_type"
            assert r.material_role, f"{r.rule_id} missing material_role"
            assert r.material_category, f"{r.rule_id} missing material_category"
            assert r.audio_rule is not None, f"{r.rule_id} missing audio_rule"
            assert r.speed_rule is not None, f"{r.rule_id} missing speed_rule"
            assert r.shot_size_sequence, f"{r.rule_id} missing shot_size_sequence"
            assert r.emotion_arc, f"{r.rule_id} missing emotion_arc"

    def test_cut_rules_have_valid_triggers(self, rules):
        valid_triggers = {"content_change", "silence_300ms", "silence_500ms",
                          "sentence_end", "beat_1", "eye_contact_lost"}
        for r in rules:
            for cr in r.cut_rules:
                assert cr.trigger in valid_triggers, f"{r.rule_id}: invalid trigger '{cr.trigger}'"

    def test_cut_rules_have_valid_actions(self, rules):
        valid_actions = {"cut", "dissolve", "fade_in", "fade_out", "whip_pan"}
        for r in rules:
            for cr in r.cut_rules:
                assert cr.action in valid_actions, f"{r.rule_id}: invalid action '{cr.action}'"

    def test_audio_rules_have_valid_actions(self, rules):
        valid_actions = {"keep", "mute", "duck", "replace_with_bgm", "replace_with_tts"}
        for r in rules:
            assert r.audio_rule.action in valid_actions, f"{r.rule_id}: invalid audio action '{r.audio_rule.action}'"

    def test_speed_rules_have_valid_actions(self, rules):
        valid_actions = {"normal", "slow_motion", "speed_up", "ramp"}
        for r in rules:
            assert r.speed_rule.action in valid_actions, f"{r.rule_id}: invalid speed action '{r.speed_rule.action}'"

    def test_shot_size_sequences_are_valid(self, rules):
        valid_sizes = {"LS", "MLS", "MS", "MCU", "CU", "ECU"}
        for r in rules:
            for sz in r.shot_size_sequence:
                assert sz in valid_sizes, f"{r.rule_id}: invalid shot size '{sz}'"


class TestDataClasses:
    def test_cut_rule_creation(self):
        from clip_agent.editing_rules import CutRule
        cr = CutRule("silence_300ms", "cut", 0, 100, 200)
        assert cr.trigger == "silence_300ms"
        assert cr.action == "cut"
        assert cr.duration_ms == 0
        assert cr.pre_roll_ms == 100
        assert cr.post_roll_ms == 200

    def test_text_rule_creation(self):
        from clip_agent.editing_rules import TextRule
        tr = TextRule("price", "pop_in", 72, "center", 0.0, 0.4, "#FF4444")
        assert tr.text_source == "price"
        assert tr.font_size == 72
        assert tr.color == "#FF4444"

    def test_audio_rule_defaults(self):
        from clip_agent.editing_rules import AudioRule
        ar = AudioRule("keep", 0.25, 1.0, 500, 300)
        assert ar.bgm_volume == 0.25
        assert ar.voice_volume == 1.0
        assert ar.fade_in_ms == 500

    def test_speed_rule_defaults(self):
        from clip_agent.editing_rules import SpeedRule
        sr = SpeedRule("normal", 1.0, 0.0)
        assert sr.speed_factor == 1.0


class TestGetRulesFor:
    def test_exact_match(self):
        from clip_agent.editing_rules import get_rules_for
        rule = get_rules_for("老板IP", "hook", "talking")
        assert rule is not None
        assert rule.rule_id == "ip_hook_01"
        assert rule.material_role == "hook"

    def test_match_without_category(self):
        from clip_agent.editing_rules import get_rules_for
        rule = get_rules_for("老板IP", "hook")
        assert rule is not None
        assert rule.material_role == "hook"

    def test_no_match_returns_none(self):
        from clip_agent.editing_rules import get_rules_for
        rule = get_rules_for("不存在的类型", "hook")
        assert rule is None

    def test_all_script_type_role_combos_have_fallback(self):
        """Every script_type × role combo should return a rule (even without category)"""
        from clip_agent.editing_rules import get_rules_for
        for st in ["老板IP", "团购售卖", "引流进店"]:
            for role in ["hook", "body", "outro"]:
                rule = get_rules_for(st, role)
                assert rule is not None, f"No rule for {st} × {role}"


class TestGetAllRulesForScript:
    def test_returns_list(self):
        from clip_agent.editing_rules import get_all_rules_for_script
        rules = get_all_rules_for_script("老板IP")
        assert isinstance(rules, list)
        assert len(rules) >= 4  # 老板IP has at least 4 rules

    def test_unknown_type_returns_empty(self):
        from clip_agent.editing_rules import get_all_rules_for_script
        rules = get_all_rules_for_script("不存在")
        assert rules == []


class TestApplyRuleToSegment:
    def test_applies_cut_rules(self):
        from clip_agent.editing_rules import get_rules_for, apply_rule_to_segment
        rule = get_rules_for("老板IP", "hook", "talking")
        seg = {"shot_type": "CU", "duration_sec": 3.0}
        result = apply_rule_to_segment(rule, seg)
        assert result["_rule_id"] == "ip_hook_01"
        assert "cut_triggers" in result
        assert len(result["cut_triggers"]) >= 1

    def test_applies_text_rules(self):
        from clip_agent.editing_rules import get_rules_for, apply_rule_to_segment
        rule = get_rules_for("团购售卖", "hook", "product")
        seg = {"shot_type": "CU", "duration_sec": 2.0}
        result = apply_rule_to_segment(rule, seg)
        assert "text_overlay" in result
        assert result["text_overlay"]["text"] == "price"
        assert "font_size" in result["text_overlay"]

    def test_applies_audio_rule(self):
        from clip_agent.editing_rules import get_rules_for, apply_rule_to_segment
        rule = get_rules_for("老板IP", "body", "talking")
        seg = {"shot_type": "MS", "duration_sec": 6.0}
        result = apply_rule_to_segment(rule, seg)
        assert result["audio"]["action"] == "keep"
        assert result["audio"]["bgm_vol"] == 0.25

    def test_applies_speed_rule(self):
        from clip_agent.editing_rules import get_rules_for, apply_rule_to_segment
        rule = get_rules_for("引流进店", "body", "service")
        seg = {"shot_type": "MCU", "duration_sec": 4.0}
        result = apply_rule_to_segment(rule, seg)
        assert "speed" in result
        assert result["speed"]["action"] == "ramp"

    def test_provides_shot_size_hint(self):
        from clip_agent.editing_rules import get_rules_for, apply_rule_to_segment
        rule = get_rules_for("老板IP", "hook", "talking")
        seg = {"shot_type": "MS", "duration_sec": 3.0}
        result = apply_rule_to_segment(rule, seg)
        assert "shot_size_hint" in result
        assert result["shot_size_hint"] in ("CU", "MS", "LS", "MCU", "MLS", "ECU")
