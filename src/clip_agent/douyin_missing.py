"""
抖音剪映缺失能力补齐 · AI配音+转场渲染+静音删除+智能美颜+AI封面
"""
from __future__ import annotations
import asyncio, base64, json, logging, os, subprocess, tempfile, time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ================================================================
# 1. AI配音 — Edge TTS 文字→语音（免费,中文自然）
# ================================================================

async def _tts_edge(text: str, output_path: str, voice: str = "zh-CN-XiaoxiaoNeural") -> dict:
    """Microsoft Edge TTS——免费,中文自然流畅"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return {"success": True, "output": output_path, "voice": voice, "text_len": len(text)}


def generate_voiceover(text: str, output_dir: str = "", voice: str = "") -> dict:
    """生成AI配音音频文件——输入文字→输出MP3

    Args:
        text: 要配音的文字
        output_dir: 输出目录
        voice: 语音角色(默认: 女声-晓晓, 可选: zh-CN-YunxiNeural男声)
    """
    voices = {
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",   # 女声-晓晓(温柔)
        "yunxi": "zh-CN-YunxiNeural",         # 男声-云希(磁性)
        "xiaoyi": "zh-CN-XiaoyiNeural",       # 女声-晓伊(活泼)
        "yunyang": "zh-CN-YunyangNeural",     # 男声-云扬(新闻)
        "default": "zh-CN-XiaoxiaoNeural",
    }
    v = voices.get(voice, voices["default"]) if voice else voices["default"]

    if not output_dir:
        output_dir = tempfile.gettempdir()
    output_path = os.path.join(output_dir, f"ai_voiceover_{int(time.time())}.mp3")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        result = asyncio.run(_tts_edge(text, output_path, v))
        logger.info("AI配音: %s → %s (%d字)", v, output_path, len(text))
        return result
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 2. 转场特效渲染 — FFmpeg crossfade/xfade
# ================================================================

TRANSITIONS_FFMPEG = {
    "fade": "fade",
    "fadeblack": "fadeblack",
    "fadewhite": "fadewhite",
    "dissolve": "dissolve",       # 叠化
    "pixelize": "pixelize",
    "wipeleft": "wipeleft",
    "wiperight": "wiperight",
    "wipeup": "wipeup",
    "wipedown": "wipedown",
    "slideright": "slideright",
    "slideleft": "slideleft",
    "slideup": "slideup",
    "slidedown": "slidedown",
    "circlecrop": "circlecrop",
    "rectcrop": "rectcrop",
    "distance": "distance",
    "fadegrays": "fadegrays",
}


def render_transition(
    video1_path: str, video2_path: str, output_path: str,
    transition_type: str = "dissolve", duration_sec: float = 0.5
) -> dict:
    """使用FFmpeg xfade滤镜渲染两个视频之间的转场效果"""
    if not os.path.exists(video1_path) or not os.path.exists(video2_path):
        return {"success": False, "error": "源视频不存在"}

    trans = TRANSITIONS_FFMPEG.get(transition_type, "dissolve")
    dur_sec = min(duration_sec, 1.0)
    offset_sec = max(0.1, dur_sec / 2)

    # 用ffprobe获取视频时长
    try:
        import json as _json
        for vp, label in [(video1_path, "v1"), (video2_path, "v2")]:
            r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format", vp],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                d = _json.loads(r.stdout)
                dur = float(d.get("format", {}).get("duration", 0))

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video1_path, "-i", video2_path,
            "-filter_complex",
            f"xfade=transition={trans}:duration={dur_sec}:offset={offset_sec}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        subprocess.run(cmd, timeout=60, check=True)
        return {"success": True, "output": output_path, "transition": transition_type}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def apply_fade_in_out(video_path: str, output_path: str, fade_in_sec: float = 0.3, fade_out_sec: float = 0.5) -> dict:
    """给视频添加淡入淡出效果"""
    try:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vf", f"fade=t=in:st=0:d={fade_in_sec},fade=t=out:st={99999}:d={fade_out_sec}",
            "-af", f"afade=t=in:st=0:d={fade_in_sec},afade=t=out:st={99999}:d={fade_out_sec}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        subprocess.run(cmd, timeout=60, check=True)
        return {"success": True, "output": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 3. 静音段自动删除 — breath_detector沉默检测→FFmpeg trim
# ================================================================

def remove_silence_segments(
    video_path: str, output_path: str,
    silence_thresh_db: int = -30, min_silence_ms: int = 500
) -> dict:
    """自动检测并删除视频中的长静音段(只保留非静音部分)"""
    try:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-af", f"silenceremove=stop_periods=-1:stop_duration={min_silence_ms/1000:.1f}:stop_threshold={silence_thresh_db}dB",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        orig_size = os.path.getsize(video_path)
        new_size = os.path.getsize(output_path)
        saved_pct = (1 - new_size / orig_size) * 100
        logger.info("静音删除: %.0f%% (%d→%d KB)", saved_pct, orig_size//1024, new_size//1024)
        return {"success": True, "output": output_path, "saved_pct": round(saved_pct, 1)}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 4. 智能美颜 — FFmpeg滤镜(磨皮+锐化+美白)
# ================================================================

def apply_beauty_filter(
    video_path: str, output_path: str,
    level: str = "medium"  # light/medium/strong
) -> dict:
    """FFmpeg美颜滤镜——磨皮(smartblur)+锐化(unsharp)+美白(eq)

    level: light=轻度, medium=中度, strong=重度
    """
    beauty_params = {
        "light": {"blur": 2, "sharpen": 0.3, "brightness": 0.03},
        "medium": {"blur": 3, "sharpen": 0.5, "brightness": 0.05},
        "strong": {"blur": 5, "sharpen": 0.8, "brightness": 0.08},
    }
    p = beauty_params.get(level, beauty_params["medium"])

    try:
        vf = (
            f"smartblur=luma_radius={p['blur']}:luma_strength=0.8:luma_threshold=0,"
            f"unsharp=luma_msize_x=3:luma_msize_y=3:luma_amount={p['sharpen']},"
            f"eq=brightness={1+p['brightness']}:saturation=1.05"
        )
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "copy",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path, "level": level}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 5. AI封面生成 — 脚本→封面设计规格
# ================================================================

@dataclass
class CoverDesign:
    """封面设计规格——可直接用于前端渲染或导出"""
    title: str
    title_style: str        # 字体/大小/颜色
    background_color: str   # 背景色
    layout: str             # 布局: center/left/top-bottom
    text_overlay: str       # 叠加文字(价格/CTA)
    tags: list[str]         # 标签
    suggested_size: str     # "1080x1920" 竖版


def generate_cover_design(
    script_text: str,
    script_type: str = "团购售卖",
    business_name: str = "",
    price: str = "",
) -> CoverDesign:
    """根据脚本内容生成封面设计方案"""
    # 提取关键信息
    lines = [l.strip() for l in script_text.split("\n") if l.strip()]
    hook = lines[0][:20] if lines else ""

    # 价格提取
    import re
    price_match = re.search(r'(\d+)\s*块', script_text)
    extracted_price = price_match.group(0) if price_match else price

    designs = {
        "老板IP": CoverDesign(
            title=business_name or "品牌故事",
            title_style="font-size:48px; color:#FFFFFF; text-shadow:2px 2px 4px rgba(0,0,0,0.5)",
            background_color="linear-gradient(135deg, #1a1a2e, #16213e)",
            layout="center",
            text_overlay=hook[:12],
            tags=["创业故事", "老板IP"],
            suggested_size="1080x1920",
        ),
        "团购售卖": CoverDesign(
            title=extracted_price or "新品上市",
            title_style="font-size:72px; color:#FF4444; font-weight:900; text-shadow:3px 3px 0 #000",
            background_color="linear-gradient(135deg, #1a1a2e, #e94560)",
            layout="center",
            text_overlay=f"↓ 左下角团购" if not extracted_price else "",
            tags=["团购", "限时优惠"],
            suggested_size="1080x1920",
        ),
        "引流进店": CoverDesign(
            title=business_name or "来店里看看",
            title_style="font-size:56px; color:#FFD700; text-shadow:3px 3px 0 #000",
            background_color="linear-gradient(135deg, #2d5016, #1a1a2e)",
            layout="top-bottom",
            text_overlay="📍 定位在左下角",
            tags=["探店", "打卡"],
            suggested_size="1080x1920",
        ),
    }
    return designs.get(script_type, designs["团购售卖"])


def render_cover_html(design: CoverDesign) -> str:
    """生成封面HTML——可直接截图作为封面"""
    tags_html = " ".join(
        f'<span style="display:inline-block;background:rgba(255,255,255,0.2);padding:4px 12px;border-radius:12px;margin:4px;font-size:24px;color:#fff;">#{t}</span>'
        for t in design.tags
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ margin:0; width:1080px; height:1920px; background:{design.background_color};
       display:flex; flex-direction:column; align-items:center; justify-content:center;
       font-family:'Microsoft YaHei',sans-serif; }}
.title {{ {design.title_style}; text-align:center; padding:40px; }}
.subtitle {{ color:#b8b8d1; font-size:32px; margin-top:20px; }}
.price-tag {{ font-size:120px; color:#FF4444; font-weight:900; text-shadow:4px 4px 0 #000; }}
.tags {{ margin-top:40px; }}
</style></head><body>
<div class="title">{design.title}</div>
<div class="subtitle">{design.text_overlay}</div>
<div class="tags">{tags_html}</div>
</body></html>"""
