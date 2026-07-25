"""
系统健康检查 · 依赖检测·API连通性·磁盘空间·模块完整性
"""
from __future__ import annotations
import importlib, logging, os, shutil, socket, subprocess, sys, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    component: str
    healthy: bool
    detail: str
    latency_ms: float = 0.0
    version: str = ""


def check_all() -> dict:
    """全系统健康检查"""
    results = {}

    # FFmpeg
    results["ffmpeg"] = _check_ffmpeg()
    # Python deps
    results["python_deps"] = _check_deps()
    # API keys
    results["api_keys"] = _check_api_keys()
    # Disk space
    results["disk"] = _check_disk()
    # OpenMontage
    results["openmontage"] = _check_openmontage()
    # Modules
    results["modules"] = _check_modules()

    healthy = all(v["healthy"] if isinstance(v, dict) else v for v in results.values())
    return {"healthy": healthy, "checks": results, "timestamp": time.time()}


def _check_ffmpeg() -> dict:
    t0 = time.time()
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        try:
            r = subprocess.run(["ffmpeg","-version"], capture_output=True, text=True, timeout=5)
            version = r.stdout.split("\n")[0][:50] if r.stdout else "unknown"
            return {"healthy": True, "detail": f"ffmpeg {version}", "latency_ms": round((time.time()-t0)*1000)}
        except: pass
    return {"healthy": False, "detail": "FFmpeg/FFprobe未安装或不在PATH中"}


def _check_deps() -> dict:
    t0 = time.time()
    missing = []
    deps = ["cv2","numpy","librosa","whisper","mediapipe","pydub","edge_tts"]
    for dep in deps:
        try:
            importlib.import_module(dep)
        except ImportError:
            missing.append(dep)
    if missing:
        return {"healthy": False, "detail": f"缺少: {', '.join(missing)}"}
    return {"healthy": True, "detail": f"全部{len(deps)}个依赖就绪", "latency_ms": round((time.time()-t0)*1000)}


def _check_api_keys() -> dict:
    keys = {"KIMI_API_KEY":"Kimi K2.6","DEEPSEEK_API_KEY":"DeepSeek","GLM_API_KEY":"GLM-4V","DOUBAO_API_KEY":"豆包"}
    configured = [name for env, name in keys.items() if os.getenv(env)]
    if not configured:
        return {"healthy": False, "detail": "无API Key配置——视觉分析不可用"}
    return {"healthy": True, "detail": f"{len(configured)}/{len(keys)}可用: {', '.join(configured)}"}


def _check_disk() -> dict:
    usage = shutil.disk_usage(os.getcwd())
    free_gb = usage.free / (1024**3)
    if free_gb < 1:
        return {"healthy": False, "detail": f"磁盘空间不足: {free_gb:.1f}GB"}
    return {"healthy": True, "detail": f"可用{free_gb:.1f}GB"}


def _check_openmontage() -> dict:
    path = Path(__file__).parent / "openmontage_full"
    if path.exists():
        schemas = len(list(path.glob("schemas/**/*.json")))
        return {"healthy": True, "detail": f"桥接就绪·{schemas}Schema"}
    return {"healthy": False, "detail": "OpenMontage桥接未安装"}


def _check_modules() -> dict:
    t0 = time.time()
    try:
        from . import clip_this, quick_execute
        return {"healthy": True, "detail": "核心模块导入成功", "latency_ms": round((time.time()-t0)*1000)}
    except Exception as e:
        return {"healthy": False, "detail": str(e)[:100]}


def print_health_report():
    """打印健康报告"""
    result = check_all()
    print("=" * 50)
    print("🩺 长益剪辑Agent 健康检查")
    print("=" * 50)
    for name, check in result["checks"].items():
        icon = "✅" if check["healthy"] else "❌"
        latency = f" ({check.get('latency_ms',0)}ms)" if check.get('latency_ms') else ""
        print(f"  {icon} {name}: {check['detail']}{latency}")
    print("=" * 50)
    print(f"  {'✅ 系统健康' if result['healthy'] else '❌ 有问题需要修复'}")


if __name__ == "__main__":
    print_health_report()
