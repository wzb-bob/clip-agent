"""
批量出片脚本 · CSV/JSON输入 → 批量处理 → 统一输出

用法:
  python batch.py scripts.csv
  python batch.py scripts.json --type 团购售卖 --output ./batch_output/

CSV格式: script_text,script_type,video_files
JSON格式: [{"script":"...","type":"团购售卖","videos":["a.mp4"]}]
"""
import sys, os, time, json, csv, argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent / "src"))
_backend = Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend")
if _backend.exists():
    sys.path.insert(0, str(_backend))

# Auto-load .env
try:
    from dotenv import load_dotenv
    for ep in [_backend / ".env", _backend.parent / ".env"]:
        if ep.exists():
            load_dotenv(ep)
            break
except ImportError:
    pass


def _detect_type(script: str) -> str:
    if any(kw in script for kw in ["块","元","价","团购","优惠"]): return "团购售卖"
    if any(kw in script for kw in ["故事","创业","老板","年","坚持","凌晨"]): return "老板IP"
    if any(kw in script for kw in ["地址","导航","排队","门头","只此"]): return "引流进店"
    return "团购售卖"


def process_one(script: str, stype: str, videos: list[str], outdir: str, idx: int) -> dict:
    """处理单条脚本"""
    from clip_agent.execution_engine import quick_direct

    t0 = time.time()
    vs = {}
    for i, vf in enumerate(videos):
        if os.path.exists(vf):
            vs[i + 1] = vf

    job_out = os.path.join(outdir, f"job_{idx:03d}")
    try:
        job = quick_direct(script, stype, video_slots=vs, output_dir=job_out)
        elapsed = time.time() - t0
        return {
            "index": idx, "success": job.status == "done",
            "script": script[:50], "type": stype,
            "segments": len(job.sentences),
            "duration": sum(s.duration_sec for s in job.sentences),
            "elapsed": round(elapsed, 1),
            "output": job_out if job.status == "done" else "",
            "errors": job.errors[:2],
        }
    except Exception as e:
        return {"index": idx, "success": False, "script": script[:50], "type": stype, "error": str(e)[:100]}


def main():
    parser = argparse.ArgumentParser(description="批量出片")
    parser.add_argument("input", help="CSV或JSON文件")
    parser.add_argument("--type", default="团购售卖", help="默认脚本类型")
    parser.add_argument("--output", default="./batch_output/", help="输出目录")
    parser.add_argument("--workers", type=int, default=2, help="并行数(默认2)")
    args = parser.parse_args()

    # 加载脚本列表
    scripts = []
    ip = Path(args.input)
    if not ip.exists():
        print(f"❌ 文件不存在: {args.input}")
        return

    if ip.suffix == ".json":
        data = json.loads(ip.read_text(encoding="utf-8"))
        for item in data:
            scripts.append((
                item.get("script", ""),
                item.get("type", args.type),
                item.get("videos", []),
            ))
    elif ip.suffix == ".csv":
        with open(ip, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                scripts.append((
                    row.get("script_text", row.get("script", "")),
                    row.get("script_type", row.get("type", args.type)),
                    [v.strip() for v in row.get("video_files", row.get("videos", "")).split(",") if v.strip()],
                ))
    else:
        print(f"❌ 不支持的文件格式: {ip.suffix}")
        return

    # 自动识别未指定的脚本类型
    for i, (script, stype, videos) in enumerate(scripts):
        if stype in ("auto", "", None):
            scripts[i] = (script, _detect_type(script), videos)

    if not scripts:
        print("❌ 无脚本")
        return

    os.makedirs(args.output, exist_ok=True)
    print(f"🎬 批量处理 {len(scripts)} 条脚本 (并行{args.workers})")
    print(f"📁 输出: {os.path.abspath(args.output)}\n")

    # 批量处理
    results = []
    t0 = time.time()
    total = len(scripts)
    done_count = [0]  # mutable counter for closure

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(process_one, s[0], s[1], s[2], args.output, i): i
            for i, s in enumerate(scripts, 1)
        }
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            done_count[0] += 1
            icon = "✅" if r["success"] else "❌"
            pct = f"[{done_count[0]}/{total}]"
            dur = f"{r.get('duration',0):.0f}s" if r["success"] else "失败"
            print(f"  {pct} {icon} #{r['index']:03d} [{r['type']}] {r['script'][:40]:40s} {dur} {r.get('elapsed',0):.0f}s")

    results.sort(key=lambda r: r["index"])
    total_elapsed = time.time() - t0
    success = sum(1 for r in results if r["success"])

    print(f"\n📊 完成: {success}/{len(scripts)} 成功 · {total_elapsed:.0f}s")

    # JSON报告
    report_path = os.path.join(args.output, "batch_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"total": len(scripts), "success": success, "elapsed": round(total_elapsed, 1), "results": results}, f, ensure_ascii=False, indent=2)

    # HTML汇总报告
    rows = "".join(
        f"<tr><td>{'✅' if r['success'] else '❌'}</td><td>#{r['index']:03d}</td>"
        f"<td>{r.get('type','?')}</td><td>{r.get('script','')[:50]}</td>"
        f"<td>{r.get('segments','?')}段</td><td>{r.get('duration',0):.0f}s</td>"
        f"<td>{r.get('elapsed',0):.0f}s</td></tr>"
        for r in results
    )
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><title>批量出片报告</title>
<style>body{{font-family:Microsoft YaHei;max-width:900px;margin:20px auto;padding:20px;background:#0a0a0a;color:#eee}}
h1{{color:#e94560}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #333}}
th{{color:#888}}.card{{background:#1a1a1a;border-radius:12px;padding:20px;margin:16px 0;border:1px solid #333}}
.stat{{display:inline-block;background:#222;border-radius:8px;padding:12px 20px;margin:8px;text-align:center}}
.stat .v{{font-size:1.5em;font-weight:bold;color:#e94560}}.stat .l{{font-size:0.75em;color:#888}}</style></head><body>
<h1>🎬 批量出片报告</h1><div class="card">
<div class="stat"><div class="v">{success}/{len(scripts)}</div><div class="l">成功率</div></div>
<div class="stat"><div class="v">{total_elapsed:.0f}s</div><div class="l">总耗时</div></div>
<div class="stat"><div class="v">{total_elapsed/len(scripts):.0f}s</div><div class="l">平均每条</div></div>
</div><div class="card"><h2>📋 结果</h2><table><tr><th></th><th>#</th><th>类型</th><th>脚本</th><th>段数</th><th>时长</th><th>耗时</th></tr>{rows}</table></div>
</body></html>"""
    html_path = os.path.join(args.output, "batch_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📊 JSON: {report_path}")
    print(f"📄 HTML: {html_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"\n❌ 批量处理出错: {e}")
        print(f"💡 {type(e).__name__}")
