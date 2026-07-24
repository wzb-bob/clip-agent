"""
命令行工具 · 一键剪辑+批量处理

用法:
  python -m clip_agent.cli "68块！十只活虾！" --type 团购售卖 --audio a1.mp4 a2.mp4 --video v1.mp4 v2.mp4
  python -m clip_agent.cli --batch scripts.txt --audio-dir ./口播/ --video-dir ./空镜/
"""
from __future__ import annotations
import argparse, logging, os, sys, time

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="长益剪辑Agent · 一键成片")
    sub = parser.add_subparsers(dest="command")

    # 单条剪辑
    single = sub.add_parser("clip", help="单条脚本一键成片")
    single.add_argument("script", help="脚本文案")
    single.add_argument("--type", default="团购售卖", choices=["老板IP","团购售卖","引流进店"])
    single.add_argument("--audio", nargs="*", default=[], help="音频/口播文件列表")
    single.add_argument("--video", nargs="*", default=[], help="视频/画面文件列表")
    single.add_argument("--output", "-o", default="", help="输出目录")
    single.add_argument("--bgm", default="", help="BGM文件路径")

    # 批量处理
    batch = sub.add_parser("batch", help="批量脚本处理")
    batch.add_argument("scripts_file", help="脚本文件(每行一条脚本)")
    batch.add_argument("--type", default="团购售卖", choices=["老板IP","团购售卖","引流进店"])
    batch.add_argument("--audio-dir", default="", help="音频/口播素材目录")
    batch.add_argument("--video-dir", default="", help="视频/画面素材目录")
    batch.add_argument("--output-dir", "-o", default="./clip_output", help="输出目录")

    # 分析模式
    analyze = sub.add_parser("analyze", help="分析视频素材")
    analyze.add_argument("video", help="视频文件路径")
    analyze.add_argument("--type", default="auto", choices=["auto","silence","scene","dna"])

    args = parser.parse_args()

    if args.command == "clip":
        _do_clip(args)
    elif args.command == "batch":
        _do_batch(args)
    elif args.command == "analyze":
        _do_analyze(args)
    else:
        parser.print_help()


def _do_clip(args):
    """单条剪辑"""
    from .clip_this import clip_this

    print(f"🎬 长益剪辑Agent")
    print(f"   类型: {args.type}")
    print(f"   脚本: {args.script[:50]}...")
    print(f"   音频: {len(args.audio)}个  视频: {len(args.video)}个")
    print()

    def progress(stage, pct, msg):
        bar = "█" * int(pct/10) + "░" * (10 - int(pct/10))
        print(f"  [{bar}] {msg}")

    result = clip_this(
        args.script, args.type,
        audio_files=args.audio, video_files=args.video,
        output_dir=args.output, bgm=args.bgm,
        on_progress=progress,
    )

    print()
    if result.success:
        print(f"✅ 成片完成!")
        print(f"   {result.sentence_count}句·{result.total_duration:.0f}秒")
        print(f"   {result.editing_cuts}切点·{result.quality_score:.0f}分·{result.bgm_genre}")
        print(f"   📁 {result.draft_path}")
    else:
        print(f"❌ 失败: {'; '.join(result.errors)}")
        sys.exit(1)


def _do_batch(args):
    """批量处理"""
    from .batch_processor import create_batch_from_scripts, run_batch
    import glob

    # 读取脚本
    with open(args.scripts_file, 'r', encoding='utf-8') as f:
        scripts = [{"text": line.strip(), "type": args.type}
                   for line in f if line.strip() and not line.startswith('#')]

    # 收集素材
    audio_files = glob.glob(f"{args.audio_dir}/*.mp4") if args.audio_dir else []
    video_files = glob.glob(f"{args.video_dir}/*.mp4") if args.video_dir else []
    all_materials = audio_files + video_files

    print(f"📦 批量处理: {len(scripts)}条脚本·{len(all_materials)}个素材")
    print()

    jobs = create_batch_from_scripts(scripts, all_materials)

    def progress(job_id, status, pct):
        print(f"  [{pct:.0%}] {job_id}: {status}")

    t0 = time.time()
    result = run_batch(jobs, on_progress=progress)
    elapsed = time.time() - t0

    print()
    print(f"✅ 批量完成: {result.success}/{result.total}成功·{elapsed:.0f}秒")


def _do_analyze(args):
    """分析视频"""
    print(f"🔍 分析: {args.video}")

    if args.type == "silence" or args.type == "auto":
        from .deep_skills import SilenceCutter
        sc = SilenceCutter()
        report = sc.execute_mark(args.video)
        print(f"   静音: {report.gap_count}段·{report.total_silence_sec:.1f}s ({report.silence_ratio:.0f}%)")
        print(f"   建议: {report.recommendation}")

    if args.type == "scene" or args.type == "auto":
        from .deep_skills import SceneAnalyzer
        sa = SceneAnalyzer()
        report = sa.analyze(args.video)
        print(f"   背景: {report.background_type}")
        print(f"   说话人: {report.speaker_position}")
        print(f"   光线: {report.lighting_quality}")
        print(f"   安全区: {report.safe_zones}")

    if args.type == "dna" or args.type == "auto":
        from .openmontage_pipeline import analyze_reference_video
        dna = analyze_reference_video(args.video)
        print(f"   DNA: {len(dna)}维·节奏={dna.get('rhythm','?')}·色调={dna.get('color_palette','?')}")


if __name__ == "__main__":
    main()
