"""
长益剪辑执行引擎 · 全链路自动化

架构: 脚本→句级分镜→A/B上传槽→增强链→编辑规则→质量门禁→剪映草稿
逻辑: 三层结构(开头/介绍/结尾)·配音驱动·covers_audio·蒙太奇景别变化
"""
from __future__ import annotations
import json, logging, os, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExecutionJob:
    """一次完整的剪辑执行任务"""
    job_id: str
    script_text: str
    script_type: str                     # 老板IP/团购售卖/引流进店
    # 上传素材(A/B槽)
    audio_slots: dict[int, str]          # {sentence_index: file_path}
    video_slots: dict[int, str]          # {sentence_index: file_path}
    # 状态
    status: str = "pending"              # pending→parsing→enhancing→editing→reviewing→exporting→done
    progress_pct: float = 0.0
    # 产出
    sentences: list = field(default_factory=list)
    enhancement_report: dict = field(default_factory=dict)
    edit_decisions: dict = field(default_factory=dict)
    quality_report: dict = field(default_factory=dict)
    draft_path: str = ""
    errors: list[str] = field(default_factory=list)


class ChangyiExecutionEngine:
    """长益剪辑执行引擎——串联所有定制化组件"""

    def __init__(self):
        self.jobs: dict[str, ExecutionJob] = {}

    # ===== Stage 1: 脚本解析 → 句级分镜 =====
    def parse_script(self, job: ExecutionJob) -> ExecutionJob:
        """解析脚本→句级时间线→每句标注素材类型+景别+时长"""
        from .sentence_editor import parse_script_to_sentences
        job.status = "parsing"
        # 边界保护
        if not job.script_text or len(job.script_text.strip()) < 3:
            job.errors.append("脚本内容太短（至少3个字）")
            return job
        try:
            job.sentences = parse_script_to_sentences(job.script_text.strip(), job.script_type)
            if not job.sentences:
                job.errors.append("无法解析脚本——请检查标点符号")
                return job
            job.progress_pct = 15
            logger.info("脚本解析: %d句·%.1fs", len(job.sentences),
                       sum(s.duration_sec for s in job.sentences))
        except Exception as e:
            job.errors.append(f"解析失败: {e}")
        return job

    # ===== Stage 2: 素材匹配 → A/B槽验证 =====
    def validate_slots(self, job: ExecutionJob) -> ExecutionJob:
        """验证A/B槽——检查上传的素材是否满足每句需求"""
        job.status = "enhancing"
        for s in job.sentences:
            has_audio = s.index in job.audio_slots
            has_video = s.index in job.video_slots
            if has_audio and has_video:
                s.audio_status = "uploaded"
                s.video_status = "uploaded"
                s.audio_file = job.audio_slots[s.index]
                s.video_file = job.video_slots[s.index]
            elif has_audio:
                s.audio_status = "uploaded"
                s.audio_file = job.audio_slots[s.index]
                s.video_status = "pending"
            elif has_video:
                s.video_status = "uploaded"
                s.video_file = job.video_slots[s.index]
                s.audio_status = "pending"

        a_ok = sum(1 for s in job.sentences if s.audio_status == "uploaded")
        v_ok = sum(1 for s in job.sentences if s.video_status == "uploaded")
        job.progress_pct = 30
        logger.info("A/B槽: A=%d/%d B=%d/%d", a_ok, len(job.sentences), v_ok, len(job.sentences))
        return job

    # ===== Stage 2.5: 预检(深度技能) =====
    def run_preflight(self, job: ExecutionJob) -> ExecutionJob:
        """预检: SilenceCutter静音分析 + SceneAnalyzer场景分析"""
        job.status = "preflight"

        # 找第一个有音频的口播素材做分析
        talking_slots = [s for s in job.sentences if s.audio_status == "uploaded"]
        if talking_slots:
            video_path = talking_slots[0].audio_file
            if os.path.exists(video_path):
                try:
                    from .smart_cutter import SmartCutter
                    sc = SmartCutter()
                    cut_points = sc.analyze_for_editing(video_path)
                    job.enhancement_report["cuts"] = {
                        "total": len(cut_points),
                        "broll_inserts": sum(1 for c in cut_points if c.type=="broll_insert"),
                        "hard_cuts": sum(1 for c in cut_points if c.type=="hard_cut"),
                        "points": [{"at": c.at_sec, "type": c.type, "detail": c.detail} for c in cut_points],
                    }
                except Exception as e:
                    logger.debug("SilenceCutter跳过: %s", e)

                try:
                    sa = SceneAnalyzer()
                    scene_report = sa.analyze(video_path)
                    job.enhancement_report["scene"] = {
                        "background": scene_report.background_type,
                        "speaker_pos": scene_report.speaker_position,
                        "lighting": scene_report.lighting_quality,
                        "safe_zones": scene_report.safe_zones,
                    }
                except Exception as e:
                    logger.debug("SceneAnalyzer跳过: %s", e)

        job.progress_pct = 40
        return job

    # ===== Stage 3: 增强链应用(深度技能) =====
    def apply_enhancement(self, job: ExecutionJob) -> ExecutionJob:
        """使用EnhancementRunner实际执行增强链"""
        from .changyi_config import get_script_enhancement
        from .deep_skills import EnhancementRunner

        enhancement = get_script_enhancement(job.script_type)

        # 找口播素材
        talking_slots = [s for s in job.sentences if s.audio_status == "uploaded"]
        report = {}

        if talking_slots:
            video_path = talking_slots[0].audio_file
            if os.path.exists(video_path):
                try:
                    runner = EnhancementRunner(video_path)
                    result = runner.run_chain(
                        face_intensity=enhancement["face_enhance"]["intensity"],
                        eye_intensity=enhancement["eye_enhance"]["dark_circle_intensity"],
                        color_preset="vivid" if "vivid" in enhancement["color_grade"]["preset"] else "warm",
                        audio_lufs=enhancement["audio"]["normalize"],
                    )
                    report = {"enhancement_chain": result}
                except Exception as e:
                    report = {"enhancement_error": str(e)[:100]}
        else:
            report = {"enhancement_skipped": "无口播素材——跳过增强"}

        job.enhancement_report.update(report)
        job.progress_pct = 55
        return job

    # ===== Stage 4: 编辑规则应用(J-cut/L-cut+节奏) =====
    def apply_editing_rules(self, job: ExecutionJob) -> ExecutionJob:
        """应用编辑规则+J-cut/L-cut+节奏控制"""
        from .editing_rules import get_rules_for, apply_rule_to_segment
        from .changyi_config import get_material_tools
        from .edit_intelligence import get_jcut_offset, get_pacing_for_format, should_cut

        total_dur = sum(s.duration_sec for s in job.sentences)
        pacing = get_pacing_for_format(total_dur, "douyin")
        decisions = {"cuts": [], "text_overlays": [], "transitions": [], "audio_mix": {},
                     "jcut_lcut": [], "pacing": pacing, "smart_cuts": []}
        cur_sec = 0.0

        # 注入SmartCutter检测到的切点
        smart_cuts = job.enhancement_report.get("cuts", {}).get("points", [])
        broll_times = [c["at"] for c in smart_cuts if c.get("type") == "broll_insert"]
        hard_cut_times = [c["at"] for c in smart_cuts if c.get("type") == "hard_cut"]
        decisions["smart_cuts"] = smart_cuts

        for s in job.sentences:
            # 确定编辑角色
            if s.index == 1: role = "hook"
            elif s.index == len(job.sentences): role = "outro"
            else: role = "body"

            # 确定素材分类
            cat_map = {"talking_head": "talking", "product_closeup": "product",
                      "environment": "environment"}
            cat = cat_map.get(s.required_material, "product")

            # 匹配规则
            rule = get_rules_for(job.script_type, role, cat)
            if not rule:
                rule = get_rules_for(job.script_type, role)

            # 获取工具映射
            tools = get_material_tools(cat)

            # 构建编辑决策
            cut = {"at_sec": round(cur_sec, 1), "duration_sec": s.duration_sec,
                   "shot_type": s.required_shot, "camera_move": s.required_camera,
                   "transition_in": tools["transition_in"],
                   "transition_out": tools["transition_out"],
                   "is_broll": s.is_broll, "has_audio": s.audio_status == "uploaded",
                   "has_video": s.video_status == "uploaded"}

            if rule:
                seg = {"shot_type": s.required_shot, "duration_sec": s.duration_sec}
                enhanced = apply_rule_to_segment(rule, seg)
                cut.update({k: v for k, v in enhanced.items()
                           if k in ("text_overlay", "audio", "speed", "cut_triggers")})

            # J-cut/L-cut决策
            if s.index > 1 and role != "hook":
                prev_cut = decisions["cuts"][-1] if decisions["cuts"] else None
                if prev_cut:
                    jc_offset = get_jcut_offset("j_cut") if s.is_broll else 0
                    lc_offset = get_jcut_offset("l_cut") if prev_cut.get("is_broll") else 0
                    if jc_offset > 0:
                        decisions["jcut_lcut"].append({"type": "j_cut", "at_sec": round(cur_sec, 1), "offset": jc_offset})
                        cut["description"] = f"J-cut: 音频提前{jc_offset}s切入"
                    if lc_offset > 0:
                        decisions["jcut_lcut"].append({"type": "l_cut", "at_sec": round(cur_sec, 1), "offset": lc_offset})

            decisions["cuts"].append(cut)

            # 文字叠加
            if s.text_overlay:
                decisions["text_overlays"].append({
                    "at_sec": round(cur_sec, 1), "duration_sec": s.duration_sec,
                    "text": s.text_overlay, "position": s.text_position,
                    "animation": tools["text_animation"],
                })

            cur_sec += s.duration_sec

        # BGM配置
        from .changyi_config import get_script_enhancement
        enh = get_script_enhancement(job.script_type)
        decisions["audio_mix"] = {
            "bgm_genre": enh["bgm"]["genre"],
            "bgm_volume": enh["bgm"]["volume"],
            "ducking": True,
            "voice_keep": True,
        }

        job.edit_decisions = decisions
        job.progress_pct = 75
        return job

    # ===== Stage 5: 质量门禁 =====
    def run_quality_gates(self, job: ExecutionJob) -> ExecutionJob:
        """运行质量检查"""
        from .openmontage_pipeline import run_quality_gate

        checks = {"cuts_count": len(job.edit_decisions.get("cuts", [])),
                  "has_hook": any(c.get("at_sec", 0) == 0 for c in job.edit_decisions.get("cuts", [])),
                  "has_outro": True,
                  "total_duration": sum(s.duration_sec for s in job.sentences),
                  "shot_types": [s.required_shot for s in job.sentences]}

        gate_result = run_quality_gate("scene_planning", checks)

        issues = []
        if checks["total_duration"] > 60:
            issues.append(f"总时长{checks['total_duration']:.0f}s超过60s限制")
        if not checks["has_hook"]:
            issues.append("缺少开头钩子")
        if len(set(checks["shot_types"])) < 2:
            issues.append("景别种类不足")

        job.quality_report = {"score": gate_result["score"], "checks": checks,
                              "issues": issues, "passed": len(issues) == 0}
        job.progress_pct = 90
        return job

    # ===== Stage 6: 导出 =====
    def export(self, job: ExecutionJob, output_dir: str = "") -> ExecutionJob:
        """导出: 剪映草稿 + 专业MP4渲染(有视频素材时)"""
        from .sentence_editor import generate_jianying_from_sentences

        job.status = "exporting"
        os.makedirs(output_dir or "", exist_ok=True) if output_dir else None

        try:
            # 1. 剪映草稿(始终生成)
            draft_path = generate_jianying_from_sentences(job.sentences, output_dir or "")
            job.draft_path = draft_path

            # 2. 专业MP4渲染(有视频文件时)
            video_segments = []
            for s in job.sentences:
                vf = s.video_file if s.video_status == "uploaded" else (
                    s.audio_file if s.audio_status == "uploaded" else "")
                if vf and os.path.exists(vf):
                    video_segments.append({
                        "file": vf, "duration": s.duration_sec,
                        "broll": s.is_broll,
                        "text": s.text_overlay,
                    })

            if video_segments and output_dir:
                try:
                    from .pro_renderer import RenderJob, render_professional
                    mp4_path = os.path.join(output_dir, "成片.mp4")
                    render_job = RenderJob(segments=video_segments, output_path=mp4_path,
                                          bgm_volume=job.edit_decisions.get("audio_mix", {}).get("bgm_volume", 0.3))
                    mp4_result = render_professional(render_job)
                    if mp4_result.success:
                        job.enhancement_report["mp4_rendered"] = True
                        job.enhancement_report["mp4_path"] = mp4_path
                        job.enhancement_report["mp4_size_mb"] = mp4_result.file_size_mb
                except Exception as e:
                    logger.debug("MP4渲染跳过: %s", e)

            job.progress_pct = 100
            job.status = "done"
        except Exception as e:
            job.errors.append(f"导出失败: {e}")
            job.status = "failed"
        return job

    # ===== 一键执行全链路 =====
    def execute(self, job: ExecutionJob, output_dir: str = "",
                on_progress: callable = None, stop_on_error: bool = False) -> ExecutionJob:
        """一键执行从脚本到导出的完整管线

        on_progress(stage_name, progress_pct, message) — 进度回调
        stop_on_error: True=遇错即停, False=容错继续
        """
        t0 = time.time()
        stages = [
            ("parse_script",       self.parse_script,       "📝 解析脚本→句级分镜..."),
            ("validate_slots",     self.validate_slots,     "🔍 验证A/B上传槽..."),
            ("run_preflight",      self.run_preflight,      "🔬 预检(静音分析·场景检测)..."),
            ("apply_enhancement",  self.apply_enhancement,  "✨ 执行增强链(美颜·调色·音频)..."),
            ("apply_editing_rules",self.apply_editing_rules,"✂️ 应用编辑规则(切点·转场·文字)..."),
            ("run_quality_gates",  self.run_quality_gates,  "🛡️ 质量门禁检查..."),
            ("export",             lambda j: self.export(j, output_dir), "📤 导出剪映草稿..."),
        ]

        for i, (name, stage_fn, msg) in enumerate(stages):
            logger.info("🚀 %s [%s]", name, job.job_id)
            if on_progress:
                on_progress(name, (i+1)/len(stages)*100, msg)
            try:
                job = stage_fn(job)
                if job.errors and stop_on_error:
                    logger.warning("⏹️ 遇错即停: %s", job.errors[-1])
                    break
            except Exception as e:
                job.errors.append(f"{name}失败: {e}")
                logger.exception("%s失败", name)
                if stop_on_error:
                    break

        elapsed = time.time() - t0
        job.status = "done" if not job.errors else "failed"
        logger.info("✅ 执行完成: %s status=%s %.1fs", job.job_id, job.status, elapsed)
        return job


# 便捷函数
def quick_execute(script_text: str, script_type: str = "团购售卖",
                  audio_slots: dict = None, video_slots: dict = None,
                  output_dir: str = "", on_progress: callable = None) -> ExecutionJob:
    """快速执行——一行代码完成全链路"""
    engine = ChangyiExecutionEngine()
    job = ExecutionJob(
        job_id=f"job_{int(time.time())}",
        script_text=script_text,
        script_type=script_type,
        audio_slots=audio_slots or {},
        video_slots=video_slots or {},
    )
    return engine.execute(job, output_dir, on_progress)
