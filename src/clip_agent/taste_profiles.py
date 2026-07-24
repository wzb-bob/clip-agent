"""
品味档案 · OpenMontage cinematic.md + enhancement-strategy.md + taste-direction.md

三脚本类型专属品味配置 · 替代主观形容词为具体参数
"""
from __future__ import annotations

# ================================================================
# 三脚本类型品味档案(OpenMontage taste-direction)
# ================================================================

TASTE_PROFILES = {
    "老板IP": {
        "design_read": "真诚可信的创始人故事: 温暖、沉淀、不推销。让观众感觉在跟朋友喝茶聊天。",
        "visual_variance": 3,        # 画面变化少——保持稳定,专注人脸
        "motion_intensity": 2,       # 几乎不运动——静态镜头,纪录片质感
        "information_density": 4,    # 信息密度中高——故事+感悟+金句
        "palette_discipline": "暖色基调,自然光,不加滤镜。\"温暖\"=\"暖色温+低对比+柔光+6s镜长\"",  # 用具体参数替代形容词
        "layout_variation": "面部特写→中景手势→产品手持→回到面部",
        "reference_strategy": "对标《一条》人物访谈——长镜·自然光·真诚表达",
        "anti_patterns": ["快节奏卡点音乐","大字弹幕覆盖人脸","过度美颜"],
        "quality_gates": ["每一镜都能感受到'真诚'——不需要解释为什么"],
        "enhancement": {
            "face_enhance": "soft_skin",   # 柔和磨皮——保持真实
            "color_grade": "cinematic_warm", "color_intensity": 0.6,
            "audio": "clean_speech",        # 清晰语音
            "letterbox": "none",            # 不用宽银幕
        },
    },
    "团购售卖": {
        "design_read": "快节奏交易引导: 冲击力、信任感、紧迫感。让观众0.5秒就停下,3秒就想下单。",
        "visual_variance": 8,        # 画面变化大——多角度快速切换
        "motion_intensity": 7,       # 运动感强——推拉摇移+Ken Burns
        "information_density": 7,    # 信息密度高——价格+工艺+反馈+CTA
        "palette_discipline": "鲜艳暖色+高对比。\"冲击力\"=\"亮夏滤镜+对比1.15+饱和度1.2+2s快切+红色大字\"",
        "layout_variation": "价格大字→产品特写→工艺展示→顾客反应→CTA引导",
        "reference_strategy": "对标抖音带货爆款——快切+大字+卡点+紧迫感",
        "anti_patterns": ["慢镜头","长镜停留","淡入淡出过渡"],
        "quality_gates": ["0.5秒钩子够不够冲击?","价格数字大不大?","CTA有没有紧迫感?"],
        "enhancement": {
            "face_enhance": "brighten",     # 亮肤——精神
            "color_grade": "bright_clean",  "color_intensity": 0.85,
            "audio": "clean_speech",        # 清晰语音+提高响度
            "letterbox": "none",
        },
    },
    "引流进店": {
        "design_read": "真实体验召唤: 像朋友带你看店——环境、氛围、独特性。\"看完就想来\"。",
        "visual_variance": 5,
        "motion_intensity": 4,       # 适中——手持感+稳定镜头混合
        "information_density": 5,
        "palette_discipline": "暖色自然+锐化。\"真实\"=\"暖色温+锐化1.1+环境音保留+手持感\"",
        "layout_variation": "门头→环境→特色→顾客→地址CTA",
        "reference_strategy": "对标探店博主——第一人称视角·边走边拍·真实环境音",
        "anti_patterns": ["过度调色","棚拍感","没有地址信息"],
        "quality_gates": ["观众看完知道怎么走吗?","环境展示够不够吸引人?","独特性说清楚了吗?"],
        "enhancement": {
            "face_enhance": "soft_skin",
            "color_grade": "cinematic_warm", "color_intensity": 0.7,
            "audio": "clean_speech",         # 保留环境音
            "letterbox": "none",
        },
    },
}

# ================================================================
# 增强预设(OpenMontage enhancement-strategy.md)
# ================================================================

FACE_ENHANCE_PRESETS = {
    "talking_head_standard": "通用口播——磨皮+锐化+暖色",
    "soft_skin": "柔肤——webcam/手机拍摄,去毛孔",
    "sharpen": "锐化——画面偏软/模糊",
    "brighten": "提亮——光线不足/逆光",
    "denoise": "降噪——高ISO/低光拍摄",
}

COLOR_GRADE_PROFILES = {
    "cinematic_warm": {"look": "暖色电影感", "intensity_default": 0.85},
    "cinematic_cool": {"look": "冷色电影感(青橙调)", "intensity_default": 0.7},
    "bright_clean": {"look": "明亮干净(YouTube风)", "intensity_default": 0.8},
    "moody_dark": {"look": "暗调戏剧化", "intensity_default": 0.6},
}

# 电影宽高比(OpenMontage cinematic.md)
ASPECT_RATIOS = {
    "2.39:1": {"resolution": "1920x803", "bars_px": 138, "feel": "史诗电影感"},
    "2.35:1": {"resolution": "1920x817", "bars_px": 131, "feel": "经典电影"},
    "1.85:1": {"resolution": "1920x1038", "bars_px": 21, "feel": "轻微电影感"},
    "16:9":   {"resolution": "1920x1080", "bars_px": 0, "feel": "标准"},
}

# 反主观形容词——用具体参数替代模糊形容词(OpenMontage cinematic.md)
ANTI_SUBJECTIVE_MAP = {
    "温暖": "暖色温+低对比+柔光",
    "冲击力": "亮夏滤镜+对比1.15+饱和度1.2+2s快切+红色大字",
    "真实": "暖色温+锐化1.1+环境音保留+手持感",
    "专业": "冷色温+高对比+稳定镜头+无BGM",
    "快节奏": "1-2s镜长+硬切+camera移动+120BPM以上",
    "慢节奏": "5-8s镜长+叠化+静态镜头+80BPM以下",
}


def get_taste_profile(script_type: str) -> dict:
    return TASTE_PROFILES.get(script_type, TASTE_PROFILES["团购售卖"])


def translate_mood_to_params(mood_word: str) -> str:
    """将模糊形容词翻译为具体参数"""
    return ANTI_SUBJECTIVE_MAP.get(mood_word, f"无对应参数——请用具体参数替代'{mood_word}'")


def get_enhancement_preset(face_preset: str = "talking_head_standard", color_profile: str = "cinematic_warm") -> dict:
    return {
        "face": FACE_ENHANCE_PRESETS.get(face_preset, FACE_ENHANCE_PRESETS["talking_head_standard"]),
        "color": COLOR_GRADE_PROFILES.get(color_profile, COLOR_GRADE_PROFILES["cinematic_warm"]),
    }


# ================================================================
# 音频工程规格(OpenMontage sound-design.md)
# ================================================================

AUDIO_MASTERING_SPECS = {
    "dialogue":     {"peak_db": -12, "lufs_range": (-16, -14)},
    "music_bed":    {"peak_db": -20, "below_dialogue_db": 20},
    "sfx":          {"peak_db": -12, "below_dialogue_db": 6},
    "whoosh":       {"start_before_visual_ms": 15, "duration_ms": 450},
    "true_peak":    -1.5,
    "voice_eq":     {"hpf_hz": 80, "cut_hz": 500, "boost_khz": (2, 5), "bgm_cut_khz": (2, 4)},
    "voice_comp":   {"ratio": "3:1", "attack_ms": 3, "release_ms": 15},
    "bgm_duck_db":  12,
}

AUDIO_BPM = {"calm":(60,80),"standard":(90,110),"upbeat":(120,140),"dramatic":(80,100)}
