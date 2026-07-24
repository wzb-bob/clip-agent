"""
批量处理引擎 · 多条脚本→并行/串行→批量成片

用户场景: 10条口播脚本,5个产品素材→一次跑完10个成片
"""
from __future__ import annotations
import json, logging, os, time, traceback
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BatchJob:
    """单个批量任务"""
    job_id: str
    script_text: str
    script_type: str            # 老板IP/团购售卖/引流进店
    material_paths: list[str]   # 素材路径
    status: str = "pending"     # pending/running/done/failed
    result: dict = field(default_factory=dict)
    error: str = ""
    started_at: float = 0
    finished_at: float = 0

@dataclass
class BatchResult:
    """批量处理结果"""
    total: int; success: int; failed: int
    jobs: list[BatchJob]
    total_time: float
    outputs: list[str]          # 导出文件路径列表


def run_batch(
    jobs: list[BatchJob],
    parallel: bool = False,
    on_progress: callable = None,  # callback(job_id, status, progress_pct)
) -> BatchResult:
    """
    批量处理多条脚本→成片

    Args:
        jobs: 任务列表
        parallel: True=并行(多API key时可用), False=串行(默认,稳定)
        on_progress: 进度回调
    """
    t0 = time.time()

    for i, job in enumerate(jobs):
        if job.status in ("done", "failed"):
            continue

        job.status = "running"
        job.started_at = time.time()
        if on_progress:
            on_progress(job.job_id, "running", (i+1)/len(jobs))

        try:
            from app.services.clip_agent import analyze_and_generate_clip_plan
            from app.services.clip_agent.media_analyzer import MediaFile

            # 构建UploadedFile模拟
            mock_files = []
            for mp in job.material_paths:
                if os.path.exists(mp):
                    ext = Path(mp).suffix.lower()
                    mime = "video/mp4" if ext in (".mp4",".mov") else "image/jpeg"
                    mock_files.append(
                        type('F',(),{
                            'name': os.path.basename(mp), 'type': mime,
                            'size': os.path.getsize(mp),
                            'read': lambda path=mp: open(path,'rb').read(),
                        })()
                    )

            if not mock_files:
                job.status = "failed"
                job.error = "没有可用素材"
                continue

            result = analyze_and_generate_clip_plan(
                files=mock_files, user_intent=job.script_text[:500],
                plan_count=1,
            )

            if result.success and result.plans:
                # 导出
                from app.services.clip_agent.jianying_export import export_storyboard_text, export_to_jianying_draft
                plan = result.plans[0]
                sb = export_storyboard_text(plan)
                jy = export_to_jianying_draft(plan, job.material_paths)

                job.result = {
                    "plan_name": plan.plan_name,
                    "segments": len(plan.segments),
                    "duration": plan.total_duration,
                    "bgm": plan.bgm_suggestion,
                    "storyboard_path": f"batch_{job.job_id}_storyboard.txt",
                    "draft_path": f"batch_{job.job_id}_draft.json",
                    "storyboard": sb.content if sb.success else "",
                    "draft": jy.content if jy.success else "",
                }
                job.status = "done"
            else:
                job.status = "failed"
                job.error = result.error or "方案生成失败"

        except Exception as e:
            job.status = "failed"
            job.error = f"{type(e).__name__}: {str(e)[:200]}"
            logger.warning("批量任务%d失败: %s", i, e)

        job.finished_at = time.time()
        if on_progress:
            on_progress(job.job_id, job.status, (i+1)/len(jobs))

    success = sum(1 for j in jobs if j.status == "done")
    failed = sum(1 for j in jobs if j.status == "failed")

    return BatchResult(
        total=len(jobs), success=success, failed=failed,
        jobs=jobs, total_time=round(time.time()-t0, 1),
        outputs=[j.result.get("draft_path","") for j in jobs if j.status=="done"],
    )


def create_batch_from_scripts(scripts: list[dict], material_paths: list[str]) -> list[BatchJob]:
    """从脚本列表创建批量任务"""
    jobs = []
    for i, s in enumerate(scripts):
        jobs.append(BatchJob(
            job_id=f"batch_{i+1:03d}",
            script_text=s.get("text",""),
            script_type=s.get("type","团购售卖"),
            material_paths=material_paths,
        ))
    return jobs
