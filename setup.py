#!/usr/bin/env python3
"""
长益剪辑Agent · 环境检测+安装脚本

运行: python setup.py
检查: FFmpeg·Python版本·依赖包·API Key·Whisper模型
"""
import sys, os, subprocess, shutil
from pathlib import Path

def check(title, ok, detail=""):
    icon = "✅" if ok else "❌"
    print(f"  {icon} {title:30s} {detail}")
    return ok

print("=" * 60)
print("🩺 长益剪辑Agent · 环境检测")
print("=" * 60)

all_ok = True

# 1. Python
ver = sys.version_info
all_ok &= check("Python 3.10+", ver >= (3, 10), f"v{ver.major}.{ver.minor}.{ver.micro}")

# 2. FFmpeg
ffmpeg = shutil.which("ffmpeg")
all_ok &= check("FFmpeg", ffmpeg is not None, ffmpeg or "未安装")

# 3. Python依赖
deps = {"opencv-python":"cv2","numpy":"numpy","librosa":"librosa",
        "whisper":"whisper","edge-tts":"edge_tts","Pillow":"PIL",
        "pydub":"pydub","python-dotenv":"dotenv"}
for pip_name, import_name in deps.items():
    try:
        __import__(import_name)
        all_ok &= check(pip_name, True)
    except ImportError:
        all_ok &= check(pip_name, False, f"pip install {pip_name}")

# 4. API Key
env_paths = [
    Path(r"c:\Users\wangzibo\enterprise-agent-content\.env"),
    Path(".env"),
]
env_loaded = False
for ep in env_paths:
    if ep.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(ep)
            env_loaded = True
            break
        except ImportError:
            pass
all_ok &= check(".env 配置", env_loaded, str(ep) if env_loaded else "未找到")

# 5. API Key 检查
for key, name in [("DEEPSEEK_API_KEY","DeepSeek"),("KIMI_API_KEY","Kimi"),
                   ("GLM_API_KEY","GLM-4V"),("DOUBAO_API_KEY","Doubao")]:
    ok = bool(os.getenv(key))
    all_ok &= check(f"  {name} Key", ok, "已配置" if ok else "未配置·部分功能降级")

# 6. Whisper模型
whisper_cache = Path.home() / ".cache" / "whisper"
has_model = any(whisper_cache.glob("*.pt")) if whisper_cache.exists() else False
all_ok &= check("Whisper模型", has_model, "已下载" if has_model else "首次运行自动下载(~500MB)")

# 7. 目录结构
script_dir = Path(__file__).parent
for d in ["src/clip_agent","tests",".agents/skills","data"]:
    exists = (script_dir / d).exists()
    all_ok &= check(f"目录 {d}", exists)

print("=" * 60)
if all_ok:
    print("✅ 环境就绪·可以开始使用")
    print()
    print("快速开始:")
    print("  python demo.py \"68块！十只活虾！\" --video 素材.mp4")
    print("  python demo.py --jianying --script \"脚本\" --talking 口播.mp4")
else:
    print("⚠️ 以上❌项需要先修复")
    print()
    print("缺少依赖: pip install opencv-python numpy librosa whisper edge-tts Pillow pydub python-dotenv")
print("=" * 60)
