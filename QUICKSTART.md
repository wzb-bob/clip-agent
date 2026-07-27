# 剪辑Agent v4.2 · 快速上手

## 命令速查

```bash
# 素材出片
python demo.py "68块！十只活虾！" --video 素材.mp4

# 数字人出片(照片→口播视频)
python demo.py "脚本" --photo 照片.jpg

# 新旧对比(看AI提升)
python demo.py "脚本" --compare

# 演示模式(诊断+报告+自动打开)
python demo.py "脚本" --showcase

# JSON输出(接API)
python demo.py "脚本" --json

# 批量处理(CSV)
python batch.py scripts.csv

# 系统诊断
python -c "from clip_agent.health import print_health_report; print_health_report()"

# 测试
python -m pytest tests/ -q           # 212 tests
python sync_to_backend.py            # 同步后端

# Python API
from clip_agent import api
api.clip("脚本", videos=["素材.mp4"])
api.digital_human("照片.jpg", "脚本")
api.diagnose()
```

## 配置

编辑 `c:\Users\wangzibo\enterprise-agent-content\.env`:
```
DEEPSEEK_API_KEY=sk-xxx    # 必填·语义+导演
KIMI_API_KEY=sk-xxx        # 选填·视觉分析
GLM_API_KEY=xxx             # 选填·帧标注
DASHSCOPE_API_KEY=xxx      # 选填·AI生图B-roll
```

## 测试

```bash
python -m pytest tests/ -q    # 212 PASS
```

## 文档

- [全部成果](SESSION_SUMMARY.md)
- [质量计划](~/.claude/plans/compressed-petting-falcon.md)
