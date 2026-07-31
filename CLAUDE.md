# 长益剪辑Agent · 全自动短视频编辑智能体

> 86模块·246 tests·ChatCut全自动管线·MLT+FFmpeg VFX双引擎·Kimi持续学习
> 独立仓库（2026-07-24）· GitHub: wzb-bob/clip-agent
> 后端集成副本: `c:\Users\wangzibo\enterprise-agent-content\acquisition-backend\app\services\clip_agent\`

## 项目状态

**当前阶段**: 阶段2（产品化）→ ✅ 门禁通过 → 阶段3（上线）
**版本**: v5.2 · ChatCut全自动·MLT+FFmpeg VFX·56着色器·Kimi持续学习
**模块**: 86模块 + 56 GLSL着色器 + 80+ PNG模板 + 22 JSON Schema
**测试**: 246 tests / 29文件 / 全部通过
**Git**: 独立仓库·origin: https://github.com/wzb-bob/clip-agent
**父项目集成**: sync_to_backend.py → acquisition-backend/app/services/clip_agent/ (86模块同步)

## ChatCut 全自动渲染管线

```
口播视频+脚本 → HEVC自动转x264 → 音频增强(人声分离+降噪) → Whisper语音→SRT字幕
  → 四类素材气口精切(±16ms帧级精度) → VFX计划(三类脚本差异化模板)
  → 三级降级渲染链:
     ① MLT引擎 (melt CLI·frei0r调色·xfade转场·BGM闪避)
     ② FFmpeg VFX (filter_complex 6步·56着色器·80+PNG文字·节拍触发)
     ③ ProRenderer (基础拼接+文字)·剪映草稿ZIP(最终兜底)
  → Kimi持续学习 (出片→评估→α=0.3平滑更新→自动改进)
  → 1080p MP4成片 (~22s全自动)
```

## 模块清单（86模块·9组）

### 核心引擎(6)
`changyi_config` · `clip_templates` · `media_analyzer` · `clip_planner` · `jianying_export` · `__init__`

### 编辑决策(8)
`editing_rules` · `rule_engine` · `cinematic_rules` · `douyin_editor` · `style_transfer` · `edit_intelligence` · `sentence_editor` · `taste_profiles`

### 抖音能力(5)
`douyin_effects` · `douyin_missing` · `pro_effects` · `smart_cutout` · `douyin_categories`

### 智能分析(12)
`breath_detector` · `video_classifier` · `dynamic_analyzer` · `precision_enhancer` · `open_source_edit`
`media_understanding` · `local_video_analyzer` · `kimi_scene_analyzer` · `visual_semantic_aligner` · `aesthetic_constraints`
`content_analyzer` · `semantic_engine`

### 渲染引擎(9)
`mlt_engine` · `chatcut_plugin` · `chatcut_vfx` · `pro_renderer` · `pro_effects`
`subtitle_overlay` · `subtitle_burner` · `rhythm_engine` · `template_gen`

### VFX引擎(4核心+56着色器)
`vfx/beat_trigger.py` · `vfx/color_matrix.py` · `vfx/glsl_renderer.py` · `vfx/shader_catalog.py`
`vfx/shaders/` — 56个 .frag 着色器 (bloom/glitch/chromatic/vignette/wipe等)

### 素材管线(6)
`four_category_pipeline` · `audio_separator` · `whisper_srt_generator` · `transcript_corrector` · `video_normalizer` · `shot_splitter`

### 学习系统(5)
`continuous_learner` · `batch_learner` · `video_learner` · `douyin_learner` · `feedback_loop`

### 执行与发布(12)
`execution_engine` · `smart_cutter` · `batch_processor` · `checkpoint_manager`
`publish_scheduler` · `platform_login` · `pipeline_tracer` · `report_generator`
`shotlist_generator` · `shot_matcher` · `guided_shooting` · `clip_this`

### 扩展能力(19)
`digital_human` · `voice_cloner` · `ai_image_gen` · `product_to_video` · `script_clip_bridge`
`jianying_timeline_builder` · `coze_pipeline` · `flowvid_plugin` · `plugin_registry`
`deep_skills` · `montage_skills` · `openmontage_pipeline` · `openmontage_full/` (22 JSON Schema)
`talking_head_pipeline` · `director_ai` · `chai_reviewer` · `platform_specs` · `cli` · `health`

## 测试覆盖

```bash
python -m pytest tests/ -q    # 246 passed (29 files)
```

覆盖: health/editing_rules/clip_templates/breath/execution_engine/pro_renderer/aesthetic/audio/chatcut/changyi_api/coze/digital_human/director/e2e/feedback/four_category/integration/local_video/pipeline_tracer/plugin_registry/product_to_video/report/rhythm/script_clip_bridge/semantic/visual/voice/whisper

## 运行

```bash
# CLI一键出片
python -m clip_agent.cli clip "脚本文字" --type 团购售卖 --audio 口播.mp4

# 批量学习
python batch.py

# 演示
python demo.py

# 同步到后端
python sync_to_backend.py

# 测试
python -m pytest tests/ -q
```

## 同步机制

```
d:\clip-agent\src\clip_agent\  ──sync_to_backend.py──>  acquisition-backend\app\services\clip_agent\
     (开发主副本·86模块)                                      (后端集成副本·86模块)
```

手动执行 `python sync_to_backend.py` 同步 .py 文件 + vfx/ + openmontage_full/ 子目录。
EXCLUDE: `__init__.py`（后端有自己的兼容导入层）

## 关键架构决策（不可推翻）

- 剪辑策略 = 脚本三分类驱动（老板IP→Emma型/团购售卖→Hormozi型/引流进店→混合型）
- MLT(melt 7.25.0) 主路径 + FFmpeg VFX 降级 + ProRenderer 兜底 + 剪映草稿 ZIP 最终降级
- BGM音量 = 人声1/3，人声时闪避至25%
- 蒙太奇强制规则: 相邻镜头景别不能重复
- 文字渲染: PIL PNG模板（圆角·阴影·不依赖系统字体）— Windows pango不可用
- 持续学习: α=0.3平滑更新·评分>=8自动停止·10行业知识从Kimi直接提取
- 两份副本(d:\clip-agent + backend)修改后须通过 sync_to_backend.py 同步
- 所有LLM调用走 gateway_client，模型名从 model_config 读取（集成模式）
