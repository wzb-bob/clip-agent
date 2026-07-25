"""
视觉-语义对齐器 v1 · 视频画面 → 脚本内容 智能匹配

核心问题: 脚本说"干煸技术"时，视频里哪段画面最配？
解决: Kimi场景描述 + GLM帧标注 + 脚本文本 → DeepSeek对齐

输入: 视频分析结果 + 脚本文本
输出: 每句脚本→最佳匹配的视频片段(具体时间·置信度)
"""
from __future__ import annotations
import json, logging, re, time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AlignedSegment:
    """一个已对齐的脚本段落→视频片段映射"""
    script_index: int
    script_text: str
    script_role: str           # hook/body/cta...
    video_start_sec: float     # 匹配到的视频起始时间
    video_end_sec: float
    video_description: str     # 匹配到的视频内容描述
    confidence: float          # 匹配置信度 0-1
    match_reason: str          # 为什么匹配


@dataclass
class AlignmentResult:
    """完整的对齐结果"""
    segments: list[AlignedSegment]
    overall_confidence: float
    unmatched_scripts: list[int]  # 没匹配到视频的脚本句索引
    unused_video_ranges: list[dict]  # 没被用到的视频片段


ALIGNMENT_PROMPT = """你是视频剪辑师。将以下脚本段落与视频片段做内容匹配。

## 脚本段落(每句需要匹配视频)
{script_segments}

## 可用的视频片段(含场景描述)
{video_scenes}

## 任务
为每句脚本匹配最合适的视频片段。考虑:
1. 语义匹配: 脚本说的内容和视频画面是否一致
2. 时长匹配: 视频片段时长是否足够覆盖脚本
3. 景别匹配: 脚本需要的景别和视频是否匹配
4. 情绪匹配: 画面色调/氛围和脚本情绪是否匹配

返回JSON:
{{"matches":[
  {{"script_idx":1,"video_start":0.0,"video_end":2.8,"confidence":0.9,"reason":"产品特写CU·画面和价格冲击匹配"}},
  ...
],"unmatched":[3],"unused_ranges":[{{"start":8.0,"end":10.0,"reason":"剩余空镜"}}]}}

只返回JSON。"""


def align_script_to_video(
    script_segments: list[dict],
    video_scenes: list[dict],
    script_type: str = "团购售卖",
) -> AlignmentResult | None:
    """
    主入口: 将脚本段落与视频片段做语义对齐。

    script_segments: [{"index":1,"text":"68块！十只活虾！","role":"hook","visual_need":"产品特写CU","shot_type":"CU"}]
    video_scenes: [{"at_sec":0.0,"description":"K2.6: 100%连续·3建议","engine":"kimi_k2.6","file":"素材.mp4"}]
    """
    if not script_segments or not video_scenes:
        return None

    try:
        from ._imports import chat_via_gateway, get_model_name
        if not chat_via_gateway:
            return _fallback_align(script_segments, video_scenes)

        # 构建prompt
        script_summary = json.dumps([
            {"idx": s.get("index", i+1), "text": s.get("text","")[:30],
             "role": s.get("role",""), "shot": s.get("shot_type","MS"),
             "visual": s.get("visual_need","")[:40]}
            for i, s in enumerate(script_segments[:8])
        ], ensure_ascii=False)

        video_summary = json.dumps([
            {"start": v.get("at_sec", i*3), "desc": v.get("description","")[:80],
             "engine": v.get("engine",""), "file": v.get("file","")}
            for i, v in enumerate(video_scenes[:5])
        ], ensure_ascii=False)

        prompt = ALIGNMENT_PROMPT.format(
            script_segments=script_summary,
            video_scenes=video_summary,
        )

        model = get_model_name("deepseek") or "deepseek-v4-flash"
        result = chat_via_gateway(
            provider="deepseek", model=model,
            system="你是视频剪辑师。只返回JSON。",
            user=prompt, temperature=0.1, max_tokens=1500,
        )

        content = result.get("content", "") if isinstance(result, dict) else str(result)
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if not m:
            return _fallback_align(script_segments, video_scenes)

        from .semantic_engine import _parse_json_safe, _repair_json
        data = _parse_json_safe(_repair_json(m.group(0)))
        if not data:
            return _fallback_align(script_segments, video_scenes)

        # 解析结果
        matches = data.get("matches", [])
        segments = []
        for m_item in matches:
            si = m_item.get("script_idx", 0)
            if 1 <= si <= len(script_segments):
                s = script_segments[si - 1]
                segments.append(AlignedSegment(
                    script_index=si,
                    script_text=s.get("text", ""),
                    script_role=s.get("role", ""),
                    video_start_sec=m_item.get("video_start", 0),
                    video_end_sec=m_item.get("video_end", 3.0),
                    video_description=m_item.get("reason", ""),
                    confidence=m_item.get("confidence", 0.7),
                    match_reason=m_item.get("reason", ""),
                ))

        confidences = [s.confidence for s in segments]
        return AlignmentResult(
            segments=segments,
            overall_confidence=round(sum(confidences)/len(confidences), 2) if confidences else 0,
            unmatched_scripts=data.get("unmatched", []),
            unused_video_ranges=data.get("unused_ranges", []),
        )

    except Exception as e:
        logger.debug("对齐AI失败,降级顺序匹配: %s", e)
        return _fallback_align(script_segments, video_scenes)


def _fallback_align(script_segments: list[dict], video_scenes: list[dict]) -> AlignmentResult:
    """降级: 按顺序匹配(简单但有效)"""
    segments = []
    total_video_dur = sum(v.get("duration", 3.0) for v in video_scenes) if video_scenes else 30
    cur_sec = 0.0

    for i, s in enumerate(script_segments):
        dur = s.get("duration_sec", 3.0)
        desc = ""
        for v in video_scenes:
            if cur_sec >= v.get("at_sec", 0):
                desc = v.get("description", "")[:60]

        segments.append(AlignedSegment(
            script_index=i + 1,
            script_text=s.get("text", ""),
            script_role=s.get("role", "body"),
            video_start_sec=round(cur_sec, 1),
            video_end_sec=round(cur_sec + dur, 1),
            video_description=desc,
            confidence=0.5,
            match_reason="顺序匹配(降级)",
        ))
        cur_sec += dur

    return AlignmentResult(
        segments=segments,
        overall_confidence=0.4,
        unmatched_scripts=[],
        unused_video_ranges=[],
    )


def align_and_inject(alignment: AlignmentResult, job_segments: list) -> list:
    """将对齐结果注入到执行作业的句子中,更新其视频文件引用和时间"""
    for seg in alignment.segments:
        if seg.script_index <= len(job_segments):
            js = job_segments[seg.script_index - 1]
            js.start_sec = seg.video_start_sec
            js.duration_sec = seg.video_end_sec - seg.video_start_sec
            if seg.match_reason and seg.match_reason != "顺序匹配(降级)":
                js.description += f" [AI对齐: {seg.match_reason[:20]}]"

    return job_segments
