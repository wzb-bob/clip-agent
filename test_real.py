"""
真实素材测试脚本 · 每阶段输出可见

用法:
  python test_real.py 口播视频.mp4 "68块！十只活虾！..."
  python test_real.py 口播视频.mp4 --script-file 脚本.txt --type 团购售卖
"""
import sys, os, time, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
_backend = Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend")
if _backend.exists():
    sys.path.insert(0, str(_backend))

try:
    from dotenv import load_dotenv
    for ep in [_backend / ".env", _backend.parent / ".env"]:
        if ep.exists():
            load_dotenv(ep)
            break
except ImportError:
    pass


def test_video(video_path: str, script_text: str, script_type: str = "团购售卖"):
    """逐阶段测试，输出每个阶段的中间结果"""
    from pathlib import Path

    vp = Path(video_path)
    if not vp.exists():
        print(f"❌ 文件不存在: {video_path}")
        return

    print("=" * 60)
    print(f"🧪 真实素材测试: {vp.name}")
    print(f"   大小: {vp.stat().st_size / 1024 / 1024:.1f}MB")
    print(f"   脚本: {script_text[:50]}...")
    print("=" * 60)

    # Stage 0: 格式检查
    try:
        import json, subprocess
        r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_streams", str(vp)],
                         capture_output=True, text=True, timeout=10)
        streams = json.loads(r.stdout).get("streams",[])
        vcodec = [s.get("codec_name") for s in streams if s.get("codec_type")=="video"]
        acodec = [s.get("codec_name") for s in streams if s.get("codec_type")=="audio"]
        if any(c in ("hevc","h265") for c in vcodec):
            print("   ⚠️ HEVC格式·自动转x264...")
            x264 = str(vp.parent / f"_x264_{vp.name}.mp4")
            if not os.path.exists(x264):
                subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                    "-i",str(vp),"-c:v","libx264","-preset","fast","-crf","18","-c:a","aac",x264],timeout=300)
            if os.path.exists(x264):
                video_path = x264
                vp = Path(x264)
                print(f"   ✅ 已转换: {vp.name}")
            else:
                print("   ❌ 转换失败·继续用原文件")
    except Exception:
        pass

    # Stage 1: FFprobe 基本信息
    print("\n📹 Stage 1: 视频基本信息")
    try:
        import json, subprocess
        r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format","-show_streams", str(vp)],
                         capture_output=True, text=True, timeout=10)
        d = json.loads(r.stdout)
        fmt = d.get("format", {})
        vs = [s for s in d.get("streams", []) if s.get("codec_type") == "video"][0]
        audio = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
        print(f"   时长: {float(fmt.get('duration',0)):.1f}s")
        print(f"   分辨率: {vs.get('width')}x{vs.get('height')}")
        print(f"   编码: {vs.get('codec_name')} | 帧率: {vs.get('r_frame_rate')}")
        print(f"   音频: {'有('+str(len(audio))+'轨)' if audio else '无'}")
        print(f"   大小: {float(fmt.get('size',0))/1024/1024:.1f}MB")
    except Exception as e:
        print(f"   ❌ FFprobe失败: {e}")
        return

    # Stage 2: Kimi K2.6 视频理解
    print("\n🤖 Stage 2: Kimi K2.6 视频理解")
    try:
        from clip_agent.kimi_scene_analyzer import analyze_video_scenes
        t0 = time.time()
        scenes = analyze_video_scenes(str(vp), frame_count=3)
        elapsed = time.time() - t0
        if scenes:
            for s in scenes:
                print(f"   @{s.at_sec:.1f}s: {s.description}")
        else:
            print("   ⚠️ 无结果(Kimi Key未配或API失败)")
    except Exception as e:
        print(f"   ❌ {e}")

    # Stage 3: OpenCV 本地分析
    print("\n📷 Stage 3: OpenCV 本地分析")
    try:
        from clip_agent.local_video_analyzer import quick_analyze
        t0 = time.time()
        va = quick_analyze(str(vp))
        elapsed = time.time() - t0
        if "error" not in va:
            print(f"   质量: {va['quality']} | 清晰度: {va.get('sharpness','?')}")
            print(f"   人脸: {'有('+str(va.get('face_coverage_pct',0))+'%)' if va.get('has_face') else '无'}")
            print(f"   类型推断: {va['inferred_type']}")
            print(f"   运动: {va['motion']} | 场景数: {va.get('scene_count',1)}")
            print(f"   建议: {va.get('recommendation','')}")
    except Exception as e:
        print(f"   ❌ {e}")

    # Stage 4: Whisper 音频理解(有音频时)
    has_audio = bool(audio)
    if has_audio:
        print("\n🎤 Stage 4: Whisper 音频理解")
        try:
            from clip_agent.media_understanding import understand_audio
            t0 = time.time()
            ad = understand_audio(str(vp))
            elapsed = time.time() - t0
            print(f"   转录({elapsed:.0f}s): {ad.get('transcript','')[:100]}")
            print(f"   分段: {len(ad.get('segments',[]))}段")
            pauses = [m for m in ad.get('moments',[]) if m.get('type')=='pause']
            emphases = [m for m in ad.get('moments',[]) if m.get('type')=='emphasis']
            print(f"   自然停顿: {len(pauses)}处")
            print(f"   能量峰值: {len(emphases)}处")
        except Exception as e:
            print(f"   ❌ {e}")

    # Stage 5: DeepSeek 语义理解
    print("\n📝 Stage 5: DeepSeek 语义分析")
    try:
        from clip_agent.semantic_engine import analyze_script_semantic
        t0 = time.time()
        analysis = analyze_script_semantic(script_text, script_type)
        elapsed = time.time() - t0
        if analysis and analysis.segments:
            print(f"   引擎: {'deepseek' if analysis.emotional_arc != '规则推断' else 'keyword'}")
            print(f"   弧线: {analysis.emotional_arc[:80]}")
            print(f"   分段({len(analysis.segments)}段):")
            for s in analysis.segments[:5]:
                b = "🎬" if s.broll_needed else "🎤"
                print(f"   {b} [{s.role:15s}] {s.text[:30]:30s} | {s.emotion:8s} {s.shot_type} | {s.visual_need[:40]}")
    except Exception as e:
        print(f"   ❌ {e}")

    # Stage 6: 完整导演管线
    print("\n🎬 Stage 6: 完整导演管线")
    try:
        from clip_agent.execution_engine import quick_direct
        t0 = time.time()
        job = quick_direct(
            script_text=script_text,
            script_type=script_type,
            audio_slots={1: str(vp)} if has_audio else {},
            video_slots={1: str(vp)},
            output_dir=str(vp.parent / f"test_output_{vp.stem}"),
        )
        elapsed = time.time() - t0

        er = job.enhancement_report
        dc = er.get("director_plan", {})
        aes = er.get("aesthetic", {})

        print(f"   状态: {job.status} | 耗时: {elapsed:.0f}s | {len(job.sentences)}段")
        print(f"   导演: {dc.get('editing_style','?')} | {dc.get('color_grade','?')} | {dc.get('bgm','?')}")
        print(f"   美学: {aes.get('score',0)}分·{aes.get('error_count',0)}错·{aes.get('warning_count',0)}警")
        print(f"   视频引擎: {er.get('video',{}).get('engine','?')}")
        print(f"   语义引擎: {er.get('semantic',{}).get('engine','?')}")

        print(f"\n   📋 导演决策:")
        for s in job.sentences:
            b = "🎬B-roll" if s.is_broll else "🎤口播"
            ov = f" [{s.text_overlay}]" if s.text_overlay else ""
            sp = getattr(s, "speed", "normal")
            fx = f" {sp}" if sp != "normal" else ""
            print(f"   {b} {s.start_sec:5.1f}s {s.required_shot:3s}{fx:10s} {s.text[:25]:25s}{ov}")

        # B-roll清单
        ba = dc.get("broll_assignments", [])
        if ba:
            print(f"\n   📋 B-roll拍摄清单:")
            for b in ba[:3]:
                print(f"   🎬 @{b['at_sec']:.1f}s [{b['shot_type']}] {b['what_to_shoot'][:50]}")
                print(f"      📱 {b['shooting_guide'][:60]}")

        if job.errors:
            print(f"\n   ⚠️ 错误: {job.errors[:3]}")

    except Exception as e:
        import traceback
        print(f"   ❌ 管线失败: {e}")
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("✅ 测试完成 — 检查以上输出判断各阶段质量")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="真实素材测试")
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("script", nargs="?", help="脚本文案")
    parser.add_argument("--script-file", help="脚本文件")
    parser.add_argument("--type", default="团购售卖", help="脚本类型")
    args = parser.parse_args()

    script_text = args.script or ""
    if args.script_file:
        script_text = Path(args.script_file).read_text(encoding="utf-8").strip()
    if not script_text:
        script_text = input("📝 请输入脚本文案: ").strip()
    if not script_text:
        print("❌ 脚本不能为空")
        sys.exit(1)

    test_video(args.video, script_text, args.type)
