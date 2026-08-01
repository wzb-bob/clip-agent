"""
持续学习引擎——每次出片自动Kimi评估→更新规则→下次更好

闭环:
  出片 → Kimi评估(位置/大小/调色) → 提取改进参数
  → 平滑更新learned_rules.json → 下次出片自动应用 → 持续变好
"""
from __future__ import annotations
import os, json, base64, subprocess, logging, time
from pathlib import Path
from dotenv import load_dotenv
for p in ['.env','../.env','c:/Users/wangzibo/enterprise-agent-content/.env']:
    if os.path.exists(p): load_dotenv(p); break

logger = logging.getLogger(__name__)
RULES_PATH = "data/learned_rules.json"

class ContinuousLearner:
    """持续学习引擎"""

    def __init__(self):
        self.api_key = os.getenv('KIMI_API_KEY', '')
        self.model = "moonshot-v1-8k-vision-preview"
        self.api_url = "https://api.moonshot.cn/v1/chat/completions"
        self._iteration = 0

    def evaluate_and_learn(self, video_path: str, category: str,
                           industry: str = "餐饮") -> dict:
        """评估当前输出·返回改进建议·自动更新规则"""
        self._iteration += 1
        frames = self._extract_frames(video_path, 3)
        if not frames:
            return {"error": "帧提取失败"}

        suggestions = self._evaluate_frames(frames, category, industry)
        if not suggestions:
            return {"error": "Kimi评估失败"}

        self._update_rules(suggestions, category)

        return {
            "iteration": self._iteration,
            "category": category,
            "suggestions": suggestions,
            "rules_updated": True,
        }

    def _extract_frames(self, video_path: str, count: int) -> list[str]:
        import tempfile, json as _json
        probe = subprocess.run(['ffprobe','-v','quiet','-print_format','json',
            '-show_format', video_path], capture_output=True, text=True, timeout=15)
        try:
            dur = float(_json.loads(probe.stdout)['format']['duration'])
        except Exception:
            dur = 10.0
        tmp = tempfile.mkdtemp(prefix='cl_')
        frames = []
        for i in range(count):
            t = dur * (i + 0.5) / count
            fp = os.path.join(tmp, f'eval_{i}.png')
            subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
                '-i', video_path, '-vframes','1','-ss',str(t), fp],
                capture_output=True, timeout=15)
            if os.path.exists(fp):
                frames.append(fp)
        return frames

    def _evaluate_frames(self, frames: list[str], category: str,
                         industry: str) -> dict | None:
        if not self.api_key:
            return None
        import requests

        prompt = f"""评估AI剪辑的{category}类{industry}行业口播视频。返回JSON:
{{"text_position_ok":true/false,"suggested_text_y":"0.05-0.15","text_too_small":true/false,"suggested_font_size":56-100,"color_too_strong":true/false,"suggested_saturation":"high/normal/low","has_artifact":true/false,"artifact_note":"有无大面积色块遮挡/黑窗·10字内","overall_rating":1-10,"top_fix":"最需要改进的一项10字内"}}"""

        content = [{'type': 'text', 'text': prompt}]
        for fp in frames:
            with open(fp, 'rb') as f:
                content.append({'type': 'image_url',
                    'image_url': {'url': f'data:image/png;base64,{base64.b64encode(f.read()).decode()}'}})

        try:
            resp = requests.post(self.api_url,
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={'model': self.model, 'messages': [{'role': 'user', 'content': content}],
                      'max_tokens': 500, 'temperature': 0.1}, timeout=120)
            text = resp.json().get('choices',[{}])[0].get('message',{}).get('content','{}')
            import re
            m = re.search(r'\{.*\}', text, re.DOTALL)
            return json.loads(m.group(0)) if m else None
        except Exception as e:
            logger.debug("评估失败: %s", str(e)[:100])
        return None

    def _update_rules(self, suggestions: dict, category: str):
        rules = {}
        if os.path.exists(RULES_PATH):
            with open(RULES_PATH) as f:
                rules = json.load(f)

        rules.setdefault('categories', {}).setdefault(category, {})
        cat = rules['categories'][category]
        alpha = 0.3  # 平滑学习率

        old_pos = float(cat.get('price_position', '0.08'))
        raw_pos = suggestions.get('suggested_text_y', old_pos)
        try:
            new_pos = float(raw_pos) if raw_pos not in (None,'',True,False) else old_pos
        except (ValueError, TypeError):
            new_pos = old_pos
        cat['price_position'] = f'{old_pos*(1-alpha) + new_pos*alpha:.2f}'

        old_size = cat.get('price_font_size', 56)
        new_size = suggestions.get('suggested_font_size', old_size)
        if isinstance(new_size, (int, float)):
            cat['price_font_size'] = int(old_size*(1-alpha) + new_size*alpha)

        sat_map = {'high': 0.2, 'normal': 0.1, 'low': 0.03}
        old_sat = cat.get('saturation_boost', 0.1)
        new_sat = sat_map.get(suggestions.get('suggested_saturation', 'normal'), 0.1)
        cat['saturation_boost'] = round(old_sat*(1-alpha) + new_sat*alpha, 2)

        cat['overall_rating'] = suggestions.get('overall_rating', 5)
        cat['top_fix'] = suggestions.get('top_fix', '')
        rules['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        rules['iterations'] = rules.get('iterations', 0) + 1

        os.makedirs(os.path.dirname(RULES_PATH) or '.', exist_ok=True)
        with open(RULES_PATH, 'w') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        logger.info("规则更新: %s·r%.0f·%s", category, suggestions.get('overall_rating',0),
                   suggestions.get('top_fix',''))

    def feedback_loop(self, talking_video: str, script: str, category: str,
                      max_iterations: int = 3) -> list[dict]:
        """完整反馈闭环——多次迭代出片·每次改进"""
        history = []
        for i in range(max_iterations):
            from .mlt_engine import MltEngine
            from .chatcut_vfx import build_vfx_plan
            from .four_category_pipeline import run_four_category_pipeline, CategoryMaterials

            output = f"data/iteration_{i}_{category}.mp4"
            os.makedirs('data', exist_ok=True)

            materials = CategoryMaterials(talking=[talking_video])
            timeline = run_four_category_pipeline(script, materials)
            plan = build_vfx_plan(timeline, talking_video, category, '餐饮')
            engine = MltEngine()
            result = engine.render_with_fallback(plan, {'talking': talking_video}, output)

            if not result.success:
                history.append({"iteration": i, "error": result.error})
                break

            ev = self.evaluate_and_learn(result.output_path, category)
            suggestions = ev.get('suggestions', {})
            rating = suggestions.get('overall_rating', 0)
            top_fix = suggestions.get('top_fix', '')
            history.append({"iteration": i, "rating": rating, "top_fix": top_fix,
                          "output": result.output_path})
            if rating >= 8:
                break
        return history
