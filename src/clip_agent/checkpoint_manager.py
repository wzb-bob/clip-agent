"""
断点续传管理器 · 每步保存→失败后从断点继续→不浪费token和时间

存储: JSON文件,每个步骤独立保存
"""
from __future__ import annotations
import json, logging, os, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"


@dataclass
class Checkpoint:
    """一个检查点"""
    session_id: str
    step: str              # classify/analyze/plan/export
    data: dict             # 该步骤的中间数据
    timestamp: float
    status: str            # done/failed


def save_checkpoint(session_id: str, step: str, data: dict) -> str:
    """保存检查点"""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    cp = Checkpoint(session_id=session_id, step=step, data=data,
                    timestamp=time.time(), status="done")
    path = CHECKPOINT_DIR / f"{session_id}_{step}.json"
    path.write_text(json.dumps({
        "session_id": cp.session_id, "step": cp.step,
        "data": cp.data, "timestamp": cp.timestamp, "status": cp.status,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(path)


def load_checkpoint(session_id: str, step: str) -> dict | None:
    """加载检查点——返回data或None"""
    path = CHECKPOINT_DIR / f"{session_id}_{step}.json"
    if not path.exists():
        return None
    try:
        cp = json.loads(path.read_text(encoding='utf-8'))
        if cp.get("status") == "done":
            logger.info("断点恢复: %s/%s", session_id, step)
            return cp.get("data", {})
    except Exception: logger.debug("断点恢复失败", exc_info=True)
    return None


def clear_session(session_id: str):
    """清除会话的所有检查点"""
    for path in CHECKPOINT_DIR.glob(f"{session_id}_*.json"):
        path.unlink(missing_ok=True)


def list_sessions() -> list[str]:
    """列出所有会话"""
    sessions = set()
    for path in CHECKPOINT_DIR.glob("*.json"):
        sid = path.stem.rsplit("_", 1)[0]
        sessions.add(sid)
    return sorted(sessions)


def run_with_checkpoint(session_id: str, step: str, fn: callable, *args, **kwargs):
    """
    带断点续传的函数调用——如果检查点存在则跳过,否则执行并保存。

    Usage:
        data = run_with_checkpoint("sess_001", "classify", lambda: classify_video(...))
    """
    # 检查是否有已保存的检查点
    cached = load_checkpoint(session_id, step)
    if cached is not None:
        return cached

    # 执行函数
    try:
        result = fn(*args, **kwargs)
        save_checkpoint(session_id, step, result if isinstance(result, dict) else {"result": str(result)})
        return result
    except Exception as e:
        save_checkpoint(session_id, step, {"error": str(e), "status": "failed"})
        raise
