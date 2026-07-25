"""semantic_engine.py 测试 — 语义理解引擎"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSemanticSegment:
    def test_creation(self):
        from clip_agent.semantic_engine import SemanticSegment
        seg = SemanticSegment(
            index=1, text="68块！十只活虾！", role="hook",
            emotion="urgent", intensity=9, visual_need="产品特写CU",
            shot_type="CU", broll_needed=False, text_overlay="68块!",
            text_position="center", duration_sec=2.5,
        )
        assert seg.role == "hook"
        assert seg.intensity == 9
        assert seg.shot_type == "CU"


class TestAnalyzeScriptKeywords:
    """关键词降级规则 — 不依赖LLM, 始终可用"""

    def test_price_detection(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("68块！十只活虾！干煸盱眙技术。左下角团购已上线！", "团购售卖")
        assert len(result.segments) >= 2
        # First segment with price should be hook
        assert result.segments[0].role == "hook"
        assert result.segments[0].intensity >= 7

    def test_process_keywords(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("我们用的是干煸盱眙技术。花雕酒泡了八个小时。", "团购售卖")
        assert any(s.role == "process" for s in result.segments)

    def test_cta_detection(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("赶紧来。左下角团购已上线！", "团购售卖")
        assert any(s.role == "cta" for s in result.segments)

    def test_trust_keywords(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("我们家做了十二年了。回头客特别多。", "老板IP")
        assert any(s.role == "value_proof" for s in result.segments)

    def test_short_text(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("ab", "团购售卖")  # Too short
        assert result.segments == []  # Min length filter

    def test_broll_detection(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("我们店在玉田建设路。导航搜虾神龙虾。", "引流进店")
        # Environment sentence should need b-roll
        env_segs = [s for s in result.segments if s.broll_needed]
        assert len(env_segs) >= 1

    def test_emotional_arc_present(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("68块！十只活虾！干煸盱眙技术。左下角团购已上线！", "团购售卖")
        assert result.emotional_arc  # Even keyword fallback has this

    def test_key_moments(self):
        from clip_agent.semantic_engine import analyze_script_keywords
        result = analyze_script_keywords("68块！十只活虾！干煸盱眙技术。左下角团购已上线！", "团购售卖")
        assert len(result.key_moments) >= 1  # Price reveal should be a key moment


class TestApplySemanticToJob:
    def test_creates_valid_job(self):
        from clip_agent.semantic_engine import analyze_script_keywords, apply_semantic_to_job
        analysis = analyze_script_keywords("68块！十只活虾！", "团购售卖")
        job = apply_semantic_to_job(analysis)
        assert job.script_type == "团购售卖"
        assert len(job.sentences) >= 1
        assert "semantic_analysis" in job.enhancement_report


class TestAnalyzeScript:
    def test_fallback_to_keywords(self):
        """When AI unavailable, should fallback to keywords"""
        from clip_agent.semantic_engine import analyze_script
        # use_ai=True but no API configured → should fallback
        result = analyze_script("68块！十只活虾！", "团购售卖", use_ai=False)
        assert result.segments
        assert result.segments[0].role in ("hook", "product_reveal")

    def test_unified_entry(self):
        from clip_agent.semantic_engine import analyze_script
        result = analyze_script("大家好。我是做小龙虾的老王。今天给大家看看我们的招牌。", "老板IP", use_ai=False)
        assert len(result.segments) >= 2


class TestExtractPrice:
    def test_block_pattern(self):
        from clip_agent.semantic_engine import _extract_price
        assert _extract_price("68块！十只活虾") == "68块!"
        assert _extract_price("只要99元") == "99元"
        assert _extract_price("没有价格") == ""
