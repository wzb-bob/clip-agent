# 剪辑Agent · 快速上手

## 一分钟出片

```bash
# 素材模式: 有视频素材
python demo.py "68块！十只活虾！干煸技术。团购上线！" --video 口播.mp4 产品.mp4

# 数字人模式: 只有照片
python demo.py "大家好我是老张..." --photo 老板照片.jpg --type 老板IP

# 对比模式: 看AI导演 vs 关键词规则
python demo.py "脚本" --compare

# 演示模式: 全流程 + 诊断 + HTML报告
python demo.py "脚本" --video 素材.mp4 --showcase

# 批量模式: CSV批量处理
python batch.py scripts.csv
```

## 测试

```bash
python -m pytest tests/ -q           # 173 tests
python sync_to_backend.py            # 同步到父项目后端
```

## 诊断

```bash
python -c "from clip_agent.health import print_health_report; print_health_report()"
```

## API Key配置

编辑 `c:\Users\wangzibo\enterprise-agent-content\.env`:

```
DEEPSEEK_API_KEY=sk-xxx    # 语义分析·导演AI
KIMI_API_KEY=sk-xxx        # 视觉场景分析
GLM_API_KEY=xxx             # 帧级深标注
DOUBAO_API_KEY=ark-xxx     # 人格分析
```

## 目录结构

```
clip-agent/
  src/clip_agent/    # 核心代码 (42+模块)
  tests/             # 173项测试
  demo.py            # 演示入口
  batch.py           # 批量处理
  sync_to_backend.py # 同步到父项目
  SESSION_SUMMARY.md # 完整成果报告
```
