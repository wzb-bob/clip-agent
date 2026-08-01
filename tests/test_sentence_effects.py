"""句级语义→效果映射 + 类别转场 单测"""
from src.clip_agent.chatcut_vfx import _classify_sentence, _xfade_for_category, _SENTIMENT_SHADER


def test_classify_suspense():
    assert _classify_sentence("店里来了个奇怪的客人") == "suspense"
    assert _classify_sentence("他沉默了半天") == "suspense"


def test_classify_conflict():
    assert _classify_sentence("点了一桌子菜,却一口都没吃") == "conflict"
    assert _classify_sentence("但是没人相信") == "conflict"


def test_classify_reveal():
    assert _classify_sentence("那一刻我才明白") == "reveal"
    assert _classify_sentence("原来他是我爸的老朋友") == "reveal"


def test_classify_warm():
    assert _classify_sentence("我守的是一代人的味道") == "warm"


def test_classify_none():
    """无关键词→None(保持角色默认效果)"""
    assert _classify_sentence("左下角囤券") is None
    assert _classify_sentence("") is None


def test_mood_shaders_exist():
    """每个情绪类别都有映射的着色器"""
    for mood in ("suspense", "conflict", "reveal", "warm"):
        assert _SENTIMENT_SHADER[mood]


def test_xfade_per_category():
    assert _xfade_for_category("趣味长剧情") == "dissolve"
    assert _xfade_for_category("团购售卖") == "fade"      # 已验证不动
    assert _xfade_for_category("老板IP") == "fade"        # 已验证不动
    assert _xfade_for_category("引流进店") == "slideleft"  # 已验证不动
    assert _xfade_for_category("未知类别") == "fade"
