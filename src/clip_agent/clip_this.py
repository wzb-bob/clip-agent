"""
终极一键剪辑 · clip_this() — 脚本+素材→全自动→成片

一行代码完成从脚本到成片的全部流程:
  from . import clip_this
  result = clip_this("68块！十只活虾！", "团购售卖",
      audio=["口播1.mp4","口播2.mp4"],
      video=["产品1.mp4","空镜.mp4"])
"""
from __future__ import annotations
import logging, os, time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClipResult:
    """一键剪辑结果"""
    success: bool
    script_type: str
    sentence_count: int
    total_duration: float
    editing_cuts: int
    quality_score: float
    bgm_genre: str
    draft_path: str
    execution_time: float
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def clip_this(
    script_text: str,
    script_type: str = "团购售卖",
    audio_files: list[str] = None,
    video_files: list[str] = None,
    output_dir: str = "",
    bgm: str = "",
    on_progress: callable = None,
) -> ClipResult:
    """
    终极一键剪辑

    Args:
        script_text: 脚本文案
        script_type: 老板IP/团购售卖/引流进店
        audio_files: 音频/口播文件列表(按句子顺序)
        video_files: 视频/画面文件列表(按句子顺序)
        output_dir: 输出目录
        bgm: BGM文件路径
        on_progress: 进度回调(stage, pct, msg)

    Returns:
        ClipResult: 完整剪辑结果

    Example:
        result = clip_this(
            "68块！十只活虾！干煸盱眙技术。左下角团购已上线！",
            "团购售卖",
            audio=["口播1.mp4", "口播2.mp4", "口播3.mp4"],
            video=["产品特写.mp4", "工艺展示.mp4", "空镜.mp4"],
        )
        print(f"✅ {result.sentence_count}句·{result.total_duration:.0f}s·{result.quality_score}分")
    """
    t0 = time.time()
    warnings = []

    # 构建A/B槽
    audio_slots = {}
    video_slots = {}
    if audio_files:
        for i, f in enumerate(audio_files):
            if os.path.exists(f):
                audio_slots[i + 1] = f
            else:
                warnings.append(f"音频文件不存在: {f}")
    if video_files:
        for i, f in enumerate(video_files):
            if os.path.exists(f):
                video_slots[i + 1] = f
            else:
                warnings.append(f"视频文件不存在: {f}")

    if not output_dir:
        output_dir = os.path.join(os.path.dirname(__file__) if "__file__" in dir() else os.getcwd(),
                                  f"clip_output_{int(time.time())}")

    # 执行全链路
    from .execution_engine import quick_execute

    job = quick_execute(
        script_text=script_text,
        script_type=script_type,
        audio_slots=audio_slots,
        video_slots=video_slots,
        output_dir=output_dir,
        on_progress=on_progress,
    )

    elapsed = time.time() - t0

    if job.status == "done":
        logger.info("✅ clip_this完成: %s·%.1fs·%d句·%.0f分",
                   script_type, elapsed, len(job.sentences), job.quality_report.get("score", 0))

    return ClipResult(
        success=job.status == "done",
        script_type=script_type,
        sentence_count=len(job.sentences),
        total_duration=sum(s.duration_sec for s in job.sentences),
        editing_cuts=len(job.edit_decisions.get("cuts", [])),
        quality_score=job.quality_report.get("score", 0),
        bgm_genre=job.edit_decisions.get("audio_mix", {}).get("bgm_genre", ""),
        draft_path=job.draft_path or output_dir,
        execution_time=round(elapsed, 1),
        errors=job.errors,
        warnings=warnings,
    )
