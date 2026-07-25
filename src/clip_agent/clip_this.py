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
    script_text: str = "",
    script_type: str = "团购售卖",
    audio_files: list[str] = None,
    video_files: list[str] = None,
    output_dir: str = "",
    bgm: str = "",
    on_progress: callable = None,
    script_output: dict = None,
) -> ClipResult:
    """
    终极一键剪辑 — 支持两种模式:

    🆕 桥接模式(Tab1→Tab4联通):
        result = clip_this(script_output={
            "script_type": "团购售卖",
            "script_text": "68块！十只活虾！",
            "shot_list": {...},         # 来自脚本Agent的分镜
            "hook_strategy": {...},     # 钩子策略
            "retention_timeline": [...], # 留存时间线
        }, audio_files=["口播.mp4"], video_files=["产品.mp4"])

    传统模式(仅脚本文字):
        result = clip_this("68块！十只活虾！", "团购售卖",
            audio=["口播.mp4"], video=["产品.mp4"])

    Args:
        script_text: 脚本文案(传统模式)
        script_type: 老板IP/团购售卖/引流进店
        script_output: 脚本Agent完整输出(桥接模式·优先)
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

    # 🆕 桥接模式: Tab1脚本输出直接驱动剪辑
    if script_output:
        from .script_clip_bridge import bridge_script_to_clip, apply_bridge_to_job
        bridge = bridge_script_to_clip(script_output, audio_files or [], video_files or [], output_dir)
        job = apply_bridge_to_job(bridge, audio_files or [], video_files or [])
        from .execution_engine import ChangyiExecutionEngine
        engine = ChangyiExecutionEngine()
        job = engine.execute(job, output_dir, stop_on_error=False)
        elapsed = time.time() - t0
        return ClipResult(
            success=job.status == "done",
            script_type=bridge.script_type,
            sentence_count=len(job.sentences),
            total_duration=sum(s.duration_sec for s in job.sentences),
            editing_cuts=len(job.edit_decisions.get("cuts", [])),
            quality_score=job.quality_report.get("score", 0),
            bgm_genre=bridge.bgm_genre,
            draft_path=job.draft_path or output_dir,
            execution_time=round(elapsed, 1),
            errors=job.errors,
            warnings=warnings,
        )

    # 传统模式: 仅脚本文字
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
