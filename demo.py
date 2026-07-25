"""
剪辑Agent 演示脚本 — 一行命令出片

用法:
  python demo.py "68块！十只活虾！干煸盱眙技术。左下角团购已上线！" \
      --type 团购售卖 \
      --video 口播.mp4 产品.mp4 \
      --output ./我的成片/

  python demo.py --interactive  # 交互式引导模式
"""
import sys, os, time, argparse, json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Try to add backend path for full capability
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
    """完整演示管线"""
    from clip_agent.semantic_engine import analyze_script
    from clip_agent.director_ai import direct, direct_to_execution_job
    from clip_agent.execution_engine import ChangyiExecutionEngine, ExecutionJob
    from clip_agent.pro_renderer import RenderJob, render_professional

    print(f"\n📝 脚本: {script_text[:60]}...")
    print(f"🎭 类型: {script_type}")
    print(f"🎬 素材: {len(video_files or [])}视频 + {len(audio_files or [])}音频")
    print()

    # Step 1: 语义理解
    print("🔍 Step 1/4: AI语义理解...")
    t0 = time.time()
    analysis = analyze_script(script_text, script_type, use_ai=True)
    semantic_segments = []
    if analysis and analysis.segments:
        print(f"   ✅ {len(analysis.segments)}句 | 弧线: {analysis.emotional_arc[:60]}")
        semantic_segments = [
            {"text": s.text, "role": s.role, "emotion": s.emotion,
             "intensity": s.intensity, "visual_need": s.visual_need,
             "shot_type": s.shot_type, "broll_needed": s.broll_needed,
             "text_overlay": s.text_overlay, "text_position": s.text_position,
             "duration_sec": s.duration_sec, "start_sec": s.start_sec}
            for s in analysis.segments
        ]
    else:
        print("   ⚠️ AI不可用, 使用关键词规则")
        from clip_agent.semantic_engine import analyze_script_keywords
        kw = analyze_script_keywords(script_text, script_type)
        semantic_segments = [
            {"text": s.text, "role": s.role, "emotion": s.emotion,
             "intensity": s.intensity, "visual_need": s.visual_need,
             "shot_type": s.shot_type, "broll_needed": s.broll_needed,
             "text_overlay": s.text_overlay, "text_position": s.text_position,
             "duration_sec": s.duration_sec, "start_sec": s.start_sec}
            for s in kw.segments
        ]

    # Step 2: 视频分析(有素材时)
    video_scenes = []
    if video_files:
        print(f"🔬 Step 2/4: 视频分析({len(video_files)}个素材)...")
        for vf in video_files[:3]:
            if os.path.exists(vf):
                try:
                    from clip_agent.local_video_analyzer import quick_analyze
                    va = quick_analyze(vf)
                    if "error" not in va:
                        video_scenes.append(va)
                        print(f"   📹 {va['file']}: {va['inferred_type']}·{va['quality']}·{va['motion']}")
                except Exception as e:
                    print(f"   ⚠️ {vf}: {e}")
    else:
        print("🔬 Step 2/4: 视频分析(无素材,跳过)")
        # 用生成测试素材
        print("   💡 提示: 用 --video 传入真实素材获得更好效果")

    # Step 3: 导演决策
    print("🎬 Step 3/4: AI导演融合决策...")
    plan = direct(
        script_type=script_type,
        semantic_segments=semantic_segments,
        audio_segments=[],
        video_scenes=[
            {"at_sec": 0, "description": f"{v.get('inferred_type','')}·{v.get('quality','')}",
             "file": v.get("file","")}
            for v in video_scenes
        ],
        use_ai=True,
    )
    print(f"   ✅ {len(plan.segments)}段 | 风格: {plan.editing_style or '信号融合'}")
    print(f"   🎨 调色: {plan.color_grade} | 🎵 BGM: {plan.bgm_recommendation or '默认'}")
    if plan.emotional_arc:
        print(f"   🎭 弧线: {plan.emotional_arc[:60]}")

    # Step 4: 渲染
    print(f"📤 Step 4/4: 渲染导出...")
    os.makedirs(output_dir, exist_ok=True)

    render_segments = []
    video_idx = 0
    for d in plan.segments:
        vf = video_files[video_idx % len(video_files)] if video_files else None
        if vf and os.path.exists(vf):
            render_segments.append({
                "file": vf, "duration": d.duration_sec,
                "broll": d.is_broll,
                "text": d.text_overlay,
                "color_grade": plan.color_grade,
                "transition": "dissolve" if d.is_broll else "cut",
            })
            video_idx += 1
        else:
            # No real file → generate a colored placeholder
            import subprocess, tempfile
            colors = ["red", "blue", "green", "darkred"]
            color = colors[video_idx % len(colors)]
            tmp = os.path.join(output_dir, f"_seg_{video_idx}.mp4")
            subprocess.run([
                "ffmpeg","-y","-hide_banner","-loglevel","error",
                "-f","lavfi","-i",f"color=c={color}:size=1080x1920:d={d.duration_sec}",
                "-c:v","libx264","-preset","ultrafast","-crf","23",
                tmp
            ], timeout=30)
            render_segments.append({
                "file": tmp, "duration": d.duration_sec,
                "broll": d.is_broll,
                "text": d.text_overlay,
                "color_grade": plan.color_grade,
                "transition": "dissolve" if d.is_broll else "cut",
            })
            video_idx += 1

    if render_segments:
        mp4_path = os.path.join(output_dir, "成片_演示.mp4")
        job = RenderJob(segments=render_segments, output_path=mp4_path,
                       width=1080, height=1920)
        result = render_professional(job)
        if result.success:
            print(f"   ✅ 渲染完成: {result.duration_sec:.1f}s | {result.file_size_mb:.1f}MB | {result.render_time_sec:.1f}s")
            print(f"   📁 输出: {os.path.abspath(mp4_path)}")
        else:
            print(f"   ❌ 渲染失败: {result.error}")

    elapsed = time.time() - t0
    print(f"\n⏱️ 总耗时: {elapsed:.1f}s")
    print(f"📁 输出目录: {os.path.abspath(output_dir)}")

    # 保存报告
    report = {
        "script": script_text,
        "type": script_type,
        "segments": len(plan.segments),
        "emotional_arc": plan.emotional_arc,
        "color_grade": plan.color_grade,
        "duration": sum(s.duration_sec for s in plan.segments),
        "elapsed": round(elapsed, 1),
    }
    report_path = os.path.join(output_dir, "剪辑报告.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"📊 报告: {report_path}")


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

    print("\n🎭 脚本类型:")
    print("  1. 团购售卖")
    print("  2. 老板IP")
    print("  3. 引流进店")
    choice = input("选择(1-3,默认1): ").strip()
    type_map = {"1": "团购售卖", "2": "老板IP", "3": "引流进店"}
    script_type = type_map.get(choice, "团购售卖")

    print("\n🎬 视频素材(逗号分隔,直接回车跳过):")
    video_input = input("> ").strip()
    video_files = [f.strip() for f in video_input.split(",") if f.strip()] if video_input else []

    print("\n🎤 音频素材(逗号分隔,直接回车跳过):")
    audio_input = input("> ").strip()
    audio_files = [f.strip() for f in audio_input.split(",") if f.strip()] if audio_input else []

    output_dir = input("\n📁 输出目录(默认./demo_output/): ").strip() or "./demo_output/"

    demo_pipeline(script_text, script_type, video_files, audio_files, output_dir)


def main():
    parser = argparse.ArgumentParser(description="长益剪辑Agent 演示脚本")
    parser.add_argument("script", nargs="?", help="脚本文案")
    parser.add_argument("--type", default="团购售卖", help="脚本类型(团购售卖/老板IP/引流进店)")
    parser.add_argument("--video", nargs="*", default=[], help="视频素材文件列表")
    parser.add_argument("--audio", nargs="*", default=[], help="音频素材文件列表")
    parser.add_argument("--output", default="./demo_output/", help="输出目录")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式引导模式")

    args = parser.parse_args()

    if args.interactive or not args.script:
        interactive_mode()
    else:
        print_banner()
        demo_pipeline(args.script, args.type, args.video, args.audio, args.output)


if __name__ == "__main__":
    main()
