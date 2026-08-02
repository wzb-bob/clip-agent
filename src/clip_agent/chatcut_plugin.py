"""
ChatCut剪辑插件 · 剪映替代方案 · 自动化剪辑引擎

C端用户(零配置): 传视频+脚本 → 自动检测类别行业 → VFX增强 → 成片MP4
B端用户(精确控制): 指定类别+行业+素材 → 批量出片

核心管线:
  音频→字幕→气口切分→VFX增强(节拍+调色+纹理+转场)→渲染MP4
  全部本地运行·零API依赖·不需要剪映
"""
from __future__ import annotations
import json, logging, os, tempfile, time
from pathlib import Path

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 工具映射表
# ══════════════════════════════════════════════════════════

CHATCUT_TOOLS = {
    "audio_to_subtitle": {
        "local": "whisper_srt_generator.generate_srt_from_video",
        "status": "✅", "desc": "Whisper语音→SRT字幕",
    },
    "video_trim": {
        "local": "four_category_pipeline",
        "status": "✅", "desc": "气口精切±16ms帧级精度",
    },
    "concat_videos": {
        "local": "render_with_vfx (主) / pro_renderer (降级)",
        "status": "✅", "desc": "VFX增强拼接+转场",
    },
    "compile_video_audio": {
        "local": "render_with_vfx",
        "status": "✅", "desc": "视频+音频+调色+纹理合成",
    },
    "add_subtitle": {
        "local": "subtitle_overlay.burn_png_subtitle",
        "status": "✅", "desc": "PIL渲染中文PNG→FFmpeg叠加",
    },
    "audio_separate": {
        "local": "audio_separator.separate_vocals",
        "status": "✅", "desc": "人声分离·去BGM·降噪",
    },
    "add_text": {
        "local": "pro_renderer._burn_text_with_animation",
        "status": "✅", "desc": "文字叠加·逐词动画",
    },
    "video_super_resolution": {
        "local": None,
        "status": "❌", "desc": "需要GPU+AI模型",
    },
}


def _ensure_x264(video_path: str) -> str | None:
    """HEVC自动转x264"""
    try:
        r = __import__('subprocess').run(
            ["ffprobe","-v","quiet","-print_format","json","-show_streams", video_path],
            capture_output=True, text=True, timeout=10)
        streams = json.loads(r.stdout).get("streams", [])
        if not any(s.get("codec_name") in ("hevc", "h265") for s in streams):
            return None
        out = str(Path(video_path).parent / f"_x264_{Path(video_path).name}.mp4")
        if os.path.exists(out):
            return out
        __import__('subprocess').run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i", video_path, "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", out], timeout=300)
        return out if os.path.exists(out) else None
    except Exception:
        return None


def _try_mlt_render(engine, talking: str, broll: list, category: str, output: str) -> tuple:
    """尝试MLT渲染·失败返回(False, error)"""
    from .mlt_engine import MltResult
    mlt_materials = {"talking": talking, "broll": broll or []}
    result = engine.render_with_fallback(
        type('P',(),{'category':category,'segments_vfx':[]})(), mlt_materials, output)
    return result.success, result.output_path if result.success else result.error


def _detect_category(script_text: str) -> str:
    """从脚本文本自动检测类别"""
    if any(kw in script_text for kw in ['块','元','¥','折','团购','左下','囤','抢','限时']):
        return "团购售卖"
    if any(kw in script_text for kw in ['那年','当时','记得','创业','故事','我是','坚持','梦想']):
        return "老板IP"
    if any(kw in script_text for kw in ['找不到','排队','导航','地址','二楼','路','街','城','广场','周末']):
        return "引流进店"
    return "团购售卖"


# 中文口播语速≈4.5字/s(实测普通商户口播4-5字/s)
_CHARS_PER_SEC = 4.5


def estimate_reading_seconds(script_text: str) -> float:
    """脚本朗读时长预估(纯函数)"""
    import re
    chars = len(re.sub(r"[\s，。！？、,.!?~…·—\-「」『』\"'“”‘’:：;；()（）]", "", script_text))
    return round(chars / _CHARS_PER_SEC, 1)


def script_audio_verdict(script_est_s: float, audio_s: float) -> dict:
    """脚本预估时长vs口播音频时长→匹配判定(纯函数)

    架构事实: 成片时长=口播音频时长(-shortest截断)。
    32s脚本配8s口播→成片只出前1/3剧情(实测)。
    """
    if audio_s <= 0:
        return {"verdict": "未知", "hint": ""}
    ratio = script_est_s / audio_s
    if ratio > 1.2:
        max_chars = int(audio_s * _CHARS_PER_SEC)
        return {"verdict": "脚本过长", "ratio": round(ratio, 1),
                "hint": f"成片只会出前{audio_s:.0f}s内容·建议脚本≤{max_chars}字"}
    if ratio < 0.6:
        return {"verdict": "脚本过短", "ratio": round(ratio, 1),
                "hint": "口播后半段无脚本覆盖·建议补文案或剪短口播"}
    return {"verdict": "匹配", "ratio": round(ratio, 1), "hint": ""}


def _detect_industry(script_text: str, video_path: str = "") -> str:
    """从脚本+路径自动检测行业"""
    combined = script_text + " " + video_path
    keywords = {
        "餐饮": ['虾','肉','菜','饭','面','火锅','烧烤','煲','卤','烤','炸','鸡','鱼','牛','羊','猪','汤','锅','辣','香','味','吃','喝','厨','灶','食材','新鲜','活','凌晨','挑','秘方','秘制','现做','手工'],
        "美容": ['脸','皮肤','美','痘','斑','敏','护理','面膜','光电','针','水光','脱毛','纹眉','双眼皮','瘦','白','嫩','滑','院长','师'],
        "汽修": ['车','修','保养','机油','轮胎','刹车','发动机','变速箱','空调','洗车','美容','贴膜','改色','轮毂','排气','避震','4S','维修','故障','异响'],
        "健身": ['健身','减肥','瘦','肌肉','腹肌','马甲线','练','私教','瑜伽','普拉提','体脂','蛋白','卡','斤','kg','课','会员'],
        "宠物": ['狗','猫','宠物','犬','喵','洗护','寄养','粮','零食','玩具','疫苗','驱虫','绝育','医院','美容','造型'],
        "教育": ['课','学','老师','学生','补习','考试','英语','数学','培训','班','家教','辅导','成绩','升学','艺考','托管'],
        "建材": ['装修','瓷砖','地板','门窗','卫浴','灯具','涂料','板材','定制','橱柜','衣柜','大理石','岩板','设计','工装','家装'],
        "零售": ['店','买','卖','货','新款','到货','上新','折扣','清仓','特价','促销','爆款','网红','同款','平替'],
        "家政": ['保洁','打扫','清洗','月嫂','保姆','育儿','养老','护工','除螨','油烟机','洗衣机','空调','搬家','收纳','整理'],
        "摄影": ['拍','摄影','写真','婚纱','婚礼','跟拍','旅拍','证件照','全家福','儿童','孕照','后期','精修','底片','相册'],
    }
    scores = {}
    for industry, kws in keywords.items():
        score = sum(1 for kw in kws if kw in combined)
        if score > 0:
            scores[industry] = score
    if not scores:
        return ""
    return max(scores, key=scores.get)


def get_chatcut_status() -> dict:
    return {
        "name": "ChatCut剪辑插件",
        "total_tools": len(CHATCUT_TOOLS),
        "ported": sum(1 for t in CHATCUT_TOOLS.values() if t["local"]),
        "tools": CHATCUT_TOOLS,
    }


# ══════════════════════════════════════════════════════════
# 主流程: ChatCut完整工作流
# ══════════════════════════════════════════════════════════

def run_chatcut_workflow(
    video_path: str,
    script_text: str = "",
    output_dir: str = "",
    broll_videos: list[str] = None,
    product_videos: list[str] = None,
    *,
    script_category: str = "",
    industry: str = "",
    shot_json: list = None,
) -> dict:
    """
    ChatCut自动剪辑成片。

    C端(零配置):
      run_chatcut_workflow("口播.mp4", script_text="68!十只活虾!...")

    B端(精确):
      run_chatcut_workflow("素材.mp4", script_text="...",
                          script_category="老板IP", industry="餐饮",
                          broll_videos=["食材.mp4","门头.mp4"])

    Shot驱动(有分镜语言):
      run_chatcut_workflow("口播.mp4", script_text="...", shot_json=[{...}])
      → 逐镜转场/情绪着色器/景别字号/叠加文
    """
    t0 = time.time()
    results = {"success": False, "steps": {}, "output": "", "vfx": {}}

    vp = Path(video_path)
    if not vp.exists():
        return {"success": False, "error": "视频不存在"}

    out = Path(output_dir) if output_dir else vp.parent / f"chatcut_{vp.stem}"
    out.mkdir(parents=True, exist_ok=True)

    # 自动检测
    if not script_category and script_text:
        script_category = _detect_category(script_text)
    if not script_category:
        script_category = "团购售卖"
    if not industry:
        industry = _detect_industry(script_text, str(vp))

    try:
        # Step 0: HEVC→x264
        converted = _ensure_x264(str(vp))
        if converted:
            vp = Path(converted)

        # Step 0.3: 素材质量门禁+评分(过暗/模糊→拒绝·否则打分)
        try:
            from .material_checker import check_material
            from .material_scorer import score_single
            qc = check_material(str(vp), need_face=True)
            results["material_qc"] = qc
            if not qc["pass"]:
                issues = [i["detail"] for i in qc.get("issues", [])]
                return {"success": False,
                        "error": f"素材质量问题: {'; '.join(issues)}",
                        "material_qc": qc}
            # 质量评分(0-1·传给前端展示)
            material_score = score_single(str(vp), "talking")
            results["material_score"] = material_score
            logger.info("素材评分: %.2f·技术=%.2f·人脸=%s",
                       material_score["score"], material_score["technical"]["sharpness"],
                       material_score["has_face"])
        except Exception as e:
            logger.debug("素材质量检测跳过: %s", e)

        broll_videos = [_ensure_x264(b) or b for b in (broll_videos or [])]
        product_videos = [_ensure_x264(p) or p for p in (product_videos or [])]

        # Step 0.5: 脚本↔口播时长匹配(给脚本Agent可机读的自我纠正信号)
        if script_text:
            try:
                from .chatcut_vfx import _probe_duration
                audio_s = _probe_duration(str(vp))
                est = estimate_reading_seconds(script_text)
                verdict = script_audio_verdict(est, audio_s)
                results["script_audio_match"] = {
                    "script_chars": len(script_text), "script_est_s": est,
                    "audio_s": audio_s, **verdict,
                }
                if verdict["verdict"] != "匹配":
                    logger.warning("脚本↔口播%s: %s", verdict["verdict"], verdict["hint"])
            except Exception:
                pass

        # Step 1+2: 音频→字幕
        from .audio_separator import enhance_audio_for_whisper
        results["steps"]["audio_separate"] = bool(enhance_audio_for_whisper(str(vp)))

        from .whisper_srt_generator import generate_srt_from_video
        srt = generate_srt_from_video(str(vp), str(out / "subtitles.srt"),
                                      expected_script=script_text)
        results["steps"]["audio_to_subtitle"] = bool(srt)

        # Step 2.5: 气口检测(5路信号融合·切点传给四类管线)
        breath_report = None
        try:
            from .breath_detector import BreathDetector
            breath_report = BreathDetector().analyze(vp)
            results["steps"]["breath_detect"] = breath_report.total_points
            if breath_report.best_cuts:
                logger.info("气口检测: %d切点·best=%d·句间=%d",
                           breath_report.total_points,
                           len(breath_report.best_cuts),
                           len(breath_report.sentence_breaks))
        except Exception as e:
            logger.debug("气口检测跳过: %s", e)

        # Step 2.6: 节拍检测+切点对齐(呼吸切点→最近节拍±150ms)
        try:
            from .rhythm_engine import detect_bpm, align_to_beat
            beat_info = detect_bpm(str(vp))
            results["bpm"] = beat_info
            if beat_info["bpm"] > 0 and breath_report and breath_report.best_cuts:
                cut_pts = [p.at_sec for p in breath_report.best_cuts]
                aligned = align_to_beat(cut_pts, beat_info)
                logger.info("节拍对齐: %dBPM·%d/%d切点对齐",
                           int(beat_info["bpm"]),
                           sum(1 for a,b in zip(aligned,cut_pts) if a!=b),
                           len(aligned))
        except Exception as e:
            logger.debug("节拍检测跳过: %s", e)

        # Step 3: 气口切割
        from .four_category_pipeline import run_four_category_pipeline, CategoryMaterials
        materials = CategoryMaterials(
            talking=[str(vp)],
            environment=broll_videos or [],
            product=product_videos or [],
            cta=[],
        )
        timeline = run_four_category_pipeline(script_text or "口播脚本", materials, output_dir=str(out))
        results["steps"]["video_trim"] = len(timeline.segments)
        if getattr(timeline, "material_adequacy", None):
            results["material_adequacy"] = timeline.material_adequacy
        mp4_path = str(out / f"成片_{vp.stem}.mp4")

        # Step 3.5: FFmpeg VFX渲染优先(人眼+Kimi双验证路径·引擎单跑不重复渲染)
        try:
            from .chatcut_vfx import build_vfx_plan, render_with_vfx

            vfx_plan = build_vfx_plan(timeline, str(vp), script_category, industry, shot_json=shot_json)
            if vfx_plan.success:
                segment_files = []
                for s in timeline.segments:
                    fpath = getattr(s, 'material_file', '')
                    if fpath and Path(fpath).exists():
                        segment_files.append((fpath, getattr(s, 'duration_sec', 2.0)))

                if segment_files:
                    ok, vfx_output = render_with_vfx(
                        vfx_plan, segment_files,
                        audio_path=str(vp), output_path=mp4_path)
                    if ok:
                        results["output"] = vfx_output
                        results["steps"]["vfx_render"] = True
                        results["vfx"] = {
                            "category": vfx_plan.category,
                            "label": vfx_plan.category_label,
                            "industry": industry,
                            "beats": vfx_plan.beat_count,
                            "bpm": vfx_plan.bpm,
                        }
                        if Path(vfx_output).exists():
                            results["size_mb"] = round(Path(vfx_output).stat().st_size / 1024 / 1024, 1)
                        logger.info("VFX成片: %.1fMB·%d拍·%.0fBPM·%s/%s",
                                   results.get("size_mb", 0), vfx_plan.beat_count,
                                   vfx_plan.bpm, script_category, industry)
        except Exception as e:
            logger.warning("VFX渲染失败(降级MLT): %s", str(e)[:100])

        # Step 4: MLT渲染(VFX失败时降级·成功则跳过)
        if not results.get("output"):
            try:
                from .mlt_engine import MltEngine, mlt_verify
                from .chatcut_vfx import build_vfx_plan
                if mlt_verify():
                    mlt_plan = build_vfx_plan(timeline, str(vp), script_category, industry)
                    mlt_engine = MltEngine()
                    mlt_materials = {"talking": str(vp), "broll": broll_videos or []}
                    mlt_result = mlt_engine.render_with_fallback(mlt_plan, mlt_materials, mp4_path)
                    if mlt_result.success:
                        results["output"] = mlt_result.output_path
                        results["steps"]["mlt_render"] = True
                        results["vfx"] = {"engine": "MLT", "category": script_category,
                                         "label": mlt_plan.category_label,
                                         "beats": mlt_plan.beat_count, "bpm": mlt_plan.bpm}
            except Exception:
                pass

        vfx_rendered = bool(results.get("output"))

        # Step 4b: 基础渲染（降级）
        if not vfx_rendered:
            try:
                from .pro_renderer import RenderJob, render_professional
                segs = []
                for s in timeline.segments:
                    if os.path.exists(s.material_file):
                        segs.append({
                            "file": s.material_file,
                            "duration": s.duration_sec,
                            "start_sec": s.start_sec,
                            "broll": s.is_broll,
                            "text": s.script_text[:30] if s.script_text else "",
                            "color_grade": "warm",
                            "transition": s.transition,
                        })
                if segs:
                    rj = RenderJob(segments=segs, output_path=mp4_path, width=1080, height=1920)
                    mp4_result = render_professional(rj)
                    if mp4_result.success:
                        results["output"] = mp4_path
                        results["steps"]["base_render"] = True
                        results["duration"] = mp4_result.duration_sec
                        results["size_mb"] = mp4_result.file_size_mb
            except Exception as e:
                results["steps"]["base_render"] = False
                results["error"] = str(e)[:100]

        # 降级: 剪映草稿ZIP
        if not results.get("output") and timeline.draft_path:
            from .jianying_timeline_builder import export_draft_zip
            results["output"] = export_draft_zip(timeline.draft_path)
            results["steps"]["draft_zip"] = bool(results["output"])

        # Step 5: 确定性artifact检测(补Kimi盲区·失败静默)
        if results.get("output") and Path(results["output"]).exists():
            try:
                from .artifact_detector import detect_artifacts
                results["artifact_check"] = detect_artifacts(results["output"])
            except Exception as e:
                logger.debug("artifact检测跳过: %s", e)

        results["success"] = bool(results.get("output"))
        results["elapsed"] = round(time.time() - t0, 1)
        results["segments"] = len(timeline.segments)

    except Exception as e:
        results["error"] = str(e)[:200]
        logger.error("ChatCut流程异常: %s", results["error"])

    return results
