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


def check_env():
    """启动前检查关键配置"""
    issues = []
    if not os.getenv("DEEPSEEK_API_KEY"):
        issues.append("DEEPSEEK_API_KEY 未配置 → AI导演降级为规则模式")
    if not os.getenv("KIMI_API_KEY"):
        issues.append("KIMI_API_KEY 未配置 → 视频分析降级为OpenCV")
    if not shutil.which("ffmpeg"):
        issues.append("FFmpeg 未安装 → 渲染不可用")
    return issues


def print_banner():
    # 快速依赖检查
    import shutil
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    deepseek_ok = bool(os.getenv("DEEPSEEK_API_KEY"))
    kimi_ok = bool(os.getenv("KIMI_API_KEY"))

    print(f"""
╔══════════════════════════════════════════════╗
║       🎬 长益剪辑Agent · 演示模式            ║
║   AI导演: 语义+视频+音频 → 一键成片          ║
╠══════════════════════════════════════════════╣
║ FFmpeg: {'✅' if ffmpeg_ok else '❌'}  DeepSeek: {'✅' if deepseek_ok else '⚠️'}  Kimi: {'✅' if kimi_ok else '⚠️'}                 ║
╚══════════════════════════════════════════════╝""")


def demo_pipeline(script_text, script_type, video_files, audio_files, output_dir, json_mode=False):
    """统一导演模式 — 语义+视频+导演+渲染一条线"""
    from clip_agent.execution_engine import quick_direct

    # 时长预估
    char_count = len(script_text)
    est_duration = char_count * 0.25 + 3  # 每字0.25s + 3s缓冲
    print(f"\n📝 脚本: {script_text[:60]}...")
    print(f"🎭 类型: {script_type} | ⏱️ 预估时长: {est_duration:.0f}s")
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

    # 带进度条的导演模式
    stages_done = set()
    def show_progress(stage, pct, msg):
        if stage not in stages_done:
            stages_done.add(stage)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            print(f"  [{bar}] {msg}")

    job = quick_direct(
        script_text=script_text, script_type=script_type,
        audio_slots=audio_slots, video_slots=video_slots,
        output_dir=output_dir,
        on_progress=show_progress,
    )

    elapsed = time.time() - t0
    er = job.enhancement_report
    sem = er.get("semantic", {})
    vid = er.get("video", {})
    dc = er.get("director_plan", {})

    print(f"\n╔══════════════════════════════════════╗")
    print(f"║      🎬 全链路阶段报告              ║")
    print(f"╠══════════════════════════════════════╣")
    print(f"║ 语义 | {sem.get('engine','?'):10s} | {sem.get('emotional_arc','?')[:35]}")
    for vs in vid.get("scenes", [])[:1]:
        print(f"║ 视频 | {vs.get('engine','?'):10s} | {vs.get('description','?')[:35]}")
    print(f"║ 导演 | {dc.get('editing_style','?'):10s} | {dc.get('color_grade','?')} | {dc.get('bgm','?')}")
    aes = er.get('aesthetic',{})
    print(f"║ 美学 | {aes.get('score',0)}分·{aes.get('error_count',0)}错·{aes.get('warning_count',0)}警")
    print(f"║ 导出 | {job.status:10s} | {len(job.sentences)}段·{elapsed:.0f}s")
    print(f"╚══════════════════════════════════════╝")
    if job.errors:
        print(f"   ⚠️: {job.errors[:2]}")
    if json_mode:
        # JSON输出模式
        import json as _json
        output = {
            "success": job.status == "done",
            "script_type": script_type,
            "segments": len(job.sentences),
            "duration": sum(s.duration_sec for s in job.sentences),
            "elapsed": elapsed,
            "semantic": sem.get("engine", "?"),
            "emotional_arc": sem.get("emotional_arc", ""),
            "video_engine": vid.get("engine", "?"),
            "director_style": dc.get("editing_style", ""),
            "color_grade": dc.get("color_grade", ""),
            "bgm": dc.get("bgm", ""),
            "aesthetic_score": aes.get("score", 0),
            "output_dir": os.path.abspath(output_dir),
        }
        print(_json.dumps(output, ensure_ascii=False, indent=2))
        return job

    if job.status == "done" or job.draft_path:
        print(f"\n✅ 输出: {os.path.abspath(output_dir)}")
        # 生成HTML报告
        try:
            from clip_agent.report_generator import generate_html_report
            report = generate_html_report(job, output_dir)
            print(f"📄 报告: {report}")
        except Exception:
            pass
        # 决策摘要
        print(f"\n🎬 导演决策摘要:")
        for s in job.sentences[:8]:
            b = "🎬B-roll" if s.is_broll else "🎤口播"
            ov = f" [{s.text_overlay}]" if s.text_overlay else ""
            sp = getattr(s, "speed", "normal")
            kb = getattr(s, "ken_burns", "")
            fx = ""
            if sp != "normal": fx += f" {sp}"
            if kb: fx += f" {kb}"
            print(f"  {b} {s.start_sec:5.1f}s {s.required_shot:3s}{fx:15s} {s.text[:20]:20s}{ov}")

        # B-roll拍摄清单
        ba = dc.get("broll_assignments", [])
        if ba:
            print(f"\n📋 B-roll拍摄清单 ({len(ba)}段):")
            for b in ba:
                ai = "🤖AI已生成" if b.get("ai_image") else "📱需拍摄"
                print(f"  {ai} @{b['at_sec']:.1f}s [{b['shot_type']}] {b['what_to_shoot'][:40]}")
                if not b.get("ai_image"):
                    print(f"     📱 {b['shooting_guide']}")


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
    parser.add_argument("--type", default="auto", help="脚本类型(auto=自动识别)")
    parser.add_argument("--video", nargs="*", default=[], help="视频素材")
    parser.add_argument("--audio", nargs="*", default=[], help="音频素材")
    parser.add_argument("--photo", help="照片路径(数字人模式)")
    parser.add_argument("--output", default="./demo_output/", help="输出目录")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式模式")
    parser.add_argument("--compare", "-c", action="store_true", help="对比模式: 旧关键词 vs 新AI导演")
    parser.add_argument("--showcase", "-s", action="store_true", help="演示模式: 全流程+HTML报告")
    parser.add_argument("--json", action="store_true", help="JSON输出(机器可读)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG, format="%(name)s:%(lineno)d %(message)s")

    # 自动识别脚本类型
    script_type = script_type
    if script_type == "auto" and args.script:
        script_type = "auto_detect"
        txt = args.script
        if any(kw in txt for kw in ["块","元","价","只","斤","团购","优惠","促销","活动"]):
            script_type = "团购售卖"
        elif any(kw in txt for kw in ["故事","经历","创业","老板","理念","年","一直","坚持","认","食材","凌晨"]):
            script_type = "老板IP"
        elif any(kw in txt for kw in ["地址","定位","导航","排队","门头","只此","独家","路","号","找"]):
            script_type = "引流进店"
        else:
            script_type = "团购售卖"

    if args.showcase and args.script:
        # 演示模式: 完整管线 + 诊断面板 + HTML报告
        print_banner()
        from clip_agent.health import print_health_report
        print_health_report()
        print()
        demo_pipeline(args.script, script_type, args.video, args.audio, args.output, args.json)
        print(f"\n📄 HTML报告: {os.path.abspath(args.output)}")
        # Auto-open in browser
        try:
            import webbrowser
            report = os.path.join(args.output, "出片报告.html")
            if os.path.exists(report):
                webbrowser.open(f"file:///{report.replace(chr(92), '/')}")
        except Exception:
            pass
    elif args.photo and args.script:
        # 🆕 数字人模式
        print_banner()
        print(f"\n👤 数字人模式: {args.photo}")
        from clip_agent.digital_human import create_and_clip
        result = create_and_clip(
            args.photo, args.script, script_type,
            output_dir=args.output,
            broll_videos=args.video,
        )
        print(f"✅ 成功: {result['success']}")
        print(f"   数字人视频: {result.get('digital_human_video','')}")
        print(f"   成品目录: {result.get('edited_video','')}")
        print(f"   {result['sentence_count']}段·{result['duration']:.0f}s")
    elif args.compare and args.script:
        print_banner()
        demo_compare(args.script, script_type)
    elif args.interactive or not args.script:
        interactive_mode()
    else:
        print_banner()
        demo_pipeline(args.script, script_type, args.video, args.audio, args.output, args.json)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"\n❌ 出错了: {e}")
        print("💡 提示:")
        print("  1. 检查 .env 文件是否存在且API Key正确")
        print("  2. 确认 FFmpeg 已安装: ffmpeg -version")
        print("  3. 运行诊断: python -c \"from clip_agent.health import print_health_report; print_health_report()\"")
        print(f"  4. 如持续失败，检查: {type(e).__name__}")
