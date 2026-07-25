"""
长益剪辑Agent v4 · 统一入口 · OpenMontage适配 · 42模块
定价: ¥19.9/次(200积分)·月¥99(1000积分)·首次免费
"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

# ── 核心引擎(5) ──
from .media_analyzer import MediaFile, MaterialAnalysis, BatchAnalysisResult, analyze_materials
from .clip_planner import ClipPlan, VideoSegment, generate_clip_plans, quality_review_and_optimize
from .clip_templates import (CLIP_TEMPLATES, PRESET_TEMPLATES, VISUAL_STRATEGIES, BGM_RULES,
    list_templates, list_preset_templates, get_template, get_preset_template, auto_select_template)
from .jianying_export import (ExportResult, export_to_jianying_draft, export_storyboard_text,
    export_srt_subtitle, export_srt_from_video, export_mp4_video)

# ── 抖音能力(5) ──
from .douyin_effects import (detect_beats, get_text_style_for_segment, apply_color_filter_cmd,
    ken_burns_keyframes, apply_douyin_style_to_plan, TEXT_ANIMATIONS, TEXT_STYLES, COLOR_FILTERS)
from .douyin_missing import (generate_voiceover, TRANSITIONS_FFMPEG, render_transition,
    apply_fade_in_out, remove_silence_segments, apply_beauty_filter, generate_cover_design, render_cover_html)
from .pro_effects import (audio_denoise, audio_normalize, speed_ramp, change_speed,
    split_screen, add_watermark, enhance_video, pro_post_process)
from .smart_cutout import (smart_cutout_image, smart_cutout_video, apply_background_replacement,
    generate_blank_background, CutoutResult)
from .douyin_categories import (get_all_categories, get_category, get_subcategory,
    get_shooting_checklist, match_material_to_category)

# ── 智能分析(5) ──
from .breath_detector import BreathDetector, BreathPoint, BreathReport, detect_breath_points
from .video_classifier import (VideoClassification, BatchClassification, classify_video, classify_batch, format_classification_report)
from .dynamic_analyzer import analyze_video_dynamic
from .precision_enhancer import (analyze_with_precision, assess_video_quality, validate_export, submit_correction, get_classification_accuracy)
from .open_source_edit import (auto_edit_silence, detect_scenes_adaptive, detect_beats_librosa, detect_silence_pydub, open_source_edit_pipeline)

# ── 编辑决策(8) ──
from .editing_rules import (EDITING_RULES, EditRule, CutRule, TextRule, AudioRule, SpeedRule,
    get_rules_for, get_all_rules_for_script, apply_rule_to_segment)
from .rule_engine import apply_rules_to_plan, auto_enhance_plans
from .cinematic_rules import (RHYTHM_PATTERNS, CINEMATIC_CONSTRAINTS, ZOOM_PACING,
    detect_rhythm_pattern, validate_cinematic_rules, get_rhythm_for_script_type)
from .douyin_editor import (MATERIAL_ORGANIZE_RULES, BREATH_EDIT_RULES, find_breath_cut_points, EditingMarker)
from .batch_processor import BatchJob, BatchResult, run_batch, create_batch_from_scripts
from .checkpoint_manager import save_checkpoint, load_checkpoint, clear_session, run_with_checkpoint

# ── OpenMontage适配(4) ──
from .openmontage_pipeline import (PIPELINE_STAGES, QUALITY_GATES, run_quality_gate,
    analyze_reference_video, clip_factory_pipeline, run_full_pipeline)
from .talking_head_pipeline import (SILENCE_CUTTER_PARAMS, ENHANCEMENT_CHAIN, EditDirector, ComposeDirector)
from .deep_skills import (SilenceCutter, SilenceReport, SceneAnalyzer, SceneReport,
    ASRCorrector, ASRReport, EnhancementRunner)
from .montage_skills import EditingSkills, EffectsSkills, AudioSkills, QualitySkills
from .changyi_config import (SCRIPT_ENHANCEMENT_CHAINS, MATERIAL_TOOL_MAP, EDITING_RULES_CONFIG,
    XIASHEN_CASE_CONFIG, get_script_enhancement, get_material_tools, build_custom_pipeline_params)

# ── 拍摄剪辑(5) ──
from .shotlist_generator import (ShotList, ShotSpec, generate_shotlist, format_shotlist_for_user, shotlist_from_parsed_annotations)
from .shot_matcher import (MatchResult, MatchedShot, match_materials_to_shotlist, build_clip_plan_from_match, format_match_report)
from .style_transfer import (EditingDNA, extract_editing_dna, apply_style_to_segments, describe_dna)
from .sentence_editor import (ScriptSentence, parse_script_to_sentences, generate_jianying_from_sentences, render_sentence_editor_html, MATERIAL_HINTS)

# ── 执行引擎(2) ──
from .execution_engine import (ExecutionJob, ChangyiExecutionEngine, quick_execute, quick_direct)
from .clip_this import clip_this, ClipResult

# ── 脚本→剪辑联通桥(1) + 闭环反馈(1) ──
from .script_clip_bridge import (BridgeConfig, bridge_script_to_clip, apply_bridge_to_job,
    bridge_and_execute, SCRIPT_TO_CLIP_CONFIG)
from .feedback_loop import (FeedbackReport, FeedbackStore, generate_feedback,
    get_script_optimization_hints)

# ── 发布体系(1) ──
from .publish_scheduler import (PLATFORMS, PublishTask, PublishResult, get_platform_status, publish_sync, schedule_publish)

# ── 定价 ──
CLIP_AGENT_PRICE = 200; CLIP_AGENT_MONTHLY = 1000; CLIP_AGENT_FREE_TRIAL = 1
def get_clip_agent_pricing():
    return {"single":{"name":"单次使用","price":"¥19.9","credits":CLIP_AGENT_PRICE},
            "monthly":{"name":"月订阅","price":"¥99/月","credits":CLIP_AGENT_MONTHLY},
            "free_trial":{"name":"免费试用","credits":0,"uses":CLIP_AGENT_FREE_TRIAL}}
def detect_voiceover_presence(analyses):
    fm=[a for a in analyses if hasattr(a,'has_face') and a.has_face]; t=len(analyses)
    if not fm: return {"has_voiceover":False,"has_talking_head":False,"avg_face_quality":0,"strategy":"script_reading","face_count":0,"total_count":t}
    avg=sum(getattr(a,'quality_score',3.0) for a in fm)/len(fm)
    s="good_presence" if avg>=3.5 else ("mixed" if avg>=2.5 else "script_reading")
    return {"has_voiceover":True,"has_talking_head":True,"avg_face_quality":round(avg,1),"strategy":s,"face_count":len(fm),"total_count":t}
