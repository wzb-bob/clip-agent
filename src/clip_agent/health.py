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
    # Version
    try:
        vf = Path(__file__).parent.parent.parent / "VERSION"
        results["version"] = {"healthy": True, "detail": vf.read_text().strip() if vf.exists() else "unknown"}
    except Exception:
        results["version"] = {"healthy": True, "detail": "unknown"}
    # Modules
    results["modules"] = _check_modules()
    # AI Services
    results["ai_services"] = _check_ai_services()

    # Flatten AI services for overall health
    all_checks = dict(results)
    ai = all_checks.pop("ai_services", {})
    healthy = all(
        (v["healthy"] if isinstance(v, dict) else v)
        for v in list(all_checks.values()) + list(ai.values())
    )
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
        from . import clip_this, quick_execute, quick_direct
        return {"healthy": True, "detail": "核心模块导入成功(quick_execute+quick_direct)", "latency_ms": round((time.time()-t0)*1000)}
    except Exception as e:
        return {"healthy": False, "detail": str(e)[:100]}


def _check_ai_services() -> dict:
    """检查AI服务可用性(DeepSeek/Kimi/GLM/Whisper)"""
    results = {}

    # DeepSeek
    try:
        from ._imports import chat_via_gateway, get_model_name
        if chat_via_gateway and get_model_name:
            results["deepseek"] = {"healthy": True, "detail": "语义分析+音频理解+导演AI可用"}
        else:
            results["deepseek"] = {"healthy": False, "detail": "gateway_client不可用·AI功能降级为规则"}
    except Exception as e:
        results["deepseek"] = {"healthy": False, "detail": str(e)[:80]}

    # Kimi Vision
    try:
        from ._imports import chat_vision
        if chat_vision:
            results["kimi_vision"] = {"healthy": True, "detail": "视觉场景分析可用"}
        else:
            results["kimi_vision"] = {"healthy": False, "detail": "API Key未配置·视觉分析不可用"}
    except Exception:
        results["kimi_vision"] = {"healthy": False, "detail": "不可用"}

    # GLM-4V
    key = os.getenv("GLM_API_KEY")
    results["glm4v"] = {"healthy": bool(key), "detail": "帧级深标注可用" if key else "API Key未配置"}

    # Whisper
    try:
        import whisper
        results["whisper"] = {"healthy": True, "detail": "本地Whisper转录可用"}
    except ImportError:
        results["whisper"] = {"healthy": False, "detail": "未安装"}
    except Exception:
        results["whisper"] = {"healthy": True, "detail": "可用(需下载模型)"}

    # OpenCV
    try:
        import cv2
        results["opencv"] = {"healthy": True, "detail": f"本地视频分析可用 v{cv2.__version__}"}
    except ImportError:
        results["opencv"] = {"healthy": False, "detail": "未安装"}

    # librosa
    try:
        import librosa
        results["librosa"] = {"healthy": True, "detail": "音频能量分析可用"}
    except ImportError:
        results["librosa"] = {"healthy": False, "detail": "未安装"}

    return results


def print_health_report():
    """打印健康报告"""
    result = check_all()
    print("=" * 60)
    print("🩺 长益剪辑Agent 系统诊断")
    print("=" * 60)
    print("  【基础设施】")
    for name in ["ffmpeg", "python_deps", "disk", "modules"]:
        check = result["checks"].get(name)
        if check:
            icon = "✅" if check["healthy"] else "❌"
            print(f"  {icon} {name}: {check['detail']}")
    print("  【AI服务】")
    ai = result["checks"].get("ai_services", {})
    for name in ["deepseek", "kimi_vision", "glm4v", "whisper", "opencv", "librosa"]:
        check = ai.get(name)
        if check:
            icon = "✅" if check["healthy"] else "⚠️"
            print(f"  {icon} {name}: {check['detail']}")
    print("  【API密钥】")
    print(f"  {result['checks']['api_keys']['detail']}")
    print("=" * 60)
    overall = "✅ 系统就绪" if result["healthy"] else "⚠️ 部分功能受限(见上方⚠️项)"
    print(f"  {overall}")
    print("=" * 60)


if __name__ == "__main__":
    print_health_report()
