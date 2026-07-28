#!/usr/bin/env python3
"""长益剪辑Agent 轻量调用脚本 · Codex Skill 入口"""
import sys, os, json, argparse
from pathlib import Path

# 自动添加 clip-agent src 到 path
_skill_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_skill_dir / "src"))

# 尝试添加 backend path
_backend = Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend")
if _backend.exists():
    sys.path.insert(0, str(_backend))

# 加载 .env
try:
    from dotenv import load_dotenv
    for ep in [_backend / ".env", _backend.parent / ".env"]:
        if ep.exists():
            load_dotenv(ep)
            break
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(description="长益剪辑Agent")
    parser.add_argument("--script", required=True, help="口播脚本文案")
    parser.add_argument("--talking", nargs="*", default=[], help="口播出镜视频")
    parser.add_argument("--env", nargs="*", default=[], help="店铺环境素材")
    parser.add_argument("--product", nargs="*", default=[], help="产品展示素材")
    parser.add_argument("--cta", nargs="*", default=[], help="引导CTA素材")
    parser.add_argument("--output", default="./output/", help="输出目录")
    parser.add_argument("--type", default="老板IP", help="脚本类型")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    from clip_agent.four_category_pipeline import run_four_category_pipeline, CategoryMaterials
    from clip_agent.jianying_timeline_builder import export_draft_zip

    materials = CategoryMaterials(
        talking=args.talking, environment=args.env,
        product=args.product, cta=args.cta,
    )

    timeline = run_four_category_pipeline(args.script, materials, output_dir=args.output)
    srt_path = getattr(timeline, "srt_path", "")

    if args.json:
        output = {
            "segments": len(timeline.segments),
            "duration": timeline.total_duration,
            "breath_points": len(timeline.breath_points),
            "srt_path": srt_path,
            "draft_zip": "",
        }
        if timeline.draft_path:
            output["draft_zip"] = export_draft_zip(timeline.draft_path)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"段数: {len(timeline.segments)}·时长: {timeline.total_duration:.0f}s")
        if srt_path:
            print(f"SRT: {srt_path}")
        if timeline.draft_path:
            zip_path = export_draft_zip(timeline.draft_path)
            print(f"草稿ZIP: {zip_path}")
        print("💡 解压 → 拖入剪映 → 字幕就位 → 智能包装 → 出片")


if __name__ == "__main__":
    main()
