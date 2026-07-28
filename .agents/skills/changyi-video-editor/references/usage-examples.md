# 使用示例

## 命令行

```bash
python scripts/pipeline.py \
  --script "哎！玉田的！龙虾别瞎吃啊！..." \
  --talking 口播/A1.mp4 \
  --env 空镜/门头.mp4 空镜/室内.mp4 \
  --product 产品/虾.mp4 产品/制作.mp4 \
  --output ./我的视频/
```

## Python API

```python
from clip_agent.four_category_pipeline import run_four_category_pipeline, CategoryMaterials

materials = CategoryMaterials(
    talking=["口播.mp4"],
    environment=["门头.mp4", "室内.mp4"],
    product=["产品1.mp4"],
    cta=["引导.mp4"],
)
timeline = run_four_category_pipeline("脚本...", materials, output_dir="./output/")
# → timeline.draft_path = 剪映草稿目录
# → timeline.srt_path = SRT字幕文件
```

## 在 Codex 对话中

```
"我有一段口播视频在 D:\素材\口播\A1.mp4，
  空镜在 D:\素材\空镜\ 文件夹里，
  脚本是：哎！玉田的！龙虾别瞎吃啊！我啊，把盱眙那的龙虾技术弄来玉田...
  帮我剪一下"
```

Codex 会自动:
1. 识别四类素材
2. 调用气口切割管道
3. 生成剪映草稿 + SRT字幕
4. 输出下载链接
