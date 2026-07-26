"""
管道追踪器 · 记录每阶段决策·调试/优化用
"""
from __future__ import annotations
import json, logging, os, time
from pathlib import Path

logger = logging.getLogger(__name__)

TRACE_DIR = Path(__file__).parent.parent.parent / "data" / "traces"


class PipelineTrace:
    """一次管道执行的完整追踪"""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.stages = []
        self.start_time = time.time()

    def stage(self, name: str, input_summary: str = "", output_summary: str = "",
              duration_ms: float = 0, success: bool = True, detail: dict = None):
        self.stages.append({
            "stage": name,
            "input": input_summary[:200],
            "output": output_summary[:200],
            "duration_ms": round(duration_ms, 1),
            "success": success,
            "detail": detail or {},
        })

    def save(self):
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        fpath = TRACE_DIR / f"trace_{self.job_id}.json"
        data = {
            "job_id": self.job_id,
            "total_duration_s": round(time.time() - self.start_time, 2),
            "stages": self.stages,
        }
        fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return str(fpath)

    def summary(self) -> str:
        lines = [f"📊 Pipeline Trace: {self.job_id}"]
        for s in self.stages:
            icon = "✅" if s["success"] else "❌"
            lines.append(f"  {icon} {s['stage']:20s} {s['duration_ms']:6.0f}ms | {s['output'][:50]}")
        return "\n".join(lines)
