"""
四类素材处理管道 v1 · v5.0 核心

输入: 脚本 + 四类素材(口播/环境/产品/引导)
输出: 剪映草稿时间线(draft_content.json)

气口切割: Whisper 词级时间戳 → 句间停顿 → 精确切点
镜头衔接: 口播主轨 → 停顿→B-roll覆盖 → 口播 → ... → CTA
"""
from __future__ import annotations
import json, logging, os, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CategoryMaterials:
    """四类素材"""
    talking: list[str] = field(default_factory=list)     # 口播出镜
    environment: list[str] = field(default_factory=list)  # 店铺环境
    product: list[str] = field(default_factory=list)      # 产品展示
    cta: list[str] = field(default_factory=list)          # 引导CTA


@dataclass
class TimelineSegment:
    """时间线上的一个段"""
    index: int
    script_text: str
    start_sec: float
    duration_sec: float
    material_file: str           # 使用的素材文件
    material_category: str       # talking/environment/product/cta
    is_broll: bool               # 是否B-roll覆盖
    transition: str              # cut/dissolve


@dataclass
class JianYingTimeline:
    """完整的剪映时间线"""
    script_text: str
    segments: list[TimelineSegment]
    total_duration: float
    talking_video: str           # 口播主视频
    breath_points: list[dict]    # 气口切点
    draft_path: str = ""


def run_four_category_pipeline(
    script_text: str,
    materials: CategoryMaterials,
    output_dir: str = "",
    turbo: bool = False,
) -> JianYingTimeline:
    """
    主入口: 四类素材 → 气口切割 → 时间线排列。

    流程:
    1. Whisper 分析口播视频 → 词级时间戳 + 气口
    2. 脚本分段(语义引擎)
    3. 素材匹配(每段选对应类别素材)
    4. 时间线排列(口播主轨↔B-roll交替)
    5. 生成剪映草稿
    """
    t0 = time.time()

    # 🆕 Turbo模式: 跳过Whisper+AI导演·纯规则快速出草稿
    if turbo:
        logger.info("⚡ Turbo模式·跳过AI分析")

    # Step 1: 气口分析(口播视频·Turbo模式跳过)
    breath_points = []
    talking_video = materials.talking[0] if materials.talking else ""
    if talking_video and os.path.exists(talking_video) and not turbo:
        breath_points = _detect_breath_points(talking_video)
        logger.info("气口检测: %d个切点", len(breath_points))

    # Step 2: 脚本分段
    segments = _segment_script(script_text)
    logger.info("脚本分段: %d段", len(segments))

    # Step 2.5: AI导演决策(Turbo模式跳过)
    if segments and not turbo:
        try:
            from .director_ai import direct
            semantic_segs = [
                {"text": s.get("text",""), "role": s.get("role","body"),
                 "duration_sec": s.get("duration_sec", 3.0),
                 "broll_needed": s.get("broll_needed", True),
                 "visual_need": "", "shot_type": "MS",
                 "text_overlay": "", "text_position": "bottom",
                 "start_sec": i * 3.0}
                for i, s in enumerate(segments)
            ]
            plan = direct("老板IP", semantic_segs, use_ai=True)
            if plan and plan.segments:
                # 用AI导演的决策覆盖简单规则
                for i, s in enumerate(segments):
                    if i < len(plan.segments):
                        d = plan.segments[i]
                        s["shot_type"] = d.shot_type
                        s["duration_sec"] = d.duration_sec
                        if d.is_broll: s["broll_needed"] = True
                        if d.text_overlay: s["text_overlay"] = d.text_overlay
                logger.info("AI导演: %d段增强", len(plan.segments))
        except Exception as e:
            logger.debug("AI导演跳过: %s", e)

    # Step 3+4: 素材匹配 + 时间线排列
    timeline_segs = _build_timeline(segments, materials, breath_points, talking_video)

    total_dur = sum(s.duration_sec for s in timeline_segs)

    # Step 5: 生成字幕(SRT文件·导出可用)
    srt_path = ""
    if talking_video and os.path.exists(talking_video):
        try:
            from .whisper_srt_generator import generate_srt_from_video
            srt_out = os.path.join(output_dir or tempfile.gettempdir(), "subtitles.srt")
            srt_path = generate_srt_from_video(talking_video, srt_out, expected_script=script_text) or ""
            if srt_path:
                logger.info("SRT字幕: %s", srt_path)
        except Exception as e:
            logger.debug("SRT生成跳过: %s", e)

        # 🆕 PNG字幕烧录(直接嵌入视频·比FFmpeg文字滤镜更可靠)
        if output_dir and timeline_segs:
            try:
                from .subtitle_overlay import render_text_to_png
                # 生成每段的PNG字幕
                for seg in timeline_segs:
                    if seg.script_text:
                        png = render_text_to_png(seg.script_text[:30], 1080, 1920, font_size=52)
                        if png:
                            seg._png_path = png  # 动态属性
                logger.debug("PNG字幕: %d张", sum(1 for s in timeline_segs if hasattr(s, '_png_path')))
            except Exception:
                pass

    # Step 6: 生成剪映草稿 + 使用说明
    draft_path = ""
    if output_dir:
        try:
            from .jianying_timeline_builder import write_output_readme
            write_output_readme(output_dir)
        except Exception:
            pass
    if output_dir and talking_video:
        draft_path = _generate_jianying_draft(timeline_segs, talking_video, output_dir)

    elapsed = time.time() - t0
    # 验证草稿
    validation = {}
    if draft_path:
        try:
            from .jianying_timeline_builder import validate_draft
            validation = validate_draft(draft_path)
            if not validation.get("valid"):
                logger.warning("草稿验证: %s", validation.get("issues", []))
            else:
                logger.info("草稿验证: ✅ %d段·v%s", validation.get("segments", 0), validation.get("version", "?"))
        except Exception:
            pass

    logger.info("四类管道完成: %d段·%.1fs·%.1fs", len(timeline_segs), total_dur, elapsed)

    result = JianYingTimeline(
        script_text=script_text,
        segments=timeline_segs,
        total_duration=total_dur,
        talking_video=talking_video,
        breath_points=breath_points,
        draft_path=draft_path,
    )
    result.srt_path = srt_path  # 动态属性

    # 容错: 无素材时生成兜底时间线（纯脚本分段·无视频）
    if not result.segments:
        logger.warning("无有效素材·生成纯脚本时间线")
        result.segments = [
            TimelineSegment(i+1, s.get("text",""), i*3.0, s.get("duration_sec",3.0), "", "placeholder", False, "cut")
            for i, s in enumerate(_segment_script(script_text))
        ]
        result.total_duration = sum(s.duration_sec for s in result.segments)

    return result


def _detect_breath_points(video_path: str) -> list[dict]:
    """Whisper气口检测 → 人声分离增强→词级时间戳→切点"""
    points = []
    try:
        # 🆕 人声分离: 去BGM+降噪→提高Whisper准确度
        try:
            from .audio_separator import enhance_audio_for_whisper
            enhanced = enhance_audio_for_whisper(video_path)
            if enhanced:
                video_path = enhanced  # 用增强后的音频
                logger.debug("使用增强音频进行Whisper转录")
        except Exception:
            pass

        import whisper
        model = whisper.load_model("small")
        result = model.transcribe(video_path, word_timestamps=True)
        word_times = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                word_times.append({
                    "word": w.get("word", "").strip(),
                    "start": round(w.get("start", 0), 2),
                    "end": round(w.get("end", 0), 2),
                })
        for i in range(1, len(word_times)):
            gap_ms = int((word_times[i]["start"] - word_times[i-1]["end"]) * 1000)
            if gap_ms >= 400:
                points.append({
                    "at_sec": round(word_times[i-1]["end"] + gap_ms/2000, 2),
                    "gap_ms": gap_ms,
                    "is_sentence_break": gap_ms >= 600,
                    "word_before": word_times[i-1]["word"],
                    "word_after": word_times[i]["word"],
                })
    except Exception as e:
        logger.warning("气口检测失败: %s", e)
    return points


def _segment_script(script_text: str) -> list[dict]:
    """脚本分段 — 优先语义引擎·降级关键词"""
    try:
        from .semantic_engine import analyze_script
        analysis = analyze_script(script_text, "老板IP", use_ai=True)
        if analysis and analysis.segments:
            return [
                {"text": s.text, "role": s.role, "duration_sec": s.duration_sec,
                 "shot_type": s.shot_type, "broll_needed": s.broll_needed}
                for s in analysis.segments
            ]
    except Exception:
        pass
    # 降级: 简单按标点分句
    import re
    sentences = re.split(r'[。！？!?\n]', script_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 3]
    total = len(sentences)
    result = []
    for i, text in enumerate(sentences):
        role = "hook" if i == 0 else ("cta" if i >= total - 2 else "body")
        result.append({
            "text": text, "role": role,
            "duration_sec": max(2.0, len(text) * 0.3 + 0.5),
            "shot_type": "MS", "broll_needed": role == "body",
        })
    return result


def _build_timeline(
    segments: list[dict],
    materials: CategoryMaterials,
    breath_points: list[dict],
    talking_video: str,
) -> list[TimelineSegment]:
    """素材匹配 + 时间线排列"""
    result = []
    cur_sec = 0.0
    env_idx = 0
    prod_idx = 0

    for i, seg in enumerate(segments):
        role = seg.get("role", "body")
        dur = seg.get("duration_sec", 3.0)

        is_first = (i == 0)
        is_last = (i == len(segments) - 1)

        # 素材选择: 开头/结尾=口播·中段交替B-roll
        if is_first or is_last:
            mat_file = talking_video
            mat_cat = "talking"
            is_broll = False
        elif i % 2 == 1 and env_idx < len(materials.environment):
            # 奇数段→环境B-roll
            mat_file = materials.environment[env_idx % len(materials.environment)]
            mat_cat = "environment"
            env_idx += 1
            is_broll = True
        elif prod_idx < len(materials.product):
            # 偶数段→产品B-roll(有产品素材时)
            mat_file = materials.product[prod_idx % len(materials.product)]
            mat_cat = "product"
            prod_idx += 1
            is_broll = True
        else:
            # 兜底: 口播主轨
            mat_file = talking_video
            mat_cat = "talking"
            is_broll = False

        # 🆕 气口对齐: 段结束时间对齐到最近的自然停顿点
        seg_end = cur_sec + dur
        best_bp = None
        for bp in breath_points:
            if abs(bp["at_sec"] - seg_end) < 0.8 and bp.get("is_sentence_break"):
                if best_bp is None or abs(bp["at_sec"] - seg_end) < abs(best_bp["at_sec"] - seg_end):
                    best_bp = bp
        if best_bp:
            # 在自然停顿+2帧处切
            from .director_ai import snap_to_frame
            dur = snap_to_frame(best_bp["at_sec"] - cur_sec + 2/30, 30)
            seg["duration_sec"] = dur  # 更新时长

        # 转场
        transition = "dissolve" if is_broll else "cut"

        result.append(TimelineSegment(
            index=i + 1,
            script_text=seg.get("text", ""),
            start_sec=round(cur_sec, 2),
            duration_sec=round(dur, 2),
            material_file=mat_file,
            material_category=mat_cat,
            is_broll=is_broll,
            transition=transition,
        ))
        cur_sec += dur

    return result


def _generate_jianying_draft(
    segments: list[TimelineSegment],
    talking_video: str,
    output_dir: str,
) -> str:
    """生成剪映草稿文件"""
    os.makedirs(output_dir, exist_ok=True)
    try:
        # 尝试使用 pyJianYingDraft
        from app.services.jianying_draft import JianYingDraftGenerator
        gen = JianYingDraftGenerator(width=1080, height=1920, fps=30)
        draft_dir = gen.init_project(output_dir)

        for seg in segments:
            if not os.path.exists(seg.material_file):
                continue
            start_us = int(seg.start_sec * 1_000_000)
            dur_us = int(seg.duration_sec * 1_000_000)

            if seg.is_broll:
                gen.add_broll_overlay(
                    seg.material_file, start_us, dur_us, dur_us,
                    fade_in_us=300000, fade_out_us=300000,
                )
            else:
                gen.add_clip(seg.material_file, start_us, dur_us, dur_us)

            if seg.script_text:
                gen.add_subtitle(start_us, dur_us, seg.script_text[:30])

        gen.save()
        return str(draft_dir)
    except Exception as e:
        logger.warning("pyJianYingDraft失败·降级手动JSON: %s", e)
        return _generate_manual_draft(segments, talking_video, output_dir)


def _generate_manual_draft(segments: list[TimelineSegment], talking_video: str, output_dir: str) -> str:
    """手动生成简版 draft_content.json"""
    draft = {
        "platform": {"os": "windows"},
        "draft_name": "AI剪辑草稿",
        "draft_info": {"version": 1},
        "materials": {"videos": [], "images": []},
        "tracks": [],
        "canvas_config": {"width": 1080, "height": 1920},
    }
    draft_path = os.path.join(output_dir, "draft_content.json")
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    return draft_path
