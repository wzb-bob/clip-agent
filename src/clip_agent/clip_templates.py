"""
剪辑模板库 v3 · 脚本Agent三分类驱动

  老板IP   → Emma型情感共鸣 · 长镜慢剪 · 人脸为主 · 不硬推销
  团购售卖 → Hormozi型价值前置 · 快切价格冲击 · 五要素全 · 文字叠加
  引流进店 → 稀缺感制造 · 三种子类型(独家/火爆/证言) · 社交证明镜头

每类含: 4层钩子(Visual/Text/Verbal/Audio) + 留存动作点时间线 + 剪辑DNA
"""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class VisualStrategy:
    key: str; label: str; condition: str; rule: str; broll_ratio: float

VISUAL_STRATEGIES = {
    "good_presence": VisualStrategy("good_presence","出镜效果好","人物表情自然、看镜头、有肢体语言","保留口播画面，自然断句处插入空镜增强",0.3),
    "script_reading": VisualStrategy("script_reading","念稿/出镜差","低头看稿、表情僵硬、眼神飘忽","只用配音，画面全空镜铺满",1.0),
    "mixed": VisualStrategy("mixed","混合模式","部分片段出镜好、部分念稿","出镜好的保留+插空镜，念稿段全空镜",0.6),
}

BGM_RULES = {"volume_ratio":0.33,"fade_in_sec":0.5,"fade_out_sec":0.8,"ducking":True,"ducking_ratio":0.25}

# ============================================================
# 三脚本类型 · 剪辑策略
# ============================================================

CLIP_TEMPLATES = {
    "老板IP": {
        "name":"老板IP·人物故事","icon":"🎯",
        "script_type":"老板IP",
        "desc":"以老板第一人称讲述创业故事/个人经历/核心理念。不硬推销，重在人格魅力和信任建立。",
        "creator_archetype":"Emma型（情感共鸣）",
        "hook_strategy": {
            "visual_0s":"静止帧——老板面部特写(CU)，自然光，眼神看镜头",
            "text_0s":"12字以内金句字幕，居中大字，白色+黑色描边，0.3s淡入",
            "verbal_0s":"老板第一句话=真实故事的开头，语气像跟朋友聊天",
            "audio_0s":"BGM从无到有，0.5s淡入，音量=人声1/3",
        },
        "retention_timeline": [
            {"at_sec":0, "action":"视觉钩子", "detail":"人脸CU特写+金句字幕，BGM淡入"},
            {"at_sec":3, "action":"信息兑现", "detail":"0-3s抛出的悬念在3s内给出第一个答案——'因为我干了12年...'"},
            {"at_sec":7, "action":"第一个为什么", "detail":"从'讲事实'切换到'讲感受'——'最难的时候...'"},
            {"at_sec":14,"action":"情感转折", "detail":"情绪波动——从低谷到转机，镜头从CU推到MCU"},
            {"at_sec":21,"action":"新信息点", "detail":"抛出新角度——'很多人不知道的是...'，切换B-roll空镜"},
            {"at_sec":28,"action":"社交证明", "detail":"顾客反馈/排队场景/'有个山西老板专门开车来'"},
            {"at_sec":35,"action":"CTA收尾", "detail":"'想听更多故事？关注我'——MS拉远，BGM渐弱"},
        ],
        "editing_dna": {
            "shot_duration":{"min":3.0,"max":12.0,"typical":6.0},
            "broll_density":0.15,"text_density":0.3,
            "preferred_camera":["static"],
            "color_filter":"无(保持自然色)",
            "transition":"cut硬切",
            "pace":"慢——像纪录片，镜头停留6-10秒，让观众沉浸在故事里",
            "opening":"人脸CU+金句字幕，BGM从无到有淡入，不加任何过渡效果",
            "ending":"MS拉远+关注CTA+下期预告，BGM渐弱至无声",
        },
        "bgm_style":"温暖/治愈/钢琴","default_bpm":80,"min_shots":5,
    },

    "团购售卖": {
        "name":"团购售卖·价格冲击","icon":"🛒",
        "script_type":"团购售卖",
        "desc":"开篇直接报价格！五要素(喊人/提痛/优势/解决/引导)缺一不可，纯交易导向。",
        "creator_archetype":"Hormozi型（价值前置）",
        "hook_strategy": {
            "visual_0s":"产品特写(CU)+大字价格覆盖——如'68块!'占画面40%",
            "text_0s":"价格数字第一帧就出现，红色/黄色大字，从画面外飞入",
            "verbal_0s":"'68块！十只活虾！'——第一句=价格+数量+品质，10个字以内",
            "audio_0s":"BGM鼓点同步价格出现，重音强调数字",
        },
        "retention_timeline": [
            {"at_sec":0, "action":"价格冲击", "detail":"产品CU+大字价格+鼓点BGM——三同步"},
            {"at_sec":1, "action":"喊人+提痛", "detail":"'玉田的吃货们，你吃过的小龙虾可能都是冷冻的——'"},
            {"at_sec":3, "action":"优势证明", "detail":"切换到工艺/食材展示B-roll——'干煸盱眙技术''花雕泡8小时'"},
            {"at_sec":7, "action":"第二优势", "detail":"新的产品角度或顾客反馈——'有个山西老板专门开车来'"},
            {"at_sec":10,"action":"解决+引导", "detail":"'来虾神，左下角团购已上线'——CTA字幕+手势指向左下角"},
            {"at_sec":14,"action":"紧迫感", "detail":"'试营业68，试营业后恢复原价108'——限时信息"},
            {"at_sec":18,"action":"二次CTA", "detail":"重复地址+团购入口——'左下角，赶紧抢'"},
        ],
        "editing_dna": {
            "shot_duration":{"min":1.0,"max":4.0,"typical":2.0},
            "broll_density":0.5,"text_density":0.6,
            "preferred_camera":["push_in","static"],
            "color_filter":"亮夏",
            "transition":"cut硬切+whip_pan甩镜头",
            "pace":"快——每2秒换镜，产品多角度快速切换，文字弹出密集",
            "opening":"产品CU+价格大字飞入+鼓点BGM，0.5秒内切入，不加过渡",
            "ending":"重复地址+团购入口+限时信息，定格3秒淡出",
        },
        "bgm_style":"快节奏卡点/电子","default_bpm":120,"min_shots":6,
    },

    "引流进店": {
        "name":"引流进店·稀缺感","icon":"📍",
        "script_type":"引流进店",
        "desc":"制造'不来就亏了'的稀缺感。三种子类型:人无我有(独家)、人多火爆(排队)、客户说话(证言)。",
        "creator_archetype":"混合型",
        "sub_types": {
            "人无我有": {
                "desc":"独家产品/技术/体验，只能来我店里才能有",
                "hook":"'全玉田只此一家——' + 独家产品镜头",
                "key_shots":["独家产品特写","工艺过程","老板/厨师展示独特性"],
            },
            "人多火爆": {
                "desc":"排队/满座/爆单，制造从众心理",
                "hook":"'你看这排队——' + 人群镜头",
                "key_shots":["排队全景","店内满座","厨房忙碌","外卖堆成山"],
            },
            "客户说话": {
                "desc":"真实顾客出镜好评，第三方背书",
                "hook":"'他吃了三年了——' + 顾客镜头",
                "key_shots":["顾客吃饭特写","顾客对镜头竖大拇指","顾客采访片段"],
            },
        },
        "hook_strategy": {
            "visual_0s":"根据子类型: 独家产品/排队人群/顾客笑脸——冲击力画面",
            "text_0s":"地点+稀缺标签——'玉田只此一家''排队到马路''回头客90%'",
            "verbal_0s":"第一句=制造认知缺口——'你可能不知道玉田有一家...'",
            "audio_0s":"环境音+BGM，人声压低BGM至25%",
        },
        "retention_timeline": [
            {"at_sec":0, "action":"稀缺钩子", "detail":"子类型专属画面+稀缺标签字幕"},
            {"at_sec":3, "action":"证明1", "detail":"为什么稀缺——独家工艺/真实排队/顾客证言"},
            {"at_sec":7, "action":"证明2", "detail":"第二个维度的证明——换个角度展示稀缺性"},
            {"at_sec":12,"action":"地址植入", "detail":"'就在玉田XX路'——地址字幕+门头镜头"},
            {"at_sec":16,"action":"CTA", "detail":"'定位在左下角，导航直达'——手指左下角手势"},
        ],
        "editing_dna": {
            "shot_duration":{"min":1.5,"max":5.0,"typical":2.5},
            "broll_density":0.45,"text_density":0.5,
            "preferred_camera":["handheld","pan_right","pan_left","static"],
            "color_filter":"亮肤",
            "transition":"cut硬切为主，场景切换用dissolve",
            "pace":"中快——根据子类型微调: 独家=慢展示/火爆=快切/证言=稳",
            "opening":"稀缺画面直切+标签字幕，0.5秒内切入",
            "ending":"地址大字+门头+导航CTA，定格3秒淡出",
        },
        "bgm_style":"轻松/生活化/节奏感","default_bpm":105,"min_shots":5,
    },
}

# 脚本类型→模板映射
SCRIPT_TO_TEMPLATE = {
    "老板IP":"老板IP","团购售卖":"团购售卖","引流进店":"引流进店",
    "product_intro":"团购售卖","company_intro":"老板IP","knowledge_share":"老板IP",
    "store_tour":"引流进店","daily_vlog":"老板IP",
}

def list_templates() -> list[dict]:
    return [{"key":k,"name":t["name"],"icon":t["icon"],"script_type":t["script_type"],"desc":t["desc"],"min_shots":t["min_shots"]} for k,t in CLIP_TEMPLATES.items()]

def get_template(template_key: str) -> dict | None:
    return CLIP_TEMPLATES.get(template_key, CLIP_TEMPLATES.get(SCRIPT_TO_TEMPLATE.get(template_key,"老板IP")))

def auto_select_template(material_types: list[str], user_intent: str = "") -> str:
    intent_lower = user_intent.lower()
    if any(kw in intent_lower for kw in ["团购","卖","促销","优惠","活动","价"]): return "团购售卖"
    if any(kw in intent_lower for kw in ["引流","来店","地址","定位","排队","火爆","独家","只此"]): return "引流进店"
    if any(kw in intent_lower for kw in ["故事","经历","创业","老板","理念","人设","ip"]): return "老板IP"
    if "人物" in material_types and "产品" in material_types: return "团购售卖"
    if "人物" in material_types: return "老板IP"
    return "团购售卖"

# ============================================================
# 剪同款·预设模板库 — 15个模板(每条产品线5个)
# ============================================================

PRESET_TEMPLATES = {
    # ==== 老板IP (5个) ====
    "ip_story_beginning": {
        "name":"创业初心","icon":"💡","script_type":"老板IP",
        "desc":"讲你为什么入这行——从0到1的故事。适合品牌故事、创始人访谈。",
        "shot_count":6,"target_duration":45,
        "bgm":"温暖钢琴","filter":"无(自然色)","text_animation":"淡入","transition":"cut",
        "example_hook":"28岁那年，我辞了工作去盱眙蹲了三个月。",
    },
    "ip_hardest_moment": {
        "name":"至暗时刻","icon":"🌧️","script_type":"老板IP",
        "desc":"讲你最难的时刻和怎么扛过来的——真诚脆弱打动人。",
        "shot_count":6,"target_duration":50,
        "bgm":"治愈钢琴","filter":"无(自然色)","text_animation":"逐字出现","transition":"dissolve",
        "example_hook":"最难的时候，员工工资都发不出来。",
    },
    "ip_proud_moment": {
        "name":"骄傲瞬间","icon":"⭐","script_type":"老板IP",
        "desc":"讲你最骄傲的一个决定或成就——展示你的判断力和坚持。",
        "shot_count":5,"target_duration":40,
        "bgm":"激昂管弦","filter":"书意","text_animation":"放大弹出","transition":"cut",
        "example_hook":"有个山西老板专门开车来，就为了吃我这口虾。",
    },
    "ip_philosophy": {
        "name":"经营理念","icon":"🧭","script_type":"老板IP",
        "desc":"用一句话说你的经营理念——差异化观点打动人。",
        "shot_count":5,"target_duration":35,
        "bgm":"lo-fi","filter":"无(自然色)","text_animation":"淡入","transition":"cut",
        "example_hook":"同行用冻虾，我凌晨四点去水产市场挑活的。",
    },
    "ip_daily_routine": {
        "name":"一天日常","icon":"📅","script_type":"老板IP",
        "desc":"记录你的一天——从早到晚的真实工作状态。",
        "shot_count":8,"target_duration":60,
        "bgm":"轻快acoustic","filter":"亮肤","text_animation":"手写体出现","transition":"dissolve",
        "example_hook":"凌晨四点，大多数人还在睡觉，我已经在水产市场了。",
    },

    # ==== 团购售卖 (5个) ====
    "sale_price_first": {
        "name":"价格冲击","icon":"💰","script_type":"团购售卖",
        "desc":"开篇直接报价格——产品特写+大字价格+鼓点BGM。适合引流转化。",
        "shot_count":6,"target_duration":25,
        "bgm":"快节奏卡点","filter":"亮夏","text_animation":"飞入弹跳","transition":"cut+whip_pan",
        "example_hook":"68块！十只活虾！",
    },
    "sale_process_show": {
        "name":"工艺展示","icon":"🔧","script_type":"团购售卖",
        "desc":"展示你的工艺/制作过程——用细节说服顾客。适合餐饮/美容/制造。",
        "shot_count":7,"target_duration":35,
        "bgm":"科技感电子","filter":"亮夏","text_animation":"逐字出现","transition":"cut",
        "example_hook":"你看这个虾腮，白的。泡了八个小时花雕酒。",
    },
    "sale_comparison": {
        "name":"对比说服","icon":"⚖️","script_type":"团购售卖",
        "desc":"你的产品 vs 别人的——用对比展示差异化优势。",
        "shot_count":6,"target_duration":30,
        "bgm":"节奏电子","filter":"高对比","text_animation":"弹出对比","transition":"cut",
        "example_hook":"左边是别家的冻虾，右边是我凌晨挑的活虾。你看出区别了吗？",
    },
    "sale_customer_proof": {
        "name":"顾客证言","icon":"🗣️","script_type":"团购售卖",
        "desc":"顾客吃了/用了之后的真实反应——第三方背书最有力。",
        "shot_count":6,"target_duration":30,
        "bgm":"轻松生活","filter":"亮肤","text_animation":"淡入","transition":"dissolve",
        "example_hook":"这个客人吃了三年了，每次来都点这个。",
    },
    "sale_urgency": {
        "name":"限时紧迫","icon":"⏰","script_type":"团购售卖",
        "desc":"制造紧迫感——试营业/限时优惠/最后X份。适合促销活动。",
        "shot_count":5,"target_duration":20,
        "bgm":"快节奏鼓点","filter":"高对比","text_animation":"倒计时/闪烁","transition":"whip_pan",
        "example_hook":"试营业68，试营业结束恢复原价108。只剩最后3天！",
    },

    # ==== 引流进店 (5个) ====
    "traffic_unique": {
        "name":"独家体验","icon":"🔒","script_type":"引流进店",
        "desc":"全城只此一家——展示你的独特性，制造'不来就亏了'。",
        "shot_count":6,"target_duration":30,
        "bgm":"节奏感强","filter":"亮夏","text_animation":"放大定格","transition":"cut",
        "example_hook":"全玉田只此一家——干煸盱眙技术。",
    },
    "traffic_crowded": {
        "name":"排队火爆","icon":"🔥","script_type":"引流进店",
        "desc":"展示排队/满座/爆单场景——从众心理驱动到店。",
        "shot_count":6,"target_duration":25,
        "bgm":"快节奏电子","filter":"亮肤","text_animation":"弹出","transition":"whip_pan",
        "example_hook":"你看这排队——周五晚上7点，门口等位20桌。",
    },
    "traffic_environment": {
        "name":"环境体验","icon":"🏠","script_type":"引流进店",
        "desc":"展示你的店面环境/装修/氛围——让人想来打卡。适合餐饮/美容/零售。",
        "shot_count":7,"target_duration":35,
        "bgm":"jazz/bossa","filter":"书意","text_animation":"淡入","transition":"dissolve",
        "example_hook":"聚餐不知道去哪？来，我带你看一圈。",
    },
    "traffic_location": {
        "name":"地址导航","icon":"📍","script_type":"引流进店",
        "desc":"直接告诉顾客怎么找到你——门头+地址+导航。适合新店/搬迁。",
        "shot_count":5,"target_duration":20,
        "bgm":"轻松生活","filter":"亮肤","text_animation":"弹出地址大字","transition":"cut",
        "example_hook":"就在玉田建设路和南环路交叉口，导航搜'虾神龙虾'。",
    },
    "traffic_event": {
        "name":"活动引流","icon":"🎉","script_type":"引流进店",
        "desc":"店里有活动——新菜试吃/开业庆典/节日活动。适合活动推广。",
        "shot_count":7,"target_duration":35,
        "bgm":"欢快电子","filter":"鲜艳","text_animation":"弹跳弹出","transition":"cut+whip_pan",
        "example_hook":"这个周六，虾神龙虾一周年庆！到店就送花雕小龙虾！",
    },
}


def list_preset_templates(script_type: str = "") -> list[dict]:
    """列出剪同款预设模板，可按脚本类型筛选"""
    all_templates = [{"key":k,**v} for k,v in PRESET_TEMPLATES.items()]
    if script_type:
        all_templates = [t for t in all_templates if t.get("script_type")==script_type]
    return all_templates


def get_preset_template(key: str) -> dict | None:
    """获取指定预设模板"""
    return PRESET_TEMPLATES.get(key)


def build_editing_prompt(template_key: str) -> str:
    t = get_template(template_key)
    if not t: return ""
    dna = t.get("editing_dna",{})
    hook = t.get("hook_strategy",{})
    rt = t.get("retention_timeline",[])
    parts = [
        f"## 剪辑策略: {t['name']}（{t['script_type']}）",
        f"创作原型: {t['creator_archetype']}",
        f"节奏: {dna.get('pace','')} | 镜长: {dna.get('shot_duration',{}).get('typical','?')}s/镜 | B-roll密度: {dna.get('broll_density','?')}",
        f"运镜: {dna.get('preferred_camera',[])} | 转场: {dna.get('transition','')} | 滤镜: {dna.get('color_filter','')}",
        "",
        "### 4层钩子系统（0-1秒必须同时作用）:",
        f"- Visual: {hook.get('visual_0s','')}",
        f"- Text: {hook.get('text_0s','')}",
        f"- Verbal: {hook.get('verbal_0s','')}",
        f"- Audio: {hook.get('audio_0s','')}",
        "",
        "### 留存动作点时间线（每N秒必须有钩子拽回观众）:",
    ]
    for r in rt:
        parts.append(f"- **{r['at_sec']}s**: {r['action']} — {r['detail']}")
    parts.extend(["","### 🎬 蒙太奇剪辑手法（核心编辑哲学）:","- **计量蒙太奇**: 镜头长度本身创造节奏——短镜=紧张/兴奋，长镜=沉思/信任","- **节奏蒙太奇**: 画面内的运动方向、速度匹配相邻镜头——人物向左走→下一个镜头也向左","- **调性蒙太奇**: 情绪色调决定镜头顺序——暖→冷=转折，冷→暖=希望","- **理性蒙太奇**: 两个看似无关的镜头并列产生新含义——比如'辛苦的厨师'+'满足的食客'=匠心值得","- **匹配剪辑**: 前一个镜头结束时的形状/颜色/运动，在下一个镜头开始处延续——如圆形盘子→圆形招牌","- **J-cut/L-cut**: 声音先于画面(J-cut)或画面先于声音(L-cut)——让观众'听到'下一个镜头再看到","","### 剪辑硬规则:","1. 介绍段时长=配音时长，精确到0.1秒","2. 空镜覆盖口播画面时只覆盖视频轨，音频轨保留","3. BGM音量=人声1/3，人声出现时闪避至25%",f"4. 最少{dna.get('shot_duration',{}).get('typical','?')}s/镜，最少{t['min_shots']}个镜头","5. 钩子(0-3s)用CU特写+static固定+center中心构图——冲击力最强","6. 结尾CTA用MS中景+拉镜——'说完了，左下角'","7. 相邻镜头必须变化景别——不能连续两个CU或连续两个MS","8. 每个B-roll镜头必须和前一个口播镜头形成蒙太奇关系（内容/情绪/运动/颜色至少一项匹配）"])
    return "\n".join(parts)
