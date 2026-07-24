"""
分镜脚本生成器 · 抖音剪映模式 — 先出分镜脚本，再按脚本拍摄，最后自动剪辑

输入: 脚本文案 + 产品信息 + 风格偏好
输出: 结构化ShotList — 每个镜头标注拍摄要求(景别/运镜/时长/构图/动作指导/文字叠加)
      用户拿着ShotList去拍摄 → 上传 → AI自动匹配 → 一键成片
"""
from __future__ import annotations
import json, logging, re
from dataclasses import dataclass, field
logger = logging.getLogger(__name__)

@dataclass
class ShotSpec:
    """单个镜头的拍摄规格——用户照着拍就行"""
    shot_id: int
    label: str                  # "镜头1: 产品特写"
    shot_type: str              # CU/MCU/MS/MLS/LS/ELS
    duration_sec: float         # 建议拍摄时长
    camera_move: str            # static/push_in/pull_out/handheld/pan
    composition: str            # center/rule_of_thirds/diagonal
    color_tone: str             # warm/cool/high_contrast/soft/vibrant
    # 拍摄指导(给用户看)
    shooting_guide: str         # "手机凑近产品，对焦虾腮，保持稳定3秒"
    what_to_shoot: str          # "产品特写——龙虾的腮部白色、调料汤汁"
    # AI编辑参数
    text_overlay: str           # "68块！" — 自动加到画面上
    text_position: str          # center/bottom/top
    transition_in: str          # cut/dissolve/fade_in
    transition_out: str
    action_guide: str           # 动作指导(如"手指左下角")
    required_material: str      # "product_closeup" / "talking_head" / "environment" / "customer"
    broll_overlay: bool         # 是否覆盖口播画面

@dataclass
class ShotList:
    """完整分镜脚本——拍摄清单"""
    project_name: str
    total_duration: float       # 预估总时长
    shots: list[ShotSpec]
    # 拍摄清单汇总
    material_checklist: list[dict]  # [{"type":"product_closeup","count":3,"description":"产品特写镜头"}]
    shooting_tips: list[str]        # 拍摄技巧提示
    bgm_suggestion: str
    script_type: str

SHOTLIST_SYSTEM_PROMPT = """你是抖音短视频导演。你的任务是根据用户的脚本和产品信息，生成一份详细的"拍摄清单"——用户照着清单去拍，拍完上传，AI自动剪辑成片。

## 输出格式(严格JSON)
{
  "project_name": "项目名",
  "shots": [
    {
      "shot_id": 1,
      "label": "镜头1: 产品特写",
      "shot_type": "CU/MCU/MS/MLS/LS/ELS",
      "duration_sec": 3.0,
      "camera_move": "static/push_in/pull_out/handheld/pan_left/pan_right",
      "composition": "center/rule_of_thirds/diagonal/frame_within",
      "color_tone": "warm/cool/high_contrast/soft/vibrant",
      "shooting_guide": "告诉用户怎么拍——手机位置、对焦、时长、注意事项(30字以内)",
      "what_to_shoot": "具体拍什么——产品/人物/环境/顾客(15字以内)",
      "text_overlay": "画面上要出现的文字——价格/卖点/地址/CTA(10字以内，空字符串=不叠加)",
      "text_position": "center/bottom/top",
      "transition_in": "cut/fade_in/dissolve",
      "transition_out": "cut/fade_out/dissolve",
      "action_guide": "人物动作——手势/表情/走位(15字以内)",
      "required_material": "product_closeup/talking_head/environment/customer/text_card/transition",
      "broll_overlay": false
    }
  ],
  "material_checklist": [
    {"type": "product_closeup", "count": 3, "description": "产品多角度特写"}
  ],
  "shooting_tips": ["拍摄技巧1", "拍摄技巧2"],
  "bgm_suggestion": "BGM风格推荐",
  "total_duration": 45.0
}

## 拍摄清单原则
1. 每个镜头必须具体到"用户能直接照着拍"的程度——不能模糊
2. 镜头的shooting_guide必须是动作指令——"手机凑近""对焦眼睛""从左往右缓慢移动"
3. 文字叠加(text_overlay)要和口播配合——价格第一帧就出现，CTA在最后出现
4. 景别必须变化——相邻镜头不能是同一个景别
5. 产品特写=大特写(CU)，环境=全景(LS)，人物=中景(MS)
6. 至少包含1个产品特写+1个环境展示+1个人物出镜
7. 开头=产品最惊艳特写(CU)，结尾=人物+CTA(MS拉远)
8. B-roll镜头(broll_overlay=true)覆盖口播画面但保留声音

## 三种脚本类型的拍摄差异
- 老板IP: 多人物中近景(MCU/MS)，少产品特写，镜头时间长(4-8s)，氛围温暖
- 团购售卖: 多产品特写(CU)，价格文字频繁，镜头短(1-3s)，节奏快
- 引流进店: 环境全景(LS)+顾客反应(CU)，地址信息，手持感"""

SHOTLIST_USER_PROMPT = """请为以下内容生成拍摄清单:

## 脚本/产品信息
{script_text}

## 风格偏好
{style_preference}

## 要求
- 生成{shot_count}个镜头的完整拍摄清单
- 预估总时长: {target_duration}秒
- 脚本类型: {script_type}
- 每个镜头都要有具体的shooting_guide（用户能直接照着拍）"""


def generate_shotlist(
    script_text: str,
    script_type: str = "团购售卖",
    style_preference: str = "",
    shot_count: int = 8,
    target_duration: float = 45.0,
) -> ShotList:
    """生成分镜脚本——用户照着拍就行"""
    from app.services.gateway_client import chat_via_gateway
    from app.services.model_config import get_model_name

    if not script_text.strip():
        raise ValueError("请提供脚本或产品信息")

    user_prompt = SHOTLIST_USER_PROMPT.format(
        script_text=script_text[:2000],
        style_preference=style_preference or "根据脚本类型自动选择",
        shot_count=shot_count,
        target_duration=target_duration,
        script_type=script_type,
    )

    try:
        result = chat_via_gateway(
            provider="deepseek", model=get_model_name("deepseek"),
            system=SHOTLIST_SYSTEM_PROMPT, user=user_prompt,
            temperature=0.7, max_tokens=2500,
        )
        content = result.get("content", "")
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return _parse_shotlist(data)
    except Exception as e:
        logger.warning("ShotList生成失败(%s), 使用规则模板", e)

    # 降级: 规则模板
    return _fallback_shotlist(script_text, script_type, shot_count, target_duration)


def _parse_shotlist(data: dict) -> ShotList:
    shots = []
    last_shot_type = ""
    for i, s in enumerate(data.get("shots", [])):
        st = s.get("shot_type", "MS")
        # 蒙太奇: 相邻景别不能相同
        if st == last_shot_type:
            st = {"CU":"MS","MS":"CU","MCU":"MS","LS":"MS","MLS":"CU","ELS":"LS"}.get(st, "MS")
        last_shot_type = st
        shots.append(ShotSpec(
            shot_id=s.get("shot_id", i+1),
            label=s.get("label", f"镜头{i+1}"),
            shot_type=st,
            duration_sec=float(s.get("duration_sec", 3.0)),
            camera_move=s.get("camera_move", "static"),
            composition=s.get("composition", "center"),
            color_tone=s.get("color_tone", "warm"),
            shooting_guide=s.get("shooting_guide", ""),
            what_to_shoot=s.get("what_to_shoot", ""),
            text_overlay=s.get("text_overlay", ""),
            text_position=s.get("text_position", "bottom"),
            transition_in=s.get("transition_in", "cut"),
            transition_out=s.get("transition_out", "cut"),
            action_guide=s.get("action_guide", ""),
            required_material=s.get("required_material", "product_closeup"),
            broll_overlay=s.get("broll_overlay", False),
        ))
    return ShotList(
        project_name=data.get("project_name", "AI拍摄项目"),
        total_duration=float(data.get("total_duration", sum(s.duration_sec for s in shots))),
        shots=shots,
        material_checklist=data.get("material_checklist", []),
        shooting_tips=data.get("shooting_tips", []),
        bgm_suggestion=data.get("bgm_suggestion", "轻快电子"),
        script_type=data.get("script_type", "团购售卖"),
    )


def _fallback_shotlist(script_text: str, script_type: str, count: int, duration: float) -> ShotList:
    """规则模板降级——三种脚本类型的预置分镜"""
    templates = {
        "老板IP": [
            ("CU","static","center","人脸特写——自然光，眼神看镜头","讲你的故事开头","",False),
            ("MS","static","rule_of_thirds","半身出镜——手势自然，像跟朋友聊天","继续讲故事","",False),
            ("CU","push_in","center","产品或老照片特写——缓慢推近","展示你的坚持","",True),
            ("MCU","static","rule_of_thirds","回到人脸——表情自然，讲到动情处","情感高潮","",False),
            ("LS","pan_right","rule_of_thirds","工作环境全景——展示你的日常","切换到环境","",True),
            ("MS","static","rule_of_thirds","半身——收尾，自然微笑","结尾感悟","关注我，下期见",False),
        ],
        "团购售卖": [
            ("CU","static","center","产品大特写——凑近拍最诱人的角度","产品最惊艳一刻","68块！",False),
            ("MS","static","rule_of_thirds","半身出镜——手指产品","报价+喊人","",False),
            ("CU","push_in","center","产品细节——缓慢推近展示工艺","工艺/食材展示","干煸盱眙技术",True),
            ("LS","pan_left","rule_of_thirds","店内环境——从左到右展示","环境展示","",True),
            ("CU","static","center","顾客反应——拍顾客吃/用的表情","社交证明","",True),
            ("MS","pull_out","rule_of_thirds","半身——手指左下角","CTA引导","左下角团购",False),
        ],
        "引流进店": [
            ("LS","pan_right","rule_of_thirds","门头+排队——从右往左拍","门头+火爆场景","玉田只此一家",False),
            ("CU","static","center","独家产品特写","独家产品展示","",False),
            ("LS","handheld","rule_of_thirds","店内环境——手持拍摄，边走边拍","店内氛围","",True),
            ("CU","static","center","顾客竖大拇指——抓拍真实反应","顾客证言","回头客90%",False),
            ("MS","static","rule_of_thirds","半身——手指地址","地址+CTA","定位在左下角",False),
        ],
    }
    tmpl = templates.get(script_type, templates["团购售卖"])
    # 扩展到需要的数量
    while len(tmpl) < count:
        tmpl.append(tmpl[len(tmpl) % len(tmpl)])
    tmpl = tmpl[:count]

    shots = []
    last_st = ""
    for i, (st, cam, comp, guide, what, text, broll) in enumerate(tmpl):
        if st == last_st:
            st = {"CU":"MS","MS":"CU","MCU":"MS","LS":"MS"}.get(st, "MS")
        last_st = st
        dur = duration / count
        trans = "fade_in" if i == 0 else ("fade_out" if i == count-1 else "cut")
        trans_out = "fade_out" if i == count-1 else "cut"
        shots.append(ShotSpec(
            shot_id=i+1, label=f"镜头{i+1}: {what}", shot_type=st,
            duration_sec=round(dur, 1), camera_move=cam, composition=comp,
            color_tone="warm" if script_type=="老板IP" else "high_contrast",
            shooting_guide=guide, what_to_shoot=what,
            text_overlay=text, text_position="center" if text and len(text)<8 else "bottom",
            transition_in=trans, transition_out=trans_out,
            action_guide="", required_material="product_closeup" if broll else "talking_head",
            broll_overlay=broll,
        ))

    checklist = [{"type":"talking_head","count":sum(1 for s in shots if not s.broll_overlay),"description":"人物出镜镜头"},
                 {"type":"product_closeup","count":sum(1 for s in shots if s.broll_overlay),"description":"产品/环境空镜"}]
    return ShotList(
        project_name="AI拍摄项目", total_duration=duration, shots=shots,
        material_checklist=checklist,
        shooting_tips=["每个镜头保持手机稳定至少3秒","产品特写时擦干净镜头","人物出镜时自然光正面照明"],
        bgm_suggestion={"老板IP":"温暖钢琴","团购售卖":"快节奏卡点","引流进店":"轻松生活"}.get(script_type,"轻快电子"),
        script_type=script_type,
    )


def shotlist_from_parsed_annotations(parsed_shots: list[dict], script_type: str = "团购售卖") -> ShotList:
    """从脚本Agent的A+分镜头标注直接构建ShotList——不需要LLM，不需要模板"""
    # 景别映射: 中文→缩写
    shot_map = {"近景":"CU","特写":"CU","大特写":"ECU","中近景":"MCU","中景":"MS","中全景":"MLS","全景":"LS","远景":"ELS"}
    cam_map = {"固定":"static","推":"push_in","拉":"pull_out","手持":"handheld","左摇":"pan_left","右摇":"pan_right","上摇":"tilt_up","下摇":"tilt_down","前移":"dolly_in","后移":"dolly_out","左跟":"track_left","右跟":"track_right","弧形":"arc"}

    shots = []
    last_st = ""
    for i, ps in enumerate(parsed_shots):
        # 解析景别
        st_raw = ps.get('shot_type_raw','MS')
        st = "MS"
        for cn, abbr in shot_map.items():
            if cn in st_raw or abbr in st_raw.upper():
                st = abbr; break
        # 蒙太奇
        if st == last_st: st = {"CU":"MS","MS":"CU","MCU":"MS","LS":"MS"}.get(st,"MS")
        last_st = st

        # 解析运镜
        cm = ps.get('camera_move','static')
        for cn, abbr in cam_map.items():
            if cn in cm: cm = abbr; break

        # 口播文案作为文字叠加
        spoken = ps.get('spoken_text','')
        text_overlay = spoken[:20] if spoken else ""

        shots.append(ShotSpec(
            shot_id=i+1,
            label=f"镜{i+1}: {ps.get('visual_desc','')[:15] or ps.get('spoken_text','')[:15]}",
            shot_type=st,
            duration_sec=3.0 if ps.get('is_broll') else 5.0,
            camera_move=cm,
            composition="center" if "中心" in ps.get('composition','') else "rule_of_thirds",
            color_tone="high_contrast" if "高对比" in ps.get('color_tone','') else "warm",
            shooting_guide=ps.get('visual_desc','') or ps.get('action_guide',''),
            what_to_shoot=ps.get('visual_desc','')[:20] or ps.get('spoken_text','')[:20],
            text_overlay=text_overlay,
            text_position="center" if len(text_overlay)<8 else "bottom",
            transition_in="fade_in" if i==0 else "cut",
            transition_out="fade_out" if i==len(parsed_shots)-1 else "cut",
            action_guide=ps.get('action_guide',''),
            required_material="product_closeup" if ps.get('is_broll') else "talking_head",
            broll_overlay=ps.get('is_broll', False),
        ))

    total_dur = sum(s.duration_sec for s in shots)
    return ShotList(
        project_name="脚本Agent直出分镜",
        total_duration=total_dur,
        shots=shots,
        material_checklist=[
            {"type":"talking_head","count":sum(1 for s in shots if not s.broll_overlay),"description":"口播出镜镜头"},
            {"type":"product_closeup","count":sum(1 for s in shots if s.broll_overlay),"description":"产品/环境B-roll"},
        ],
        shooting_tips=["按脚本Agent分镜拍摄——景别/运镜/构图已标注","B-roll镜头可覆盖口播画面,保留配音"],
        bgm_suggestion={"老板IP":"温暖钢琴","团购售卖":"快节奏卡点","引流进店":"轻松生活"}.get(script_type,"轻快电子"),
        script_type=script_type,
    )


def format_shotlist_for_user(sl: ShotList) -> str:
    """格式化为用户可读的拍摄清单"""
    lines = [
        f"══════════════════════",
        f"  📋 拍摄清单: {sl.project_name}",
        f"  ⏱️ 预估时长: {sl.total_duration:.0f}秒 | {len(sl.shots)}个镜头",
        f"  🎵 推荐BGM: {sl.bgm_suggestion}",
        f"══════════════════════",
        "", "━━━ 📸 拍摄清单 ━━━", ""
    ]
    for s in sl.shots:
        broll = " [B-ROLL: 覆盖口播画面]" if s.broll_overlay else ""
        lines.append(f"【镜头{s.shot_id}】{s.label}{broll}")
        lines.append(f"   🎥 景别:{s.shot_type} | 运镜:{s.camera_move} | 构图:{s.composition} | {s.duration_sec}秒")
        lines.append(f"   📷 拍什么: {s.what_to_shoot}")
        lines.append(f"   🎬 怎么拍: {s.shooting_guide}")
        if s.text_overlay: lines.append(f"   📝 文字叠加: \"{s.text_overlay}\"")
        if s.action_guide: lines.append(f"   🎭 动作: {s.action_guide}")
        lines.append("")

    lines.extend(["━━━ 📦 素材清单 ━━━", ""])
    for m in sl.material_checklist:
        lines.append(f"  {m['count']}个 {m['type']}: {m['description']}")
    lines.extend(["", "━━━ 💡 拍摄技巧 ━━━", ""])
    for tip in sl.shooting_tips:
        lines.append(f"  • {tip}")
    return "\n".join(lines)
