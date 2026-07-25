"""
剪辑Agent 演示脚本 — 一行命令出片

用法:
  python demo.py "68块！十只活虾！干煸盱眙技术。左下角团购已上线！" --type 团购售卖 --video 口播.mp4 产品.mp4
  python demo.py --interactive  # 交互式引导模式
"""
import sys, os, time, argparse, json
from pathlib import Path

# Auto-load .env for API keys (must happen before any clip_agent imports)
try:
    from dotenv import load_dotenv
    for _ep in [
        Path(r"c:\Users\wangzibo\enterprise-agent-content\.env"),
        Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend\.env"),
    ]:
        if _ep.exists():
            load_dotenv(_ep)
            break
    else:
        load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent / "src"))
_backend = Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend")
if _backend.exists():
    sys.path.insert(0, str(_backend))


def print_banner():
    print("""
╔══════════════════════════════════════════════╗
║       🎬 长益剪辑Agent · 演示模式            ║
║   AI导演: 语义+视频+音频 → 一键成片          ║
╚══════════════════════════════════════════════╝""")


def demo_pipeline(script_text, script_type, video_files, audio_files, output_dir):
    """统一导演模式 — 语义+视频+导演+渲染一条线"""
    from clip_agent.execution_engine import quick_direct

    print(f"\n📝 脚本: {script_text[:60]}...")
    print(f"🎭 类型: {script_type}")
    print(f"🎬 素材: {len(video_files or [])}视频 + {len(audio_files or [])}音频\n")

    audio_slots = {}
    video_slots = {}
    if audio_files:
        for i, f in enumerate(audio_files):
            if os.path.exists(f):
                audio_slots[i + 1] = f
    if video_files:
        for i, f in enumerate(video_files):
            if os.path.exists(f):
                video_slots[i + 1] = f

    t0 = time.time()
    os.makedirs(output_dir, exist_ok=True)

    job = quick_direct(
        script_text=script_text, script_type=script_type,
        audio_slots=audio_slots, video_slots=video_slots,
        output_dir=output_dir,
    )

    elapsed = time.time() - t0
    sem = job.enhancement_report.get("semantic", {})
    vid = job.enhancement_report.get("video", {})
    dc = job.enhancement_report.get("director_plan", {})

    print(f"\n📊 结果:")
    print(f"   语义: {sem.get('engine','?')} | 弧线: {sem.get('emotional_arc','?')[:50]}")
    for vs in vid.get("scenes", [])[:2]:
        print(f"   视频: {vs.get('engine','?')} | {vs.get('description','?')[:80]}")
    print(f"   导演: {dc.get('editing_style','信号融合')} | {dc.get('color_grade','?')} | {dc.get('bgm','?')}")
    print(f"   段数: {len(job.sentences)} | 状态: {job.status} | 耗时: {elapsed:.1f}s")
    if job.errors:
        print(f"   ⚠️: {job.errors[:2]}")
    if job.status == "done" or job.draft_path:
        print(f"\n✅ 输出: {os.path.abspath(output_dir)}")
        # 决策摘要
        print(f"\n🎬 导演决策摘要:")
        for s in job.sentences[:8]:
            b = "🎬B-roll" if s.is_broll else "🎤口播"
            ov = f" [{s.text_overlay}]" if s.text_overlay else ""
            print(f"  {b} {s.start_sec:5.1f}s {s.required_shot:3s} {s.text[:20]:20s}{ov}")


def demo_compare(script_text, script_type):
    """对比模式: 旧关键词 vs 新AI导演"""
    from clip_agent.semantic_engine import analyze_script_keywords, analyze_script_semantic

    print(f"\n📝 脚本: {script_text[:60]}...")
    print(f"🎭 类型: {script_type}\n")

    # 旧: 关键词规则
    old = analyze_script_keywords(script_text, script_type)
    # 新: AI语义
    new = analyze_script_semantic(script_text, script_type)

    if not old or not new:
        print("❌ 分析失败")
        return

    print(f"{'':5s} {'旧(关键词规则)':40s} {'新(AI语义理解)':40s}")
    print("-" * 90)

    for i in range(max(len(old.segments), len(new.segments))):
        os = old.segments[i] if i < len(old.segments) else None
        ns = new.segments[i] if i < len(new.segments) else None
        if os and ns:
            print(f"[{os.text[:12]}]")
            print(f"{'':5s} role={os.role:15s} I={os.intensity} {os.shot_type:3s} {'':15s} role={ns.role:15s} I={ns.intensity} {ns.shot_type:3s}")
            print(f"{'':5s} {os.emotion:10s} → '{os.visual_need[:30]}' {'':5s} {ns.emotion:10s} → '{ns.visual_need[:30]}'")
            print()

    print("-" * 90)
    print(f"情感弧线:")
    print(f"  旧: 规则推断(无AI理解)")
    print(f"  新: {new.emotional_arc}")
    print(f"\n旧版只看关键词(if '块' in text→产品句)")
    print(f"新版AI理解整句语义+情感+画面需求")


def interactive_mode():
    """交互式引导"""
    print_banner()
    print("\n📝 请输入脚本内容(输入完成后按Ctrl+Z回车):")
    lines = []
    try:
        while True:
            lines.append(input())
    except (EOFError, KeyboardInterrupt):
        pass
    script_text = "\n".join(lines).strip()
    if not script_text:
        print("❌ 脚本不能为空")
        return

    print("\n🎭 脚本类型: 1.团购售卖 2.老板IP 3.引流进店")
    choice = input("选择(默认1): ").strip()
    type_map = {"1": "团购售卖", "2": "老板IP", "3": "引流进店"}
    script_type = type_map.get(choice, "团购售卖")

    print("\n🎬 视频素材(逗号分隔,直接回车跳过):")
    video_input = input("> ").strip()
    video_files = [f.strip() for f in video_input.split(",") if f.strip()] if video_input else []

    output_dir = input("\n📁 输出目录(默认./demo_output/): ").strip() or "./demo_output/"
    demo_pipeline(script_text, script_type, video_files, [], output_dir)


def main():
    parser = argparse.ArgumentParser(description="长益剪辑Agent 演示脚本")
    parser.add_argument("script", nargs="?", help="脚本文案")
    parser.add_argument("--type", default="团购售卖", help="脚本类型")
    parser.add_argument("--video", nargs="*", default=[], help="视频素材")
    parser.add_argument("--audio", nargs="*", default=[], help="音频素材")
    parser.add_argument("--output", default="./demo_output/", help="输出目录")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式模式")
    parser.add_argument("--compare", "-c", action="store_true", help="对比模式: 旧关键词 vs 新AI导演")
    args = parser.parse_args()

    if args.compare and args.script:
        print_banner()
        demo_compare(args.script, args.type)
    elif args.interactive or not args.script:
        interactive_mode()
    else:
        print_banner()
        demo_pipeline(args.script, args.type, args.video, args.audio, args.output)


if __name__ == "__main__":
    main()
