---
name: changyi-video-editor
description: 长益剪辑Agent·四类素材上传·AI气口切割·剪映草稿+SRT字幕·实体店口播专用
version: 5.1.0
tags: [video-editing, short-video, douyin, jianying, subtitle, talking-head]
---

# 长益剪辑Agent

> 给实体店老板做抖音口播视频的AI剪辑工具。
> 四类素材上传 → AI气口切割 → 剪映草稿 + SRT字幕 → 拖入剪映即用。

## 触发条件

当用户说以下关键词时自动加载此Skill:
- "剪视频" "做口播" "帮我剪" "剪辑" "生成草稿" "做短视频"
- "口播出镜" "产品展示" "店铺环境" "引导CTA"
- "四类素材" "剪映草稿" "智能包装"

## 工作流

### Step 1: 收集素材
请用户提供:
1. **脚本**（口播文案）
2. **四类素材**的文件夹路径:
   - 🎤 口播出镜（真人/数字人·主轨）
   - 🏠 店铺环境（门头/室内/室外·B-roll）
   - 📦 产品展示（特写/制作过程·B-roll）
   - 👉 引导CTA（结尾引导·最后一段）

### Step 2: 气口切割
调用 `four_category_pipeline.run()`:
- Whisper word-level 转录口播视频
- 检测句间自然停顿（≥500ms = 句子边界）
- 每段精确到 ±16ms @30fps
- B-roll 在停顿处交替插入（口播→环境→产品→口播→CTA）

### Step 3: 生成输出
- **剪映草稿 ZIP**（draft_content.json）
- **SRT 字幕文件**（Whisper 精准时间戳）
- 用户解压 → 拖入剪映 → 字幕自动就位

### Step 4: 用户操作
1. 解压草稿 ZIP
2. 打开剪映 → 导入草稿文件夹
3. 导入 SRT 字幕文件
4. 点「智能包装」（会员功能·可选）
5. 导出 MP4

## 安装

```bash
npx skills add wzb-bob/clip-agent --skill changyi-video-editor -g -a codex
```

## 示例对话

```
用户: 帮我剪个视频。口播在 D:\素材\口播\ 里，空镜在 D:\素材\空镜\，
      脚本是"哎！玉田的！龙虾别瞎吃啊！..."

Codex: 📹 分析口播视频...
       检测到 6 个句子边界
       📋 时间线:
         🎤 0.0s 口播 "哎！玉田的！"
         🎬 4.0s B-roll(环境) "我啊，把盱眙技术弄来玉田"
         🎬 9.0s B-roll(产品) "外头的龙虾不干净"
         🎤 14.0s 口播 "来虾神，左下角团购！"
       📥 草稿 ZIP 已生成
       📝 SRT 字幕已生成
       💡 解压 → 拖入剪映 → 字幕自动就位
```

## 依赖

- Python 3.10+
- FFmpeg
- Whisper (自动下载 small 模型)
- pyJianYingDraft (可选·草稿JSON生成)
- 4/4 API Key (DeepSeek+Kimi+GLM+Doubao·可选·语义增强)

## 参考

- [四类素材说明](references/four-categories.md)
- [使用示例](references/usage-examples.md)
- [脚本调用](scripts/pipeline.py)
