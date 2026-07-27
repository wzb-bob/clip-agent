"""aesthetic_constraints.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestCheckAesthetics:
    def test_empty_segments(self):
        from clip_agent.aesthetic_constraints import check_aesthetics
        issues = check_aesthetics([], "团购售卖")
        assert issues == []

    def test_repeat_shot_detection(self):
        from clip_agent.aesthetic_constraints import AestheticIssue
        # 3 consecutive CU shots should trigger R1
        segs = [
            type('S',(),{'shot_type':'CU','start_sec':0,'duration_sec':2,'is_broll':False})(),
            type('S',(),{'shot_type':'CU','start_sec':2,'duration_sec':2,'is_broll':False})(),
            type('S',(),{'shot_type':'CU','start_sec':4,'duration_sec':2,'is_broll':False})(),
        ]
        from clip_agent.aesthetic_constraints import check_aesthetics
        issues = check_aesthetics(segs)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        assert "R1" in errors[0].rule

    def test_long_segment_warning(self):
        segs = [
            type('S',(),{'shot_type':'MS','start_sec':0,'duration_sec':10,'is_broll':False})(),
        ]
        from clip_agent.aesthetic_constraints import check_aesthetics
        issues = check_aesthetics(segs)
        warnings = [i for i in issues if i.severity == "warning" and "R3" in i.rule]
        assert len(warnings) >= 1

    def test_short_segment_warning(self):
        segs = [
            type('S',(),{'shot_type':'CU','start_sec':0,'duration_sec':0.3,'is_broll':False})(),
        ]
        from clip_agent.aesthetic_constraints import check_aesthetics
        issues = check_aesthetics(segs)
        warnings = [i for i in issues if i.severity == "warning" and "R4" in i.rule]
        assert len(warnings) >= 1

class TestValidatePlan:
    def test_perfect_plan(self):
        segs = [
            type('S',(),{'shot_type':'CU','start_sec':0,'duration_sec':2.5,'is_broll':False})(),
            type('S',(),{'shot_type':'MS','start_sec':2.5,'duration_sec':3,'is_broll':True})(),
            type('S',(),{'shot_type':'CU','start_sec':5.5,'duration_sec':2.5,'is_broll':False})(),
        ]
        from clip_agent.aesthetic_constraints import validate_plan
        result = validate_plan(segs)
        assert result["score"] >= 90
