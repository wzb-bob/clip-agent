"""
批量学习器 · Kimi知识库提取·4类×10维=200案例

利用Kimi训练数据中的海量抖音视频知识·无需爬虫
"""
from __future__ import annotations
import os, json, time, requests, logging, re
from dotenv import load_dotenv
for p in ['.env','../.env','c:/Users/wangzibo/enterprise-agent-content/.env']:
    if os.path.exists(p): load_dotenv(p); break

logger = logging.getLogger(__name__)

CATEGORIES = {
    "团购售卖": {"desc":"餐饮团购口播·价格冲击·食物展示·紧迫CTA","style":"鲜艳·大字号价格·快节奏·红黄色调·食物特写"},
    "老板IP打造": {"desc":"个人品牌故事·创业经历·信任建立·温暖真实","style":"温暖·胶片质感·慢节奏·暗角·自然色调"},
    "趣味长剧情": {"desc":"多段叙事·剧情节奏·悬念设置·角色对话","style":"节奏多变·悬念转场·音效丰富·字幕大字·多镜头"},
    "引流进店": {"desc":"店面环境展示·地址引导·排队氛围·到店诱惑","style":"明亮·干净·地址大字·环境全景·导航引导"},
}

DIMENSIONS = [
    "文字叠加(价格/标题/引导文字)的位置、大小、颜色、动画方式",
    "转场类型(硬切/淡入淡出/推入/缩放)和使用频率",
    "调色风格(饱和度/亮度/色温/对比度/暗角)",
    "B-roll使用规律(插入时机/占比/类型/时长)",
    "音频处理(BGM选择/音量/音效/人声处理)",
    "剪辑节奏(平均段时长/切点频率/加速减速使用)",
    "字幕样式(字体/大小/颜色/描边/位置)",
    "CTA引导方式(如何引导用户行动/话术/视觉设计)",
    "开头钩子设计(前三秒怎么做/用什么吸引停留)",
    "结尾设计(最后三秒怎么做/如何促转化)",
]

class BatchLearner:
    def __init__(self):
        self.api_key = os.getenv('KIMI_API_KEY', '')
        self.api_url = "https://api.moonshot.cn/v1/chat/completions"
        self.model = "moonshot-v1-8k"

    def learn_category(self, category: str, desc: str, style: str) -> dict:
        results = {"category": category, "dimensions": {}, "total_examples": 0}
        for dim in DIMENSIONS:
            prompt = f"""你是抖音短视频编辑专家。分析{category}类视频({desc})的编辑模式。风格: {style}
针对"{dim}"维度，给出具体参数和5个真实案例。JSON格式: {{"参数":{{}},"案例":["","","","",""],"最佳实践":""}}。只返回JSON。"""
            try:
                resp = requests.post(self.api_url,
                    headers={'Authorization': f'Bearer {self.api_key}','Content-Type': 'application/json'},
                    json={'model': self.model,'messages': [{'role':'user','content': prompt}],
                          'max_tokens': 500, 'temperature': 0.3}, timeout=30)
                content = resp.json().get('choices',[{}])[0].get('message',{}).get('content','{}')
                m = re.search(r'\{.*\}', content, re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                    dim_key = dim.split("(")[0].strip()
                    results["dimensions"][dim_key] = data
                    results["total_examples"] += len(data.get("案例", []))
                    print(f'  {dim_key}: {len(data.get("案例",[]))}案例')
                time.sleep(0.3)
            except Exception as e:
                logger.debug("查询失败: %s", str(e)[:80])
        return results

    def learn_all(self, output_path: str = "data/learned_rules.json") -> dict:
        all_rules = {"categories": {}, "total_examples": 0,
                     "source": "kimi_batch_learning", "updated": time.strftime('%Y-%m-%dT%H:%M:%S')}
        for cat, info in CATEGORIES.items():
            print(f"\n学习: {cat}")
            result = self.learn_category(cat, info["desc"], info["style"])
            all_rules["categories"][cat] = result
            all_rules["total_examples"] += result["total_examples"]
            print(f"  合计: {result['total_examples']}案例")
            time.sleep(1)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_rules, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 学习完成: {all_rules['total_examples']}案例·{len(CATEGORIES)}类别")
        return all_rules
