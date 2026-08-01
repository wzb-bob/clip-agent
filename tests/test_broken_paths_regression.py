"""断头路修复回归测试(P2)

4处被try/except吞掉的必失败代码 + 假成功:
- sentence_editor._generate_simple_draft 用不存在的segment_id→AttributeError
- render_sentence_editor_html 用不存在的upload_status→AttributeError
- execution_engine 缺subprocess import→HEVC转码从未执行
- execution_engine SceneAnalyzer未import→场景检测永久no-op
- execute_unified 渲染失败仍status=done(基线实测零产物)
"""
import json
import os

from src.clip_agent.sentence_editor import (
    ScriptSentence, _generate_simple_draft, render_sentence_editor_html,
)


def _s(i, text="测试句"):
    return ScriptSentence(index=i, text=text, duration_sec=2.0)


def test_simple_draft_uses_index(tmp_path):
    """之前: s.segment_id不存在→AttributeError"""
    out = _generate_simple_draft([_s(1), _s(2, "第二句")], str(tmp_path))
    data = json.load(open(out, encoding="utf-8"))
    ids = [seg["id"] for seg in data["segments"]]
    assert ids == ["main_1", "main_2"]


def test_html_editor_renders():
    """之前: s.upload_status不存在→AttributeError"""
    html = render_sentence_editor_html([_s(1, "68块十只活虾"), _s(2, "左下角囤券")])
    assert "68块十只活虾" in html
    assert "左下角囤券" in html


def test_execution_engine_has_subprocess():
    """HEVC转码块用subprocess但文件头没import→NameError"""
    import src.clip_agent.execution_engine as ee
    assert hasattr(ee, "subprocess")


def test_scene_analyzer_available():
    """SceneAnalyzer在deep_skills里存在且可实例化(引擎内嵌import)"""
    from src.clip_agent.deep_skills import SceneAnalyzer
    sa = SceneAnalyzer()
    assert sa is not None


def test_unified_no_fake_done(tmp_path):
    """渲染失败/无素材→status必须是failed而非假done(基线实测教训)"""
    from src.clip_agent.execution_engine import quick_direct
    job = quick_direct("68块十只活虾", "团购售卖",
                       audio_slots={}, video_slots={},
                       output_dir=str(tmp_path))
    assert job.status == "failed"
    assert job.errors
