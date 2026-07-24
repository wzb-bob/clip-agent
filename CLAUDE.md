# 长益剪辑Agent · 全自动短视频编辑智能体

> 42模块·106 tests·15/15抖音能力·4层精度·剪映草稿+MP4双输出
> 已从 enterprise-agent-content 独立（2026-07-24）· 后端集成副本维持在 `../enterprise-agent-content/acquisition-backend/app/services/clip_agent/`

## 项目状态

**当前阶段**: 阶段2（产品化）— 测试已建立，待安全审计+性能验证+CR
**版本**: v4 生产就绪
**模块**: 42模块（含__init__共43文件）
**测试**: 106 tests / 6文件 / 全部通过
**Git**: 独立仓库
**父项目集成**: Streamlit :8501 Tab4（依赖 gateway_client/model_config/credit_service）

## 架构

```
用户素材+脚本 → 执行引擎6阶段管线 → 剪映草稿+MP4成片
  ├── Stage 1: 脚本解析→句级分镜
  ├── Stage 2: A/B上传槽验证
  ├── Stage 2.5: 预检(静音+场景分析)
  ├── Stage 3: 增强链(美颜+调色+音频)
  ├── Stage 4: 编辑规则(J-cut/L-cut+节奏)
  ├── Stage 5: 质量门禁
  └── Stage 6: 导出(剪映草稿+专业MP4)
```

## 编辑规则引擎（核心差异化能力）

15条精确规则 = 3脚本类型 × 5角色(hook/body/broll/outro) × 帧级参数

```
团购+product+hook → CU特写·72px红价弹出·原声静音·beat卡点切
老板IP+talking+body → MS长镜·无文字·keep原声·silence500ms才切
引流+storefront+outro → LS门头定·52px金CTA·keep原声·fade_out
```

## 模块清单（42模块）

### 核心引擎(6)
`changyi_config` · `clip_templates` · `media_analyzer` · `clip_planner` · `jianying_export` · `__init__`

### 编辑决策(8)
`editing_rules` · `rule_engine` · `cinematic_rules` · `douyin_editor` · `style_transfer` · `edit_intelligence` · `sentence_editor` · `taste_profiles`

### 抖音能力(5)
`douyin_effects` · `douyin_missing` · `pro_effects` · `smart_cutout` · `douyin_categories`

### 智能分析(5)
`breath_detector` · `video_classifier` · `dynamic_analyzer` · `precision_enhancer` · `open_source_edit`

### 拍摄剪辑(5)
`shotlist_generator` · `shot_matcher` · `guided_shooting` · `batch_processor` · `talking_head_pipeline`

### 执行与渲染(5)
`execution_engine` · `pro_renderer` · `smart_cutter` · `cli` · `health`

### 发布体系(3)
`publish_scheduler` · `platform_login` · `checkpoint_manager`

### 蒙太奇与技能(4)
`montage_skills` · `openmontage_pipeline` · `deep_skills` · `clip_this`

### 审片与平台(2)
`chai_reviewer` · `platform_specs`

## 精度层级
```
frame_level(12帧独立API) → three_stage → multi_frame → single_frame
```

## 运行
```bash
# 测试
python -m pytest tests/ -v       # 106 passed

# 通过父项目 Streamlit 使用
cd ../enterprise-agent-content/acquisition-backend
streamlit run app.py             # → localhost:8501 Tab4
```

## 关键架构决策（不可推翻）
- 剪辑策略=脚本三分类驱动（老板IP→Emma型/团购售卖→Hormozi型/引流进店→混合型）
- BGM音量=人声1/3，人声时闪避至25%
- 蒙太奇强制规则: 相邻镜头景别不能重复
- 所有LLM调用走gateway_client，模型名从model_config读取
- 本目录为开发主副本，修改后须同步到 backend `app/services/clip_agent/`
