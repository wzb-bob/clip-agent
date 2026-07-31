"""
内容分析器 · Kimi Vision驱动·实时画面分类

每2秒提取帧→Kimi判断画面类型→缓存避免重复分析

分类: 人物口播/产品特写/空镜/门头/文字画面
"""
from __future__ import annotations
import os, json, base64, subprocess, logging, time, tempfile
from pathlib import Path
from dotenv import load_dotenv
for p in ['.env','../.env','c:/Users/wangzibo/enterprise-agent-content/.env']:
    if os.path.exists(p): load_dotenv(p); break

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "talking":    {"effect": "none",          "label": "人物口播"},
    "product":    {"effect": "warm_boost",   "label": "产品特写"},
    "environment":{"effect": "bright_grade",  "label": "空镜/环境"},
    "storefront": {"effect": "bright_clean", "label": "门头/店面"},
    "text_overlay":{"effect": "vivid_pop",   "label": "文字画面"},
    "unknown":    {"effect": "warm_grade",   "label": "未知"},
}


class ContentAnalyzer:
    """Kimi Vision画面内容分析器"""

    def __init__(self):
        self.api_key = os.getenv('KIMI_API_KEY', '')
        self.model = "moonshot-v1-8k-vision-preview"
        self.api_url = "https://api.moonshot.cn/v1/chat/completions"
        self._cache: dict[str, str] = {}

    def analyze_frame(self, frame_path: str) -> str:
        """分析单帧·返回内容类型(talking/product/environment/storefront/text_overlay)"""
        if not self.api_key:
            return "unknown"

        # 检查缓存
        cache_key = str(Path(frame_path).stat().st_mtime) if os.path.exists(frame_path) else ""
        if cache_key in self._cache:
            return self._cache[cache_key]

        with open(frame_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()

        import requests
        try:
            resp = requests.post(self.api_url,
                headers={'Authorization': f'Bearer {self.api_key}',
                         'Content-Type': 'application/json'},
                json={'model': self.model, 'messages': [{'role': 'user', 'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}'}},
                    {'type': 'text', 'text': '这个视频画面的内容类型是什么?只回答以下之一: talking(人物在说话)/product(产品食物特写)/environment(空镜环境)/storefront(门头店面)。一个字回答。'}
                ]}], 'max_tokens': 10, 'temperature': 0.1}, timeout=30)

            content = resp.json().get('choices',[{}])[0].get('message',{}).get('content','').strip().lower()
            for key in CONTENT_TYPES:
                if key in content:
                    self._cache[cache_key] = key
                    return key
        except Exception as e:
            logger.debug("内容分析失败: %s", str(e)[:80])

        self._cache[cache_key] = "unknown"
        return "unknown"

    def analyze_video(self, video_path: str, sample_interval: float = 2.0) -> list[dict]:
        """分析视频·每sample_interval秒采样一帧"""
        import subprocess, json as _json
        probe = subprocess.run(['ffprobe','-v','quiet','-print_format','json','-show_format',video_path],
                               capture_output=True, text=True, timeout=15)
        try:
            dur = float(_json.loads(probe.stdout)['format']['duration'])
        except Exception:
            dur = 10.0

        tmp = tempfile.mkdtemp(prefix='ca_')
        results = []

        t = sample_interval / 2  # 从半间隔开始
        while t < dur:
            fp = os.path.join(tmp, f'frame_{t:.1f}s.png')
            subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
                '-i', video_path, '-vframes','1','-ss',str(t), fp],
                capture_output=True, timeout=15)
            if os.path.exists(fp):
                content_type = self.analyze_frame(fp)
                results.append({"time_sec": round(t,1), "type": content_type,
                               "label": CONTENT_TYPES.get(content_type,{}).get("label","")})
            t += sample_interval

        return results

    def get_effect_for(self, content_type: str) -> str:
        """内容类型→推荐效果"""
        return CONTENT_TYPES.get(content_type, CONTENT_TYPES["unknown"]).get("effect", "warm_grade")
