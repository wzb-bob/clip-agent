"""
智能切点检测 · 带BGM视频专用 · 多种检测策略

DJI/云台视频通常有BGM——不能用纯静音检测。
改用: 轻声段检测·词边界·节奏峰值·场景变化
"""
from __future__ import annotations
import logging, os, subprocess, tempfile, time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CutPoint:
    """一个编辑切点"""
    at_sec: float
    type: str              # "hard_cut"/"broll_insert"/"j_cut"/"l_cut"/"emphasis"
    confidence: float      # 0-1
    source: str            # "quiet"/"word_boundary"/"scene_change"/"rhythm"
    detail: str


class SmartCutter:
    """智能切点检测器——适配带BGM/音乐的视频"""

    def __init__(self, quiet_threshold_db: int = -25, min_quiet_ms: int = 200):
        self.quiet_threshold = quiet_threshold_db
        self.min_quiet_ms = min_quiet_ms

    def find_quiet_points(self, video_path: str) -> list[CutPoint]:
        """
        找'轻声段'——不是纯静音,而是音量降低到阈值以下
        适用于有BGM/背景音乐的视频
        """
        points = []
        try:
            from pydub import AudioSegment
            from pydub.silence import detect_silence

            wav = tempfile.mktemp(suffix=".wav")
            subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                "-i",video_path,"-vn","-acodec","pcm_s16le","-ar","16000","-ac","1",wav],
                timeout=30, check=True)

            audio = AudioSegment.from_wav(wav)
            quiet_ranges = detect_silence(audio, min_silence_len=self.min_quiet_ms,
                                          silence_thresh=self.quiet_threshold)

            for start_ms, end_ms in quiet_ranges:
                dur_sec = (end_ms - start_ms) / 1000
                at_sec = (start_ms + end_ms) / 2000

                if dur_sec >= 0.5:
                    points.append(CutPoint(at_sec=round(at_sec,1), type="broll_insert",
                        confidence=0.8, source="quiet",
                        detail=f"轻声段{dur_sec:.1f}s——适合B-roll插入"))
                elif dur_sec >= 0.2:
                    points.append(CutPoint(at_sec=round(at_sec,1), type="hard_cut",
                        confidence=0.6, source="quiet",
                        detail=f"轻声段{dur_sec:.1f}s——硬切"))

            os.remove(wav)
        except Exception as e:
            logger.warning("轻声检测失败: %s", e)

        return points

    def find_scene_changes(self, video_path: str) -> list[CutPoint]:
        """
        场景变化检测——画面内容突变处=自然切点
        """
        points = []
        try:
            r = subprocess.run(["ffmpeg","-hide_banner","-i",video_path,
                "-vf","select='gt(scene,0.3)',showinfo","-f","null","-"],
                capture_output=True, text=True, timeout=60)
            import re
            times = re.findall(r"pts_time:([\d.]+)", r.stderr)
            for t in times[:20]:  # 最多20个
                at = float(t)
                points.append(CutPoint(at_sec=round(at,1), type="hard_cut",
                    confidence=0.7, source="scene_change",
                    detail=f"画面变化@{at:.1f}s"))

            # 过滤: 相邻<1s的合并
            filtered = []
            for i, p in enumerate(points):
                if i == 0 or p.at_sec - points[i-1].at_sec >= 1.0:
                    filtered.append(p)
            points = filtered

        except Exception as e:
            logger.debug("场景检测跳过: %s", e)

        return points

    def find_word_boundaries(self, video_path: str) -> list[CutPoint]:
        """
        Whisper词级时间戳→找句子边界
        词间gap>300ms=句末→自然切点
        """
        points = []
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(video_path, word_timestamps=True)
            words = []
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        words.append({"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)})

            for i in range(1, len(words)):
                gap = words[i]["start"] - words[i-1]["end"]
                if gap >= 0.5:  # >500ms=句子结束
                    at = round(words[i-1]["end"] + gap/2, 1)
                    points.append(CutPoint(at_sec=at, type="broll_insert",
                        confidence=0.85, source="word_boundary",
                        detail=f"句末 {words[i-1]['word']}→{words[i]['word']} gap={gap:.1f}s"))
                elif gap >= 0.3:  # >300ms=词间停顿
                    at = round(words[i-1]["end"] + gap/2, 1)
                    points.append(CutPoint(at_sec=at, type="hard_cut",
                        confidence=0.7, source="word_boundary",
                        detail=f"词间 {words[i-1]['word']}→{words[i]['word']}"))

            logger.info("Whisper: %d词→%d切点", len(words), len(points))
        except Exception as e:
            logger.warning("Whisper词边界失败: %s", e)

        return points

    def analyze_for_editing(self, video_path: str) -> list[CutPoint]:
        """
        综合分析→输出编辑切点列表
        优先级: 词边界(Whisper) > 场景变化 > 轻声段 > 均匀分布
        """
        words = self.find_word_boundaries(video_path)
        scenes = self.find_scene_changes(video_path)
        quiets = self.find_quiet_points(video_path)

        # 合并去重(词边界优先级最高)
        all_points = words.copy()
        existing_times = {p.at_sec for p in words}
        for p in scenes + quiets:
            if not any(abs(p.at_sec - t) < 0.5 for t in existing_times):
                all_points.append(p)
                existing_times.add(p.at_sec)
        for q in quiets:
            if not any(abs(q.at_sec - t) < 0.5 for t in existing_times):
                all_points.append(q)
                existing_times.add(q.at_sec)

        all_points.sort(key=lambda p: p.at_sec)

        # 确保至少3个切点(3段结构)
        if len(all_points) < 2:
            # 获取时长
            dur = 0
            try:
                import json
                r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",video_path],
                    capture_output=True, text=True, timeout=5)
                dur = float(json.loads(r.stdout).get("format",{}).get("duration",0))
            except: pass
            if dur > 0:
                all_points.append(CutPoint(at_sec=round(dur*0.33,1), type="hard_cut",
                    confidence=0.4, source="fallback", detail="均匀分布1/3"))
                all_points.append(CutPoint(at_sec=round(dur*0.67,1), type="broll_insert",
                    confidence=0.4, source="fallback", detail="均匀分布2/3"))
                all_points.sort(key=lambda p: p.at_sec)

        return all_points


def quick_cut_analysis(video_path: str) -> list[CutPoint]:
    """快速切点分析"""
    return SmartCutter().analyze_for_editing(video_path)
