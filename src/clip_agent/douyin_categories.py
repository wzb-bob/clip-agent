"""
抖音素材分类体系 · 比抖音更细节

抖音4大类: 商品展示/服务过程/店内环境/门头外景
我们6大类×3-4子类型×专属拍摄指南×编辑角色×推荐时长
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json, logging

logger = logging.getLogger(__name__)


@dataclass
class SubCategory:
    """子类型——最细粒度的素材分类"""
    key: str                      # "product_static_closeup"
    name: str                     # "产品静态特写"
    desc: str                     # 描述
    # 拍摄指导
    shooting_guide: str           # 怎么拍(20字以内)
    shot_type: str                # 推荐景别
    camera_move: str              # 推荐运镜
    composition: str              # 推荐构图
    duration_hint: str            # 建议时长 "3-5秒"
    lighting_tip: str             # 光线建议
    phone_position: str           # 手机位置
    common_mistakes: list[str]    # 常见错误
    # 剪辑参数
    editing_role: str             # hook/body/broll/outro
    transition_in: str            # 推荐入点转场
    transition_out: str           # 推荐出点转场
    text_overlay_hint: str        # 文字叠加建议
    broll_overlay: bool           # 是否覆盖口播画面


@dataclass
class MaterialCategory:
    """素材大类"""
    key: str
    name: str                     # "商品/产品展示"
    icon: str
    desc: str
    sub_categories: list[SubCategory]
    # 这类素材在剪辑中的角色
    primary_role: str             # hook/body/broll/outro
    typical_usage: str            # 典型用途描述


# ================================================================
# 6大类×22个子类型——全部比抖音更细节
# ================================================================

DOUYIN_MATERIAL_CATEGORIES = [
    MaterialCategory("product", "商品/产品展示", "📦",
        "展示实体产品的各种角度和细节——这是团购售卖类视频的核心素材",
        [
            SubCategory("product_static_closeup", "产品静态特写",
                "产品放在最佳位置,不移动,只拍产品本身的质感/颜色/细节",
                "手机凑近10-15cm,对焦产品最吸引人的细节,保持绝对稳定3-5秒",
                "CU","固定","中心","3-5秒","侧光45°——突出质感和立体感","与产品平齐,10-15cm距离",
                ["手持抖动——必须用支架或靠墙","对焦在背景上——点一下屏幕对焦产品","逆光——产品正面要有光"],
                "hook","cut","dissolve","价格/卖点大字居中",True),

            SubCategory("product_angle_rotation", "产品多角度环绕",
                "手机围绕产品缓慢转半圈,展示产品的各个角度",
                "手机与产品保持20cm距离,以产品为圆心缓慢移动90°-180°,速度均匀",
                "CU","弧形运动","中心","5-8秒","环形光——避免单侧阴影","与产品同高,20cm距离,缓慢环绕",
                ["移动太快——5秒转90°","距离变化——保持20cm不变","手抖——双手握手机,肘夹紧身体"],
                "body","dissolve","dissolve","工艺/产地/材质小字底部", True),

            SubCategory("product_use_demo", "产品使用演示",
                "展示产品被使用的过程——做菜/操作/试用,让观众看到产品'活'起来",
                "找一个好角度,拍下产品从准备到完成的关键3-5秒,重点拍动作最精彩的部分",
                "MS","固定","三分法","5-10秒","操作区的光线要充足——必要时补光","略高于操作台,30-50cm,斜向下",
                ["只拍结果不拍过程——过程比结果好看","手挡住产品——手机角度要避开自己的手","太快——动作放慢,让观众看清"],
                "body","cut","cut","步骤文字底部", True),

            SubCategory("product_comparison", "产品对比展示",
                "你的产品vs别人的/之前的vs现在的——对比产生说服力",
                "两个产品并排放,手机从上往下拍,或者先拍A再平移拍B,突出差异",
                "MS","固定","中心","5-8秒","均匀照明——两个产品光线要一致","正上方俯拍或正前方平拍",
                ["两个产品距离太远——并排放,紧凑","光线不均匀——两个产品要同样的光","只说不好不说好在哪——指出具体差异"],
                "body","cut","cut","对比标签(A vs B)居中", False),
        ],
        "hook","团购售卖类视频中产品特写是最强的钩子——0.5秒抓住眼球"),

    MaterialCategory("service", "服务/体验过程", "🔧",
        "展示你的服务流程和顾客体验过程——让观众看到专业和用心",
        [
            SubCategory("service_process", "服务操作过程",
                "展示你的核心服务是怎么做的——美容师操作/厨师做菜/技师维修",
                "找一个不挡手但能看清操作的角度,拍下完整的关键步骤,手部动作要清晰",
                "MCU","固定","三分法","10-20秒","操作台上方要有灯——照亮手部动作","高于操作台30cm,斜向下45°,不挡手",
                ["身体挡住操作——手机放在侧面","动作太快看不清——关键步骤放慢","只拍手不拍脸——偶尔拍到人物表情更好"],
                "body","cut","cut","步骤编号+描述底部", True),

            SubCategory("service_customer_reaction", "顾客体验反应",
                "顾客在体验你的服务时的真实反应——享受/惊喜/满足的表情",
                "远远地拍,不要打扰顾客。捕捉自然的表情变化——微笑、点头、惊喜",
                "CU","固定","中心","3-5秒","利用环境光——不要打闪光灯惊动顾客","2-3米外,用长焦或放大拍",
                ["顾客发现被拍——要隐蔽,或者事后征求同意","表情不自然——等顾客沉浸体验时再拍","只拍一个人——多拍几个不同顾客"],
                "broll","dissolve","dissolve","",True),

            SubCategory("service_before_after", "服务前后对比",
                "服务前vs服务后的对比——美容前后/清洁前后/维修前后 冲击力最强",
                "先拍before(同样角度同样光线),再拍after,两个画面要能直接对比",
                "MS","固定","中心","3+3秒(各3秒)","两次拍摄光线必须一致——固定灯光位置","同一位置同一角度,只换拍摄对象",
                ["角度变了——前后必须同一角度","光线变了——固定灯光","只拍了before没拍after——两个都要"],
                "hook","cut","cut","前后对比标签", False),
        ],
        "body","引流进店类视频的核心——展示你的专业度"),

    MaterialCategory("environment", "店内环境", "🏠",
        "展示你的店面空间——环境好是顾客来的重要理由",
        [
            SubCategory("env_interior_panorama", "店内全景",
                "展示整个店面的空间感——让观众感觉'这里环境不错,值得来'",
                "站在店的最里面或最外面,手机缓慢从左到右平移,展示整个空间",
                "LS","右摇/左摇","三分法","5-8秒","利用店内灯光——展示氛围,不要额外打光","站在角落,手机与眼同高,缓慢左→右",
                ["移动太快——8秒从左到右","拍到天花板太多——手机稍微向下","顾客不愿意出镜——拍空镜或背影"],
                "body","dissolve","dissolve","店名+特色标签底部", True),

            SubCategory("env_feature_area", "特色区域展示",
                "展示店里最有特色的区域——打卡墙/包间/吧台/儿童区",
                "先拍全景再推到特色细节——或者从特色细节拉到全景",
                "MS","推近/拉远","中心","5-8秒","突出区域的特色灯光或装饰","正对该区域,平视,展示完整空间",
                ["只拍全景没细节——推近到特色元素","移动不平滑——用身体转动不是手腕","光线太暗——打开这个区域的灯"],
                "broll","cut","cut","区域名称标签", True),

            SubCategory("env_atmosphere", "氛围细节",
                "展示店里的氛围细节——灯光/装饰/音乐/气味(通过画面暗示)",
                "找最有氛围感的角落,拍下灯光效果/装饰细节/桌上的摆设",
                "CU","固定","中心","3-5秒","利用环境光——氛围感来自光线,不要破坏它","手机与细节平齐,10-20cm,稳定",
                ["拍得太亮——保持氛围的暗调","元素太多——每次只拍一个焦点","背景杂乱——选干净的背景"],
                "broll","dissolve","dissolve","",True),

            SubCategory("env_crowded_scene", "人气火爆场景",
                "展示店里人多/排队/满座的场景——从众心理是最强的引流手段",
                "远远拍门口排队/店内满座/外卖堆成山的画面",
                "LS","固定","三分法","5-8秒","自然光或店内光——不要惊动顾客","门口或角落,手机平视,拍自然状态",
                ["人太少反而反效果——选最忙的时候拍","顾客不自然——远远拍,不要让他们发现","只拍排队不拍店内——店内有空位就显得假"],
                "hook","cut","cut","排队/火爆标签居中", False),
        ],
        "broll","引流视频的核心——环境和氛围是最好的引流素材"),

    MaterialCategory("storefront", "门头特写/外景", "🚪",
        "展示你的门头和周边环境——顾客怎么找到你",
        [
            SubCategory("sfront_signage", "门头招牌特写",
                "你的店招——顾客远远看到的第一眼",
                "站在马路对面拍门头全景,或者门口仰拍招牌——要拍到完整的店名",
                "LS","固定","中心","3-5秒","白天自然光——招牌要清晰可见,不要逆光","马路对面或门口3-5米,正面拍",
                ["招牌被遮挡——换个角度","只拍招牌不拍门——门头=招牌+门+周边","逆光——招牌背光看不清"],
                "hook","cut","cut","店名+地址大字", False),

            SubCategory("sfront_street_view", "街道外景",
                "展示你的店在什么位置——街景/周边环境/怎么找到",
                "从街道远处走进店面,或者从店面看出去的街景——给观众空间定位",
                "LS","左摇/右摇","三分法","5-8秒","自然光——展示真实的街道环境","街对面或远处,手机平视",
                ["只拍店不拍街——观众不知道在哪","镜头晃动——走路拍要稳,最好用稳定器","光线太强——避开正午强光"],
                "outro","dissolve","dissolve","定位/导航提示底部", True),

            SubCategory("sfront_parking_access", "停车/到达指引",
                "告诉开车来的顾客怎么停车,怎么走到你店里——解决最后100米问题",
                "从停车场拍向店面,或者从路口拍到店面——展示到达路线",
                "LS","固定/左摇","三分法","5-10秒","白天拍——让观众看清路线","手持,边走边拍,速度慢而稳",
                ["走太快——观众看不清路","只拍路线不拍店面——终点要给店面镜头","没拍到停车场入口——开车的人最关心这个"],
                "outro","cut","dissolve","停车指引/步行2分钟", False),
        ],
        "outro","帮助顾客找到你的店——地址信息类视频的核心素材"),

    MaterialCategory("talking", "人物出镜/口播", "🎤",
        "老板/员工出镜讲解——建立信任和人格连接",
        [
            SubCategory("talking_face_cu", "面部特写出镜",
                "人物面对镜头,面部占画面70%以上——传递真诚和信任",
                "手机距离面部50-70cm,眼神看镜头(不是看屏幕),把你最想说的那句话说出来",
                "CU","固定","中心","5-15秒","正面自然光——窗边或门口光线最好,不要顶光","与眼同高,50-70cm,使用支架",
                ["看屏幕不看镜头——看摄像头上方","光线从头顶来——脸上一片阴影","离太远——面部特写就是要有冲击力"],
                "body","fade_in","cut","金句/关键词居中", False),

            SubCategory("talking_half_body", "半身出镜讲解",
                "人物腰部以上出镜,配合手势——适合讲解产品/服务/环境",
                "手机距离1-1.5米,腰部以上入镜,手势要自然,像跟朋友介绍一样",
                "MS","固定","三分法","10-20秒","正面光或侧光——突出人物和背景的层次","与胸同高,1-1.5米,使用支架",
                ["手势僵硬——自然就好,平时怎么比划就怎么比划","站得太正——稍微侧身更有亲和力","背景太乱——简洁背景突出人物"],
                "body","cut","cut","",False),

            SubCategory("talking_action_combo", "边说边做",
                "人物一边说话一边展示——做菜边说/操作边说/带看边说",
                "手机跟拍人物的动作,同时收音要清晰——这是最自然的口播形式",
                "MS","手持/跟拍","三分法","15-30秒","操作区的光线——照亮动作和面部","手持,跟随人物移动,保持1米距离",
                ["镜头晃动厉害——用稳定器或双手握紧","收音不清晰——靠近人物,减少环境噪音","动作和说话不同步——先说再做或边说边做"],
                "body","cut","cut","",False),
        ],
        "body","所有类型视频都需要——人物是建立信任的核心"),

    MaterialCategory("social", "社交证明/顾客", "👥",
        "真实顾客的反应和评价——第三方背书比老板说一万句都有用",
        [
            SubCategory("social_customer_eating", "顾客用餐/体验",
                "顾客正在享受你的产品/服务——自然的愉悦表情",
                "远远地拍,捕捉顾客享受的瞬间——微笑/点头/大口吃",
                "CU","固定","中心","3-5秒","环境光——不要打扰顾客","2-3米外,长焦或放大拍",
                ["顾客发现被拍——要隐蔽或先征得同意","表情不自然——等顾客沉浸时抓拍","只拍一个人——多拍几个不同年龄段的顾客"],
                "broll","dissolve","dissolve","",True),

            SubCategory("social_testimonial", "顾客直接推荐",
                "顾客对着镜头说推荐的话——'这家真的不错,我吃了三年了'",
                "手机距离1米,拍顾客半身,让顾客用自己的话说为什么喜欢来",
                "MS","固定","三分法","5-10秒","正面自然光——让顾客看起来自然","与顾客眼同高,1米距离",
                ["顾客看镜头紧张——让顾客看着你而不是镜头","说的话太假——让顾客用自己的话说","拍完没征求同意——拍完一定要问能不能用"],
                "body","cut","cut","顾客的话大字底部", False),

            SubCategory("social_data_proof", "数据/荣誉证明",
                "展示你的数据——销量/好评/奖牌/媒体报道——用事实说话",
                "手机拍证书/奖牌/数据截图——缓慢推近展示细节",
                "CU","推近","中心","3-5秒","均匀光——让文字清晰可读","正对证书,20-30cm,稳定",
                ["数据看不清——推近到能看清数字","只拍证书不拍实物——证书+店面一起拍","造假——必须真实数据"],
                "broll","cut","cut","数据大字弹出", True),
        ],
        "broll","最强的信任背书——老板IP和引流视频的杀手锏"),
]


def get_all_categories() -> list[MaterialCategory]:
    return DOUYIN_MATERIAL_CATEGORIES


def get_category(key: str) -> MaterialCategory | None:
    for c in DOUYIN_MATERIAL_CATEGORIES:
        if c.key == key: return c
    return None


def get_subcategory(key: str) -> SubCategory | None:
    for c in DOUYIN_MATERIAL_CATEGORIES:
        for s in c.sub_categories:
            if s.key == key: return s
    return None


def get_shooting_checklist(script_type: str = "团购售卖") -> list[dict]:
    """根据脚本类型生成拍摄清单——每个子类型一个条目"""
    role_map = {
        "老板IP": ["talking_face_cu","talking_half_body","social_testimonial",
                    "env_feature_area","product_static_closeup"],
        "团购售卖": ["product_static_closeup","product_angle_rotation",
                      "talking_half_body","social_customer_eating","sfront_signage"],
        "引流进店": ["sfront_signage","env_crowded_scene","env_interior_panorama",
                      "social_testimonial","talking_action_combo"],
    }
    keys = role_map.get(script_type, role_map["团购售卖"])
    checklist = []
    for k in keys:
        sc = get_subcategory(k)
        if sc:
            checklist.append({
                "sub_key": sc.key, "name": sc.name,
                "shooting_guide": sc.shooting_guide,
                "shot_type": sc.shot_type, "duration": sc.duration_hint,
                "common_mistakes": sc.common_mistakes,
                "editing_role": sc.editing_role,
                "broll_overlay": sc.broll_overlay,
            })
    return checklist


def match_material_to_category(analysis_result: dict) -> str:
    """将Kimi K2.6的分析结果匹配到最合适的子类型"""
    ct = analysis_result.get("content_type", analysis_result.get("type", ""))
    tags = analysis_result.get("tags", [])
    content = analysis_result.get("content", "")

    # 映射规则——比简单的ct匹配更精确
    mapping = {
        "talking_head": "talking_face_cu" if "特写" in str(tags) or "CU" in str(tags) else "talking_half_body",
        "product_show": "product_static_closeup" if "静态" in str(tags) else "product_angle_rotation",
        "environment": "env_interior_panorama" if "全景" in str(tags) else "env_feature_area",
        "action_demo": "service_process",
        "customer_reaction": "social_customer_eating",
        "text_card": "social_data_proof",
    }
    return mapping.get(ct, "product_static_closeup")
