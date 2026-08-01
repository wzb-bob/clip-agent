"""行业色调A/B测试——Kimi Vision盲选

8个未A/B验证的行业(汽修/建材/零售/教育/健身/宠物/家政/摄影):
  A=当前INDUSTRY_COLOR_TWEAK理论值  B=中性对照(warmth0/sat0/con0.05)
  同一帧分别调色 → Kimi Vision盲选(顺序随机防位置偏倚) → 结果写回learned_rules.json

用法: python -X utf8 industry_ab_test.py [行业...]   (无参=全部8个)
"""
from __future__ import annotations
import base64, json, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv("c:/Users/wangzibo/enterprise-agent-content/.env")

from clip_agent.chatcut_vfx import INDUSTRY_COLOR_TWEAK

SOURCE_FRAME_TS = 4.5
SOURCE_VIDEO = "C:/Users/wangzibo/Desktop/测试视频/口播出镜/_x264_A5_0086.MP4.mp4"
RULES_PATH = os.path.join(os.path.dirname(__file__), "data", "learned_rules.json")
NEUTRAL = {"warmth": 0.0, "saturation": 0.0, "contrast": 0.05}
# 餐饮/美容已验证, 默认跳过
UNTESTED = ["汽修", "建材", "零售", "教育", "健身", "宠物", "家政", "摄影"]


def _eq_from_tweak(tweak: dict) -> str:
    sat = 1.0 + tweak.get("saturation", 0)
    con = 1.0 + tweak.get("contrast", 0)
    gamma = 1.0 + tweak.get("warmth", 0)
    return f"eq=saturation={sat:.2f}:contrast={con:.2f}:gamma={gamma:.2f}"


def _grade_frame(src_frame: str, vf: str, out_frame: str) -> bool:
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src_frame,
                        "-vf", vf, "-frames:v", "1", out_frame],
                       capture_output=True, timeout=30)
    return r.returncode == 0 and os.path.exists(out_frame)


def _kimi_pick(frame1: str, frame2: str, industry: str) -> str | None:
    """盲选: 返回 '1'/'2'/None"""
    import requests
    key = os.getenv("KIMI_API_KEY")
    if not key:
        return None
    b64s = []
    for fp in (frame1, frame2):
        b64s.append(base64.b64encode(open(fp, "rb").read()).decode())
    prompt = (f"这是同一个{industry}行业实体店短视频画面的两个调色版本(图1/图2)。"
              f"从{industry}行业抖音内容氛围、肤色自然度、行业质感匹配度判断,哪张更适合?"
              f"只回答: 图1 或 图2")
    content = [{"type": "text", "text": prompt}]
    for b in b64s:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
    try:
        r = requests.post("https://api.moonshot.cn/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "moonshot-v1-8k-vision-preview", "temperature": 0.1,
                  "messages": [{"role": "user", "content": content}]}, timeout=60)
        answer = r.json()["choices"][0]["message"]["content"]
        return "1" if "图1" in answer else ("2" if "图2" in answer else None)
    except Exception as e:
        print(f"  Kimi调用失败: {e}")
        return None


def run_industry(industry: str, tmp: str) -> dict:
    """双程盲选: 两轮顺序对调, 只有两轮一致才采信(防Kimi位置偏倚——实测8/8总选图2)"""
    a_tweak = INDUSTRY_COLOR_TWEAK.get(industry, {})
    variants = [("A理论值", a_tweak), ("B中性", NEUTRAL)]
    src = os.path.join(tmp, "src.jpg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(SOURCE_FRAME_TS),
                    "-i", SOURCE_VIDEO, "-frames:v", "1", "-q:v", "3", src],
                   check=True, timeout=30)
    # 预渲染两个变体帧
    graded = []
    for i, (name, tw) in enumerate(variants):
        fp = os.path.join(tmp, f"v{i}.jpg")
        if not _grade_frame(src, _eq_from_tweak(tw), fp):
            return {"industry": industry, "error": "调色渲染失败"}
        graded.append(fp)

    wins = []
    for pass_no, order in enumerate([(0, 1), (1, 0)], 1):
        pick = _kimi_pick(graded[order[0]], graded[order[1]], industry)
        if not pick:
            return {"industry": industry, "error": f"第{pass_no}轮Kimi未给出选择"}
        wins.append(variants[order[int(pick) - 1]][0])

    if wins[0] != wins[1]:
        return {"industry": industry, "winner": "不一致", "detail": f"两轮结果{wins}·差异不显著"}
    winner_name = wins[0]
    winner_tweak = dict(variants[winner_name == "B中性"][1])
    return {"industry": industry, "winner": winner_name, "tweak": winner_tweak}


def main():
    industries = sys.argv[1:] or UNTESTED
    results = []
    for ind in industries:
        with tempfile.TemporaryDirectory(prefix="ab_") as tmp:
            print(f"■ {ind} ...", flush=True)
            r = run_industry(ind, tmp)
            print(f"  → {json.dumps(r, ensure_ascii=False)}", flush=True)
            results.append(r)

    # 写回learned_rules.json(只有双程一致选中性才写回; 理论值胜/不一致=不动)
    rules = json.load(open(RULES_PATH, encoding="utf-8"))
    cats = rules.setdefault("categories", {})
    changed = []
    for r in results:
        if r.get("winner") != "B中性":
            continue
        cats[r["industry"]] = {**r["tweak"], "source": "kimi_ab_neutral_win_2pass"}
        changed.append(r["industry"])
    if changed:
        json.dump(rules, open(RULES_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    inconsistent = [r["industry"] for r in results if r.get("winner") == "不一致"]
    print(f"\n完成: {len(results)}行业 · 理论值胜(双程一致)={sum(1 for r in results if r.get('winner')=='A理论值')} · "
          f"中性胜(已写回)={changed} · 不一致(差异不显著)={inconsistent} · 失败={sum(1 for r in results if 'error' in r)}")


if __name__ == "__main__":
    main()
