"""素材分析器 v4 · 三阶段Kimi K2.6驱动: 分类→深度分析→编辑决策 · 模型从model_config读取"""
from __future__ import annotations
import base64, json, logging, os, subprocess
from dataclasses import dataclass, field
from pathlib import Path
logger = logging.getLogger(__name__)
MAX_IMAGE_SIZE_MB=20; MAX_VIDEO_SIZE_MB=500
ALLOWED_IMAGE={"image/jpeg","image/png","image/jpg"}; ALLOWED_VIDEO={"video/mp4","video/quicktime","video/mov"}

@dataclass
class MediaFile: filename:str; file_type:str; mime_type:str; size_bytes:int; temp_path:str=""; thumbnail_base64:str=""
@dataclass
class MaterialAnalysis:
    filename:str; file_type:str; scene_type:str=""; content_summary:str=""; emotion_tone:str=""; quality_score:float=3.0
    suitable_for:list=field(default_factory=list); lighting:str=""; composition:str=""; has_text:bool=False; has_face:bool=False
    eye_contact:str=""; color_tone:str=""; tags:list=field(default_factory=list); issues:list=field(default_factory=list)
    start_sec:float=0.0; end_sec:float=0.0; duration:float=0.0; placement:str="any"; narrative_role:str=""; analysis_source:str="heuristic"
    # 编辑决策字段(K2.6专属)
    montage_potential:str=""; editing_action:str=""; broll_suggestion:str=""; transition_hint:str=""
    presence_quality:float=3.0; best_moment_sec:float=0.0; editability:str=""
@dataclass
class BatchAnalysisResult:
    files:list=field(default_factory=list); analyses:list=field(default_factory=list)
    overall_scene:str=""; recommended_template:str=""; suggested_bgm:str=""; total_duration_estimate:str=""; analysis_quality:str="heuristic"
    main_video_path:str=""; broll_paths:list=field(default_factory=list); image_paths:list=field(default_factory=list)
    has_talking_head:bool=False; voiceover_duration:float=0.0

def validate_file(fn,mt,sz):
    if mt in ALLOWED_IMAGE:
        if sz>MAX_IMAGE_SIZE_MB*1024*1024: return False,f"图片超过{MAX_IMAGE_SIZE_MB}MB"
        return True,""
    elif mt in ALLOWED_VIDEO:
        if sz>MAX_VIDEO_SIZE_MB*1024*1024: return False,f"视频超过{MAX_VIDEO_SIZE_MB}MB"
        return True,""
    return False,f"不支持格式: {mt}"

def _probe_video(p):
    try:
        r=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format","-show_streams",p],capture_output=True,text=True,timeout=15)
        if r.returncode==0:
            d=json.loads(r.stdout); fmt=d.get("format",{}); streams=d.get("streams",[])
            return {"duration":float(fmt.get("duration",0)),"has_audio":any(s.get("codec_type")=="audio" for s in streams)}
    except: pass
    return {"duration":0.0,"has_audio":False}

# ================================================================
# 三阶段分析提示词 — 精确到每个细节
# ================================================================

STAGE1_CLASSIFY_PROMPT="""你是顶级短视频公司的素材分类专家。看这一帧,3秒内精确分类。返回严格JSON。

## 必须从以下7种选一(不要用模糊词):
- talking_head: 人物出镜,正在面对镜头说话/讲解
- product_show: 产品/物品特写展示(美食/商品/工具等)
- environment: 环境/场景/空间(店内/门头/街道/自然)
- action_demo: 动作演示(制作过程/操作展示/运动)
- text_card: 纯文字/图表/PPT画面
- customer_reaction: 顾客/用户的使用反应
- waste: 废片(严重抖动/失焦/过曝/无意义画面)

## 辅助判断:
- 人脸占画面比例: >30%=近景(CU), 15-30%=中近景(MCU), <5%=远景
- 画面中是否有文字? 什么内容?
- 光线质量: 正常/偏暗/过曝/逆光
- 是否可以直接用于剪辑? 有什么问题?

## 输出(严格JSON,10秒内完成):
{"content_type":"talking_head","shot_size":"CU/MCU/MS/LS","has_face":true,"has_text":false,"text_content":"","lighting":"正常","quality_hint":4,"usable":true,"issues":[],"quick_note":"3字描述"}"""

STAGE2_DEEP_TALKING="""
你是抖音爆款视频导演。刚才分类为"人物口播"。现在看{frame_count}帧的时间序列,深度分析这段口播素材。

## 出镜表现力分析(1-5):
5分标准: 眼神始终看镜头+表情自然+有手势强调+语气有起伏+像朋友聊天
4分标准: 大部分时间看镜头+偶有僵硬+有基本手势
3分标准: 部分看镜头+部分看稿+表情偏平
2分标准: 明显念稿+眼神飘忽+无手势
1分标准: 全程低头读稿+表情僵硬+无法使用

## 必须精确判断:
1. 看镜头帧占比(0-100%): {frame_count}帧中有几帧在看镜头?
2. 是否有手势? 什么样的手势?(指/比划/挥手/无)
3. 表情变化: 前几帧什么表情→后几帧什么表情?
4. 说话节奏感: 快/中/慢? 有停顿吗?
5. 这个人的出镜风格更接近:
   - 真诚大气型(适合品牌故事)
   - 专业匠人型(适合工艺展示)
   - 亲切活泼型(适合引流转化)
   - 严肃说教型(不太适合抖音)
6. 这个口播素材的最佳使用方式:
   - 保留完整画面+声音(出镜效果好)
   - 画面可以部分被B-roll替换,但声音保留
   - 只保留声音,画面全部用B-roll覆盖(念稿感强)
   - 不适合使用

## 蒙太奇潜力:
- 这个镜头和前后的什么画面并列能产生新含义?
- 情绪高潮在哪个时间点?

## 输出(严格JSON):
{"person_performance":"自然出镜/部分僵硬/明显念稿","presence_quality":4.5,"eye_contact_ratio":0.8,"gesture_type":"强调手势/无手势/偶尔手势","expression_arc":"微笑→认真→微笑","speaking_rhythm":"快/中/慢","persona_style":"真诚大气/专业匠人/亲切活泼/严肃说教","editability":"保留完整/部分B-roll覆盖/全部B-roll覆盖/不适合","best_moment_frame":"第N帧(当...时)","montage_hint":"与前后的XX画面并列可产生YY效果","tags":["标签1","标签2"],"issues":["问题1"],"quality":4.5}"""

STAGE2_DEEP_PRODUCT="""
你是顶级电商视频导演。刚才分类为"产品展示"。现在看{frame_count}帧序列,深度分析这段产品素材。

## 产品展示力分析(1-5):
5分: 光线完美+角度诱人+细节清晰+有动态展示+让人想买
4分: 光线良好+角度合适+细节可见
3分: 基本可用+光线一般+角度单调
2分: 光线差/角度差/细节看不清
1分: 无法展示产品

## 必须精确判断:
1. 展示了产品的哪些角度? (正面/侧面/俯拍/细节/使用场景)
2. 有什么独特的视觉亮点? (颜色/质感/动态/对比)
3. 画面的景别: 特写(CU)/近景(MCU)/中景(MS)
4. 适合放在视频的哪个位置:
   - 开头钩子: 最有冲击力的角度,让人0.5秒就想看下去
   - 主体展示: 配合口播讲解产品特点
   - 结尾引导: 配合价格/CTA信息
   - 社交证明: 展示品质/细节

## 蒙太奇潜力:
- 这个产品画面的"钩子力"有多强?
- 和什么画面配合效果最好?

## 输出(严格JSON):
{"product_angle":"正面/侧面/细节/使用场景","visual_highlight":"颜色/质感/动态/对比","shot_size":"CU/MCU/MS","hook_power":4.5,"best_placement":"hook/body/outro/social_proof","montage_hint":"与XX画面配合最佳","quality":4.5,"tags":["标签"],"issues":[],"notes":"10字使用建议"}"""

STAGE2_DEEP_ENVIRONMENT="""
你是场景导演。刚才分类为"环境/场景"。看{frame_count}帧序列,深度分析这段环境素材。

## 环境展示力(1-5):
5分: 构图专业+光线好+有故事感+让人想去
4分: 展示清晰+光线可接受
3分: 基本可用

## 必须精确判断:
1. 展示的是什么环境? (店内/门头/街道/自然/工作间)
2. 画面信息量: 观众能从中了解到什么?
3. 景别: 全景(LS)/中景(MS)/特写(CU)
4. 是否有独特的视觉元素? (特色装饰/排队人群/独特氛围)
5. 适合什么用途:
   - 店面引流: 展示"值得来"
   - 氛围营造: 展示"有格调"
   - 过程记录: 展示"真实"
   - B-roll覆盖: 配合口播填充画面

## 输出(严格JSON):
{"scene_type":"店内/门头/街道/自然","info_value":"观众能看到什么(15字)","unique_element":"特色元素","shot_size":"LS/MS/CU","best_use":"引流/氛围/过程/broll","montage_hint":"与XX配合","quality":4.0,"tags":["标签"],"issues":[]}"""

STAGE3_EDIT_DECISION="""
你是最终剪辑决策者。综合前面的分析,做出精确的编辑决策。

## 基于素材分析结果:
- 素材类型: {content_type}
- 素材分析: {analysis_summary}

## 做出以下决策(每个都必须具体):
1. 这个素材在最终视频中的角色: hook(开头钩子)/body(主体)/broll(空镜覆盖)/outro(结尾)/waste(不用)
2. 建议使用时长: 精确到0.5秒
3. 是否需要调速: 正常/慢动作(0.5x-0.8x)/快进(1.2x-2x)
4. 入点转场: 硬切/淡入/叠化/甩镜头
5. 出点转场: 硬切/淡出/叠化
6. 是否需要稳定器/防抖处理
7. 是否需要调色: 原色/暖色加强/冷色/高对比/柔和
8. 文字叠加建议: 什么文字? 什么位置? 什么动画?
9. 音频处理: 保留原声/降低BGM/静音/替换为配音
10. 与前后镜头的蒙太奇关系

## 输出(严格JSON):
{"editing_role":"hook/body/broll/outro/waste","duration_sec":3.5,"speed":1.0,"transition_in":"cut","transition_out":"dissolve","stabilize":false,"color_grade":"原色","text_overlay":"","text_position":"bottom","text_animation":"fade_in","audio_action":"保留原声","montage_relation":"与下一个产品特写形成对比","confidence":0.9}"""

if __name__ == "__main__": print("Kimi K2.6 三阶段分析提示词就绪")


@dataclass
class MediaFile: filename:str; file_type:str; mime_type:str; size_bytes:int; temp_path:str=""; thumbnail_base64:str=""
@dataclass
class MaterialAnalysis:
    filename:str; file_type:str; scene_type:str=""; content_summary:str=""; emotion_tone:str=""; quality_score:float=3.0
    suitable_for:list=field(default_factory=list); lighting:str=""; composition:str=""; has_text:bool=False; has_face:bool=False
    eye_contact:str=""; color_tone:str=""; tags:list=field(default_factory=list); issues:list=field(default_factory=list)
    start_sec:float=0.0; end_sec:float=0.0; duration:float=0.0; placement:str="any"; narrative_role:str=""; analysis_source:str="heuristic"
@dataclass
class BatchAnalysisResult:
    files:list=field(default_factory=list); analyses:list=field(default_factory=list)
    overall_scene:str=""; recommended_template:str=""; suggested_bgm:str=""; total_duration_estimate:str=""; analysis_quality:str="heuristic"
    main_video_path:str=""; broll_paths:list=field(default_factory=list); image_paths:list=field(default_factory=list)
    has_talking_head:bool=False; voiceover_duration:float=0.0

def validate_file(fn,mt,sz):
    if mt in ALLOWED_IMAGE:
        if sz>MAX_IMAGE_SIZE_MB*1024*1024: return False,f"图片超过{MAX_IMAGE_SIZE_MB}MB"
        return True,""
    elif mt in ALLOWED_VIDEO:
        if sz>MAX_VIDEO_SIZE_MB*1024*1024: return False,f"视频超过{MAX_VIDEO_SIZE_MB}MB"
        return True,""
    return False,f"不支持格式: {mt}"

def _probe_video(p):
    try:
        r=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format","-show_streams",p],capture_output=True,text=True,timeout=15)
        if r.returncode==0:
            d=json.loads(r.stdout); fmt=d.get("format",{}); streams=d.get("streams",[])
            return {"duration":float(fmt.get("duration",0)),"has_audio":any(s.get("codec_type")=="audio" for s in streams)}
    except: pass
    return {"duration":0.0,"has_audio":False}

VISION_PROMPT="""作为专业电影剪辑师，精确分析这张画面的景别和蒙太奇潜力。返回严格JSON。

## 景别判断(必须精确,从以下7种选一):
- ELS(远景): 人物<画面10%, 环境为主, 展示空间关系
- LS(全景): 人物全身+环境, 展示动作/走位
- MLS(中全景): 膝盖以上, 多人对话/手势体态
- MS(中景): 腰部以上, 口播最常用——看清表情+手势
- MCU(中近景): 胸部以上, 强调情绪/关键信息
- CU(近景/特写): 面部或物体占满画面, 包袱爆发点/产品展示
- ECU(大特写): 眼睛/嘴唇/产品细节极致放大

## 景别判断规则(必须遵守):
1. 看人物占比: 人脸>50%画面→CU或MCU; 上半身→MS; 全身→LS; 人物很小→ELS
2. 看产品/物体: 单个产品充满画面→CU; 产品+环境→MS; 远景中产品→LS
3. 如果画面中同时有人物和产品,以主体为准

## 蒙太奇潜力评估(用于后续剪辑):
- 这个画面如果和前一个/后一个画面并列,能产生什么新的含义?
- 画面中的运动方向? 视线方向? 能否和下一个镜头形成匹配剪辑?
- 情绪基调是什么? 能否作为情感转折点?

## 输出格式(严格JSON):
{"content":"画面描述(15字)","shot_type":"CU/MCU/MS/MLS/LS/ELS/ECU","type":"talking_head/broll/text_card/empty/waste","emotion":"激动/平静/严肃/开心/疑惑/紧张/温馨","lighting":"自然光/棚拍/偏暗/过曝/正常","composition":"中心/偏左/偏右/留白多/紧凑/三分法","eye_contact":"看镜头/看别处/闭眼/不确定","color_tone":"暖色/冷色/中性/高对比/柔和","placement":"hook/body/outro/any","montage_value":"高/中/低——为什么这个镜头适合蒙太奇","visual_rhythm":"静态/慢移/快动/爆发——画面内在运动节奏","quality":4.5,"tags":["标签1","标签2"],"usable":true,"issues":[]}"""

def _call_vision_api(fb64, prompt_text="", ctx=""):
    """统一视觉调用——使用传入的专用prompt,默认用STAGE1分类"""
    import re
    from app.services.gateway_client import chat_vision
    p=prompt_text or STAGE1_CLASSIFY_PROMPT
    if ctx: p+=f"\n上下文:{ctx}"
    try:
        r=chat_vision(image_base64=fb64, prompt=p, system="你是顶级视频分析专家。只返回严格JSON。")
        c=r.get("content",""); m=re.search(r'\{.*\}',c,re.DOTALL)
        if m: return json.loads(m.group(0))
    except Exception as e: logger.warning("Vision失败: %s",e)
    return {}

def _vision_to_analysis(data,fn,ft):
    """将K2.6分析结果映射为MaterialAnalysis——含编辑决策字段"""
    src=data.get("analysis_source","heuristic")
    ct=data.get("content_type",data.get("type",""))
    quality=float(data.get("presence_quality",data.get("quality",3.0)))

    # 内容摘要——帧级精度用segments,旧版用单值
    segs=data.get("segments",[])
    if segs:
        content=f"{fn}: {len(segs)}段"
        first_seg=segs[0]
        last_seg=segs[-1]
        content+=f" | {first_seg.get('content_type','?')}→{last_seg.get('content_type','?')}"
        content+=f" | 质量{data.get('quality','?')}/5"
        content+=f" | 人脸{data.get('face_ratio',0):.0%} 看镜头{data.get('eye_contact_ratio',0):.0%}"
        notes=data.get("editing_notes","")
    else:
        content=data.get("content",f"{ft}:{fn}")
        best=data.get("best_moment",""); notes=data.get("notes","")
        if best: content=f"{content} | 高光:{best}"
    if notes: content=f"{content} | {notes}"

    # 编辑决策(K2.6专属)
    editing_role=data.get("editing_role","body")
    montage=data.get("montage_hint","")
    broll_sug=data.get("broll_suggestion","")
    trans_hint=data.get("transition_hint","")
    ed=data.get("editability","")

    # 出镜表现
    perf=data.get("person_performance","")
    has_face=perf not in ("","无人物") and str(data.get("eye_contact","")) not in ("","无人物")
    suitable=["body"]
    if "保留完整" in ed and has_face: suitable=["body","hook"]
    elif "部分B-roll" in ed: suitable=["body","broll"]
    elif "全部B-roll" in ed or "只取音频" in ed: suitable=["broll"]
    elif "不适合" in ed: suitable=[]

    return MaterialAnalysis(
        filename=fn,file_type=ft, scene_type=_map_ct(ct),
        content_summary=content, emotion_tone=data.get("emotion_arc",data.get("emotion","平静")),
        quality_score=quality, suitable_for=suitable,
        lighting=data.get("lighting","正常"), composition=data.get("composition","中心"),
        has_face=has_face, eye_contact=data.get("eye_contact",""),
        color_tone=data.get("color_tone","中性"), tags=data.get("tags",[]),
        issues=data.get("issues",[]), placement=data.get("placement","any"),
        analysis_source=src,
        montage_potential=montage, editing_action=editing_role,
        broll_suggestion=brol_sug, transition_hint=trans_hint,
        presence_quality=float(data.get("presence_quality",3.0)),
        best_moment_sec=float(data.get("best_moment_sec",0)),
        editability=ed,
    )

def _map_ct(ct): return {"talking_head":"人物","broll":"环境","text_card":"文字","empty":"空镜","waste":"废片","product_show":"产品","environment":"环境","action_demo":"动作","customer_reaction":"人物"}.get(ct,ct or "环境")


def _analyze_video(tp,fn,vu=""):
    """三阶段Kimi K2.6分析: Stage1分类→Stage2深度→Stage3编辑决策"""
    import re
    # 路径A: Kimi K2.6原生视频模型
    if vu:
        try:
            from app.services.gateway_client import chat_video
            combined_prompt=f"{STAGE1_CLASSIFY_PROMPT}\n\n---\n\n{STAGE3_EDIT_DECISION}"
            r=chat_video(video_url=vu, prompt=combined_prompt, system="你是顶级视频分析+剪辑决策专家。只返回JSON。")
            c=r.get("content",""); m=re.search(r'\{.*\}',c,re.DOTALL)
            if m: d=json.loads(m.group(0)); d["analysis_source"]="kimi_k2.6_video"; return d
        except Exception as e: logger.warning("K2.6视频失败: %s",e)

    # 路径B: 三阶段帧序列分析
    try:
        info=_probe_video(tp); dur=info["duration"]
        from app.services.material_analyzer import MaterialAnalyzer
        ma=MaterialAnalyzer()

        # === Stage 1: 快速分类(1帧) ===
        mid_frame=ma._extract_frame(Path(tp), dur/2)
        if not mid_frame: return {}
        stage1=_call_vision_api(mid_frame, STAGE1_CLASSIFY_PROMPT)
        if not stage1: return {}

        ct=stage1.get("content_type","unknown")
        logger.debug("Stage1分类: %s → %s", fn, ct)

        # === Stage 2: 深度分析(5帧+类型专用prompt) ===
        frames=[]
        sample_count=min(5, max(2, int(dur/3)))
        for i in range(sample_count):
            t=dur*(i+0.5)/sample_count
            b64=ma._extract_frame(Path(tp), t)
            if b64: frames.append(b64)

        if ct=="talking_head": deep_prompt=STAGE2_DEEP_TALKING.format(frame_count=len(frames))
        elif ct in ("product_show","text_card"): deep_prompt=STAGE2_DEEP_PRODUCT.format(frame_count=len(frames))
        else: deep_prompt=STAGE2_DEEP_ENVIRONMENT.format(frame_count=len(frames))

        stage2=_call_vision_api(frames[0], deep_prompt) if frames else {}
        if not stage2: stage2={}

        # === Stage 3: 编辑决策 ===
        analysis_summary=json.dumps({"ct":ct,**stage1,**stage2},ensure_ascii=False)
        decision_prompt=STAGE3_EDIT_DECISION.format(content_type=ct,analysis_summary=analysis_summary[:500])

        # 用任一可用帧
        frame_for_decision=frames[0] if frames else mid_frame
        stage3=_call_vision_api(frame_for_decision, decision_prompt)
        if not stage3: stage3={}

        # 合并三阶段结果
        result={**stage1,**stage2,**stage3}
        result["analysis_source"]="kimi_k2.6_3stage"
        result["duration"]=dur
        result["frame_count"]=len(frames)+1
        logger.info("K2.6三阶段分析: %s→%s→edit_role=%s",fn,ct,stage3.get("editing_role","?"))
        return result

    except Exception as e: logger.warning("三阶段分析失败: %s",e)

    # 路径C: 单帧降级
    try:
        info=_probe_video(tp); dur=info["duration"]
        from app.services.material_analyzer import MaterialAnalyzer
        ma=MaterialAnalyzer(); fb64=ma._extract_frame(Path(tp), dur/2)
        if fb64:
            d=_call_vision_api(fb64)
            if d: d["analysis_source"]="single_frame"; d["duration"]=dur; return d
    except Exception: pass
    return {}


# ================================================================
# 帧级精度分析 — 每帧独立视觉分析 → 帧级编辑决策
# ================================================================

FRAME_LEVEL_PROMPT="""分析这一帧。返回严格JSON(20字以内每个字段)。
{"t":时间秒,"ct":"talking_head/product/environment/text/waste","sz":"CU/MCU/MS/LS","fc":true,"ec":"看镜头/偏离/闭眼","em":"激动/平静/严肃/开心","gs":"强调手势/无手势/偶尔","lt":"正常/偏暗/过曝","cp":"中心/三分/偏左","cl":"暖色/冷色/中性","qt":5,"tg":["标签"],"is":[],"us":true}"""

def _analyze_frame_level(tp, fn, vu="", max_frames=12):
    """
    帧级精度分析: 每帧独立调用Kimi K2.6 Vision → 聚合 → 帧间变化检测 → 精确编辑决策

    这是最高精度的分析模式, 产生帧级编辑数据。
    """
    import re
    # 路径A: K2.6原生视频(完整视频流不需要逐帧)
    if vu:
        try:
            from app.services.gateway_client import chat_video
            combined=f"{STAGE1_CLASSIFY_PROMPT}\n\n{STAGE3_EDIT_DECISION}"
            r=chat_video(video_url=vu, prompt=combined, system="只返回JSON。")
            c=r.get("content",""); m=re.search(r'\{.*\}',c,re.DOTALL)
            if m: d=json.loads(m.group(0)); d["analysis_source"]="kimi_k2.6_video"; d["frame_count"]=0; return d
        except Exception as e: logger.warning("K2.6视频失败: %s",e)

    # 路径B: 帧级分析
    try:
        info=_probe_video(tp); dur=info["duration"]
        from app.services.material_analyzer import MaterialAnalyzer
        ma=MaterialAnalyzer()

        # 采样: 每2秒1帧, 最少5帧, 最多12帧
        frame_count=max(5, min(max_frames, int(dur/2)))
        frame_interval=dur/frame_count

        # === 提取所有帧 ===
        frames=[]
        for i in range(frame_count):
            t=dur*(i+0.5)/frame_count
            b64=ma._extract_frame(Path(tp), t)
            if b64: frames.append({"index":i,"time_sec":round(t,1),"base64":b64})
        if not frames: return {}

        # === 逐帧调用Kimi K2.6 Vision(每帧独立分析) ===
        frame_data=[]
        for fr in frames:
            d=_call_vision_api(fr["base64"], FRAME_LEVEL_PROMPT,
                              f"{fn}@{fr['time_sec']:.1f}s")
            if d:
                d["_index"]=fr["index"]; d["_time"]=fr["time_sec"]
                frame_data.append(d)

        if not frame_data: return {}

        # === 聚合分析 ===
        # 1. 主导内容类型
        from collections import Counter
        cts=[fd.get("ct","unknown") for fd in frame_data]
        dom_ct=Counter(cts).most_common(1)[0][0]
        ct_consistency=Counter(cts).most_common(1)[0][1]/len(cts)

        # 2. 帧间变化检测——找切点
        cut_points=[]
        for i in range(1,len(frame_data)):
            prev=frame_data[i-1]; curr=frame_data[i]
            # 内容类型变化=强制切点
            if prev.get("ct")!=curr.get("ct"): cut_points.append(curr["_time"])
            # 景别大幅变化=建议切点
            elif prev.get("sz")!=curr.get("sz"): cut_points.append(curr["_time"])

        # 3. 分段: 在切点处断开
        segments=[]
        seg_start=0
        for cp in cut_points+[dur]:
            seg_frames=[fd for fd in frame_data if seg_start<=fd["_time"]<=cp]
            if seg_frames:
                qualities=[fd.get("qt",3) for fd in seg_frames]
                face_ratio=sum(1 for fd in seg_frames if fd.get("fc"))/len(seg_frames)
                eye_ratios=[1 if fd.get("ec")=="看镜头" else 0 for fd in seg_frames]
                eye_ratio=sum(eye_ratios)/len(eye_ratios) if eye_ratios else 0
                seg_ct=Counter([fd.get("ct","?") for fd in seg_frames]).most_common(1)[0][0]

                segments.append({
                    "start_sec":round(seg_start,1),
                    "end_sec":round(cp,1),
                    "duration":round(cp-seg_start,1),
                    "content_type":seg_ct,
                    "avg_quality":round(float(np.mean(qualities)),1),
                    "face_ratio":round(face_ratio,2),
                    "eye_contact_ratio":round(eye_ratio,2),
                    "frames_analyzed":len(seg_frames),
                })
            seg_start=cp

        # 4. 综合推荐
        all_qt=[fd.get("qt",3) for fd in frame_data]
        avg_qt=round(float(np.mean(all_qt)),1)
        face_frames=sum(1 for fd in frame_data if fd.get("fc"))
        face_ratio=face_frames/len(frame_data)
        eye_frames=sum(1 for fd in frame_data if fd.get("ec")=="看镜头")
        eye_ratio=eye_frames/max(face_frames,1)

        if dom_ct=="talking_head" and face_ratio>0.6 and eye_ratio>0.5:
            edit_role="body"; edit_note=f"优质口播({len(segments)}段,看镜头{eye_ratio:.0%})"
        elif dom_ct=="talking_head" and face_ratio>0.3:
            edit_role="body"; edit_note="口播可用,部分段可B-roll覆盖"
        elif dom_ct in ("product","text"):
            edit_role="broll"; edit_note="产品/B-roll素材"
        else:
            edit_role="broll"; edit_note="通用素材"

        # 5. 每段编辑参数
        for seg in segments:
            if seg["content_type"]=="talking_head" and seg["eye_contact_ratio"]>0.5:
                seg["editing_action"]="保留完整出镜+声音"
                seg["transition_in"]="cut"; seg["transition_out"]="cut"
            elif seg["content_type"]=="talking_head":
                seg["editing_action"]="部分B-roll覆盖(保留声音)"
                seg["transition_in"]="dissolve"; seg["transition_out"]="dissolve"
            else:
                seg["editing_action"]="B-roll覆盖口播画面"
                seg["transition_in"]="cut"; seg["transition_out"]="cut"

        result={
            "analysis_source":"frame_level_precision",
            "duration":dur,"frame_count":len(frame_data),"total_frames_sampled":len(frames),
            "content_type":dom_ct,"content_consistency":round(ct_consistency,2),
            "quality":avg_qt,"face_ratio":round(face_ratio,2),"eye_contact_ratio":round(eye_ratio,2),
            "segments":segments,"cut_points":[round(c,1) for c in cut_points],
            "editing_role":edit_role,"editing_notes":edit_note,
            "tags":list(set(t for fd in frame_data for t in fd.get("tg",[]))),
            "issues":list(set(i for fd in frame_data for i in fd.get("is",[]))),
            "usable":avg_qt>=2.5,
        }
        logger.info("帧级精度: %s → %s(%d段/%d切点/%.0f帧)", fn, dom_ct, len(segments), len(cut_points), len(frame_data))
        return result

    except Exception as e:
        logger.warning("帧级分析失败: %s",e)
        return _analyze_video(tp,fn,vu)  # 降级三阶段

def analyze_materials(files,user_intent="",provider="",model="",video_url=""):
    if not files: raise ValueError("至少1个素材")
    if len(files)>10: raise ValueError("最多10个")
    result=BatchAnalysisResult(); result.files=files
    videos=[f for f in files if f.file_type=="video"]; images=[f for f in files if f.file_type=="image"]
    mv=None
    if videos:
        for v in videos:
            if any(kw in v.filename.lower() for kw in ["口播","talking","主","main"]): mv=v; break
        if not mv: mv=max(videos,key=lambda v:v.size_bytes)
    bv=[v for v in videos if v!=mv]; hva=False
    if mv and mv.temp_path:
        result.main_video_path=mv.temp_path; result.has_talking_head=True
        info=_probe_video(mv.temp_path); result.voiceover_duration=info["duration"]; result.total_duration_estimate=f"{int(info['duration'])}秒"
        d=_analyze_frame_level(mv.temp_path,mv.filename,video_url)
        if d:
            ma=_vision_to_analysis(d,mv.filename,"video"); ma.duration=info["duration"]; result.analyses.append(ma); hva=True
        else: result.analyses.append(MaterialAnalysis(filename=mv.filename,file_type="video",scene_type="人物",content_summary=f"视频:{mv.filename} ({info['duration']:.1f}s)",quality_score=3.5,suitable_for=["body"],has_face=True,analysis_source="ffprobe_only"))
    for b in bv:
        if b.temp_path:
            result.broll_paths.append(b.temp_path)
            d=_analyze_frame_level(b.temp_path,b.filename,video_url)
            if d: result.analyses.append(_vision_to_analysis(d,b.filename,"video")); hva=True
            else:
                info=_probe_video(b.temp_path)
                result.analyses.append(MaterialAnalysis(filename=b.filename,file_type="video",scene_type="环境",content_summary=f"B-roll:{b.filename} ({info['duration']:.1f}s)",quality_score=3.5,suitable_for=["broll"],analysis_source="ffprobe_only"))
    for img in images:
        if img.temp_path:
            result.image_paths.append(img.temp_path); result.broll_paths.append(img.temp_path)
            try:
                with open(img.temp_path,"rb") as f: b64=base64.b64encode(f.read()).decode()
                d=_call_vision_api(b64,f"图片:{img.filename}")
                if d: result.analyses.append(_vision_to_analysis(d,img.filename,"image")); hva=True; continue
            except Exception: pass
            sc="产品" if any(kw in img.filename.lower() for kw in ["产品","product"]) else "环境"
            result.analyses.append(MaterialAnalysis(filename=img.filename,file_type="image",scene_type=sc,content_summary=f"图片:{img.filename}",quality_score=4.0,suitable_for=["broll"],analysis_source="heuristic"))
    sources={a.analysis_source for a in result.analyses}
    if "kimi_k2.6_video" in sources: result.analysis_quality="full_video"
    elif "frame_level_precision" in sources: result.analysis_quality="frame_precision"
    elif "kimi_k2.6_3stage" in sources: result.analysis_quality="three_stage"
    elif "glm4v_vision" in sources or "frame_extraction" in sources: result.analysis_quality="full_vision"
    elif mv: result.analysis_quality="partial"
    else: result.analysis_quality="heuristic"
    result.recommended_template="团购售卖"
    result.overall_scene=user_intent[:20] if user_intent else ("口播+素材混剪" if result.has_talking_head else "素材展示")
    result.suggested_bgm="轻快电子/lo-fi" if result.has_talking_head else "大气/科技感"
    return result
