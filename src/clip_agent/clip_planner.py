"""剪辑方案生成器 v3 · 对接编辑引擎 + 脚本类型驱动剪辑策略"""
from __future__ import annotations
import concurrent.futures, logging, re
from dataclasses import dataclass, field
from pathlib import Path
logger = logging.getLogger(__name__)

@dataclass
class VideoSegment:
    segment_id: int; section: str; sub_type: str; label: str
    material_index: int; material_filename: str; start_sec: float; duration_sec: float
    shot_type: str="MS"; camera_move: str="static"; composition: str="rule_of_thirds"
    color_tone: str="warm"; transition_in: str="cut"; transition_out: str="cut"
    covers_audio: bool=False; description: str=""; action_guide: str=""
    has_subtitle: bool=True; subtitle_text: str=""; subtitle_position: str="bottom"

@dataclass
class ClipPlan:
    plan_id: int; plan_name: str; plan_style: str; template_key: str
    opening_duration: float=3.0; body_duration: float=0.0; ending_duration: float=3.0
    total_duration: float=0.0; visual_strategy: str="good_presence"; strategy_reason: str=""
    voiceover_duration: float=0.0; voiceover_available: bool=False
    bgm_style: str=""; bgm_suggestion: str=""; bgm_volume_ratio: float=0.33
    segments: list[VideoSegment]=field(default_factory=list)
    summary: str=""; difficulty: str="简单"; estimated_time: str=""
    draft_path: str=""; exported_video: str=""
    deep_annotation_count: int=0; shot_count: int=0; review_score: float=0.0
    bgm_recommendations: list[str]=field(default_factory=list)
    breath_report: any=None; breath_broll_points: list=field(default_factory=list)

def generate_clip_plans(analysis, user_intent="", plan_count=2, provider="", model=""):
    from app.services.clip_agent.clip_templates import get_template, auto_select_template, VISUAL_STRATEGIES
    if not analysis.analyses: raise ValueError("没有可用的素材分析结果")
    template_key = auto_select_template([a.scene_type for a in analysis.analyses], user_intent)
    template = get_template(template_key) or get_template("老板IP")
    engine_failed_reason = ""
    if analysis.main_video_path and Path(analysis.main_video_path).exists():
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                plan = ex.submit(_generate_via_orchestrator, analysis, user_intent).result(timeout=300)
            if plan and plan.segments:
                logger.info("引擎方案: %d镜头", len(plan.segments))
                # 质量审查(引擎成功时运行)
                try: plan = quality_review_and_optimize(plan, analysis, max_iterations=1)
                except Exception: logger.debug("质量审查跳过", exc_info=True)
                plans = [plan]
                if plan_count>=2:
                    try:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                            alt = ex.submit(_generate_via_orchestrator, analysis, user_intent, True).result(timeout=120)
                        if alt and alt.segments: alt.plan_id=2; alt.plan_name+=" · 快速版"; plans.append(alt)
                    except Exception: logger.debug("替代方案生成跳过", exc_info=True)
                if plan_count>=3 and analysis.has_talking_head:
                    alt_sk = "script_reading" if plan.visual_strategy=="good_presence" else "mixed"
                    fb = _fallback_plan(analysis, template, template_key, len(plans)+1, strategy_key=alt_sk)
                    fb.plan_name = f"{template.get('name','')} · {VISUAL_STRATEGIES[alt_sk].label}版"
                    plans.append(fb)
                return plans
            else: engine_failed_reason = "引擎返回空方案"
        except concurrent.futures.TimeoutError: engine_failed_reason = "引擎超时(>300s)"
        except Exception as e: engine_failed_reason = f"引擎异常: {type(e).__name__}"; logger.exception("引擎失败")
    strategies = _pick_strategies(analysis, plan_count)
    plans = []
    for i, sk in enumerate(strategies):
        p = _fallback_plan(analysis, template, template_key, i+1, strategy_key=sk)
        if engine_failed_reason: p.summary = f"[模板·{VISUAL_STRATEGIES[sk].label}] {p.summary} ({engine_failed_reason})"
        plans.append(p)
    return plans

def _pick_strategies(analysis, count):
    has_t, has_b = analysis.has_talking_head, any(not a.has_face for a in analysis.analyses)
    if has_t and has_b: return ["good_presence","mixed","script_reading"][:count]
    elif has_t: return ["good_presence","script_reading"][:count]
    return ["script_reading"][:count]

def _generate_via_orchestrator(analysis, user_intent="", fast_mode=False):
    from app.services.edit_orchestrator import run_full_edit
    mv = analysis.main_video_path
    if not mv or not Path(mv).exists(): return None
    bp = analysis.broll_paths + analysis.image_paths
    try:
        result = run_full_edit(video_path=mv, broll_paths=bp if bp else None, script_context=user_intent or "", portrait=True, project_name=f"AI剪辑_{Path(mv).stem}", fast_mode=fast_mode, turbo=False)
        if not result.success: return None
        plan = _map_edit_result_to_plan(result, analysis, fast_mode)
        if not fast_mode and plan.segments:
            try:
                from app.services.clip_agent.breath_detector import BreathDetector
                br = BreathDetector().analyze(Path(mv)); plan.breath_report = br
                if br.best_cuts or br.good_cuts:
                    bpts = BreathDetector().get_optimal_broll_points(br, count=sum(1 for s in plan.segments if s.sub_type=="broll"), min_gap_sec=3.0)
                    plan.breath_broll_points = bpts
            except Exception as e: logger.warning("气口跳过: %s", e)
        return plan
    except Exception as e: logger.exception("引擎异常"); return None

def _map_edit_result_to_plan(result, analysis, fast_mode=False):
    from app.services.clip_agent.media_analyzer import MaterialAnalysis
    td = analysis.voiceover_duration or 30.0
    od = min(3.5, td*0.1); ed = min(3.5, td*0.1); bd = td-od-ed if td>od+ed else td
    cmds = result.director_commands or []
    has_t = any(c.get("action") in ("open_hook","keep_talking","emotional_peak","close") for c in cmds)
    has_b = any(c.get("action")=="cut_to_broll" for c in cmds)
    strategy = "mixed" if (has_b and len([c for c in cmds if c.get("action")=="cut_to_broll"])>len(cmds)*0.5) else ("good_presence" if has_t else "script_reading")
    segs, cur, sid = [], 0.0, 0
    for cmd in cmds:
        a = cmd.get("action",""); d = float(cmd.get("duration_sec",3.0)); si = int(cmd.get("shot_id",0)); r = cmd.get("reason","")
        if a=="open_hook": sec, st, lb = "opening","talking","开头钩子"
        elif a in ("keep_talking","emotional_peak"): sec, st, lb = "body","talking","口播主体" if a=="keep_talking" else "情感高潮"
        elif a=="cut_to_broll": sec, st, lb = "body","broll","空镜覆盖"
        elif a=="transition": sec, st, lb = "body","broll","转场"
        elif a=="close": sec, st, lb = "ending","talking","结尾CTA"
        else: sec, st, lb = "body","talking",a
        mi = max(0, min(si, len(analysis.analyses)-1)) if analysis.analyses else 0
        mat = analysis.analyses[mi] if mi<len(analysis.analyses) else MaterialAnalysis(filename="口播",file_type="video",scene_type="人物")
        sid += 1
        segs.append(VideoSegment(segment_id=sid,section=sec,sub_type=st,label=lb,material_index=mi,material_filename=mat.filename,start_sec=cur,duration_sec=d,shot_type="CU" if a in ("open_hook","emotional_peak") else "MS",camera_move="static" if st=="talking" else "push_in",composition="center" if a=="open_hook" else "rule_of_thirds",color_tone="high_contrast" if a=="open_hook" else "warm",transition_in="fade_in" if a=="open_hook" else "cut",transition_out="dissolve" if a=="close" else "cut",covers_audio=(st=="broll"),description=r or f"导演决策:{a}",action_guide="保留配音" if st=="broll" else ""))
        cur += d
    bl = result.bgm_recommendations or []
    plan = ClipPlan(plan_id=1, plan_name=f"AI智能剪辑{'(快速版)' if fast_mode else ''}", plan_style=result.director_story or "AI全自动剪辑", template_key="团购售卖", opening_duration=od, body_duration=bd, ending_duration=ed, total_duration=cur if segs else td, visual_strategy=strategy, strategy_reason=f"引擎:{result.shot_count}镜→{result.deep_annotation_count}标注", voiceover_duration=td, voiceover_available=analysis.has_talking_head, bgm_suggestion=bl[0] if bl else "轻快电子", segments=segs, summary=result.director_story or "全自动剪辑", draft_path=result.draft_path, exported_video=result.exported_video, deep_annotation_count=result.deep_annotation_count, shot_count=result.shot_count, review_score=result.review_score, bgm_recommendations=bl)
    if not plan.segments:
        from app.services.clip_agent.clip_templates import get_template
        fb = _fallback_plan(analysis, get_template("团购售卖") or {}, "团购售卖", 1)
        plan.segments = fb.segments; plan.total_duration = fb.total_duration
    return plan

def _fallback_plan(analysis, template, template_key, plan_id, strategy_key=""):
    from app.services.clip_agent.clip_templates import VISUAL_STRATEGIES
    if not strategy_key: strategy_key = "good_presence" if analysis.has_talking_head else "script_reading"
    strategy = VISUAL_STRATEGIES.get(strategy_key, VISUAL_STRATEGIES["good_presence"])
    dna = template.get("editing_dna", {})
    sd = dna.get("shot_duration", {"min":1.5,"max":6.0,"typical":3.0})
    pref_cam = dna.get("preferred_camera", ["static"])
    dna_broll = dna.get("broll_density", strategy.broll_ratio)
    trans_pref = dna.get("transition", "cut")
    pace = dna.get("pace", "")
    rt = template.get("retention_timeline", [])
    analyses = analysis.analyses
    if not analyses:
        plan = ClipPlan(plan_id=plan_id, plan_name="基础方案", plan_style="无素材", template_key=template_key, total_duration=30, summary="未检测到可用素材")
        plan.segments = [VideoSegment(segment_id=1, section="body", sub_type="broll", label="请上传素材", material_index=0, material_filename="无", start_sec=0, duration_sec=30)]
        return plan
    ht, vd = analysis.has_talking_head, analysis.voiceover_duration or 30.0
    od, ed, bd = min(3.0, vd*0.1), min(3.5, vd*0.1), vd
    bm = [a for a in analyses if not a.has_face]; tm = [a for a in analyses if a.has_face]
    if not bm: bm = analyses
    if not tm: tm = analyses
    plan = ClipPlan(plan_id=plan_id, plan_name=f"{template.get('name','')} · {strategy.label}", plan_style=f"{pace or template.get('desc','')[:40]}", template_key=template_key, opening_duration=od, body_duration=bd, ending_duration=ed, visual_strategy=strategy_key, strategy_reason=f"模板:{template.get('script_type','')} | {sd['typical']}s/镜 | {','.join(pref_cam[:2])} | {trans_pref}", voiceover_duration=vd, voiceover_available=ht, bgm_style=template.get("bgm_style",""), bgm_suggestion=_get_bgm_for_plan(template), summary=f"{template.get('name','')}·{strategy.label}: {pace or ''} (开头{od}s→介绍{bd}s→结尾{ed}s)", difficulty="简单", estimated_time="15分钟")
    try: plan.bgm_recommendations = _get_bgm_list(template)
    except Exception: logger.debug("BGM推荐获取跳过", exc_info=True)
    LAST_SHOT = None  # 蒙太奇规则: 追踪上一个镜头景别
    sid, cur = 0, 0.0
    om = tm[0] if tm else bm[0]; sid += 1
    plan.segments.append(VideoSegment(segment_id=sid,section="opening",sub_type="talking" if om.has_face else "broll",label="开头钩子",material_index=analyses.index(om),material_filename=om.filename,start_sec=cur,duration_sec=od,shot_type="CU",camera_move=pref_cam[0],composition="center",color_tone="high_contrast",transition_in="fade_in",transition_out="cut" if "cut" in trans_pref else "dissolve",description=dna.get("opening","开场抓注意力"),action_guide="稳住镜头",has_subtitle=True,subtitle_position="center"))
    LAST_SHOT = "CU"; cur += od
    br_r = dna_broll; bsc = max(3, template.get("min_shots",5)-2); rt_rem = bd*(1-br_r); rb_rem = bd*br_r
    # 按留存时间线分配B-roll
    broll_times = [r["at_sec"] for r in rt if r["at_sec"]>0 and r["at_sec"]<bd]
    for bi in range(bsc):
        is_t = (bi%2==0 and rt_rem>0.5) or rb_rem<=0
        dur = min(rt_rem if is_t else rb_rem, bd/bsc*1.5)
        if is_t: rt_rem-=dur; st,lb,cv="talking","口播——保留出镜",False; mat=tm[bi%len(tm)]
        else: rb_rem-=dur; st,lb,cv="broll","空镜——覆盖画面",True; mat=bm[bi%len(bm)]
        if dur<0.5: continue
        # 气口对齐: 如果有留存时间线,把B-roll放在最近的留存点
        if cv and broll_times:
            nearest = min(broll_times, key=lambda t: abs(t-cur))
            if abs(nearest-cur)<2.0: cur = nearest
        sid+=1
        act = "保留出镜+声音" if not cv else "空镜覆盖画面(保留配音)"
        cam = pref_cam[bi%len(pref_cam)]
        # 蒙太奇: 相邻镜头必须变化景别
        if st=="talking":
            shot_opts = ["MS","MCU","CU","MLS"]
            shot_type = next((s for s in shot_opts if s!=LAST_SHOT), "MS")
        else:
            shot_opts = ["CU","ECU","MS"]
            shot_type = next((s for s in shot_opts if s!=LAST_SHOT), "CU")
        LAST_SHOT = shot_type
        plan.segments.append(VideoSegment(segment_id=sid,section="body",sub_type=st,label=lb,material_index=analyses.index(mat),material_filename=mat.filename,start_sec=cur,duration_sec=round(dur,1),shot_type=shot_type,camera_move=cam,composition="rule_of_thirds" if st=="talking" else "center",color_tone="warm" if st=="talking" else "vibrant",transition_in="cut",transition_out="cut",covers_audio=cv,description=act,has_subtitle=True,subtitle_position="bottom" if st=="talking" else "center"))
        cur+=dur
    em=tm[-1] if tm else bm[-1]; sid+=1
    plan.segments.append(VideoSegment(segment_id=sid,section="ending",sub_type="talking" if em.has_face else "broll",label="结尾CTA",material_index=analyses.index(em),material_filename=em.filename,start_sec=cur,duration_sec=ed,shot_type="MS",camera_move="pull_out",composition="rule_of_thirds",color_tone="warm",transition_in="cut",transition_out="fade_out",description=dna.get("ending","收尾引导"),action_guide="镜头拉远",has_subtitle=True,subtitle_position="center"))
    plan.total_duration = sum(s.duration_sec for s in plan.segments)
    return plan

def _get_bgm_for_plan(template):
    try:
        from app.services.bgm_library import recommend_bgm
        m = {"快节奏卡点/电子":"快节奏卡点","温暖/治愈/钢琴":"情感治愈","轻松/生活化/节奏感":"餐饮美食","大气/科技感/轻电子":"产品带货","lo-fi/轻电子/专注":"口播讲故事","大气/温暖/管弦":"企业宣传/品牌","轻快/治愈/acoustic/indie":"生活Vlog"}
        tracks = recommend_bgm(script_category=m.get(template.get("bgm_style",""),"口播讲故事"))
        return tracks[0].name if tracks else template.get("bgm_style","轻快")
    except Exception: return template.get("bgm_style","轻快")

def _get_bgm_list(template):
    try:
        from app.services.bgm_library import recommend_bgm
        m = {"快节奏卡点/电子":"快节奏卡点","温暖/治愈/钢琴":"情感治愈","轻松/生活化/节奏感":"餐饮美食","大气/科技感/轻电子":"产品带货","lo-fi/轻电子/专注":"口播讲故事","大气/温暖/管弦":"企业宣传/品牌","轻快/治愈/acoustic/indie":"生活Vlog"}
        return [t.name for t in recommend_bgm(script_category=m.get(template.get("bgm_style",""),"口播讲故事"))]
    except Exception: return []


def quality_review_and_optimize(plan, analysis, max_iterations=2, min_score=7.0):
    """质量审查闭环(借鉴auto-vid-editor): Kimi审片→低于阈值自动优化→再审查"""
    try:
        from app.services.model_config import get_model_name
        from app.services.gateway_client import chat_via_gateway

        best_plan = plan
        best_score = plan.review_score if plan.review_score > 0 else 0.0

        for iteration in range(max_iterations):
            # 构建审查prompt
            segs_summary = "; ".join(
                f"[{s.section}]{s.label}({s.duration_sec}s,{s.shot_type},{'B-roll覆盖' if s.covers_audio else '口播'})"
                for s in best_plan.segments[:8]
            )
            review_prompt = f"""作为资深剪辑导演，审查以下AI生成的剪辑方案。

## 方案信息
- 模板: {best_plan.template_key} | 策略: {best_plan.visual_strategy}
- 总时长: {best_plan.total_duration:.0f}s | {len(best_plan.segments)}镜
- 镜头序列: {segs_summary}
- BGM: {best_plan.bgm_suggestion} | 音量: {int(best_plan.bgm_volume_ratio*100)}%

## 评分标准(每项1-10分)
1. 结构完整性: 开头→展开→高潮→收尾 是否完整
2. 节奏匹配度: 镜长是否符合模板风格
3. 蒙太奇运用: 相邻景别是否变化,J-cut/L-cut是否恰当
4. B-roll覆盖: 空镜插入时机是否自然
5. 综合评分

## 输出格式(严格JSON)
{{"structure":分数,"rhythm":分数,"montage":分数,"broll":分数,"overall":分数,"suggestions":["改进建议1","改进建议2"]}}

只返回JSON,不要其他文字。"""

            result = chat_via_gateway(
                provider="kimi", model=get_model_name("kimi"),
                system="你是资深剪辑导演。只返回JSON评分,不要其他文字。",
                user=review_prompt, temperature=0.3, max_tokens=400,
            )
            content = result.get("content", "")
            import re, json
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                break
            review = json.loads(match.group(0))
            score = float(review.get("overall", 0))
            logger.info("质量审查#%d: %.1f分 (结构%.0f/节奏%.0f/蒙太奇%.0f/B-roll%.0f)",
                       iteration+1, score,
                       review.get("structure",0), review.get("rhythm",0),
                       review.get("montage",0), review.get("broll",0))

            if score > best_score:
                best_score = score
                best_plan.review_score = score
                best_plan.strategy_reason += f" | 审片{score:.1f}分"

            # 达到阈值或最后一次迭代→停止
            if score >= min_score or iteration >= max_iterations-1:
                break

            # 低于阈值→尝试优化
            suggestions = review.get("suggestions", [])
            if suggestions and "节奏" in str(suggestions):
                # 调整镜长
                for seg in best_plan.segments:
                    if "快" in str(suggestions) and seg.duration_sec > 5:
                        seg.duration_sec *= 0.8
                    elif "慢" in str(suggestions) and seg.duration_sec < 2:
                        seg.duration_sec *= 1.3
            if suggestions and "蒙太奇" in str(suggestions):
                # 强制相邻景别变化
                for i in range(1, len(best_plan.segments)):
                    if best_plan.segments[i].shot_type == best_plan.segments[i-1].shot_type:
                        best_plan.segments[i].shot_type = {"CU":"MS","MS":"CU","MCU":"MS","LS":"MS"}.get(
                            best_plan.segments[i].shot_type, "MS")

        best_plan.review_score = best_score
        return best_plan
    except Exception as e:
        logger.warning("质量审查跳过: %s", e)
        return plan
