# 剪辑Agent v5.1 · 快速上手

## 命令速查

```bash
# 四类素材→剪映草稿（推荐）
python demo.py --jianying --script "脚本..." --talking 口播.mp4 --env 门头.mp4 --product 产品.mp4

# 素材出片（AI导演）
python demo.py "68块！十只活虾！" --video 素材.mp4

# 数字人（照片→口播）
python demo.py "脚本" --photo 照片.jpg

# 产品图→带货视频
python demo.py "68块！十只活虾！干煸技术" --product-img 产品.jpg

# 新旧对比
python demo.py "脚本" --compare

# 批量处理
python batch.py scripts.csv

# JSON输出（接API）
python demo.py "脚本" --json

# 系统诊断
python -c "from clip_agent.health import print_health_report; print_health_report()"

# Python API
from clip_agent import api
api.clip("脚本", videos=["素材.mp4"])
api.digital_human("照片.jpg", "脚本")

# Codex Skill 安装
npx skills add wzb-bob/clip-agent --skill changyi-video-editor -g -a codex
```

## 测试

```bash
python -m pytest tests/ -q    # 232 PASS
```

## 文档

- [全部成果](SESSION_SUMMARY.md)
- [Codex Skill](.agents/skills/changyi-video-editor/SKILL.md)
- [扣子工作流](.agents/workflows/coze-video-edit.json)
