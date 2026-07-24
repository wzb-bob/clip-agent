"""
抖音式逐镜拍摄指导 · "拍同款"模式——每镜预览→倒计时→自动推进→拍完自动成片

借鉴抖音剪映的拍摄流程:
1. 选模板 → 看到完整分镜预览
2. 逐镜拍摄: 显示参考画面+拍摄要点+倒计时
3. 每镜拍完自动跳到下一镜
4. 全部拍完 → 自动匹配→自动成片
"""
from __future__ import annotations
import json, logging, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ShootingStep:
    """一个拍摄步骤——用户照着做就行"""
    step_id: int
    label: str                    # "第1步: 产品特写"
    # 视觉参考(告诉用户拍什么)
    visual_hint: str              # "拍小龙虾的腮部——白色、干净"
    reference_description: str    # "参考: 手机凑近10cm,对焦虾腮,光线从侧面打"
    # 拍摄参数
    shot_type: str                # CU/MCU/MS
    duration_sec: float           # 建议拍多久
    camera_move: str              # 固定/推近/拉远/手持
    composition: str              # 中心/三分法
    # 文字叠加预览
    text_overlay: str             # "68块!" — 成片后这个位置会出现的文字
    text_position: str            # center/bottom
    # 成片中的位置
    timeline_position: str        # "0:00-0:03 开头钩子"
    # 拍摄技巧
    tips: list[str]               # ["手机横过来拍","保持稳定3秒","自然光从正面来"]
    # B-roll标记
    is_broll: bool = False        # 是否是覆盖口播的空镜


@dataclass
class ShootingGuide:
    """完整拍摄指南——打印出来照着拍"""
    template_name: str
    template_desc: str
    total_duration: float
    total_shots: int
    steps: list[ShootingStep]
    # 拍摄前准备
    preparation: list[str]        # ["准备三脚架或稳定器","清理镜头","找好光线"]
    # BGM信息
    bgm_suggestion: str
    # 成片预览描述
    final_video_preview: str      # "开头产品特写→老板出镜讲解→工艺展示→结尾CTA"


TEMPLATE_GUIDES = {
    "sale_price_first": {
        "name": "价格冲击·团购脚本",
        "desc": "适合团购优惠、新品上市、限时促销。快节奏,产品特写多,文字大。",
        "total_duration": 25,
        "preparation": [
            "擦干净手机镜头——产品特写时灰尘很明显",
            "准备一个手机支架或稳定器——开头特写必须稳",
            "找一个光线好的位置——自然光从侧面打过来最好",
            "准备好产品——要拍的菜品/商品摆到光线最好的位置",
        ],
        "bgm": "快节奏卡点",
        "steps": [
            ShootingStep(1, "产品最惊艳特写", "拍你产品最诱人的角度——龙虾的腮部白色、调料流淌、热气腾腾",
                "手机凑近10cm,对焦在产品最吸引人的细节上", "CU", 3, "固定", "中心",
                "68块！", "center", "0:00-0:03 开头钩子",
                ["特写要稳——用三脚架或靠墙","对焦后等1秒再开始录","光线从侧面来,不要逆光"],
                False),
            ShootingStep(2, "老板出镜介绍", "你站在产品旁边,面对镜头,手指产品,自然说话",
                "手机距离1米,拍你腰部以上。你用'我'开头讲。", "MS", 8, "固定", "三分法",
                "", "bottom", "0:03-0:11 主体口播",
                ["看镜头,不要看产品","手势自然,像跟朋友聊天","说话时停顿一下,不要一口气说完"],
                False),
            ShootingStep(3, "工艺/食材细节", "展示你的工艺——干煸过程、花雕酒泡制、活虾挑选",
                "手机缓慢推近(慢慢靠近产品),展示细节变化", "CU", 5, "推近", "中心",
                "干煸盱眙技术", "center", "0:11-0:16 B-roll覆盖",
                ["推近要慢——2秒推5厘米","对焦保持在产品的关键细节上","可以分段拍,选最好的一段"],
                True),
            ShootingStep(4, "店内环境展示", "展示你的店面环境——让观众感觉值得来",
                "手机从左到右缓慢平移,展示空间", "LS", 5, "右摇", "三分法",
                "", "bottom", "0:16-0:21 B-roll覆盖",
                ["移动要均匀——用身体转动,不是手腕","速度: 从左到右5秒","展示最有特色的区域"],
                True),
            ShootingStep(5, "顾客反应/社交证明", "如果有顾客在吃,拍他们的反应——笑容、竖大拇指",
                "远远地拍,不要打扰顾客。拍他们享受的表情", "CU", 4, "固定", "中心",
                "", "bottom", "0:21-0:25 社交证明",
                ["远远拍,不要打扰顾客","捕捉自然的表情和动作","如果顾客不愿意出镜,拍背影也行"],
                True),
            ShootingStep(6, "结尾CTA引导", "回到你出镜,手指左下角,微笑说'左下角团购已上线'",
                "手机慢慢拉远——从你面部特写拉到半身", "MS", 3, "拉远", "三分法",
                "左下角团购", "center", "0:25-0:28 结尾CTA",
                ["手指的方向要对着左下角","微笑,语气肯定","拉远要慢——3秒从脸拉到半身"],
                False),
        ],
        "preview": "0-3s:产品特写+大字价格→3-11s:老板出镜讲解→11-16s:工艺细节特写→16-21s:店内环境→21-25s:顾客反应→25-28s:CTA引导",
    },

    "ip_story_beginning": {
        "name": "创业初心·老板IP",
        "desc": "适合品牌故事、创始人访谈。慢节奏、真诚、不推销。",
        "total_duration": 50,
        "preparation": ["找一个安静的地方——背景干净不杂乱","用自然光——窗边最好,不要顶光","准备一杯水——讲久了嘴干","想好你最想说的那个故事——不用背,自然讲"],
        "bgm": "温暖钢琴",
        "steps": [
            ShootingStep(1,"开场:你是谁","面对镜头,用'我是XX,在玉田开了家XX店'开头——自然,像跟朋友聊天","手机距离60cm,拍面部特写,眼睛看镜头不要看屏幕","CU",5,"固定","中心","", "center","0:00-0:05 开场","看镜头上方(摄像头位置),不要看屏幕里的自己","说话慢一点,有停顿——你不是在背稿子","深呼吸,放松肩膀——紧张会被观众看出来"],False),
            ShootingStep(2,"转折:为什么入行","讲你入行的故事——'28岁那年我辞了工作...'","手机稍微拉远一点,拍到你的手势","MS",12,"固定","三分法","","bottom","0:05-0:17 故事展开","用手势辅助——讲到'辞了工作'时可以摆手","讲到关键处停顿1秒——观众需要消化","看镜头,不要低头——低头就断了连接"],False),
            ShootingStep(3,"展示:你的坚持","展示你坚持的东西——老照片/工具/店面/证书","手机拍你手中的物品,或者你指向的东西","CU",8,"推近","中心","","bottom","0:17-0:25 展示","物品要提前准备好——不要临时找","推近要慢——2秒推10cm","对焦在物品的关键细节上"],True),
            ShootingStep(4,"高潮:最难的时刻","讲你最难的时刻——'最难的时候员工工资都发不出来'","手机回到面部特写——这需要真诚","CU",10,"固定","中心","","center","0:25-0:35 情感高潮","讲到最难的时候,停顿,看镜头——不要急着往下说","声音可以稍微低一点——不需要一直高亢","如果讲到红了眼眶——不用忍,真实最有力量"],False),
            ShootingStep(5,"感悟:学到了什么","讲你从这段经历中学到了什么——'后来我明白了...'","手机拉远到中景——感觉你在跟观众分享人生经验","MS",8,"固定","三分法","","bottom","0:35-0:43 感悟","不用讲大道理——讲你真实的感悟","语气可以轻松一点——'后来想想其实挺傻的'","微笑——过去了,现在很好"],False),
            ShootingStep(6,"结尾:下期预告","'还想听什么故事?评论区告诉我。下期见。'","手机慢慢拉远——从你面部拉到半身","MS",5,"拉远","三分法","关注我,下期见","center","0:43-0:48 结尾","拉远要慢——3秒从脸到半身","给一个微笑或招手——友好的结束","不要说太多——留白让观众期待下一条"],False),
        ],
        "preview": "0-5s:面部特写我是谁→5-17s:入行故事+手势→17-25s:展示你的坚持→25-35s:情感高潮→35-43s:感悟→43-48s:下期预告",
    },

    "traffic_unique": {
        "name": "独家体验·引流进店",
        "desc": "全城只此一家——展示独特性，制造'不来就亏了'。",
        "total_duration": 30,
        "preparation": ["确认今天店里环境整洁","选好2-3个最有特色的区域","如果可能,等到客人最多的时候拍","准备门头——招牌、灯光、门面要干净"],
        "bgm": "节奏感强",
        "steps": [
            ShootingStep(1,"钩子:独家标签","拍你店里最独特的东西——'全玉田只此一家'","手机靠近你最有特色的元素——产品/装饰/环境","CU",3,"固定","中心","全玉田只此一家","center","0:00-0:03 钩子","标签文字要大——占画面40%","画面要有冲击力——选最独特的角度","0.5秒就要让观众停下来"],False),
            ShootingStep(2,"门头指引","站在马路对面拍你的门头——让观众知道怎么找到你","手机拍门头全景,缓慢从左到右——或者从远到近走进","LS",6,"右摇","三分法","📍玉田XX路","bottom","0:03-0:09 门头","招牌要清晰——站在马路对面能看清字","周围环境也要拍进去——地标/路口","光线要好——门头不能背光"],False),
            ShootingStep(3,"店内环境","展示你的店内环境——让观众觉得值得来","从门口走进店里——拍摄空间的变化","MS",8,"手持跟拍","三分法","","bottom","0:09-0:17 环境","走路要稳——用稳定器或双手握紧","按顺序展示——不是随便走","每个区域停2-3秒——给观众看清"],True),
            ShootingStep(4,"特色展示","展示你最值得来的理由——招牌菜/独特服务/专有体验","拍你的核心特色——让观众知道只有来你这里才能体验到","CU",5,"推近","中心","只有这里才能体验","center","0:17-0:22 特色","选最能代表你独特性的画面","推近到细节——让观众看清","如果能拍到正在体验的顾客更好"],True),
            ShootingStep(5,"顾客证言","如果有顾客,拍他们的反应——自然的微笑/享受","远远拍顾客,不要打扰,捕捉自然瞬间","CU",4,"固定","中心","回头客都说好","center","0:22-0:26 证言","用长焦——离远点拍,不要让顾客发现","等顾客最自然的时候按快门","如果顾客不愿意出镜,拍背影或手也行"],True),
            ShootingStep(6,"结尾引导","回到门头——手指左下角——'定位在左下角,导航直达'","门头定格,你站在门口或镜头外旁白","LS",4,"固定","三分法","定位在左下角","center","0:26-0:30 CTA","门头要拍正——让观众能认出","字幕:定位在左下角,导航直达","最后2秒画面定格——让观众看清地址"],False),
        ],
        "preview": "0-3s:独家标签→3-9s:门头指引→9-17s:店内环境→17-22s:特色展示→22-26s:顾客证言→26-30s:CTA引导",
    },
}


def get_shooting_guide(template_key: str) -> ShootingGuide | None:
    """获取指定模板的拍摄指南"""
    tg = TEMPLATE_GUIDES.get(template_key)
    if not tg:
        return None
    return ShootingGuide(
        template_name=tg["name"],
        template_desc=tg["desc"],
        total_duration=tg["total_duration"],
        total_shots=len(tg["steps"]),
        steps=tg["steps"],
        preparation=tg["preparation"],
        bgm_suggestion=tg["bgm"],
        final_video_preview=tg["preview"],
    )


def render_step_card(step: ShootingStep, step_index: int, total: int) -> str:
    """渲染单个拍摄步骤的卡片——手机屏幕大小友好"""
    broll_tag = ' <span style="background:#f7a04a;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;">B-ROLL</span>' if step.is_broll else ''
    tips_html = ''.join(f'<li>{t}</li>' for t in step.tips)

    return f"""<div style="background:#1a1a2e;border-radius:12px;padding:16px;margin:8px 0;color:#fff;border-left:3px solid #e94560;">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
  <b style="font-size:1.1rem;">第{step_index}/{total}步: {step.label}</b>{broll_tag}
  <span style="color:#e94560;font-weight:700;">{step.duration_sec}秒</span>
</div>
<div style="background:#16213e;border-radius:8px;padding:10px;margin:8px 0;">
  <div style="color:#b8b8d1;font-size:0.85rem;">📷 拍什么</div>
  <div style="font-size:1rem;">{step.visual_hint}</div>
</div>
<div style="background:#16213e;border-radius:8px;padding:10px;margin:8px 0;">
  <div style="color:#b8b8d1;font-size:0.85rem;">🎬 怎么拍 ({step.shot_type}·{step.camera_move}·{step.composition})</div>
  <div style="font-size:0.95rem;">{step.reference_description}</div>
</div>
<div style="display:flex;gap:8px;margin:8px 0;">
  <span style="background:#e94560;padding:2px 8px;border-radius:6px;font-size:0.8rem;">🎥 {step.shot_type}</span>
  <span style="background:#2d2d44;padding:2px 8px;border-radius:6px;font-size:0.8rem;">📐 {step.composition}</span>
  <span style="background:#2d2d44;padding:2px 8px;border-radius:6px;font-size:0.8rem;">⏱ {step.timeline_position}</span>
</div>
{f'<div style="background:#2d2d44;border-radius:6px;padding:8px;margin:8px 0;text-align:center;font-size:1.2rem;color:#ffd460;">📝 成片文字: "{step.text_overlay}"</div>' if step.text_overlay else ''}
<div style="margin-top:8px;">
  <div style="color:#b8b8d1;font-size:0.8rem;margin-bottom:4px;">💡 拍摄技巧</div>
  <ul style="margin:0;padding-left:16px;font-size:0.85rem;color:#ccc;">{tips_html}</ul>
</div>
</div>"""


def render_full_guide(guide: ShootingGuide) -> str:
    """渲染完整拍摄指南——可在手机上查看"""
    prep_html = ''.join(f'<li>{p}</li>' for p in guide.preparation)
    steps_html = ''.join(render_step_card(s, i+1, guide.total_shots) for i, s in enumerate(guide.steps))

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {{ font-family:'Microsoft YaHei',sans-serif; background:#0f0f23; color:#fff; padding:12px; max-width:500px; margin:0 auto; }}
h2 {{ color:#e94560; }}
</style></head><body>
<h2>🎬 {guide.template_name} · 拍摄指南</h2>
<p style="color:#b8b8d1;">{guide.template_desc}</p>
<div style="background:#16213e;border-radius:8px;padding:12px;margin:8px 0;">
  <b>⏱ 总时长:</b> {guide.total_duration}秒 | <b>📸 镜头数:</b> {guide.total_shots}个 | <b>🎵 BGM:</b> {guide.bgm_suggestion}
</div>
<div style="background:#16213e;border-radius:8px;padding:12px;margin:8px 0;">
  <b>📋 拍摄前准备</b>
  <ul style="margin:4px 0;padding-left:16px;">{prep_html}</ul>
</div>
<div style="background:#0a0a1a;border-radius:8px;padding:12px;margin:12px 0;border:1px solid #e94560;">
  <b>🎞️ 成片预览:</b><br><span style="color:#ffd460;">{guide.final_video_preview}</span>
</div>
{steps_html}
<div style="text-align:center;padding:20px;color:#b8b8d1;">拍完后上传 → AI自动匹配 → 一键成片!</div>
</body></html>"""
