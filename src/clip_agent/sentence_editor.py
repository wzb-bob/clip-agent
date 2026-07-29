"""
句级编辑系统 · 每句脚本→识别素材类型→[+]上传→全部完成→一键生成剪映草稿

核心理念: 脚本的每一句话就是一条时间线，用户为每句话上传匹配画面，AI自动组装。
"""
from __future__ import annotations
import json, logging, os, re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ScriptSentence:
    """脚本中的一句话——A/B双槽上传"""
    index: int
    text: str
    start_sec: float = 0.0
    duration_sec: float = 3.0
    required_material: str = "talking_head"
    required_shot: str = "MS"
    required_camera: str = "static"
    text_overlay: str = ""
    text_position: str = "bottom"
    is_broll: bool = False
    speed: str = "normal"        # normal/slow_motion/fast_forward
    ken_burns: str = ""          # zoom_in/zoom_out/空
    # A槽: 音频(可传视频——只取声音)
    audio_file: str = ""
    audio_status: str = "pending"
    # B槽: 视频(画面覆盖——只取画面)
    video_file: str = ""
    video_status: str = "pending"


def parse_script_to_sentences(script_text: str, script_type: str = "团购售卖") -> list[ScriptSentence]:
    """
    将脚本文本拆解为句级时间线。
    每句话自动推断所需素材类型和景别。
    """
    # 按标点拆句
    sentences_raw = re.split(r'[。！？!?\n]', script_text)
    sentences_raw = [s.strip() for s in sentences_raw if len(s.strip()) >= 3]

    # 关键词→素材类型映射
    PRODUCT_KEYWORDS = ["块","元","钱","价","只","斤","份","碗","盘","盒"]
    PROCESS_KEYWORDS = ["泡","腌","煸","炒","煮","蒸","烤","炸","卤","工艺","技术","手法","秘方"]
    ENV_KEYWORDS = ["店","环境","来了","地址","定位","导航","门头","路","号"]
    CTA_KEYWORDS = ["左下","团购","点击","关注","抢","优惠","便宜","赶紧","快来","定位"]
    HOOK_KEYWORDS = ["!", "！","不看","错过","只此","独家","第一","最好"]

    result = []
    current_sec = 0.0
    total_sentences = len(sentences_raw)

    for i, text in enumerate(sentences_raw):
        # 估算时长: 每字0.3秒 + 0.5秒停顿
        duration = max(2.0, len(text) * 0.3 + 0.5)

        # 判断素材类型
        is_first = (i == 0)
        is_last = (i == total_sentences - 1)

        if is_first:
            mat, shot = "product_closeup", "CU"  # 开头=产品特写钩子
            broll = False
        elif is_last:
            mat, shot = "talking_head", "MS"      # 结尾=口播CTA
            broll = False
        elif any(kw in text for kw in PRODUCT_KEYWORDS + PROCESS_KEYWORDS):
            mat, shot = "product_closeup", "CU"   # 产品/工艺→特写
            broll = True  # B-roll覆盖
        elif any(kw in text for kw in ENV_KEYWORDS):
            mat, shot = "environment", "LS"        # 环境→全景
            broll = True
        elif any(kw in text for kw in CTA_KEYWORDS):
            mat, shot = "talking_head", "MS"       # CTA→口播
            broll = False
        else:
            mat, shot = "talking_head", "MS"       # 默认口播
            broll = False

        # 文字叠加(提取关键数字/价格)
        overlay = ""
        price_match = re.search(r'(\d+)\s*块', text)
        if price_match:
            overlay = price_match.group(0)
        elif any(kw in text for kw in HOOK_KEYWORDS):
            overlay = text[:12] if len(text) > 12 else text

        result.append(ScriptSentence(
            index=i + 1,
            text=text,
            start_sec=round(current_sec, 1),
            duration_sec=round(duration, 1),
            required_material=mat,
            required_shot=shot,
            required_camera="push_in" if broll else "static",
            text_overlay=overlay,
            text_position="center" if overlay and len(overlay) < 8 else "bottom",
            is_broll=broll,
        ))
        current_sec += duration

    return result


MATERIAL_HINTS = {
    "talking_head": {"icon":"🎤","label":"人物出镜","guide":"拍你自己面对镜头说话——半身或面部","shot":"MS/MCU","tip":"看镜头,不要看屏幕"},
    "product_closeup": {"icon":"📦","label":"产品特写","guide":"凑近拍产品的关键细节——特写要大","shot":"CU","tip":"对焦产品,保持3秒稳定"},
    "environment": {"icon":"🏠","label":"环境空镜","guide":"拍店面环境/门头/街道——展示空间","shot":"LS","tip":"缓慢移动,展示完整空间"},
    "text_card": {"icon":"📝","label":"文字卡片","guide":"纯色背景+大字——强调关键数字","shot":"—","tip":"字体要大,颜色要跳"},
}


def _generate_simple_draft(sentences, output_dir: str = "") -> str:
    """简化草稿: JSON描述文件(独立仓库模式·不依赖剪映SDK)"""
    import json
    draft = {
        "version": "1.0",
        "segments": [],
        "total_duration": sum(s.duration_sec for s in sentences),
    }
    for s in sentences:
        draft["segments"].append({
            "id": f"main_{s.segment_id}",
            "text": s.text_overlay or "",
            "start": s.start_sec,
            "duration": s.duration_sec,
            "start_sec": s.start_sec,
            "duration_sec": s.duration_sec,
            "broll": s.is_broll,
            "sub_type": "broll" if s.is_broll else "talking",
            "audio": s.audio_file if s.audio_status == "uploaded" else "",
            "video": s.video_file if s.video_status == "uploaded" else "",
        })
    out = os.path.join(output_dir or ".", "draft.json")
    os.makedirs(output_dir or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    return out


def generate_jianying_from_sentences(
    sentences: list[ScriptSentence],
    output_dir: str = "",
) -> str:
    """
    A/B双槽→剪映多轨草稿

    规则:
    - A槽有文件(音频/视频): 提取音频→放音频轨(口播声音)
    - B槽有文件(视频/图片): 放主视频轨(画面)
    - A+B都有: B的画面+A的音频=B-roll覆盖效果!
    """
    try:
        from app.services.jianying_draft import JianYingDraftGenerator
        gen = JianYingDraftGenerator(width=1080, height=1920, fps=30)
    except ImportError:
        logger.warning("jianying_draft不可用(独立仓库模式), 使用简化草稿")
        return _generate_simple_draft(sentences, output_dir)

    for s in sentences:
        dur_us = int(s.duration_sec * 1_000_000)
        start_us = int(s.start_sec * 1_000_000)

        has_audio = s.audio_file and os.path.exists(s.audio_file)
        has_video = s.video_file and os.path.exists(s.video_file)

        if has_video and has_audio:
            # A+B都有: B画面+A音频=B-roll覆盖
            gen.add_clip(s.video_file, start_us=start_us, duration_us=dur_us)
            # 静音B轨,用A轨音频
        elif has_video:
            # 只有B(视频): 正常口播或空镜
            if s.is_broll:
                gen.add_broll_overlay(s.video_file, start_us=start_us, duration_us=dur_us)
            else:
                gen.add_clip(s.video_file, start_us=start_us, duration_us=dur_us)
        elif has_audio:
            # 只有A(音频): 用音频,画面留空或黑屏
            pass  # 音频轨由JianYingDraftGenerator后续处理

        # 文字叠加
        if s.text_overlay:
            gen.add_subtitle(start_us, start_us + dur_us, s.text_overlay)

    gen.add_fade(in_dur_us=300_000, out_dur_us=800_000)

    draft_json = gen.script.dumps()
    draft_data = json.loads(draft_json) if isinstance(draft_json, str) else draft_json

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        draft_path = f"{output_dir}/draft_content.json"
        with open(draft_path, 'w', encoding='utf-8') as f:
            json.dump(draft_data, f, ensure_ascii=False, indent=2)
        return draft_path

    return json.dumps(draft_data, ensure_ascii=False, indent=2)


def render_sentence_editor_html(sentences: list[ScriptSentence]) -> str:
    """渲染句级编辑器HTML——每句一行+上传槽"""
    rows = []
    for s in sentences:
        hint = MATERIAL_HINTS.get(s.required_material, MATERIAL_HINTS["product_closeup"])
        broll_tag = '<span style="color:#f7a04a;font-size:0.7rem;">[B-ROLL]</span>' if s.is_broll else ''
        upload_status = '✅' if s.upload_status == 'uploaded' else '📤'

        rows.append(f"""
<tr>
  <td style="width:50px;text-align:center;color:#888;">{s.index}</td>
  <td style="padding:8px;">
    <div style="font-size:1rem;color:#fff;">{s.text}</div>
    <div style="font-size:0.75rem;color:#888;margin-top:4px;">
      {hint['icon']} {hint['label']} · {s.required_shot} · {s.duration_sec:.1f}s · {hint['guide'][:30]}
      {broll_tag}
    </div>
  </td>
  <td style="width:80px;text-align:center;">
    <span style="font-size:1.2rem;">{upload_status}</span>
  </td>
  <td style="width:100px;text-align:center;">
    <span style="background:#e94560;color:#fff;padding:4px 8px;border-radius:4px;font-size:0.8rem;cursor:pointer;">[+] 上传</span>
  </td>
</tr>""")

    return f"""
<div style="background:#1a1a2e;border-radius:12px;overflow:hidden;">
<table style="width:100%;border-collapse:collapse;color:#fff;">
<thead><tr style="background:#16213e;">
  <th style="padding:8px;">#</th>
  <th style="padding:8px;text-align:left;">脚本内容+素材要求</th>
  <th style="padding:8px;">状态</th>
  <th style="padding:8px;">操作</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>"""
