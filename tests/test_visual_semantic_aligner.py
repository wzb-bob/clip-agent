"""visual_semantic_aligner.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestFallbackAlign:
    def test_basic_alignment(self):
        from clip_agent.visual_semantic_aligner import _fallback_align
        segs = [{"text":"68块！","role":"hook","duration_sec":2.5}]
        vids = [{"at_sec":0,"description":"test","duration":10}]
        result = _fallback_align(segs, vids)
        assert len(result.segments) == 1
        assert result.segments[0].script_index == 1
        assert result.overall_confidence == 0.4  # fallback confidence

    def test_multiple_segments(self):
        from clip_agent.visual_semantic_aligner import _fallback_align
        segs = [
            {"text":"68块！","role":"hook","duration_sec":2.5},
            {"text":"干煸技术","role":"process","duration_sec":3.0},
        ]
        vids = [{"at_sec":0,"description":"test","duration":10}]
        result = _fallback_align(segs, vids)
        assert len(result.segments) == 2

class TestAlignedSegment:
    def test_fields(self):
        from clip_agent.visual_semantic_aligner import AlignedSegment
        s = AlignedSegment(1, "test", "hook", 0, 2.5, "desc", 0.8, "匹配")
        assert s.script_index == 1
        assert s.confidence == 0.8

class TestAlignmentResult:
    def test_fields(self):
        from clip_agent.visual_semantic_aligner import AlignmentResult
        r = AlignmentResult([], 0.5, [], [])
        assert r.overall_confidence == 0.5
