"""
导演AI v1 · 统一决策层 · 融合所有理解信号

这是"打配合"的核心——不单独依赖任何一个分析模块,
而是把语义理解、音频理解、视频分析、编辑规则的结果全部
汇总, 让DeepSeek做最终的剪辑导演决策。

信号优先级: 音频(时间精度最高) > 语义(内容理解) > 视频(辅助验证) > 规则(兜底)
"""
from __future__ import annotations
import json, logging, re, time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DirectorDecision:
    """导演的最终剪辑决策 — 时间线上每一段的精确参数"""
    # 时间
    start_sec: float
    duration_sec: float

    # 内容
    script_text: str = ""
    audio_text: str = ""           # Whisper实际转录
    segment_role: str = ""         # hook/body/cta...

    # 画面决策 (融合所有信号)
    shot_type: str = "MS"          # CU/MCU/MS/LS
    camera_move: str = "static"
    is_broll: bool = False         # 是否覆盖B-roll
    broll_visual: str = ""         # B-roll画面描述
    visual_source: str = ""        # 决策来源: semantic/audio/cross_modal/rule

    # 文字决策
    text_overlay: str = ""
    text_animation: str = ""       # pop_in/fade_in/scale_up
    text_position: str = "bottom"

    # 音频决策
    audio_action: str = "keep"     # keep/mute/duck
    is_golden_moment: bool = False # 金句时刻→大字+特效
    emphasis_effect: str = ""      # 强调特效

    # 转场
    transition_in: str = "cut"
    transition_out: str = "cut"

    # 置信度 (这个决策有多确定)
    confidence: float = 0.7
    decision_basis: str = ""       # 基于什么做的决策


@dataclass
class DirectorPlan:
    """导演的完整剪辑计划"""
    script_type: str
    total_duration: float
    segments: list[DirectorDecision]
    emotional_arc: str = ""
    golden_moments: list[dict] = field(default_factory=list)
    broll_assignments: list[dict] = field(default_factory=list)
    editing_style: str = ""
    bgm_recommendation: str = ""
    color_grade: str = "neutral"
    segments: list = field(default_factory=list)


# ══════════════════════════════════════════════════════════
# 信号融合引擎: 从多个来源聚合信息
# ══════════════════════════════════════════════════════════

def fuse_signals(
    script_type: str,
    semantic_segments: list[dict],    # 来自 semantic_engine
    audio_segments: list[dict],       # 来自 audio_understanding
    whisper_gaps: list[dict],         # 来自 Whisper
    video_scenes: list[dict],         # 来自 local_video_analyzer
    editing_rules: list,              # 来自 editing_rules
) -> DirectorPlan:
    """
    信号融合: 把多个来源的信息合并成统一的导演计划。

    融合策略:
    1. 时间对齐: Whisper的时间戳最准 → 以此为基础
    2. 内容匹配: 语义引擎的visual_need比关键词准
    3. B-roll时机: 音频停顿 > 视频场景切换 > 规则"每15秒"
    4. 文字叠加: 语义引擎text_overlay > 规则提取
    5. 景别: 语义引擎shot_type > 编辑规则 > 默认MS
    """
    total_dur = sum(s.get("duration_sec", 3.0) for s in semantic_segments)

    plan = DirectorPlan(
        script_type=script_type,
        total_duration=total_dur,
    )

    # 时间对齐: audio_segments有精确时间戳
    audio_map = {}
    for i, a in enumerate(audio_segments):
        key = round(a.get("start", i * 3.0), 1)
        audio_map[key] = a

    gap_map = {}
    for g in whisper_gaps:
        gap_map[round(g.get("at_sec", 0), 1)] = g

    for i, sem in enumerate(semantic_segments):
        # 找到最接近的音频段
        approx_time = sem.get("start_sec", i * 3.0)
        closest_audio = None
        for at, a in audio_map.items():
            if abs(at - approx_time) < 1.0:
                closest_audio = a
                break

        # 时间源优先级: 音频 > 语义估算
        if closest_audio:
            start = closest_audio.get("start", approx_time)
            dur = closest_audio.get("end", start + 3.0) - start
            audio_text = closest_audio.get("text", "")
            emotion = closest_audio.get("emotion", sem.get("emotion", "calm"))
            intensity = closest_audio.get("intensity", sem.get("intensity", 5))
        else:
            start = approx_time
            dur = sem.get("duration_sec", 3.0)
            audio_text = ""
            emotion = sem.get("emotion", "calm")
            intensity = sem.get("intensity", 5)

        # 景别: 语义 > 音频 > 规则 > 默认
        shot = sem.get("shot_type", "") or (closest_audio or {}).get("shot", "") or "MS"

        # B-roll: 在自然停顿处优先
        is_broll = sem.get("broll_needed", False)
        gap_at = gap_map.get(round(start, 1))
        if gap_at and gap_at.get("gap_ms", 0) >= 400:
            is_broll = True  # 停顿>400ms → 适合插B-roll

        # B-roll画面: 语义visual_need > 场景描述
        broll_visual = sem.get("visual_need", "")
        visual_source = "semantic"
        if not broll_visual and video_scenes:
            for vs in video_scenes:
                if abs(vs.get("at_sec", 0) - start) < 1.0:
                    broll_visual = vs.get("description", "")
                    visual_source = "video"
                    break

        # 文字: 语义overlay > 音频金句
        overlay = sem.get("text_overlay", "")
        is_golden = (closest_audio or {}).get("golden", False) if closest_audio else False
        if is_golden and not overlay:
            overlay = audio_text[:12] if audio_text else ""
        text_anim = "scale_up" if is_golden else "fade_in"

        # 音频动作: 金句保留原声, B-roll压低音量
        audio_action = "keep"
        if is_golden:
            audio_action = "keep"
            emphasis = "音量+10%·大字弹出"
        elif is_broll:
            audio_action = "duck"
            emphasis = "保留配音·画面覆盖"
        else:
            emphasis = ""

        # 转场: 在自然停顿处用dissolve
        trans_out = "dissolve" if (gap_at and gap_at.get("gap_ms", 0) >= 500) else "cut"

        # 置信度: 音频对齐的 > 纯语义的
        confidence = 0.85 if closest_audio else (0.7 if gap_at else 0.5)

        decision = DirectorDecision(
            start_sec=round(start, 1),
            duration_sec=round(max(dur, 1.0), 1),
            script_text=sem.get("text", ""),
            audio_text=audio_text,
            segment_role=sem.get("role", "transition"),
            shot_type=shot,
            camera_move="push_in" if is_broll else "static",
            is_broll=is_broll,
            broll_visual=broll_visual,
            visual_source=visual_source,
            text_overlay=overlay,
            text_animation=text_anim,
            text_position=sem.get("text_position", "bottom"),
            audio_action=audio_action,
            is_golden_moment=is_golden,
            emphasis_effect=emphasis,
            transition_in="cut",
            transition_out=trans_out,
            confidence=confidence,
            decision_basis=f"audio_aligned" if closest_audio else f"semantic_only",
        )

        plan.segments.append(decision)

    # 汇总金句时刻
    plan.golden_moments = [
        {"at_sec": s.start_sec, "text": s.script_text, "effect": s.emphasis_effect}
        for s in plan.segments if s.is_golden_moment
    ]

    # 情绪弧线
    emotions = [s.segment_role for s in plan.segments]
    plan.emotional_arc = "→".join(emotions[:6])

    logger.info("信号融合: %d段·%d金句·置信度avg=%.2f",
               len(plan.segments), len(plan.golden_moments),
               sum(s.confidence for s in plan.segments) / max(len(plan.segments), 1))

    return plan


# ══════════════════════════════════════════════════════════
# AI导演: DeepSeek做最终决策
# ══════════════════════════════════════════════════════════

DIRECTOR_PROMPT = """你是短视频剪辑总导演。下面汇集了多个AI分析模块的结果,请做最终决策。

## 剧本分析(语义引擎)
{semantic_summary}

## 音频分析(Whisper+librosa)
{audio_summary}

## 视频分析(OpenCV本地)
{video_summary}

## 编辑规则建议
{rules_summary}

## 脚本类型: {script_type}

## 任务: 综合所有信号,输出精确到帧的剪辑方案。

JSON格式:
{{
  "plan_name": "方案名称",
  "editing_style": "剪辑风格描述(10字)",
  "color_grade": "warm|vivid|bright|cool|cinematic",
  "bgm": "BGM风格推荐",
  "emotional_arc": "情绪弧线",
  "segments": [
    {{
      "start": 0.0, "duration": 2.8,
      "script": "原文", "audio_actual": "实际说的",
      "shot": "CU", "camera": "static",
      "broll": false, "broll_visual": "",
      "text": "叠加文字", "text_anim": "scale_up",
      "audio_action": "keep", "golden": true,
      "transition": "dissolve",
      "reason": "决策理由(10字)"
    }}
  ],
  "key_insights": ["最重要的3个洞察"]
}}

只返回JSON。"""


def ai_director_decision(
    script_type: str,
    semantic_summary: str,
    audio_summary: str,
    video_summary: str,
    rules_summary: str,
) -> dict | None:
    """
    AI总导演: 把所有分析结果喂给DeepSeek, 让它做最终决策。

    这是"打配合"的终极体现 — 不是独立决策, 而是综合所有信号。
    """
    try:
        from ._imports import chat_via_gateway, get_model_name
        if not chat_via_gateway:
            return None

        prompt = DIRECTOR_PROMPT.format(
            script_type=script_type,
            semantic_summary=semantic_summary[:600],
            audio_summary=audio_summary[:400],
            video_summary=video_summary[:300],
            rules_summary=rules_summary[:200],
        )

        model = get_model_name("deepseek") or "deepseek-v4-flash"
        t0 = time.time()
        result = chat_via_gateway(
            provider="deepseek", model=model,
            system="你是短视频剪辑总导演。综合所有信号做决策。只返回JSON。",
            user=prompt, temperature=0.2, max_tokens=2000,
        )
        content = result.get("content", "") if isinstance(result, dict) else str(result)

        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            from .semantic_engine import _repair_json
            data = json.loads(_repair_json(m.group(0)))
            elapsed = time.time() - t0
            logger.info("AI导演决策: %d段·%.1fs·风格=%s",
                       len(data.get("segments", [])), elapsed,
                       data.get("editing_style", ""))
            return data

    except Exception as e:
        logger.warning("AI导演失败, 降级信号融合: %s", e)

    return None


# ══════════════════════════════════════════════════════════
# 统一入口: 所有信号 → 导演决策
# ══════════════════════════════════════════════════════════

def direct(
    script_type: str,
    semantic_segments: list[dict],
    audio_segments: list[dict] = None,
    whisper_gaps: list[dict] = None,
    video_scenes: list[dict] = None,
    editing_rules: list = None,
    use_ai: bool = True,
) -> DirectorPlan:
    """
    统一导演入口。

    流程:
    1. 信号融合 (本地·确定性)
    2. AI导演决策 (DeepSeek·综合判断, 优先)
    3. 降级: 信号融合结果直接作为导演计划

    这是"打配合"的API — 所有分析模块的结果在这里汇合。
    """
    audio_segments = audio_segments or []
    whisper_gaps = whisper_gaps or []
    video_scenes = video_scenes or []
    editing_rules = editing_rules or []

    # Step 1: 信号融合 (确定性聚合)
    fused = fuse_signals(
        script_type, semantic_segments, audio_segments,
        whisper_gaps, video_scenes, editing_rules,
    )

    # Step 2: AI导演 (DeepSeek综合判断)
    if use_ai:
        sem_summary = json.dumps([
            {"t": s.get("text",""), "r": s.get("role",""), "v": s.get("visual_need","")}
            for s in semantic_segments[:8]
        ], ensure_ascii=False)
        audio_summary = json.dumps(audio_segments[:8], ensure_ascii=False)
        video_summary = json.dumps(video_scenes[:6], ensure_ascii=False)
        rules_summary = json.dumps([
            {"role": s.segment_role, "shot": s.shot_type} for s in fused.segments[:6]
        ], ensure_ascii=False)

        ai_plan = ai_director_decision(
            script_type, sem_summary, audio_summary, video_summary, rules_summary,
        )

        if ai_plan and ai_plan.get("segments"):
            # AI导演覆盖信号融合结果
            fused.segments = []
            for s in ai_plan.get("segments", []):
                fused.segments.append(DirectorDecision(
                    start_sec=s.get("start", 0),
                    duration_sec=s.get("duration", 3.0),
                    script_text=s.get("script", ""),
                    audio_text=s.get("audio_actual", ""),
                    segment_role="body",
                    shot_type=s.get("shot", "MS"),
                    camera_move=s.get("camera", "static"),
                    is_broll=s.get("broll", False),
                    broll_visual=s.get("broll_visual", ""),
                    visual_source="ai_director",
                    text_overlay=s.get("text", ""),
                    text_animation=s.get("text_anim", "fade_in"),
                    text_position="center",
                    audio_action=s.get("audio_action", "keep"),
                    is_golden_moment=s.get("golden", False),
                    emphasis_effect="AI导演标注",
                    transition_in="cut",
                    transition_out=s.get("transition", "cut"),
                    confidence=0.9,
                    decision_basis=s.get("reason", "AI综合判断"),
                ))
            fused.editing_style = ai_plan.get("editing_style", "")
            fused.emotional_arc = ai_plan.get("emotional_arc", fused.emotional_arc)
            fused.color_grade = ai_plan.get("color_grade", "neutral")
            fused.bgm_recommendation = ai_plan.get("bgm", "")

    return fused


def direct_to_execution_job(plan: DirectorPlan, audio_slots=None, video_slots=None):
    """导演计划 → ExecutionJob (可直接送入执行管线)"""
    from .execution_engine import ExecutionJob
    from .sentence_editor import ScriptSentence

    sentences = []
    for d in plan.segments:
        sentences.append(ScriptSentence(
            index=len(sentences) + 1,
            text=d.script_text or d.audio_text,
            start_sec=d.start_sec,
            duration_sec=d.duration_sec,
            required_material="talking_head" if not d.is_broll else "product_closeup",
            required_shot=d.shot_type,
            required_camera=d.camera_move,
            text_overlay=d.text_overlay,
            text_position=d.text_position,
            is_broll=d.is_broll,
        ))

    job = ExecutionJob(
        job_id=f"director_{plan.script_type}_{len(plan.segments)}seg",
        script_text=" ".join(s.text for s in sentences),
        script_type=plan.script_type,
        audio_slots=audio_slots or {},
        video_slots=video_slots or {},
    )
    job.sentences = sentences
    job.enhancement_report["director_plan"] = {
        "emotional_arc": plan.emotional_arc,
        "golden_moments": plan.golden_moments,
        "editing_style": plan.editing_style,
        "color_grade": plan.color_grade,
        "bgm": plan.bgm_recommendation,
    }

    return job
