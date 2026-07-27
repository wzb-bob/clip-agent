"""rhythm_engine.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestAnalyzeRhythm:
    def test_empty_input(self):
        from clip_agent.rhythm_engine import analyze_rhythm
        profile = analyze_rhythm([])
        assert profile.overall_pace == "medium"
        assert profile.recommended_shot_dur == 3.0

    def test_fast_pace(self):
        from clip_agent.rhythm_engine import analyze_rhythm
        segs = [{"speed_cps": 6.0}, {"speed_cps": 5.5}, {"speed_cps": 6.2}]
        profile = analyze_rhythm(segs)
        assert profile.overall_pace == "fast"

    def test_slow_pace(self):
        from clip_agent.rhythm_engine import analyze_rhythm
        segs = [{"speed_cps": 2.0}, {"speed_cps": 2.5}]
        profile = analyze_rhythm(segs)
        assert profile.overall_pace == "slow"

    def test_medium_pace(self):
        from clip_agent.rhythm_engine import analyze_rhythm
        segs = [{"speed_cps": 4.0}, {"speed_cps": 3.5}]
        profile = analyze_rhythm(segs)
        assert profile.overall_pace == "medium"

class TestRhythmProfile:
    def test_defaults(self):
        from clip_agent.rhythm_engine import RhythmProfile
        rp = RhythmProfile()
        assert rp.avg_speed_cps == 4.0
        assert rp.overall_pace == "medium"
