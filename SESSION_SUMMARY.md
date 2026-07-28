# 剪辑Agent · 全部成果报告

**日期**: 2026年7月24-27日
**GitHub**: https://github.com/wzb-bob/clip-agent
**提交**: 156次
**测试**: 232（独立）+ 301（后端）= **533项全部通过**
**API Key**: 4/4在线

---

## 版本演进

| 版本 | 核心变更 |
|------|---------|
| v4.0 | AI导演主导·K2.6+GLM并行·质量4→7 |
| v4.1 | 统一API·Pixelle集成·渲染修复 |
| v4.2 | 真实素材验证·SRT/ASS字幕 |
| v4.3 | 帧级精度·HEVC自动转换 |
| v5.0 | 四类素材管道·Whisper气口·JianYing草稿·Tab1↔Tab4 |
| v5.1 | Codex Skill·扣子双通道·产品→视频·PNG字幕·环境检测 |

## 五种出片方式

```bash
python demo.py "脚本" --video 素材.mp4                    # AI导演
python demo.py --jianying --script "..." --talking 口播.mp4  # 剪映草稿
python demo.py "脚本" --photo 照片.jpg                     # 数字人
python demo.py "68块!" --product-img 产品.jpg              # 带货视频
python batch.py scripts.csv                                # 批量
```

## 核心能力

- **四类素材**: 口播出镜·店铺环境·产品展示·引导CTA
- **Whisper气口**: ±16ms帧级精度·5信号融合
- **SRT字幕**: 不再依赖剪映会员·PNG/ASS/SRT三方案
- **Codex Skill**: `npx skills add wzb-bob/clip-agent --skill changyi-video-editor`
- **扣子双通道**: JianYing草稿 + Coze工作流直出
- **环境检测**: `python setup.py` 一键诊断

## 诚实差距

- 字幕烧录到视频仍偶有兼容问题（已有PNG方案降级）
- 扣子API未实际配置（需COZE_API_KEY）
- Whisper中文准确度有限（small模型·约70%）
- 未在真实付费场景验证
