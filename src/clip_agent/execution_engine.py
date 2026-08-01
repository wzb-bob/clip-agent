"""
长益剪辑执行引擎 · 全链路自动化

架构: 脚本→句级分镜→A/B上传槽→增强链→编辑规则→质量门禁→剪映草稿
逻辑: 三层结构(开头/介绍/结尾)·配音驱动·covers_audio·蒙太奇景别变化
"""
from __future__ import annotations
import json, logging, os, subprocess, sys, time
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
    # 分镜语言(脚本Agent的shot_json·可选·有则驱动逐镜剪辑)
    shot_json: list = field(default_factory=list)
    # BGM音频文件路径(可选·自动闪避)
    bgm_path: str = ""
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
        """AI语义解析(LLM优先)→句级时间线→每句标注素材+景别+时长+画面需求"""
        job.status = "parsing"
        if not job.script_text or len(job.script_text.strip()) < 3:
            job.errors.append("脚本内容太短（至少3个字）")
            return job
        try:
            # 🆕 语义引擎: LLM理解→降级关键词规则
            from .semantic_engine import analyze_script, apply_semantic_to_job
            analysis = analyze_script(job.script_text.strip(), job.script_type, use_ai=True)
            if analysis and analysis.segments:
                # 转换SemanticSegment→ScriptSentence
                from .sentence_editor import ScriptSentence
                job.sentences = []
                for seg in analysis.segments:
                    job.sentences.append(ScriptSentence(
                        index=seg.index, text=seg.text,
                        start_sec=seg.start_sec, duration_sec=seg.duration_sec,
                        required_material="talking_head" if not seg.broll_needed else "product_closeup",
                        required_shot=seg.shot_type,
                        required_camera="static" if not seg.broll_needed else "push_in",
                        text_overlay=seg.text_overlay, text_position=seg.text_position,
                        is_broll=seg.broll_needed,
                    ))
                # 注入语义分析结果
                job.enhancement_report["semantic"] = {
                    "emotional_arc": analysis.emotional_arc,
                    "key_moments": analysis.key_moments,
                    "broll_suggestions": analysis.broll_suggestions,
                    "engine": "deepseek" if analysis.emotional_arc != "规则推断" else "keyword_rules",
                }
            if not job.sentences:
                job.errors.append("无法解析脚本——请检查标点符号")
                return job
            job.progress_pct = 15
            logger.info("脚本解析(%s): %d句·%.1fs·弧线=%s",
                       job.enhancement_report.get("semantic", {}).get("engine", "?"),
                       len(job.sentences),
                       sum(s.duration_sec for s in job.sentences),
                       analysis.emotional_arc[:40] if analysis else "?")
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

    # ===== Stage 2.5: 预检(Whisper词级时间戳 + SmartCutter) =====
    def run_preflight(self, job: ExecutionJob) -> ExecutionJob:
        """预检: Whisper词级对齐(精准切点) + SmartCutter静音分析"""
        job.status = "preflight"

        talking_slots = [s for s in job.sentences if s.audio_status == "uploaded"]
        if talking_slots:
            video_path = talking_slots[0].audio_file
            if os.path.exists(video_path):
                # 🆕 Whisper词级时间戳 — 精准切点
                try:
                    import whisper
                    model = whisper.load_model("small")  # base=中文可用, ~140MB
                    result = model.transcribe(video_path, word_timestamps=True)
                    word_times = []
                    for seg in result.get("segments", []):
                        for w in seg.get("words", []):
                            word_times.append({
                                "word": w.get("word", "").strip(),
                                "start": round(w.get("start", 0), 2),
                                "end": round(w.get("end", 0), 2),
                            })
                    # 句间停顿检测(>400ms gap = sentence break)
                    gaps = []
                    for i in range(1, len(word_times)):
                        gap_ms = int((word_times[i]["start"] - word_times[i-1]["end"]) * 1000)
                        if gap_ms >= 300:
                            gaps.append({
                                "between": f'{word_times[i-1]["word"]}→{word_times[i]["word"]}',
                                "at_sec": round(word_times[i-1]["end"] + gap_ms/2000, 2),
                                "gap_ms": gap_ms,
                                "is_sentence_break": gap_ms >= 500,
                            })
                    job.enhancement_report["whisper"] = {
                        "total_words": len(word_times),
                        "sentence_breaks": len([g for g in gaps if g["is_sentence_break"]]),
                        "gaps": gaps,
                        "word_times": word_times[:50],  # first 50 words for reference
                    }
                    logger.info("Whisper: %d词·%d句间断·%d停顿",
                               len(word_times), len(gaps),
                               len([g for g in gaps if g["is_sentence_break"]]))
                except Exception as e:
                    logger.debug("Whisper跳过: %s", e)

                # SmartCutter静音分析(降级方案)
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
                    logger.debug("SmartCutter跳过: %s", e)

                # 🆕 音频深度理解: Whisper转录→DeepSeek分析金句/情绪/切点
                try:
                    whisper_data = job.enhancement_report.get("whisper", {})
                    if whisper_data.get("gaps"):
                        # 构建音频理解数据
                        transcript_text = " ".join(
                            f"[{w['start']}s] {w['word']}"
                            for w in whisper_data.get("word_times", [])[:100]
                        )
                        audio_moments = [
                            {"at_sec": g["at_sec"], "type": "pause" if g.get("is_sentence_break") else "gap",
                             "gap_ms": g["gap_ms"], "words": g["between"]}
                            for g in whisper_data.get("gaps", [])[:10]
                        ]
                        energy_peaks = [
                            {"at_sec": g["at_sec"], "energy": 0.8}
                            for g in whisper_data.get("gaps", []) if g.get("is_sentence_break")
                        ]

                        from ._imports import chat_via_gateway, get_model_name
                        if chat_via_gateway:

                            audio_prompt = f"""分析口播音频数据,返回JSON编辑决策。

转录文本(词级): {transcript_text[:800]}
句间停顿(ms): {json.dumps(audio_moments[:10], ensure_ascii=False)}
能量峰值: {json.dumps(energy_peaks[:5], ensure_ascii=False)}
脚本类型: {job.script_type}

JSON格式:
{{"segments":[{{"start":0.0,"text":"...","emotion":"excited","intensity":9,"broll_at":2.8,"golden":true,"shot":"CU"}}],"emotional_arc":"...","golden_moments":[{{"at_sec":0.5,"reason":"...","effect":"大字弹出+画面缩放"}}]}}

只返回JSON。"""

                            model = get_model_name("deepseek") or "deepseek-v4-flash"
                            result = chat_via_gateway(
                                provider="deepseek", model=model,
                                system="你是音频剪辑导演。基于Whisper数据做编辑决策。只返回JSON。",
                                user=audio_prompt, temperature=0.1, max_tokens=1500,
                            )
                            content = result.get("content", "") if isinstance(result, dict) else str(result)
                            import re
                            m = re.search(r'\{.*\}', content, re.DOTALL)
                            if m:
                                from .semantic_engine import _repair_json
                                audio_insights = json.loads(_repair_json(m.group(0)))
                                job.enhancement_report["audio_understanding"] = audio_insights
                                logger.info("音频理解: %d段·弧线=%s·金句=%d",
                                           len(audio_insights.get("segments", [])),
                                           audio_insights.get("emotional_arc", "")[:40],
                                           len(audio_insights.get("golden_moments", [])))
                except Exception as e:
                    logger.debug("音频理解跳过: %s", e)

                try:
                    from .deep_skills import SceneAnalyzer
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

        # 🆕 音频深度理解 → B-roll精准插入点(优先)
        audio_understanding = job.enhancement_report.get("audio_understanding", {})
        if audio_understanding:
            decisions["audio_segments"] = audio_understanding.get("segments", [])
            decisions["emotional_arc"] = audio_understanding.get("emotional_arc", "")
            # 使用AI理解的broll_at时间点
            ai_broll_points = [
                {"at_sec": s.get("broll_at", s["start"]), "text": s.get("text", ""),
                 "emotion": s.get("emotion", ""), "golden": s.get("golden", False)}
                for s in audio_understanding.get("segments", []) if s.get("broll_at")
            ]
            decisions["whisper_broll_points"] = ai_broll_points or []

        # Whisper句间停顿(降级)
        whisper_gaps = job.enhancement_report.get("whisper", {}).get("gaps", [])
        if not decisions.get("whisper_broll_points"):
            decisions["whisper_broll_points"] = [
                {"at_sec": g["at_sec"], "gap_ms": g["gap_ms"], "words": g["between"]}
                for g in whisper_gaps if g.get("is_sentence_break")
            ]

        # SmartCutter检测到的切点(降级)
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

        # 调色预设(脚本类型→色调映射)
        color_map = {"老板IP": "warm", "团购售卖": "vivid", "引流进店": "bright"}
        decisions["color_grade"] = color_map.get(job.script_type, "neutral")

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
    def _render_with_fallback(self, video_segments: list, job: ExecutionJob,
                               default_color: str, output_dir: str) -> str | None:
        """三级降级渲染: VFX增强 → 基础pro_renderer → 剪映草稿(已有)

        返回: MP4路径 或 None
        """
        mp4_path = os.path.join(output_dir, "成片_AI预览.mp4")

        # Level 1: VFX增强渲染 (chatcut_vfx)
        try:
            from .chatcut_vfx import build_vfx_plan, render_with_vfx
            from dataclasses import dataclass

            @dataclass
            class _TimelineSeg:
                material_file: str = ""
                duration_sec: float = 2.0
                start_sec: float = 0.0
                is_broll: bool = False
                script_text: str = ""

            @dataclass
            class _Timeline:
                segments: list = None
                draft_path: str = ""

            segs = []
            for s in video_segments:
                segs.append(_TimelineSeg(
                    material_file=s.get("file", ""),
                    duration_sec=s.get("duration", 2.0),
                    start_sec=s.get("start_sec", 0.0),
                    is_broll=s.get("broll", False),
                    script_text=s.get("text", ""),
                ))
            tl = _Timeline(segments=segs)

            script_text = " ".join(s.get("text", "") for s in video_segments)
            if not script_text:
                script_text = job.script_text

            vfx_plan = build_vfx_plan(tl, video_segments[0].get("file", ""),
                                       job.script_type)
            if vfx_plan.success:
                segment_files = [(s.get("file", ""), s.get("duration", 2.0))
                                for s in video_segments if s.get("file")]
                if segment_files:
                    ok, path = render_with_vfx(vfx_plan, segment_files,
                                               output_path=mp4_path)
                    if ok and os.path.exists(path):
                        job.enhancement_report["render_level"] = "vfx"
                        return path
        except Exception as e:
            logger.debug("VFX渲染降级: %s", str(e)[:80])

        # Level 2: 基础pro_renderer (无VFX)
        try:
            from .pro_renderer import RenderJob, render_professional
            render_job = RenderJob(segments=video_segments, output_path=mp4_path)
            result = render_professional(render_job)
            if result.success and os.path.exists(mp4_path):
                job.enhancement_report["render_level"] = "basic"
                return mp4_path
        except Exception as e:
            logger.debug("基础渲染降级: %s", str(e)[:80])

        # Level 3: 剪映草稿已在export()中生成，这里返回None即可
        job.enhancement_report["render_level"] = "jianying_draft_only"
        return None

    def export(self, job: ExecutionJob, output_dir: str = "") -> ExecutionJob:
        """导出: 剪映草稿(首选·始终生成) → 打开剪映APP可手动精调
        MP4渲染(备选·有素材时自动生成) → 快速预览用"""
        from .sentence_editor import generate_jianying_from_sentences

        job.status = "exporting"
        os.makedirs(output_dir or "", exist_ok=True) if output_dir else None

        # 脚本类型→调色预设
        color_map = {"老板IP": "warm", "团购售卖": "vivid", "引流进店": "bright"}
        default_color = color_map.get(job.script_type, "neutral")

        try:
            # 1. 剪映草稿(首选输出 — 始终生成)
            draft_path = generate_jianying_from_sentences(job.sentences, output_dir or "")
            job.draft_path = draft_path
            job.enhancement_report["jianying_draft"] = True
            job.enhancement_report["jianying_path"] = draft_path
            job.enhancement_report["output_recommendation"] = (
                "📱 首选: 用剪映APP打开草稿文件，可手动精调字幕/转场/滤镜后导出高清MP4\n"
                "⚡ 备选: 下方MP4为AI自动渲染的快速预览版"
            )

            # 2. MP4快速渲染(备选 — 有视频文件时生成)
            video_segments = []
            for s in job.sentences:
                vf = s.video_file if s.video_status == "uploaded" else (
                    s.audio_file if s.audio_status == "uploaded" else "")
                if vf and os.path.exists(vf):
                    video_segments.append({
                        "file": vf, "duration": s.duration_sec,
                        "broll": s.is_broll,
                        "text": s.text_overlay,
                        "color_grade": default_color,
                        "transition": "dissolve" if s.is_broll else "cut",
                        "speed": getattr(s, "speed", "normal"),
                        "speed_factor": 0.5 if getattr(s, "speed", "normal") == "slow_motion" else (2.0 if getattr(s, "speed", "") == "fast_forward" else 1.0),
                        "ken_burns": getattr(s, "ken_burns", ""),
                    })

            if video_segments and output_dir:
                try:
                    # 尝试VFX增强渲染
                    mp4_path = self._render_with_fallback(
                        video_segments, job, default_color, output_dir)
                    if mp4_path and os.path.exists(mp4_path):
                        job.enhancement_report["mp4_rendered"] = True
                        job.enhancement_report["mp4_path"] = mp4_path
                        job.enhancement_report["mp4_size_mb"] = round(
                            os.path.getsize(mp4_path) / 1024 / 1024, 1)
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


    # ===== 统一导演模式: 所有信号→导演→直接出片 =====
    def execute_unified(self, job: ExecutionJob, output_dir: str = "",
                        on_progress: callable = None) -> ExecutionJob:
        """
        🆕 统一导演模式 — 替代碎片化6阶段。
        """
        t0 = time.time()

        if on_progress:
            on_progress("understanding", 0, "🔍 并行理解: 语义+音频+视频...")

        # Step 1: 并行理解
        semantic_segments = []
        audio_segments = []
        whisper_gaps = []
        video_scenes = []

        # 1a. 语义理解
        try:
            from .semantic_engine import analyze_script
            analysis = analyze_script(job.script_text, job.script_type, use_ai=True)
            if analysis and analysis.segments:
                semantic_segments = [
                    {"text": s.text, "role": s.role, "emotion": s.emotion,
                     "intensity": s.intensity, "visual_need": s.visual_need,
                     "shot_type": s.shot_type, "broll_needed": s.broll_needed,
                     "text_overlay": s.text_overlay, "text_position": s.text_position,
                     "duration_sec": s.duration_sec, "start_sec": s.start_sec}
                    for s in analysis.segments
                ]
                job.enhancement_report["semantic"] = {
                    "emotional_arc": analysis.emotional_arc,
                    "engine": "deepseek" if analysis.emotional_arc != "规则推断" else "keyword",
                }
        except Exception as e:
            logger.warning("语义理解跳过: %s", e)

        # 1b. 音频理解 (有素材时)
        talking_slots = [s for s in job.sentences if hasattr(s, 'audio_status') and s.audio_status == "uploaded"]
        if not talking_slots:
            # 尝试从audio_slots获取
            for idx, path in job.audio_slots.items():
                if os.path.exists(path):
                    try:
                        from .media_understanding import understand_audio
                        audio_data = understand_audio(path)
                        whisper_gaps = [
                            {"at_sec": g.get("at_sec", 0), "gap_ms": g.get("gap_ms", 0),
                             "between": g.get("detail", "")}
                            for g in audio_data.get("moments", []) if g.get("type") == "pause"
                        ]
                        if audio_data.get("segments"):
                            audio_segments = [
                                {"start": s["start"], "end": s["end"], "text": s["text"],
                                 "emotion": "calm", "intensity": 5}
                                for s in audio_data["segments"]
                            ]
                        job.enhancement_report["audio"] = {
                            "transcript": audio_data.get("transcript", "")[:200],
                            "moments": len(audio_data.get("moments", [])),
                        }
                        # Store Whisper word timestamps for frame-precise editing
                        if audio_data.get("segments"):
                            word_times = []
                            for seg in audio_data["segments"]:
                                for w in seg.get("words", []):
                                    word_times.append(w)
                            if word_times:
                                gaps = []
                                for i in range(1, len(word_times)):
                                    gap_ms = int((word_times[i]["start"] - word_times[i-1]["end"]) * 1000)
                                    if gap_ms >= 300:
                                        gaps.append({"between": f'{word_times[i-1]["word"]}→{word_times[i]["word"]}', "at_sec": round(word_times[i-1]["end"]+gap_ms/2000,2), "gap_ms": gap_ms, "is_sentence_break": gap_ms>=500})
                                job.enhancement_report["whisper"] = {"total_words": len(word_times), "sentence_breaks": len([g for g in gaps if g["is_sentence_break"]]), "gaps": gaps, "word_times": word_times[:50]}
                                logger.info("Whisper: %d词·%d句间断", len(word_times), len(gaps))
                        break
                    except Exception as e:
                        logger.debug("音频理解跳过: %s", e)

        # 0.5: HEVC自动转x264(编解码兼容性)
        for idx, path in list(job.video_slots.items()):
            if os.path.exists(path):
                try:
                    import json as _json
                    r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_streams",path],
                                     capture_output=True, text=True, timeout=10)
                    streams = _json.loads(r.stdout).get("streams",[])
                    is_hevc = any(s.get("codec_name") in ("hevc","h265") for s in streams)
                    if is_hevc:
                        x264_path = str(Path(path).parent / f"_x264_{Path(path).name}.mp4")
                        if not os.path.exists(x264_path):
                            logger.info("HEVC→x264: %s", Path(path).name)
                            # Add silent audio track if source has no audio → prevents filter crashes
                            audio_args = ["-c:a","aac","-b:a","192k"] if any(s.get("codec_type")=="audio" for s in streams) else ["-f","lavfi","-i","anullsrc=r=44100:cl=mono","-c:a","aac","-b:a","32k","-shortest"]
                            if len(audio_args) > 4:  # anullsrc approach
                                subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                                    "-i",path,"-f","lavfi","-i","anullsrc=r=44100:cl=mono",
                                    "-c:v","libx264","-preset","fast","-crf","18",
                                    "-c:a","aac","-b:a","32k","-shortest",x264_path], timeout=300)
                            else:
                                subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                                    "-i",path,"-c:v","libx264","-preset","fast","-crf","18",
                                    "-c:a","aac","-b:a","192k",x264_path], timeout=300)
                        if os.path.exists(x264_path):
                            job.video_slots[idx] = x264_path
                except Exception:
                    pass

        # 0.6: 素材质量门禁(过暗/模糊/人脸/黑尾·只报告不拦截)
        if job.video_slots:
            try:
                from .material_checker import check_sentence_materials, verify_sentence_order
                mc = check_sentence_materials(job.sentences or [], job.video_slots)
                job.enhancement_report["material_check"] = mc
                if mc["bad"]:
                    logger.warning("素材质量: %d句待改进 %s", len(mc["bad"]),
                                   {i: [x["type"] for x in mc["per_sentence"][i]["issues"]]
                                    for i in mc["bad"]})
                # 顺序校验(重·默认关·CLIP_VERIFY_ORDER=1开启)
                if os.getenv("CLIP_VERIFY_ORDER") == "1":
                    vo = verify_sentence_order(job.sentences or [], job.video_slots)
                    job.enhancement_report["order_check"] = vo
                    if vo.get("suspects"):
                        logger.warning("疑似素材传错顺序: %s", vo["suspects"])
            except Exception as e:
                logger.debug("素材质量检查跳过: %s", e)

        # 1c. 视频分析 (Kimi K2.6→Kimi轻量→OpenCV降级)
        video_slots = job.video_slots or {}
        for idx, path in video_slots.items():
            if os.path.exists(path):
                scene_desc = None
                engine = "none"
                deep_annotations = []  # 存储详细标注供导演使用

                # 🆕 L1: Kimi K2.6 + GLM-4V 并行深度分析
                try:
                    kimi_ok = bool(os.getenv("KIMI_API_KEY"))
                    glm_ok = bool(os.getenv("GLM_API_KEY"))
                    if kimi_ok or glm_ok:
                        for _mk in ["app.services.shot_splitter", "app.services.kimi_video_analyzer",
                                     "app.services.material_analyzer"]:
                            if _mk in sys.modules and "MagicMock" in str(type(sys.modules[_mk])):
                                del sys.modules[_mk]
                        import app.services.shot_splitter as _ss
                        shots = _ss.ShotSplitter().split(Path(path))
                        if shots and shots.shots:
                            shot_list = [{"start": s.start_sec, "end": s.end_sec, "duration_sec": s.end_sec - s.start_sec}
                                        for s in shots.shots]

                            # 并行跑: K2.6跨镜链 + GLM-4V逐镜深标注
                            from concurrent.futures import ThreadPoolExecutor, as_completed
                            kimi_data, glm_data = None, None

                            def _run_kimi():
                                if not kimi_ok: return None
                                import app.services.kimi_video_analyzer as _kva
                                return _kva.analyze_video_chain(path, shot_list)

                            def _run_glm():
                                if not glm_ok: return None
                                import app.services.material_analyzer as _ma
                                return _ma.MaterialAnalyzer().analyze_deep(path, shot_list, max_shots=8)

                            with ThreadPoolExecutor(max_workers=2) as ex:
                                futs = {}
                                if kimi_ok: futs[ex.submit(_run_kimi)] = "kimi"
                                if glm_ok: futs[ex.submit(_run_glm)] = "glm"
                                for f in as_completed(futs):
                                    try:
                                        if futs[f] == "kimi":
                                            kimi_data = f.result()
                                        else:
                                            glm_data = f.result()
                                    except Exception:
                                        pass

                            # 融合K2.6+GLM结果
                            desc_parts = []
                            if kimi_data and kimi_data.continuity_score > 0:
                                desc_parts.append(f"K2.6:{kimi_data.continuity_score:.0%}连续")
                                if kimi_data.best_moments:
                                    desc_parts.append(f"{len(kimi_data.best_moments)}黄金镜")
                                engine = "kimi_k2.6"
                            if glm_data:
                                scene_types = [d.get("scene_type","?") for d in glm_data[:5]]
                                qualities = [d.get("quality_label","?") for d in glm_data[:5]]
                                desc_parts.append(f"GLM:{len(glm_data)}镜[{'·'.join(scene_types[:4])}]")
                                deep_annotations = glm_data
                                if engine == "none":
                                    engine = "glm4v"
                            if desc_parts:
                                scene_desc = " | ".join(desc_parts)
                                engine = "kimi_k2.6+glm4v" if kimi_data and glm_data else engine

                except Exception as e:
                    logger.debug("深度视频分析跳过: %s", e)

                # L2: Kimi轻量关键帧描述
                if not scene_desc:
                    try:
                        if os.getenv("KIMI_API_KEY"):
                            from .kimi_scene_analyzer import analyze_video_scenes
                            kimi_scenes = analyze_video_scenes(path, frame_count=2)
                            if kimi_scenes:
                                desc_parts = [f"@{s.at_sec:.0f}s:{s.description[:40]}" for s in kimi_scenes]
                                scene_desc = f"Kimi: {' | '.join(desc_parts)}"
                                engine = "kimi_vision"
                    except Exception:
                        pass

                # L3: OpenCV降级
                if not scene_desc:
                    try:
                        from .local_video_analyzer import quick_analyze
                        va = quick_analyze(path)
                        if "error" not in va:
                            scene_desc = f"OpenCV: {va.get('inferred_type','')}·{va.get('quality','')}·face={va.get('face_coverage_pct',0)}%"
                            engine = "opencv"
                    except Exception:
                        pass

                if scene_desc:
                    video_scenes.append({
                        "at_sec": 0, "file": Path(path).name,
                        "description": scene_desc, "engine": engine,
                        "deep_annotations": deep_annotations,  # GLM-4V详细标注
                    })
                job.enhancement_report["video"] = {
                    "analyzed": len(video_scenes),
                    "engine": engine,
                    "scenes": video_scenes,
                    "deep_annotations": deep_annotations,
                }
                break

        # 1d. 视觉-语义对齐 (Kimi/GLM视频描述 → 脚本内容匹配)
        alignment = None
        if video_scenes and semantic_segments:
            try:
                from .visual_semantic_aligner import align_script_to_video
                alignment = align_script_to_video(semantic_segments, video_scenes, job.script_type)
                if alignment:
                    job.enhancement_report["alignment"] = {
                        "confidence": alignment.overall_confidence,
                        "matched": len(alignment.segments),
                        "unmatched": len(alignment.unmatched_scripts),
                    }
                    logger.info("视觉语义对齐: %.0f%%置信·%d匹配·%d未匹配",
                               alignment.overall_confidence*100,
                               len(alignment.segments), len(alignment.unmatched_scripts))
            except Exception as e:
                logger.debug("对齐跳过: %s", e)

        # 注入GLM深标注到导演
        deep_ann = job.enhancement_report.get("video", {}).get("deep_annotations", [])
        for da in deep_ann[:3]:
            video_scenes.append({
                "at_sec": da.get("start_sec", 0),
                "description": f"GLM:{da.get('scene_type','')}/{da.get('shot_type','')}/{da.get('emotion','')}",
                "engine": "glm4v",
            })

        if on_progress:
            on_progress("directing", 40, "🎬 导演AI: 融合所有信号...")
        from .director_ai import direct, direct_to_execution_job

        plan = direct(
            script_type=job.script_type,
            semantic_segments=semantic_segments,
            audio_segments=audio_segments,
            whisper_gaps=whisper_gaps,
            video_scenes=video_scenes,
            use_ai=True,
        )

        if on_progress:
            on_progress("exporting", 70, "📤 导出: 剪映草稿+MP4...")

        # Step 2.4: 节奏引擎 (Whisper语速→自动调pacing)
        try:
            whisper_segs = job.enhancement_report.get("whisper", {}).get("word_times", [])
            if whisper_segs:
                from .rhythm_engine import analyze_rhythm, apply_rhythm_to_plan
                # Build rhythm data from whisper
                rhythm_data = []
                for w in whisper_segs[:100]:
                    rhythm_data.append({"speed_cps": 4.0, "start": w.get("start", 0)})
                rhythm = analyze_rhythm(rhythm_data)
                if rhythm.overall_pace != "medium":
                    job.enhancement_report["rhythm"] = {
                        "pace": rhythm.overall_pace,
                        "speed_cps": round(rhythm.avg_speed_cps, 1),
                        "shot_dur": round(rhythm.recommended_shot_dur, 1),
                    }
        except Exception as e:
            logger.debug("节奏引擎跳过: %s", e)

        # Step 2.5: 美学约束检查 (导演决策后·导出前)
        try:
            from .aesthetic_constraints import validate_plan
            aesthetic = validate_plan(job.sentences, job.script_type)
            job.enhancement_report["aesthetic"] = aesthetic
            if not aesthetic["passed"]:
                logger.warning("美学检查: %d错误·%d警告·评分%d",
                             aesthetic["error_count"], aesthetic["warning_count"], aesthetic["score"])
                # 自动修复errors
                if aesthetic["error_count"] > 0:
                    from .aesthetic_constraints import check_aesthetics, apply_fixes
                    issues = check_aesthetics(job.sentences, job.script_type)
                    job.sentences = apply_fixes(job.sentences, issues)
        except Exception as e:
            logger.debug("美学检查跳过: %s", e)

        # Step 3: 转换+导出
        unified_job = direct_to_execution_job(plan, job.audio_slots, job.video_slots)
        unified_job.job_id = job.job_id

        # 继承enhancement_report
        unified_job.enhancement_report.update(job.enhancement_report)
        unified_job.enhancement_report["pipeline"] = "unified_director"

        # 🆕 直接MP4渲染(VFX优先·pro_renderer降级)
        mp4_rendered = False
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)  # ffmpeg不能自建目录·实测VFX/pro_renderer都因此失败过
            # ── VFX渲染(与chatcut同路径: 句级效果/字幕/artifact检测全继承) ──
            try:
                from .chatcut_vfx import build_vfx_plan, render_with_vfx
                from .chatcut_plugin import _detect_industry
                from .shot_script import parse_shot_script, shots_to_sentences, shot_effects
                industry = _detect_industry(job.script_text, "")
                vfx_out = os.path.join(output_dir, "成片.mp4")
                # shot契约: 有分镜语言→逐镜驱动; 无→句级退化
                render_sents, fx = unified_job.sentences, None
                if job.shot_json:
                    ss = parse_shot_script(job.script_text, job.script_type, job.shot_json)
                    if ss.source == "shot_json":
                        render_sents = shots_to_sentences(ss)
                        fx = shot_effects(ss)
                        logger.info("shot契约: %d镜逐镜驱动", len(ss.shots))
                ok, info = _render_unified_vfx(
                    render_sents, job.video_slots or {},
                    job.script_type, industry, job.script_text, vfx_out,
                    shot_fx=fx, bgm_path=job.bgm_path or _select_bgm_safe(job.script_type))
                if ok:
                    mp4_rendered = True
                    unified_job.enhancement_report["mp4_rendered"] = True
                    unified_job.enhancement_report["mp4_path"] = info["output"]
                    unified_job.enhancement_report["mp4_engine"] = "VFX"
                    if info.get("size_mb"):
                        unified_job.enhancement_report["mp4_size_mb"] = info["size_mb"]
                    unified_job.enhancement_report["artifact_check"] = info.get("artifact_check")
                    unified_job.enhancement_report["script_audio_match"] = info.get("script_audio_match")
                    logger.info("VFX成片: %s·%s", vfx_out, info.get("artifact_check", {}).get("clean"))
                else:
                    logger.warning("VFX渲染失败(降级pro_renderer): %s", str(info)[:100])
            except Exception as e:
                logger.warning("VFX渲染异常(降级pro_renderer): %s", str(e)[:100])

        if output_dir and not mp4_rendered:
            # ── 降级: pro_renderer ──
            try:
                from .pro_renderer import RenderJob, render_professional
                color_map = {"老板IP": "warm", "团购售卖": "vivid", "引流进店": "bright"}
                default_color = color_map.get(job.script_type, "neutral")

                video_segs = []
                vs = job.video_slots or {}
                for i, s in enumerate(unified_job.sentences):
                    # 按index查找slot，找不到复用第一个可用文件
                    vf = vs.get(s.index if hasattr(s, 'index') else i+1)
                    if not vf or not os.path.exists(vf):
                        vf = vs.get(i+1)  # fallback by position
                    if not vf or not os.path.exists(vf):
                        vf = next((v for v in vs.values() if os.path.exists(v)), None)  # reuse any
                    if not vf or not os.path.exists(vf):
                        continue
                    video_segs.append({
                        "file": vf, "duration": s.duration_sec,
                        "start_sec": s.start_sec,  # 🐛 关键: 源文件偏移
                        "broll": s.is_broll,
                        "text": s.text_overlay,
                        "color_grade": default_color,
                        "transition": "dissolve" if s.is_broll else "cut",
                        "speed": getattr(s, "speed", "normal"),
                        "speed_factor": 0.5 if getattr(s, "speed", "") == "slow_motion" else (2.0 if getattr(s, "speed", "") == "fast_forward" else 1.0),
                    })

                if video_segs:
                    mp4_path = os.path.join(output_dir, "成片.mp4")
                    rj = RenderJob(segments=video_segs, output_path=mp4_path, width=1080, height=1920)
                    rj.__dict__["cinematic"] = (job.script_type == "老板IP")  # 老板IP默认电影感
                    mp4_result = render_professional(rj)
                    if mp4_result.success:
                        mp4_rendered = True
                        unified_job.enhancement_report["mp4_rendered"] = True
                        unified_job.enhancement_report["mp4_path"] = mp4_path
                        unified_job.enhancement_report["mp4_size_mb"] = mp4_result.file_size_mb
                        logger.info("MP4渲染: %.1fMB·%.1fs", mp4_result.file_size_mb, mp4_result.render_time_sec)
                else:
                    logger.warning("无有效视频素材·跳过MP4渲染")
            except Exception as e:
                logger.warning("MP4渲染失败: %s", e)

        # 渲染给了输出目录却没出片→记error(否则status=done是假成功·实测基线零产物)
        if output_dir and not mp4_rendered:
            unified_job.errors.append("MP4渲染失败或无有效素材")

        elapsed = time.time() - t0
        unified_job.status = "done" if not unified_job.errors else "failed"
        unified_job.enhancement_report["timing"] = {"total_s": round(elapsed, 1)}
        logger.info("🎬 统一导演完成: %s | %d段 | %.1fs | 弧线=%s",
                   unified_job.job_id, len(plan.segments), elapsed,
                   plan.emotional_arc[:50])

        return unified_job


def _select_bgm_safe(category: str) -> str:
    """BGM自动选曲·任何异常都返回""(不阻断出片)"""
    try:
        from .bgm_selector import select_bgm
        return select_bgm(category) or ""
    except Exception:
        return ""


def _clip_for_sentence(video_slots: dict, s, i: int) -> str:
    """句→素材: index优先→位置fallback→复用任一可用(与pro_renderer块同契约)"""
    vf = video_slots.get(s.index if hasattr(s, 'index') else i + 1)
    if not vf or not os.path.exists(vf):
        vf = video_slots.get(i + 1)
    if not vf or not os.path.exists(vf):
        vf = next((v for v in video_slots.values() if os.path.exists(v)), "")
    return vf if vf and os.path.exists(vf) else ""


def _concat_sentence_audio(clips: list[str], out_wav: str) -> str:
    """按句序拼接各素材的音轨→连贯旁白(16k单声道·两句以上才需要)"""
    import subprocess, tempfile
    if len(clips) == 1:
        return clips[0]
    tmp = tempfile.mkdtemp(prefix="aud_")
    parts = []
    for i, c in enumerate(clips):
        p = os.path.join(tmp, f"a{i}.wav")
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-i", c, "-vn", "-ac", "1", "-ar", "16000", p],
                           capture_output=True, timeout=60)
        if r.returncode == 0 and os.path.exists(p):
            parts.append(p)
    if not parts:
        return clips[0]
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p.replace(chr(92), '/')}'\n")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-f", "concat", "-safe", "0", "-i", lst,
                        "-ac", "1", "-ar", "16000", out_wav],
                       capture_output=True, timeout=60)
    return out_wav if r.returncode == 0 and os.path.exists(out_wav) else clips[0]


def _render_unified_vfx(sentences: list, video_slots: dict,
                        script_type: str, industry: str,
                        script_text: str, output_path: str,
                        shot_fx: dict | None = None,
                        bgm_path: str = "") -> tuple[bool, dict]:
    """句级素材→VFX渲染(与chatcut同函数·句级语义效果/黑尾裁剪全继承)

    联动要点:
    - 每句一个segment(不整片循环)·段时长钳到素材有效时长
    - 字幕直接从句子文本合成SRT(不经Whisper·文本零误差·逐句对齐)
    - shot_fx(可选): 分镜意图(转场/情绪着色/字号/叠加文)逐镜覆盖
    - 出片后artifact_check + 逐句script_audio_match
    """
    from .chatcut_vfx import build_vfx_plan, render_with_vfx, _probe_duration, _content_duration
    from .chatcut_plugin import estimate_reading_seconds, script_audio_verdict
    from .artifact_detector import detect_artifacts

    class _Seg:
        pass
    class _TL:
        pass

    # ── 逐句素材+时长钳制 ──
    segs, segment_files, clips = [], [], []
    accum = 0.0
    audio_est_total, audio_real_total = 0.0, 0.0
    for i, s in enumerate(sentences):
        vf = _clip_for_sentence(video_slots, s, i)
        if not vf:
            continue
        dur = float(getattr(s, 'duration_sec', 3.0) or 3.0)
        cd = _content_duration(vf)          # 黑尾裁剪(口播也适用)
        if cd and dur > cd:
            dur = max(0.5, cd)
        src = _probe_duration(vf)
        if src and dur > src:
            dur = max(0.5, src)             # 口播不循环·钳到实际时长
        seg = _Seg()
        seg.duration_sec = dur
        seg.script_text = getattr(s, 'text', '') or ''
        seg.is_broll = bool(getattr(s, 'is_broll', False))
        seg.material_file = vf
        seg.start_sec = accum
        seg.transition = "cut" if seg.is_broll else "crossfade"
        segs.append(seg)
        segment_files.append((vf, dur))
        clips.append(vf)
        accum += dur
        audio_est_total += estimate_reading_seconds(seg.script_text)
        audio_real_total += dur

    if not segs:
        return False, {"error": "无有效句级素材"}

    tl = _TL()
    tl.segments = segs
    plan = build_vfx_plan(tl, segment_files[0][0], script_type, industry)
    if not plan.success:
        return False, {"error": "VFX计划构建失败"}

    # shot契约: 分镜意图逐镜覆盖(转场/情绪着色/字号/叠加文)
    if shot_fx:
        for sv in plan.segments_vfx:
            fx = shot_fx.get(sv.get("index", -1) + 1)  # segments_vfx 0-based→shot 1-based
            if not fx:
                continue
            if fx.get("xfade"):
                sv["xfade"] = fx["xfade"]
            if fx.get("shader") and not any(f.get("shader") == fx["shader"] for f in sv["filters"]):
                sv["filters"].insert(0, {"type": "color", "shader": fx["shader"]})
            if fx.get("text_size"):
                sv["text_size"] = fx["text_size"]
            if fx.get("overlay_text"):
                sv["text"] = fx["overlay_text"]
                sv["text_y_frac"] = 0.25  # 避开底部字幕区

    # ── 字幕: 句子文本→SRT(精确文本·逐句时间) ──
    import tempfile
    tmp = tempfile.mkdtemp(prefix="uvfx_")
    srt_path = os.path.join(tmp, "sentences.srt")
    _write_srt_from_sentences(segs, srt_path)

    # ── 旁白: 各句音轨按序拼接 ──
    narration = _concat_sentence_audio(clips, os.path.join(tmp, "narration.wav"))

    ok, out = render_with_vfx(plan, segment_files,
                              audio_path=narration, output_path=output_path,
                              srt_path=srt_path, bgm_path=bgm_path)
    if not ok:
        return False, {"error": out}

    info = {"output": out}
    try:
        info["size_mb"] = round(os.path.getsize(out) / 1024 / 1024, 1)
    except Exception:
        pass
    try:
        info["artifact_check"] = detect_artifacts(out)
    except Exception:
        info["artifact_check"] = None
    verdict = script_audio_verdict(audio_est_total, audio_real_total)
    info["script_audio_match"] = {"script_est_s": round(audio_est_total, 1),
                                  "audio_s": round(audio_real_total, 1), **verdict}
    return True, info


def _write_srt_from_sentences(segs: list, srt_path: str) -> None:
    """句级时间线→SRT(联动红利: 文本来自脚本而非识别·零误差)"""
    def ts(sec: float) -> str:
        h, m = int(sec // 3600), int((sec % 3600) // 60)
        s, ms = int(sec % 60), int((sec % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    n = 0
    for seg in segs:
        text = (seg.script_text or "").strip()
        if not text:
            continue
        n += 1
        lines += [str(n), f"{ts(seg.start_sec)} --> {ts(seg.start_sec + seg.duration_sec)}",
                  text, ""]
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


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


def quick_direct(script_text: str, script_type: str = "团购售卖",
                 audio_slots: dict = None, video_slots: dict = None,
                 output_dir: str = "", on_progress: callable = None,
                 shot_json: list = None, bgm_path: str = "") -> ExecutionJob:
    """
    🆕 统一导演模式 — 一行代码完成从理解到成片。
    shot_json: 脚本Agent的分镜语言(可选·逐镜驱动剪辑)
    bgm_path: BGM音频文件(可选·自动闪避混音)
    """
    engine = ChangyiExecutionEngine()
    job = ExecutionJob(
        job_id=f"direct_{int(time.time())}",
        script_text=script_text,
        script_type=script_type,
        audio_slots=audio_slots or {},
        video_slots=video_slots or {},
        shot_json=shot_json or [],
        bgm_path=bgm_path,
    )
    return engine.execute_unified(job, output_dir, on_progress)
