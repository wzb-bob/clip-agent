"""
剪映时间线构建器 v1 · Whisper气口→draft_content.json

输入: TimelineSegment列表 + 口播视频 + 气口数据
输出: 完整的JianYing 7+ 草稿目录结构
"""
from __future__ import annotations
import json, logging, os, tempfile, zipfile
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def build_draft_from_timeline(
    segments: list,
    talking_video: str,
    output_dir: str,
    project_name: str = "AI剪辑",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> str:
    """
    从时间线生成剪映草稿。

    输出结构(JianYing 7+):
      output_dir/
        draft_content.json       # 根级索引
        draft_meta_info.json     # 项目元信息
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        # 优先 pyJianYingDraft
        from app.services.jianying_draft import JianYingDraftGenerator
        gen = JianYingDraftGenerator(width=width, height=height, fps=fps)

        # 导入口播视频为主轨
        if os.path.exists(talking_video):
            gen.add_clip(talking_video, 0, 0, 0)  # 整段导入

        # 逐段添加B-roll覆盖和字幕
        for seg in segments:
            start_us = int(seg.start_sec * 1_000_000)
            dur_us = int(seg.duration_sec * 1_000_000)

            if seg.is_broll and os.path.exists(seg.material_file) and seg.material_file != talking_video:
                gen.add_broll_overlay(
                    seg.material_file, start_us, dur_us, dur_us,
                    fade_in_us=300000, fade_out_us=300000,
                )

            if seg.transition == "dissolve":
                gen.add_transition(start_us, " dissolve")

            if seg.script_text:
                gen.add_subtitle(start_us, dur_us, seg.script_text[:50])

        gen.save()
        logger.info("剪映草稿: %s", output_dir)
        return str(output_dir)

    except Exception as e:
        logger.warning("pyJianYingDraft失败·降级手动JSON: %s", e)
        return _build_manual_draft(segments, talking_video, output_dir, project_name)


def _build_manual_draft(segments, talking_video, output_dir, project_name):
    """手动构建简化版草稿(降级)"""
    draft = {
        "platform": {"os": "windows"},
        "draft_name": project_name,
        "draft_info": {"version": 1, "create_time": int(datetime.now().timestamp())},
        "canvas_config": {"width": 1080, "height": 1920, "ratio": "9:16"},
        "materials": {"videos": [], "texts": [], "audios": []},
        "tracks": [{"id": 0, "type": "video", "segments": []}],
        "content": {"ai_packaging_meta": {"draft_is_ai_packaging_used": False}},
    }

    for seg in segments:
        start_us = int(seg.start_sec * 1_000_000)
        dur_us = int(seg.duration_sec * 1_000_000)
        draft["tracks"][0]["segments"].append({
            "id": f"seg_{seg.index}",
            "start": start_us,
            "duration": dur_us,
            "material_type": "video",
            "source": "upload" if seg.material_file != talking_video else "main",
            "is_broll": seg.is_broll,
            "transition": seg.transition,
            "script_text": seg.script_text[:50],
        })

    draft_path = os.path.join(output_dir, "draft_content.json")
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    return draft_path


def validate_draft(draft_path: str) -> dict:
    """验证草稿JSON结构完整性"""
    result = {"valid": False, "issues": [], "segments": 0}
    try:
        draft_file = draft_path
        if os.path.isdir(draft_path):
            draft_file = os.path.join(draft_path, "draft_content.json")
        if not os.path.exists(draft_file):
            result["issues"].append("draft_content.json不存在")
            return result

        with open(draft_file, encoding="utf-8") as f:
            data = json.loads(f.read())

        if "platform" not in data:
            result["issues"].append("缺少platform字段")
        if "materials" not in data:
            result["issues"].append("缺少materials字段")
        if "tracks" in data:
            for track in data["tracks"]:
                segs = track.get("segments", [])
                result["segments"] += len(segs)
                for seg in segs:
                    if "start" not in seg or "duration" not in seg:
                        result["issues"].append(f"段{seg.get('id','?')}缺少start/duration")
        elif "content" not in data:
            result["issues"].append("缺少tracks或content字段")

        # 检查AI包装标记
        ai_meta = data.get("content", {}).get("ai_packaging_meta", {})
        if not ai_meta.get("draft_is_ai_packaging_used", True):
            result["ai_packaging_ready"] = True  # 标记为可触发智能包装

        result["valid"] = len(result["issues"]) == 0
        result["version"] = data.get("draft_info", {}).get("version", "unknown")
    except json.JSONDecodeError as e:
        result["issues"].append(f"JSON格式错误: {e}")
    except Exception as e:
        result["issues"].append(str(e))
    return result


def write_output_readme(output_dir: str, timeline=None):
    """在输出目录写入使用说明"""
    readme = os.path.join(output_dir, "使用说明.txt")
    jianying_dir = _find_jianying_draft_dir()
    lines = [
        "═══════════════════════════",
        "  长益剪辑Agent · 使用说明",
        "═══════════════════════════",
        "",
        "📁 文件说明:",
        "  draft_content.json  — 剪映草稿文件（拖入剪映即用）",
    ]
    if os.path.exists(os.path.join(output_dir, "subtitles.srt")):
        lines.append("  subtitles.srt       — SRT字幕文件（导入剪映·自动同步）")
    lines.extend([
        "",
        "🚀 使用方法（3步）:",
        "  1. 打开剪映APP",
        "  2. 文件→导入草稿→选择 draft_content.json",
        "  3. 导入SRT字幕文件（如果有）",
        "  4. 点「智能包装」（会员功能·可选）→ 导出MP4",
        "",
        "💡 提示:",
        "  - 字幕已自动对齐气口时间轴·无需手动调整",
        "  - 如需精调·直接在剪映时间线拖拽修改",
    ])
    if jianying_dir:
        lines.append(f"  - 剪映草稿目录: {jianying_dir}")
    lines.append("")
    with open(readme, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return readme


def _find_jianying_draft_dir() -> str:
    """自动检测剪映草稿目录"""
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft"),
        os.path.expandvars(r"%USERPROFILE%\Documents\JianyingPro\User Data\Projects\com.lveditor.draft"),
    ]
    for d in candidates:
        if os.path.exists(d):
            return d
    return ""


def export_draft_zip(draft_dir: str) -> str:
    """将草稿目录打包为ZIP(方便下载)"""
    zip_path = draft_dir.rstrip("/\\") + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(draft_dir):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, draft_dir)
                zf.write(fp, arcname)
    return zip_path
