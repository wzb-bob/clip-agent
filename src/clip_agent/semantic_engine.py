"""
语义理解引擎 v1 · 脚本→情感弧线→智能编辑决策

替换硬编码关键词匹配, 用DeepSeek LLM真正理解:
  1. 脚本说了什么 (语义结构)
  2. 每句话在干什么 (情感弧线·关键瞬间)
  3. 哪里该插什么画面 (语义匹配·非关键词)

依赖: DeepSeek API (gateway_client)
降级: 无API时回退到关键词规则引擎
"""
from __future__ import annotations
import json, logging, re, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SemanticSegment:
    """一个经过语义理解的脚本段落"""
    index: int
    text: str
    # 语义角色
    role: str                # hook/product_reveal/process/value_proof/cta/transition
    emotion: str             # urgent/excited/calm/trust/surprise/warm
    intensity: int           # 1-10 情绪强度
    # 画面需求
    visual_need: str         # "产品特写·虾腮白色·汤汁淋漓" 具体的画面描述
    shot_type: str           # CU/MCU/MS/LS
    broll_needed: bool
    text_overlay: str        # 建议叠加的文字
    text_position: str       # center/bottom/top
    # 时间
    duration_sec: float
    start_sec: float = 0.0


@dataclass
class ScriptSemanticAnalysis:
    """整个脚本的语义分析结果"""
    script_type: str
    script_text: str
    emotional_arc: str = ""       # "紧急开场→产品展示→信任建立→紧迫收尾"
    key_moments: list[dict] = field(default_factory=list)
    tone_shifts: list[dict] = field(default_factory=list)
    broll_suggestions: list[dict] = field(default_factory=list)
    segments: list[SemanticSegment] = field(default_factory=list)
    total_duration: float = 0.0


# ══════════════════════════════════════════════════════════
# 语义分析 Prompt
# ══════════════════════════════════════════════════════════

SEMANTIC_ANALYSIS_PROMPT = """分析短视频脚本,返回JSON编辑方案。字段不可省略。

脚本类型:{script_type}
脚本内容:{script_text}

JSON格式(严格):
{{"emotional_arc":"一句话情感弧线","key_moments":[{{"at_sec":0,"type":"price_reveal","intensity":9}}],"tone_shifts":[],"broll_suggestions":[{{"at_sec":3.0,"description":"画面描述"}}],"segments":[{{"index":1,"text":"原文","role":"hook|product_reveal|process|value_proof|cta|transition","emotion":"urgent|excited|calm|trust|surprise|warm","intensity":8,"visual_need":"具体画面描述","shot_type":"CU|MCU|MS|LS","broll_needed":false,"text_overlay":"","text_position":"center","duration_sec":2.5}}],"total_duration":30.0}}

只返回JSON。"""


def _repair_json(raw: str) -> str:
    """修复LLM生成JSON的常见错误: 尾逗号, 缺失引号, 截断补全"""
    # 0. 去掉markdown代码块
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r'^```\w*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw)
    # 1. 移除尾逗号 (在 ] 或 } 之前)
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    # 2. 修复缺失引号的key (word: → "word":)
    raw = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', raw)
    # 3. 截断修复: 找到最后一个完整的数组/对象结束
    # 如果JSON在中途截断, 补全缺失的括号
    open_braces = raw.count('{') - raw.count('}')
    open_brackets = raw.count('[') - raw.count(']')
    raw = raw.rstrip(',\n\r\t ')
    raw += '}' * open_braces + ']' * open_brackets
    return raw


def analyze_script_semantic(
    script_text: str,
    script_type: str = "团购售卖",
    provider: str = "",
    model: str = "",
) -> ScriptSemanticAnalysis | None:
    """
    核心: 用LLM深度理解脚本语义, 返回结构化编辑方案。

    相比旧版关键词匹配的质变:
    - 旧: if '块' in text → '产品句'  (只看关键词)
    - 新: LLM理解'68块!十只活虾!' → {role:'price_reveal', emotion:'urgent', intensity:9, visual_need:'产品特写CU·活虾特写·强调新鲜'}

    Returns None on API failure → caller should fallback to keyword rules.
    """
    # 清理脚本: 移除多余空白
    script_text = script_text.strip()
    if len(script_text) < 5:
        return None

    prompt = SEMANTIC_ANALYSIS_PROMPT.format(
        script_type=script_type,
        script_text=script_text,
    )

    try:
        # 尝试通过gateway_client调用DeepSeek
        from ._imports import chat_via_gateway, get_model_name

        if not chat_via_gateway or not get_model_name:
            logger.warning("gateway_client不可用 — 降级为关键词规则")
            return None

        model_name = model or get_model_name("deepseek") or "deepseek-v4-flash"

        t0 = time.time()
        result = chat_via_gateway(
            provider=provider or "deepseek",
            model=model_name,
            system="你是短视频剪辑导演。只返回JSON。不要markdown。不要额外文字。",
            user=prompt,
            temperature=0.1,
            max_tokens=4000,  # 长脚本需要更多token
        )

        content = result.get("content", "") if isinstance(result, dict) else str(result)
        elapsed = time.time() - t0

        # 提取JSON + 修复常见LLM错误
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            logger.warning("LLM未返回有效JSON: %s...", content[:100])
            return None

        raw_json = json_match.group(0)
        # 修复: 尾逗号/缺失引号/多余文字
        raw_json = _repair_json(raw_json)
        data = json.loads(raw_json)
        logger.info("语义分析完成: %s·%d句·%.1fs", script_type, len(data.get("segments", [])), elapsed)

        return _parse_semantic_result(data, script_type, script_text)

    except Exception as e:
        logger.warning("语义分析失败(%s), 降级关键词规则", e)
        return None


def _parse_semantic_result(data: dict, script_type: str, script_text: str) -> ScriptSemanticAnalysis:
    """解析LLM返回的JSON → ScriptSemanticAnalysis"""
    segments = []
    cur_sec = 0.0

    for seg_data in data.get("segments", []):
        dur = seg_data.get("duration_sec", 3.0)
        seg = SemanticSegment(
            index=seg_data.get("index", len(segments) + 1),
            text=seg_data.get("text", ""),
            role=seg_data.get("role", "transition"),
            emotion=seg_data.get("emotion", "calm"),
            intensity=seg_data.get("intensity", 5),
            visual_need=seg_data.get("visual_need", ""),
            shot_type=seg_data.get("shot_type", "MS"),
            broll_needed=seg_data.get("broll_needed", False),
            text_overlay=seg_data.get("text_overlay", ""),
            text_position=seg_data.get("text_position", "bottom"),
            duration_sec=dur,
            start_sec=round(cur_sec, 1),
        )
        segments.append(seg)
        cur_sec += dur

    return ScriptSemanticAnalysis(
        script_type=script_type,
        script_text=script_text,
        emotional_arc=data.get("emotional_arc", ""),
        key_moments=data.get("key_moments", []),
        tone_shifts=data.get("tone_shifts", []),
        broll_suggestions=data.get("broll_suggestions", []),
        segments=segments,
        total_duration=data.get("total_duration", cur_sec),
    )


# ══════════════════════════════════════════════════════════
# 语义→ExecutionJob 转换
# ══════════════════════════════════════════════════════════

def apply_semantic_to_job(analysis: ScriptSemanticAnalysis, audio_slots=None, video_slots=None):
    """
    将语义分析结果直接转换为ExecutionJob — 完全替代旧的关键词解析。

    对比:
    - 旧: sentence_editor.parse_script_to_sentences() — 关键词规则
    - 新: semantic_engine.analyze_script_semantic() → apply_semantic_to_job() — AI理解
    """
    from .execution_engine import ExecutionJob
    from .sentence_editor import ScriptSentence

    # 将SemanticSegment转为ScriptSentence (兼容现有管线)
    sentences = []
    for seg in analysis.segments:
        s = ScriptSentence(
            index=seg.index,
            text=seg.text,
            start_sec=seg.start_sec,
            duration_sec=seg.duration_sec,
            required_material="talking_head" if not seg.broll_needed else "product_closeup",
            required_shot=seg.shot_type,
            required_camera="static" if not seg.broll_needed else "push_in",
            text_overlay=seg.text_overlay,
            text_position=seg.text_position,
            is_broll=seg.broll_needed,
        )
        sentences.append(s)

    job = ExecutionJob(
        job_id=f"semantic_{analysis.script_type}_{len(analysis.segments)}句_{int(time.time())}",
        script_text=analysis.script_text,
        script_type=analysis.script_type,
        audio_slots=audio_slots or {},
        video_slots=video_slots or {},
    )

    # 注入语义分析结果
    job.sentences = sentences
    job.enhancement_report["semantic_analysis"] = {
        "emotional_arc": analysis.emotional_arc,
        "key_moments": analysis.key_moments,
        "tone_shifts": analysis.tone_shifts,
        "broll_suggestions": analysis.broll_suggestions,
        "total_duration": analysis.total_duration,
    }

    return job


# ══════════════════════════════════════════════════════════
# 降级: 硬编码关键词规则 (当API不可用时)
# ══════════════════════════════════════════════════════════

def analyze_script_keywords(script_text: str, script_type: str = "团购售卖") -> ScriptSemanticAnalysis:
    """
    关键词规则降级 — 当LLM不可用时的保底方案。
    比旧版sentence_editor更完善: 加入了情感推断+画面建议。
    """
    sentences_raw = re.split(r'[。！？!?\n]', script_text)
    sentences_raw = [s.strip() for s in sentences_raw if len(s.strip()) >= 3]

    # 关键词集
    PRICE_KW = {"块","元","钱","价","只","斤","份","碗","盘","盒","优惠","便宜"}
    PROCESS_KW = {"泡","腌","煸","炒","煮","蒸","烤","炸","卤","工艺","技术","手法","秘方","配方"}
    ENV_KW = {"店","环境","来了","地址","定位","导航","门头","路","号","排队"}
    CTA_KW = {"左下","团购","点击","关注","抢","赶紧","快来","定位","优惠"}
    TRUST_KW = {"年","老店","回头","客户","口碑","评价","好吃","推荐"}
    HOOK_KW = {"!", "！","不看","错过","只此","独家","第一","最好","惊"}

    segments = []
    cur_sec = 0.0

    for i, text in enumerate(sentences_raw):
        duration = max(1.5, len(text) * 0.25 + 0.3)

        # 角色判断
        if i == 0 and any(kw in text for kw in HOOK_KW | PRICE_KW):
            role, emotion, intensity = "hook", "urgent", 8
            visual = "产品特写CU·价格冲击画面"
            shot = "CU"
            broll = False
            overlay = _extract_price(text)
        elif any(kw in text for kw in PRICE_KW):
            role, emotion, intensity = "product_reveal", "excited", 7
            visual = "产品特写CU·展示产品细节"
            shot = "CU"
            broll = True
            overlay = _extract_price(text)
        elif any(kw in text for kw in PROCESS_KW):
            role, emotion, intensity = "process", "calm", 5
            visual = "工艺过程特写·制作步骤展示"
            shot = "MCU"
            broll = True
            overlay = ""
        elif any(kw in text for kw in TRUST_KW):
            role, emotion, intensity = "value_proof", "trust", 4
            visual = "顾客反馈·口碑场景·店面氛围"
            shot = "MS"
            broll = True
            overlay = ""
        elif any(kw in text for kw in CTA_KW):
            role, emotion, intensity = "cta", "urgent", 8
            visual = "门头全景LS·CTA引导手势"
            shot = "LS" if any(kw in text for kw in ENV_KW) else "MS"
            broll = False
            overlay = "左下角·团购已上线" if "团购" in text else "点击关注"
        elif any(kw in text for kw in ENV_KW):
            role, emotion, intensity = "transition", "warm", 4
            visual = "环境空镜·店面展示"
            shot = "LS"
            broll = True
            overlay = ""
        elif i == len(sentences_raw) - 1:
            role, emotion, intensity = "cta", "urgent", 7
            visual = "半身口播MS·CTA结尾"
            shot = "MS"
            broll = False
            overlay = "赶紧来·左下角定位"
        else:
            role, emotion, intensity = "transition", "calm", 3
            visual = "口播MS"
            shot = "MS"
            broll = False
            overlay = ""

        segments.append(SemanticSegment(
            index=i + 1, text=text, role=role, emotion=emotion,
            intensity=intensity, visual_need=visual, shot_type=shot,
            broll_needed=broll, text_overlay=overlay,
            text_position="center" if overlay and len(overlay) < 8 else "bottom",
            duration_sec=round(duration, 1), start_sec=round(cur_sec, 1),
        ))
        cur_sec += duration

    return ScriptSemanticAnalysis(
        script_type=script_type, script_text=script_text,
        emotional_arc="规则推断",
        key_moments=[{"at_sec": s.start_sec, "type": s.role, "intensity": s.intensity}
                     for s in segments if s.intensity >= 7],
        segments=segments, total_duration=round(cur_sec, 1),
    )


def _extract_price(text: str) -> str:
    """提取价格信息用于叠加文字"""
    m = re.search(r'(\d+)\s*块', text)
    if m:
        return f"{m.group(1)}块!"
    m = re.search(r'(\d+)元', text)
    if m:
        return f"{m.group(1)}元"
    return ""


# ══════════════════════════════════════════════════════════
# 统一入口: LLM优先, 关键词降级
# ══════════════════════════════════════════════════════════

def analyze_script(script_text: str, script_type: str = "团购售卖",
                   use_ai: bool = True) -> ScriptSemanticAnalysis:
    """
    统一脚本分析入口。

    策略: LLM语义分析(DeepSeek) → 失败则降级关键词规则。
    关键词规则也比旧版更好: 加入了情感推断+画面建议。
    """
    if use_ai:
        result = analyze_script_semantic(script_text, script_type)
        if result and result.segments:
            return result
        logger.info("AI语义分析不可用, 降级关键词规则")

    return analyze_script_keywords(script_text, script_type)
