"""导出模块 v2 · 引擎草稿优先 + Whisper SRT + MP4渲染"""
from __future__ import annotations
import json, logging, os, tempfile, zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
logger = logging.getLogger(__name__)

@dataclass
class ExportResult: success:bool; format:str; content:str; file_path:str=""; error:str=""

def export_to_jianying_draft(plan, material_paths, output_dir=""):
    if plan.draft_path and os.path.exists(plan.draft_path): return _pack_draft_dir(plan.draft_path, output_dir)
    if plan.exported_video and os.path.exists(plan.exported_video): return ExportResult(True,"mp4_video",plan.exported_video,plan.exported_video)
    try:
        from app.services.jianying_draft import create_jianying_draft
        mv=""
        for mp in material_paths:
            if mp.lower().endswith(('.mp4','.mov')) and os.path.exists(mp): mv=mp; break
        if mv:
            shots=[{"start_sec":s.start_sec,"duration_sec":s.duration_sec,"content_type":s.sub_type,"index":s.segment_id,"label":s.label,"covers_audio":s.covers_audio} for s in plan.segments]
            dp=create_jianying_draft(video_path=mv,shots=shots,srt_path=None,bgm_path=None,output_dir=output_dir or None,portrait=True,project_name=f"AI剪辑_{plan.plan_name}",style_data={"rhythm":"medium","music":{"has_bgm":False,"bgm_volume":plan.bgm_volume_ratio}})
            return ExportResult(True,"jianying_json",Path(dp).read_text(encoding="utf-8"),str(dp))
    except Exception as e: logger.debug("create_jianying_draft: %s",e)
    return _export_manual_json(plan, material_paths, output_dir)

def _pack_draft_dir(dp,od):
    df=Path(dp); root=df.parent.parent if (df.is_file() and df.parent.name=="draft") else (df.parent if df.is_file() else df)
    if not root.exists(): return ExportResult(False,"jianying_draft_dir","","","草稿目录不存在")
    zp=os.path.join(od or tempfile.gettempdir(),f"剪映草稿_{datetime.now().strftime('%m%d_%H%M')}.zip")
    os.makedirs(os.path.dirname(zp) or od or tempfile.gettempdir(),exist_ok=True)
    with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as zf:
        for r,_,fs in os.walk(str(root)):
            for fn in fs: fp=os.path.join(r,fn); zf.write(fp,os.path.relpath(fp,str(root)))
    return ExportResult(True,"jianying_draft_dir",zp,zp)

def _export_manual_json(plan, mps, od):
    from app.services.clip_agent.clip_templates import BGM_RULES
    vs,ims=[],[]
    for i,mp in enumerate(mps):
        if not os.path.exists(mp): continue
        ext=Path(mp).suffix.lower(); mid=f"mat_{i}_{Path(mp).stem}"
        if ext in (".mp4",".mov"): vs.append({"id":mid,"path":mp,"type":"video"})
        elif ext in (".jpg",".jpeg",".png"): ims.append({"id":mid,"path":mp,"type":"image"})
    am=vs+ims; vsegs,tsegs=[],[]; cur=0
    for seg in plan.segments:
        du=int(seg.duration_sec*1_000_000); mat=am[seg.material_index%len(am)] if am else {"id":"empty"}
        vsegs.append({"material_id":mat["id"],"target_timerange":{"start":0,"duration":du},"timerange":{"start":cur,"duration":du},"speed":1.0,"volume":0.0 if seg.covers_audio else 1.0})
        if seg.has_subtitle: tsegs.append({"content":seg.subtitle_text or seg.label,"timerange":{"start":cur,"duration":du},"style":{"font_size":48,"pos_y":0.5 if seg.subtitle_position=="center" else 0.88}})
        cur+=du
    draft={"platform":{"os":"windows","app":"jianying","version":"5.0.0"},"draft_name":f"AI剪辑_{plan.plan_name}","draft_info":{"total_duration_us":cur,"three_section":True},"materials":{"videos":vs,"images":ims},"tracks":[{"type":"video","name":"主画面轨","segments":vsegs},{"type":"audio","name":"BGM轨","segments":[{"material_id":"bgm","timerange":{"start":0,"duration":cur},"volume":BGM_RULES["volume_ratio"]}]},{"type":"text","name":"字幕轨","segments":tsegs}]}
    js=json.dumps(draft,ensure_ascii=False,indent=2); fp=""
    if od: os.makedirs(od,exist_ok=True); fp=os.path.join(od,"draft_content.json")
    return ExportResult(True,"jianying_json",js,fp)

def export_storyboard_text(plan):
    from app.services.shot_director import SHOT_TYPES,CAMERA_MOVEMENTS,COMPOSITIONS,EMOTIONAL_TONES
    from app.services.clip_agent.clip_templates import VISUAL_STRATEGIES
    s=VISUAL_STRATEGIES.get(plan.visual_strategy); sn=s.label if s else plan.visual_strategy
    lines=[f"══ {plan.plan_name} ══",f"策略: {sn}",f"开头{plan.opening_duration}s→介绍{plan.body_duration}s→结尾{plan.ending_duration}s",f"BGM: {plan.bgm_suggestion} | 音量1/3",""]
    if plan.review_score>0: lines.append(f"Kimi审片: {plan.review_score:.1f}/10")
    lines.extend(["",f"💡 {plan.summary}","","── 🎬 分镜头 ──",""])
    for seg in plan.segments:
        shot=SHOT_TYPES.get(seg.shot_type,{}).get("name",seg.shot_type); cam=CAMERA_MOVEMENTS.get(seg.camera_move,{}).get("name",seg.camera_move)
        comp=COMPOSITIONS.get(seg.composition,{}).get("name",seg.composition); tone=EMOTIONAL_TONES.get(seg.color_tone,{}).get("name",seg.color_tone)
        si={"opening":"📂开头","body":"📂介绍","ending":"📂结尾"}; cv=" ⚠️覆盖画面" if seg.covers_audio else ""
        lines.append(f"[{seg.segment_id}] {si.get(seg.section,'')} | {seg.label} ({seg.duration_sec}s){cv}")
        lines.append(f"  素材:{seg.material_filename} | {shot}|{cam}|{comp}|{tone}")
        if seg.description: lines.append(f"  {seg.description}"); lines.append("")
    return ExportResult(True,"storyboard_text","\n".join(lines))

def export_srt_subtitle(plan, video_path=""):
    if video_path and os.path.exists(video_path):
        r=_export_srt_whisper(video_path)
        if r.success: return r
    return _export_srt_segments(plan)

def _export_srt_whisper(vp):
    try:
        from app.services.subtitle_generator import SubtitleGenerator
        gen=SubtitleGenerator(model="tiny"); ap=gen.extract_audio(vp); segs=gen.transcribe(ap,language="zh")
        if not segs: return ExportResult(False,"srt_subtitle","","","未识别到语音")
        lines=[f"{i}\n{_fts(s['start'])} --> {_fts(s['end'])}\n{s['text']}\n" for i,s in enumerate(segs,1)]
        try: os.unlink(ap)
        except: pass
        return ExportResult(True,"srt_subtitle","\n".join(lines))
    except Exception as e: return ExportResult(False,"srt_subtitle","","",str(e)[:100])

def _export_srt_segments(plan):
    srt=[]; seq=0
    for s in plan.segments:
        if not s.has_subtitle: continue
        seq+=1; text=s.subtitle_text or s.label
        if s.covers_audio: text=f"[空镜] {text}"
        srt.append(f"{seq}\n{_fts(s.start_sec)} --> {_fts(s.start_sec+s.duration_sec)}\n{text}\n")
    return ExportResult(True,"srt_subtitle","\n".join(srt))

def export_srt_from_video(plan,vp): return _export_srt_whisper(vp)

def export_mp4_video(plan,mvp,srt="",bgm="",op=""):
    try:
        from app.services.video_editor import get_video_editor,EditOptions
        editor=get_video_editor()
        opts=EditOptions(output_size="1080x1920",remove_silence=False,subtitle_file=srt if srt and os.path.exists(srt) else None,bg_music=bgm if bgm and os.path.exists(bgm) else None,bg_music_volume=plan.bgm_volume_ratio)
        if not op: op=os.path.join(tempfile.gettempdir(),f"clip_agent_{plan.plan_name}_{datetime.now().strftime('%m%d_%H%M')}.mp4")
        rp=editor.edit(mvp,op,opts)
        return ExportResult(True,"mp4_video",str(rp),str(rp))
    except Exception as e: return ExportResult(False,"mp4_video","","",str(e)[:200])

def _fts(s): h,m=int(s//3600),int((s%3600)//60); sec,ms=int(s%60),int((s-int(s))*1000); return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
