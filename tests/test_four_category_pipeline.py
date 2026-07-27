"""four_category_pipeline.py 测试"""
import sys, tempfile, os
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestCategoryMaterials:
    def test_empty(self):
        from clip_agent.four_category_pipeline import CategoryMaterials
        m = CategoryMaterials()
        assert m.talking == []
        assert m.environment == []

    def test_with_files(self):
        from clip_agent.four_category_pipeline import CategoryMaterials
        m = CategoryMaterials(talking=["a.mp4"], product=["b.mp4"])
        assert len(m.talking) == 1
        assert len(m.product) == 1

class TestSegmentScript:
    def test_basic(self):
        from clip_agent.four_category_pipeline import _segment_script
        segs = _segment_script("68块！十只活虾！干煸技术。团购上线！")
        assert len(segs) >= 2

    def test_short_text(self):
        from clip_agent.four_category_pipeline import _segment_script
        segs = _segment_script("ab")
        assert len(segs) <= 1

class TestBuildTimeline:
    def test_alternates_broll(self):
        from clip_agent.four_category_pipeline import CategoryMaterials, _build_timeline
        segs = [
            {"text":"开头","role":"hook","duration_sec":3,"broll_needed":False},
            {"text":"中段1","role":"body","duration_sec":3,"broll_needed":True},
            {"text":"中段2","role":"body","duration_sec":3,"broll_needed":True},
            {"text":"结尾","role":"cta","duration_sec":3,"broll_needed":False},
        ]
        mats = CategoryMaterials(talking=["talk.mp4"], environment=["env.mp4"], product=["prod.mp4"])
        timeline = _build_timeline(segs, mats, [], "talk.mp4")
        assert len(timeline) == 4
        assert timeline[0].is_broll == False  # first = talking
        assert timeline[1].is_broll == True   # odd = B-roll
        assert timeline[3].is_broll == False  # last = talking

class TestRunPipeline:
    def test_minimal(self):
        from clip_agent.four_category_pipeline import run_four_category_pipeline, CategoryMaterials
        timeline = run_four_category_pipeline("68块！十只活虾！团购上线！", CategoryMaterials())
        assert len(timeline.segments) >= 2
        assert timeline.total_duration > 0

class TestTimelineSegment:
    def test_fields(self):
        from clip_agent.four_category_pipeline import TimelineSegment
        s = TimelineSegment(1, "test", 0, 2.5, "file.mp4", "talking", False, "cut")
        assert s.index == 1
        assert s.is_broll == False
        assert s.transition == "cut"
