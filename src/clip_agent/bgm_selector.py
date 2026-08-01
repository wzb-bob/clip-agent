"""BGM选曲——按脚本类别从曲库选文件(用户自备音频·不下载版权曲)

后端 bgm_library 有60+曲目元数据; 本模块负责: 类别→候选曲目→在bgm/目录找文件。
找不到文件→None(不加BGM不报错·优雅降级)。
"""
from __future__ import annotations
import logging, os
from pathlib import Path

logger = logging.getLogger(__name__)

# 脚本类别→曲目特征(独立模式精简表)
_CATEGORY_STYLE = {
    "团购售卖": {"energy": "high", "categories": ["产品带货", "餐饮美食"]},
    "老板IP":   {"energy": "low",  "categories": ["口播讲故事"]},
    "引流进店": {"energy": "medium", "categories": ["生活Vlog", "餐饮美食"]},
    "趣味长剧情": {"energy": "low", "categories": ["口播讲故事"]},
}

_DEFAULT_DIRS = [
    "bgm",
    "../bgm",
    "c:/Users/wangzibo/enterprise-agent-content/acquisition-backend/bgm",
]
_AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")


def _candidate_names(category: str) -> list[str]:
    """类别→候选曲名列表(后端曲库优先·独立模式用特征表只取类别)"""
    try:
        from ._imports import recommend_bgm
        if recommend_bgm:
            style = _CATEGORY_STYLE.get(category, _CATEGORY_STYLE["团购售卖"])
            tracks = recommend_bgm({"energy": style["energy"]}, script_category=category) or []
            return [t.name for t in tracks if getattr(t, "name", "")]
    except Exception:
        pass
    return []


def select_bgm(category: str, bgm_dirs: list[str] | None = None) -> str | None:
    """类别→BGM音频文件路径。找不到→None"""
    names = _candidate_names(category)
    dirs = bgm_dirs or _DEFAULT_DIRS
    # 1) 按候选曲名精确匹配文件名
    for name in names:
        for d in dirs:
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                stem, ext = os.path.splitext(f)
                if ext.lower() in _AUDIO_EXT and name in stem:
                    logger.info("BGM选中: %s ← %s", f, category)
                    return str(Path(d) / f)
    # 2) 曲库无结果→目录里任意音频兜底(用户只放了一首的场景)
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if os.path.splitext(f)[1].lower() in _AUDIO_EXT:
                logger.info("BGM兜底: %s(目录唯一音频)", f)
                return str(Path(d) / f)
    logger.debug("BGM无可用文件(类别%s)", category)
    return None
