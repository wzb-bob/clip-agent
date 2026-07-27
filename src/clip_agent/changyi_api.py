"""
长益剪辑Agent · 统一API

完整集成入口 — 一个类暴露全部能力:
  clip(): 素材出片
  digital_human(): 照片出片
  batch(): 批量处理
  voice(): 声音克隆
  diagnose(): 系统诊断
  plugins(): 查看可用插件
"""
from __future__ import annotations
import json, logging, os, time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class APIResult:
    success: bool
    mode: str              # clip/digital_human/batch/diagnose
    data: dict = field(default_factory=dict)
    error: str = ""
    elapsed: float = 0.0


class ChangyiAPI:
    """长益剪辑Agent 统一API"""

    def __init__(self):
        self._load_env()

    def _load_env(self):
        for ep in [
            Path(r"c:\Users\wangzibo\enterprise-agent-content\.env"),
            Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend\.env"),
        ]:
            if ep.exists():
                try:
                    from dotenv import load_dotenv
                    load_dotenv(ep)
                    break
                except ImportError:
                    pass

    # ── 素材出片 ──
    def clip(self, script: str, script_type: str = "auto",
             videos: list[str] = None, output: str = "") -> APIResult:
        """视频素材 → AI导演出片"""
        # 输入校验
        if not script or len(script.strip()) < 3:
            return APIResult(False, "clip", error="脚本太短(需≥3字)")
        if len(script) > 5000:
            return APIResult(False, "clip", error="脚本过长(限5000字)")

        t0 = time.time()
        try:
            if script_type == "auto":
                script_type = self._detect_type(script)
            from .execution_engine import quick_direct
            vs = {}
            for i, vf in enumerate(videos or []):
                if os.path.exists(vf):
                    vs[i + 1] = vf
            outdir = output or f"./output_{int(time.time())}"
            job = quick_direct(script, script_type, video_slots=vs, output_dir=outdir)
            return APIResult(
                success=job.status == "done", mode="clip",
                data={"segments": len(job.sentences), "duration": sum(s.duration_sec for s in job.sentences),
                      "style": job.enhancement_report.get("director_plan", {}).get("editing_style", ""),
                      "output": outdir},
                elapsed=round(time.time() - t0, 1),
            )
        except Exception as e:
            return APIResult(False, "clip", error=str(e)[:200])

    # ── 数字人出片 ──
    def digital_human(self, photo: str, script: str, script_type: str = "老板IP",
                      output: str = "") -> APIResult:
        """照片+脚本 → 数字人口播视频"""
        if not photo or not os.path.exists(photo):
            return APIResult(False, "digital_human", error="照片文件不存在")
        if not script or len(script.strip()) < 3:
            return APIResult(False, "digital_human", error="脚本太短(需≥3字)")

        t0 = time.time()
        try:
            from .digital_human import create_and_clip
            result = create_and_clip(photo, script, script_type, output_dir=output or f"./dh_{int(time.time())}")
            return APIResult(
                success=result["success"], mode="digital_human",
                data={"face_detected": result.get("face_detected", False),
                      "duration": result.get("duration", 0),
                      "clip_success": result.get("clip_success", False),
                      "output": result.get("edited_video", "")},
                elapsed=round(time.time() - t0, 1),
            )
        except Exception as e:
            return APIResult(False, "digital_human", error=str(e)[:200])

    # ── 批量处理 ──
    def batch(self, scripts: list[dict], output: str = "./batch_output/") -> APIResult:
        """批量处理多条脚本"""
        t0 = time.time()
        results = []
        for i, item in enumerate(scripts):
            r = self.clip(
                item.get("script", ""),
                item.get("type", "auto"),
                item.get("videos", []),
                os.path.join(output, f"job_{i:03d}"),
            )
            results.append({"index": i+1, "success": r.success, "error": r.error})
        return APIResult(
            success=all(r["success"] for r in results), mode="batch",
            data={"total": len(scripts), "results": results},
            elapsed=round(time.time() - t0, 1),
        )

    # ── 系统诊断 ──
    def diagnose(self) -> APIResult:
        t0 = time.time()
        try:
            from .health import check_all
            h = check_all()
            from .plugin_registry import PLUGINS
            return APIResult(
                success=h["healthy"], mode="diagnose",
                data={"health": h["healthy"], "checks": h["checks"],
                      "plugins": {cat: [p.name for p in plgs] for cat, plgs in PLUGINS.items()}},
                elapsed=round(time.time() - t0, 1),
            )
        except Exception as e:
            return APIResult(False, "diagnose", error=str(e)[:200])

    # ── 工具方法 ──
    def plugins(self) -> dict:
        from .plugin_registry import PLUGINS
        return PLUGINS

    def voices(self) -> list:
        from .voice_cloner import list_voices
        return list_voices()

    def _detect_type(self, script: str) -> str:
        if any(kw in script for kw in ["块","元","价","团购","优惠"]):
            return "团购售卖"
        if any(kw in script for kw in ["故事","创业","老板","年","坚持","凌晨"]):
            return "老板IP"
        if any(kw in script for kw in ["地址","导航","排队","门头","只此"]):
            return "引流进店"
        return "团购售卖"


# 全局实例
api = ChangyiAPI()
