"""气口检测器 · 5路信号融合：Whisper词间(35%)+FFmpeg静音(30%)+转场(15%)+运动(10%)+呼吸(10%)"""
from __future__ import annotations
import json, logging, os, re, subprocess
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
logger = logging.getLogger(__name__)

@dataclass
class BreathPoint:
    at_sec: float; score: float; sources: list[str]=field(default_factory=list)
    confidence: float=0.5; duration_ms: int=0; label: str=""
    gap_ms: int=0; word_before: str=""; word_after: str=""

@dataclass
class BreathReport:
    video_path: str=""; duration_sec: float=0.0; total_points: int=0
    points: list[BreathPoint]=field(default_factory=list)
    best_cuts: list[BreathPoint]=field(default_factory=list); good_cuts: list[BreathPoint]=field(default_factory=list)
    sentence_breaks: list[BreathPoint]=field(default_factory=list); breath_points: list[BreathPoint]=field(default_factory=list)
    visual_cuts: list[BreathPoint]=field(default_factory=list)
    avg_gap_between_words_ms: int=0; avg_gap_between_sentences_ms: int=0
    speech_rate_cps: float=0.0; breath_count: int=0

class BreathDetector:
    SILENCE_THRESH_DB=-30; MIN_SILENCE_MS=200; MIN_SENTENCE_GAP_MS=400; MIN_WORD_GAP_MS=100
    WEIGHT_SILENCE=0.30; WEIGHT_WORD_GAP=0.35; WEIGHT_SHOT_BOUNDARY=0.15; WEIGHT_MOTION_LOW=0.10; WEIGHT_BREATH=0.10

    def detect_silence_ffmpeg(self, video_path):
        v=Path(video_path)
        if not v.exists(): return []
        try:
            r=subprocess.run(["ffmpeg","-hide_banner","-i",str(v),"-af",f"silencedetect=n={self.SILENCE_THRESH_DB}dB:d={self.MIN_SILENCE_MS/1000:.1f}","-f","null","-"],capture_output=True,text=True,timeout=120)
            s=r.stderr if isinstance(r.stderr,str) else ""
            st=re.findall(r"silence_start:\s*([\d.]+)",s); en=re.findall(r"silence_end:\s*([\d.]+)",s); du=re.findall(r"silence_duration:\s*([\d.]+)",s)
            return [{"start":float(st[i]),"end":float(en[i]) if i<len(en) else float(st[i])+0.5,"duration_ms":int(float(du[i])*1000) if i<len(du) else 500} for i in range(len(st))]
        except Exception as e: logger.warning("静音检测失败: %s",e); return []

    def detect_word_gaps(self, video_path):
        v=Path(video_path); words,gaps=[],[]
        try:
            from faster_whisper import WhisperModel
            m=WhisperModel('tiny',device='cpu',compute_type='int8')
            segs,_=m.transcribe(str(v),word_timestamps=True)
            for seg in segs:
                if seg.words:
                    for w in seg.words: words.append({"word":w.word.strip(),"start":round(w.start,2),"end":round(w.end,2)})
            for i in range(1,len(words)):
                gs=words[i]["start"]-words[i-1]["end"]; gm=int(gs*1000)
                if gm>=self.MIN_WORD_GAP_MS:
                    gaps.append({"between":f"{words[i-1]['word']}->{words[i]['word']}","gap_ms":gm,"at_sec":round(words[i-1]["end"]+gs/2,2),"is_sentence_break":gm>=self.MIN_SENTENCE_GAP_MS,"word_before":words[i-1]["word"],"word_after":words[i]["word"]})
        except Exception as e: logger.warning("Whisper失败: %s",e)
        return words,gaps

    def detect_shot_boundaries(self, video_path):
        try:
            from app.services.shot_splitter import ShotSplitter
            raw=ShotSplitter().split(Path(video_path))
            return [round(s.end_sec,2) for s in raw.shots[:-1]] if raw.shots else []
        except Exception: return []

    def detect_motion_lows(self, video_path):
        v=Path(video_path)
        if not v.exists(): return []
        try:
            r=subprocess.run(["ffmpeg","-hide_banner","-i",str(v),"-vf","mestimate=epzs=16:mb_size=32,metadata=print","-vframes","100","-f","null","-"],capture_output=True,text=True,timeout=60)
            stderr=r.stderr if isinstance(r.stderr,str) else ""
            vals=[abs(float(m.group(1))) for line in stderr.splitlines() for pat in [r"motion_x[:=]\s*([-\d.]+)",r"dx[:=]\s*([-\d.]+)"] if (m:=re.search(pat,line,re.IGNORECASE))]
            if not vals: return []
            th=np.mean(vals)*0.3
            return [{"at_sec":round(i*0.5,2),"motion_intensity":round(float(v),4)} for i,v in enumerate(vals) if v<th]
        except Exception as e: logger.warning("运动分析失败: %s",e); return []

    def analyze(self, video_path):
        v=Path(video_path); report=BreathReport(video_path=str(v))
        try:
            from app.services.video_editor import get_video_editor
            report.duration_sec=get_video_editor().probe(v).duration
        except Exception: pass
        from concurrent.futures import ThreadPoolExecutor,as_completed
        signals={}
        def _c(name,fn,*a):
            try: return name,fn(*a)
            except Exception as e: logger.debug("信号%s失败: %s",name,e); return name,([],[]) if name=="word_gaps" else []
        with ThreadPoolExecutor(max_workers=4) as ex:
            for f in as_completed([ex.submit(_c,n,fn,v) for n,fn in [("silence",self.detect_silence_ffmpeg),("word_gaps",self.detect_word_gaps),("shot",self.detect_shot_boundaries),("motion",self.detect_motion_lows)]]):
                name,data=f.result(); signals[name]=data
        silences=signals.get("silence",[]); words,gaps=signals.get("word_gaps",([],[]))
        shot_b=signals.get("shot",[]); motion_l=signals.get("motion",[])
        all_mids={round((s["start"]+s["end"])/2,2) for s in silences}
        for gap in gaps:
            at=gap["at_sec"]; score=0.0; sources=[]
            if gap["is_sentence_break"]: score+=min(gap["gap_ms"]/1000,1.0)*self.WEIGHT_WORD_GAP; sources.append("word_gap_sentence")
            else: score+=min(gap["gap_ms"]/500,0.6)*self.WEIGHT_WORD_GAP; sources.append("word_gap")
            if any(abs(sm-at)<0.3 for sm in all_mids): score+=self.WEIGHT_SILENCE; sources.append("silence")
            if any(abs(sb-at)<0.5 for sb in shot_b): score+=self.WEIGHT_SHOT_BOUNDARY; sources.append("shot_boundary")
            if any(abs(ml["at_sec"]-at)<0.3 for ml in motion_l): score+=self.WEIGHT_MOTION_LOW; sources.append("motion_low")
            bp=BreathPoint(at_sec=at,score=round(min(score,1.0),2),sources=sources,confidence=round(len(sources)/5.0,2),duration_ms=gap["gap_ms"],gap_ms=gap["gap_ms"],word_before=gap.get("word_before",""),word_after=gap.get("word_after",""))
            bp.label="句间停顿" if (gap["is_sentence_break"] and "silence" in sources) else ("句边界" if gap["is_sentence_break"] else ("转场切点" if "shot_boundary" in sources else ("静音点" if "silence" in sources else "词间")))
            report.points.append(bp)
        wt={p.at_sec for p in report.points}
        for sm in all_mids:
            if not any(abs(sm-w)<0.3 for w in wt): report.points.append(BreathPoint(at_sec=sm,score=0.35,sources=["silence_only"],confidence=0.2,duration_ms=300,label="纯静音点"))
        report.points.sort(key=lambda p:p.at_sec); report.total_points=len(report.points)
        for bp in report.points:
            if bp.score>=0.8: report.best_cuts.append(bp)
            if bp.score>=0.6: report.good_cuts.append(bp)
            if "word_gap_sentence" in bp.sources: report.sentence_breaks.append(bp)
            if "shot_boundary" in bp.sources: report.visual_cuts.append(bp)
        if gaps:
            ag=[g["gap_ms"] for g in gaps]; sg=[g["gap_ms"] for g in gaps if g["is_sentence_break"]]
            report.avg_gap_between_words_ms=int(np.mean(ag)); report.avg_gap_between_sentences_ms=int(np.mean(sg)) if sg else 0
        if words and report.duration_sec>0: report.speech_rate_cps=round(len(words)/report.duration_sec,1)
        return report

    def get_optimal_broll_points(self, report, count=5, min_gap_sec=3.0, prefer_sentence_breaks=True):
        candidates=report.sentence_breaks if prefer_sentence_breaks else report.good_cuts
        if not candidates: candidates=report.points
        selected=[]
        for pt in sorted(candidates,key=lambda p:p.score,reverse=True):
            if len(selected)>=count: break
            if any(abs(pt.at_sec-s.at_sec)<min_gap_sec for s in selected): continue
            selected.append(pt)
        selected.sort(key=lambda p:p.at_sec)
        return selected

def detect_breath_points(video_path): return BreathDetector().analyze(Path(video_path))
def get_broll_insert_points(video_path, count=5, prefer_sentence=True): return BreathDetector().get_optimal_broll_points(BreathDetector().analyze(Path(video_path)),count=count,prefer_sentence_breaks=prefer_sentence)
