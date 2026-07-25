"""director_ai.py 测试 — 导演决策层"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFuseSignals:
    def test_empty_inputs(self):
        from clip_agent.director_ai import fuse_signals
        plan = fuse_signals("团购售卖", [], [], [], [], [])
        assert plan.script_type == "团购售卖"
        assert plan.segments == []

    def test_semantic_only(self):
        from clip_agent.director_ai import fuse_signals
        sem = [
            {"text": "68块！", "role": "hook", "emotion": "urgent", "intensity": 9,
             "shot_type": "CU", "broll_needed": False, "text_overlay": "68块!",
             "visual_need": "产品特写", "duration_sec": 2.5, "start_sec": 0.0,
             "text_position": "center"},
        ]
        plan = fuse_signals("团购售卖", sem, [], [], [], [])
        assert len(plan.segments) == 1
        assert plan.segments[0].shot_type == "CU"
        assert plan.segments[0].text_overlay == "68块!"

    def test_audio_overrides_semantic_timing(self):
        from clip_agent.director_ai import fuse_signals
        sem = [
            {"text": "68块！", "role": "hook", "emotion": "urgent", "intensity": 9,
             "shot_type": "CU", "duration_sec": 3.0, "start_sec": 0.0,
             "visual_need": "", "broll_needed": False, "text_overlay": "", "text_position": "bottom"},
        ]
        audio = [
            {"start": 0.0, "end": 2.8, "text": "68块！十只活虾！",
             "emotion": "excited", "intensity": 9, "shot": "CU", "golden": True},
        ]
        plan = fuse_signals("团购售卖", sem, audio, [], [], [])
        assert len(plan.segments) == 1
        # Audio timing should be more precise
        assert abs(plan.segments[0].duration_sec - 2.8) < 0.2
        assert plan.segments[0].is_golden_moment is True

    def test_gap_triggers_broll(self):
        from clip_agent.director_ai import fuse_signals
        sem = [
            {"text": "工艺展示", "role": "process", "emotion": "calm", "intensity": 5,
             "shot_type": "MCU", "duration_sec": 3.0, "start_sec": 3.0,
             "visual_need": "厨房干煸", "broll_needed": False, "text_overlay": "", "text_position": "bottom"},
        ]
        gaps = [{"at_sec": 3.0, "gap_ms": 520, "between": "虾→我们"}]
        plan = fuse_signals("团购售卖", sem, [], gaps, [], [])
        # Gap >400ms at segment start → should trigger broll
        assert plan.segments[0].is_broll is True

    def test_video_scene_used_for_visual(self):
        from clip_agent.director_ai import fuse_signals
        sem = [
            {"text": "工艺", "role": "process", "emotion": "calm", "intensity": 5,
             "shot_type": "MCU", "duration_sec": 3.0, "start_sec": 3.0,
             "visual_need": "", "broll_needed": True, "text_overlay": "", "text_position": "bottom"},
        ]
        video = [{"at_sec": 3.0, "description": "蓝色调·清晰·动态"}]
        plan = fuse_signals("团购售卖", sem, [], [], video, [])
        assert "蓝色调" in plan.segments[0].broll_visual
        assert plan.segments[0].visual_source == "video"


class TestDirectorDecision:
    def test_dataclass(self):
        from clip_agent.director_ai import DirectorDecision
        d = DirectorDecision(start_sec=0.0, duration_sec=2.5, shot_type="CU",
                           is_golden_moment=True, confidence=0.9)
        assert d.shot_type == "CU"
        assert d.is_golden_moment is True


class TestDirectorPlan:
    def test_dataclass(self):
        from clip_agent.director_ai import DirectorPlan
        p = DirectorPlan(script_type="老板IP", total_duration=30.0)
        assert p.script_type == "老板IP"
        assert p.segments == []


class TestDirectToExecutionJob:
    def test_converts_to_job(self):
        from clip_agent.director_ai import DirectorPlan, DirectorDecision, direct_to_execution_job

        plan = DirectorPlan(script_type="团购售卖", total_duration=10.0)
        plan.segments = [
            DirectorDecision(start_sec=0.0, duration_sec=2.5, shot_type="CU",
                           script_text="68块！", is_golden_moment=True,
                           text_overlay="68块!", text_animation="scale_up"),
            DirectorDecision(start_sec=2.5, duration_sec=5.0, shot_type="MCU",
                           script_text="干煸技术", is_broll=True,
                           broll_visual="厨房干煸"),
        ]

        job = direct_to_execution_job(plan)
        assert job.script_type == "团购售卖"
        assert len(job.sentences) == 2
        assert job.sentences[0].is_broll is False
        assert job.sentences[1].is_broll is True
        assert "director_plan" in job.enhancement_report
