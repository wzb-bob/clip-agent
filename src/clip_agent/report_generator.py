"""
出片报告生成器 · HTML格式·客户可直接打开查看
"""
from __future__ import annotations
import json, os, time
from pathlib import Path


def generate_html_report(job, output_dir: str) -> str:
    """生成HTML出片报告"""
    er = job.enhancement_report
    dc = er.get("director_plan", {})
    sem = er.get("semantic", {})
    vid = er.get("video", {})
    aes = er.get("aesthetic", {})
    dh = er.get("digital_human", {})

    segments_html = ""
    for s in job.sentences:
        b_icon = "🎬" if s.is_broll else "🎤"
        ov = f'<span class="overlay">{s.text_overlay}</span>' if s.text_overlay else ""
        segments_html += f"""
        <tr>
            <td>{b_icon}</td>
            <td>{s.start_sec:.1f}s</td>
            <td>{s.duration_sec:.1f}s</td>
            <td><b>{s.required_shot}</b></td>
            <td>{s.text[:30]}</td>
            <td>{ov}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>剪辑Agent · 出片报告</title>
<style>
body{{font-family:'Microsoft YaHei',sans-serif;max-width:800px;margin:0 auto;padding:20px;background:#0a0a0a;color:#eee}}
.card{{background:#1a1a1a;border-radius:12px;padding:20px;margin:16px 0;border:1px solid #333}}
h1{{color:#e94560;font-size:1.5em}}
h2{{color:#ffd700;font-size:1.1em;margin:0 0 12px 0}}
.stats{{display:flex;gap:12px;flex-wrap:wrap}}
.stat{{background:#222;border-radius:8px;padding:12px 16px;min-width:80px;text-align:center}}
.stat .value{{font-size:1.4em;font-weight:bold;color:#e94560}}
.stat .label{{font-size:0.75em;color:#888;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin:12px 0}}
th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #333}}
th{{color:#888;font-size:0.85em}}
.overlay{{background:#e94560;color:white;padding:2px 6px;border-radius:4px;font-size:0.8em}}
.good{{color:#4caf50}}.warn{{color:#ff9800}}
.footer{{text-align:center;color:#555;font-size:0.8em;margin-top:24px}}
</style>
</head>
<body>
<h1>🎬 长益剪辑Agent · 出片报告</h1>

<div class="card">
<h2>📊 概览</h2>
<div class="stats">
<div class="stat"><div class="value">{len(job.sentences)}</div><div class="label">段数</div></div>
<div class="stat"><div class="value">{sum(s.duration_sec for s in job.sentences):.0f}s</div><div class="label">总时长</div></div>
<div class="stat"><div class="value">{aes.get('score', '?')}</div><div class="label">美学分</div></div>
<div class="stat"><div class="value">{dc.get('editing_style','AI导演')}</div><div class="label">风格</div></div>
<div class="stat"><div class="value">{dc.get('color_grade','?')}</div><div class="label">调色</div></div>
<div class="stat"><div class="value">{dc.get('bgm','?')}</div><div class="label">BGM</div></div>
</div>
</div>

<div class="card">
<h2>🎭 AI分析</h2>
<p><b>语义引擎:</b> {sem.get('engine','?')}</p>
<p><b>情感弧线:</b> {sem.get('emotional_arc','?')}</p>
<p><b>视频引擎:</b> {vid.get('engine','?')}</p>
<p><b>数字人:</b> {'✅ 人脸检测' if dh.get('face_detected') else '⚠️ 无人脸'}</p>
</div>

<div class="card">
<h2>📋 剪辑决策</h2>
<table>
<tr><th></th><th>时间</th><th>时长</th><th>景别</th><th>内容</th><th>叠加文字</th></tr>
{segments_html}
</table>
</div>

<div class="card">
<h2>🛡️ 美学检查</h2>
<p>评分: <b class="{'good' if aes.get('score',0)>=80 else 'warn'}">{aes.get('score',0)}</b>分 ·
{aes.get('error_count',0)}错误 · {aes.get('warning_count',0)}警告 · {aes.get('info_count',0)}提示</p>
</div>

<div class="footer">
长益Agent · AI导演主导 · {len(job.sentences)}段·自动出片报告
</div>
</body>
</html>"""

    report_path = os.path.join(output_dir, "出片报告.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    return report_path
