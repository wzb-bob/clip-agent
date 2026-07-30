"""
抖音学习数据采集+分析系统

目标: 从抖音优质视频中学习编辑模式
筛选条件: 点赞>2000·转化评论>50%·2025-2026·10行业覆盖

数据来源: 手动下载视频帧→Kimi Vision批量分析→learned_rules.json
"""
from __future__ import annotations
import os, json, logging
from pathlib import Path
from dotenv import load_dotenv
for p in ['.env','../.env','c:/Users/wangzibo/enterprise-agent-content/.env']:
    if os.path.exists(p): load_dotenv(p); break

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# 10行业搜索关键词
# ══════════════════════════════════════════════════════════

INDUSTRY_KEYWORDS = {
    "餐饮": ["团购套餐", "美食探店", "火锅", "烧烤", "小龙虾", "餐厅推荐", "好吃不贵", "新店开业"],
    "美容": ["皮肤管理", "水光针", "光电美容", "纹眉", "美容院", "护肤推荐", "敏感肌"],
    "汽修": ["汽车保养", "修车", "4S店", "机油更换", "二手车", "汽车美容", "贴膜"],
    "建材": ["装修设计", "全屋定制", "瓷砖", "地板", "橱柜", "大理石", "岩板背景墙"],
    "零售": ["新店开业", "折扣清仓", "爆款", "新款到货", "网红同款", "平替", "探店"],
    "教育": ["英语辅导", "数学补习", "艺考培训", "托班", "奥数", "编程", "书法班"],
    "健身": ["减脂", "私教课", "瑜伽", "普拉提", "马甲线", "增肌", "减肥打卡"],
    "宠物": ["猫咪", "狗狗", "宠物美容", "猫粮推荐", "宠物医院", "寄养", "驱虫"],
    "家政": ["保洁", "月嫂", "保姆", "收纳整理", "除螨", "家电清洗", "护工"],
    "摄影": ["婚纱照", "写真", "旅拍", "全家福", "证件照", "儿童摄影", "婚礼跟拍"],
}

# ══════════════════════════════════════════════════════════
# 高转化评论模式(评论中提到购买意图/位置询问/质量认可)
# ══════════════════════════════════════════════════════════

CONVERSION_COMMENTS = {
    "位置询问": ["在哪里", "地址", "怎么去", "导航", "定位", "在哪", "位置", "哪里", "哪个城市", "店在哪"],
    "价格询问": ["多少钱", "价格", "怎么收费", "费用", "贵不贵", "划算", "团购", "优惠", "套餐价"],
    "购买意图": ["怎么买", "怎么订", "预约", "囤了", "已团", "买了", "拍下", "下单", "冲了"],
    "质量认可": ["好吃", "不错", "推荐", "值得", "绝了", "太棒", "靠谱", "专业", "效果好"],
    "到店意图": ["想去", "周末去", "明天去", "试试", "尝尝", "体验一下", "改天去", "要去"],
}

class DouyinLearner:
    """抖音视频学习器——从优质视频帧中提取编辑模式"""

    def __init__(self, data_dir: str = ""):
        self.data_dir = Path(data_dir) if data_dir else Path("data/douyin_learning")
        os.makedirs(str(self.data_dir), exist_ok=True)

    def filter_videos(self, metadata: list[dict]) -> list[dict]:
        """筛选符合标准的视频: 点赞>2000·2025-2026"""
        qualified = []
        for v in metadata:
            likes = v.get("likes", 0)
            year = v.get("year", 0)
            if likes >= 2000 and 2025 <= year <= 2026:
                qualified.append(v)
        return qualified

    def check_conversion_comments(self, comments: list[str]) -> dict:
        """检查评论转化率·返回转化统计"""
        total = len(comments)
        if total == 0:
            return {"total": 0, "conversion_rate": 0, "matches": {}}

        matches = {}
        for category, keywords in CONVERSION_COMMENTS.items():
            count = 0
            for c in comments:
                if any(kw in c for kw in keywords):
                    count += 1
            matches[category] = {"count": count, "rate": count / total}

        total_conversion = sum(
            1 for c in comments
            if any(any(kw in c for kw in kws) for kws in CONVERSION_COMMENTS.values())
        )
        return {
            "total": total,
            "conversion_count": total_conversion,
            "conversion_rate": total_conversion / total,
            "by_category": matches,
        }

    def build_learning_dataset(self, video_frames_dir: str, industry: str,
                               metadata: list[dict]) -> dict:
        """
        从视频帧目录构建学习数据集。

        video_frames_dir: 包含视频帧PNG的目录(按视频分组)
        metadata: [{video_id, likes, year, comments: [...]}]

        返回: 学习数据集摘要
        """
        import subprocess, tempfile

        qualified = self.filter_videos(metadata)
        if not qualified:
            return {"error": f"无符合标准的视频(点赞>2000·2025-2026)·当前{len(metadata)}个"}

        # 检查评论转化率
        high_conversion = []
        for v in qualified:
            result = self.check_conversion_comments(v.get("comments", []))
            if result["conversion_rate"] >= 0.5:
                high_conversion.append({**v, "comment_analysis": result})

        return {
            "industry": industry,
            "total_videos": len(metadata),
            "qualified_by_likes": len(qualified),
            "high_conversion": len(high_conversion),
            "samples": high_conversion[:10],  # Top10
        }

    def get_search_prompt(self, industry: str) -> str:
        """生成抖音搜索提示词"""
        keywords = INDUSTRY_KEYWORDS.get(industry, [])
        return f"推荐搜索: {' / '.join(keywords[:5])}"

    def get_comment_filter_prompt(self) -> str:
        """生成评论过滤说明"""
        return "高转化评论特征: 询问位置/价格·表达购买意图·质量认可·到店意图"

DOUYIN_LEARNER = DouyinLearner()
