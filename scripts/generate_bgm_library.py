"""FFmpeg合成零版权BGM曲库——每类脚本3首·共12首·持续60-120秒
生成到 bgm/ 目录，bgm_selector 自动识别"""
import subprocess, os, sys
from pathlib import Path

BGM_DIR = Path(__file__).parent.parent / "bgm"
BGM_DIR.mkdir(exist_ok=True)

# 曲目定义: (文件名, 时长s, FFmpeg音频合成滤镜)
TRACKS = [
    # ── 团购售卖(高能量·快节奏) ──
    ("sell_hype_1", 90,
     "aevalsrc=0.5:d=90,"
     "equalizer=f=110:width=50:g=8,"
     "equalizer=f=220:width=100:g=4,"
     "equalizer=f=440:width=200:g=2,"
     "volume=0.3"),
    ("sell_hype_2", 90,
     "aevalsrc=0.4:d=90,"
     "equalizer=f=220:width=100:g=7,"
     "equalizer=f=330:width=80:g=5,"
     "equalizer=f=440:width=60:g=3,"
     "tremolo=f=5:d=0.6,"
     "volume=0.25"),
    ("sell_hype_3", 120,
     "aevalsrc=0.3:d=120,"
     "equalizer=f=150:width=60:g=6,"
     "equalizer=f=300:width=120:g=3,"
     "tremolo=f=4:d=0.7,"
     "volume=0.28"),

    # ── 老板IP(低能量·温暖) ──
    ("boss_calm_1", 90,
     "aevalsrc=0.35:d=90,"
     "equalizer=f=220:width=80:g=6,"
     "equalizer=f=277:width=60:g=4,"
     "equalizer=f=330:width=40:g=2,"
     "lowpass=f=600,"
     "volume=0.15"),
    ("boss_calm_2", 90,
     "aevalsrc=0.4:d=90,"
     "equalizer=f=200:width=80:g=5,"
     "equalizer=f=400:width=150:g=2,"
     "lowpass=f=800,"
     "volume=0.2"),
    ("boss_calm_3", 120,
     "aevalsrc=0.3:d=120,"
     "equalizer=f=165:width=70:g=5,"
     "equalizer=f=220:width=50:g=3,"
     "equalizer=f=277:width=30:g=1.5,"
     "lowpass=f=500,"
     "volume=0.15"),

    # ── 引流进店(中能量·明快) ──
    ("flow_upbeat_1", 90,
     "aevalsrc=0.4:d=90,"
     "equalizer=f=180:width=70:g=6,"
     "equalizer=f=360:width=140:g=3,"
     "tremolo=f=3:d=0.5,"
     "volume=0.25"),
    ("flow_upbeat_2", 90,
     "aevalsrc=0.35:d=90,"
     "equalizer=f=262:width=80:g=6,"
     "equalizer=f=330:width=60:g=4,"
     "equalizer=f=392:width=40:g=2,"
     "tremolo=f=4:d=0.5,"
     "volume=0.2"),
    ("flow_upbeat_3", 120,
     "aevalsrc=0.35:d=120,"
     "equalizer=f=250:width=80:g=5,"
     "highpass=f=100,"
     "volume=0.22"),

    # ── 趣味长剧情(低能量·叙事) ──
    ("story_ambient_1", 90,
     "aevalsrc=0.3:d=90,"
     "equalizer=f=150:width=60:g=4,"
     "lowpass=f=500,"
     "volume=0.18"),
    ("story_ambient_2", 90,
     "aevalsrc=0.25:d=90,"
     "equalizer=f=196:width=70:g=4,"
     "equalizer=f=247:width=50:g=2.5,"
     "equalizer=f=294:width=30:g=1.5,"
     "lowpass=f=450,"
     "volume=0.12"),
    ("story_ambient_3", 120,
     "aevalsrc=0.25:d=120,"
     "equalizer=f=130:width=50:g=3,"
     "equalizer=f=260:width=100:g=1.5,"
     "lowpass=f=400,"
     "volume=0.15"),
]

FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")
generated = 0
for name, duration, vf in TRACKS:
    out = BGM_DIR / f"{name}.mp3"
    if out.exists():
        print(f"  SKIP {name}.mp3 (exists)")
        continue
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", vf,
        "-codec:a", "libmp3lame", "-b:a", "192k",
        "-t", str(duration),
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode == 0 and out.exists():
        kb = out.stat().st_size // 1024
        print(f"  OK  {name}.mp3  ({duration}s, {kb}KB)")
        generated += 1
    else:
        print(f"  FAIL {name}: {r.stderr[:100]}")

print(f"\n生成 {generated}/12 首 → {BGM_DIR}")
print(f"总大小: {sum(f.stat().st_size for f in BGM_DIR.glob('*.mp3')) // 1024}KB")
