"""
视频学习器 · Kimi Vision批量分析参考视频·提取编辑模式

用法:
  learner = VideoLearner()
  rules = learner.analyze_video("参考口播.mp4", "团购售卖", "餐饮")
  learner.save_rules(rules, "data/learned_rules.json")

提取维度:
  - 文字叠加: 位置/大小/颜色/时机
  - 调色: 亮度/饱和度/色温
  - 转场: 类型/频率
  - 字幕: 样式/位置
  - B-roll: 比例/时机
"""
from __future__ import annotations
import os, json, base64, subprocess, logging, time, tempfile
from pathlib import Path
from dotenv import load_dotenv

# 加载Kimi API Key
for env_path in ['.env', '../.env', 'c:/Users/wangzibo/enterprise-agent-content/.env']:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

logger = logging.getLogger(__name__)

class VideoLearner:
    """Kimi Vision驱动的视频编辑模式学习器"""

    def __init__(self):
        self.api_key = os.getenv('KIMI_API_KEY', '')
        self.model = "moonshot-v1-8k-vision-preview"
        self.api_url = "https://api.moonshot.cn/v1/chat/completions"

    def analyze_video(self, video_path: str, category: str = "团购售卖",
                      industry: str = "餐饮", sample_count: int = 5) -> dict:
        """
        分析参考视频·提取编辑参数。

        返回: {category, industry, text_rules, color_rules, timing_rules, ...}
        """
        if not os.path.exists(video_path):
            return {"error": "视频不存在"}

        # 提取采样帧
        frames = self._extract_frames(video_path, sample_count)
        if not frames:
            return {"error": "帧提取失败"}

        # Kimi Vision分析每帧
        analyses = []
        for fp in frames:
            result = self._analyze_frame(fp, category, industry)
            if result:
                analyses.append(result)

        # 汇总为编辑规则
        return self._synthesize_rules(analyses, category, industry)

    def _extract_frames(self, video_path: str, count: int) -> list[str]:
        """从视频提取均匀分布的帧"""
        import subprocess, json
        # 获取时长
        probe = subprocess.run(['ffprobe','-v','quiet','-print_format','json',
            '-show_format', video_path], capture_output=True, text=True, timeout=15)
        try:
            dur = float(json.loads(probe.stdout)['format']['duration'])
        except Exception:
            dur = 10.0

        tmp = tempfile.mkdtemp(prefix='vl_')
        frames = []
        for i in range(count):
            t = dur * (i + 0.5) / count  # 均匀分布
            fp = os.path.join(tmp, f'f{i}.png')
            subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
                '-i', video_path, '-vframes','1','-ss',str(t), fp],
                capture_output=True, timeout=15)
            if os.path.exists(fp):
                frames.append(fp)
        return frames

    def _analyze_frame(self, frame_path: str, category: str, industry: str) -> dict | None:
        """Kimi Vision分析单个帧"""
        if not self.api_key:
            logger.warning("KIMI_API_KEY未配置")
            return None

        with open(frame_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()

        import requests
        prompt = f"""你是抖音短视频编辑分析专家。分析这个{category}类·{industry}行业的口播视频帧。
请以JSON格式返回以下信息(只返回JSON,不要其他文字):
{{
  "has_text_overlay": true/false,
  "text_content": "画面中的文字内容",
  "text_position": "top_center/bottom_center/center/middle_left等",
  "text_size": "large/medium/small",
  "text_color": "white/red/yellow/black等",
  "has_subtitle": true/false,
  "subtitle_position": "bottom/center等",
  "brightness": "bright/normal/dark",
  "saturation": "high/normal/low",
  "color_warmth": "warm/neutral/cool",
  "shot_type": "CU特写/MS中景/LS远景/food食物/environment环境",
  "is_broll": true/false,
  "has_price": true/false
}}"""

        try:
            resp = requests.post(self.api_url,
                headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
                json={'model': self.model, 'messages': [{'role': 'user', 'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}'}},
                    {'type': 'text', 'text': prompt}
                ]}], 'max_tokens': 400, 'temperature': 0.1}, timeout=60)

            content = resp.json().get('choices',[{}])[0].get('message',{}).get('content','{}')
            # 提取JSON
            import re
            m = re.search(r'\{.*\}', content, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            logger.debug("帧分析失败: %s", str(e)[:100])
        return None

    def _synthesize_rules(self, analyses: list[dict], category: str, industry: str) -> dict:
        """从多帧分析结果合成编辑规则"""
        if not analyses:
            return {"category": category, "industry": industry, "error": "无分析数据"}

        # 统计
        text_count = sum(1 for a in analyses if a.get('has_text_overlay'))
        broll_count = sum(1 for a in analyses if a.get('is_broll'))
        price_count = sum(1 for a in analyses if a.get('has_price'))
        n = len(analyses)

        # 最常见的文字位置
        positions = [a.get('text_position','') for a in analyses if a.get('has_text_overlay')]
        top_pos = max(set(positions), key=positions.count) if positions else "top_center"

        # 调色倾向
        sat_levels = [a.get('saturation','normal') for a in analyses]
        sat_high = sum(1 for s in sat_levels if s == 'high')
        warm_levels = [a.get('color_warmth','neutral') for a in analyses]
        warm_count = sum(1 for w in warm_levels if w == 'warm')

        return {
            "category": category,
            "industry": industry,
            "frames_analyzed": n,
            "text_overlay_ratio": text_count / n,
            "text_position_preferred": top_pos,
            "broll_ratio": broll_count / n,
            "price_tag_ratio": price_count / n,
            "saturation_high_ratio": sat_high / n,
            "color_warmth_ratio": warm_count / n,
            "recommended": {
                "price_position": "0.08" if top_pos == "top_center" else "0.15",
                "cta_position": "0.82",
                "price_font_size": 72 if text_count/n > 0.5 else 56,
                "saturation_boost": 0.15 if sat_high/n > 0.5 else 0.05,
                "warmth_boost": 0.08 if warm_count/n > 0.5 else 0.02,
                "broll_insert_rate": broll_count / n,
            },
            "raw_analyses": analyses,
        }

    def save_rules(self, rules: dict, output_path: str = "data/learned_rules.json"):
        """保存学习到的规则"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        return output_path

    def load_rules(self, path: str = "data/learned_rules.json") -> dict:
        """加载已学习的规则"""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
