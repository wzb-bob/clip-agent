# 预渲染透明视频模板

复杂动画不实时计算。预先制作透明WebM/ProRes视频片段，渲染时用FFmpeg overlay叠加。

## 使用方式

在 `pro_renderer.py` 中调用 `_overlay_template(working, template_path, start_sec, duration)`。

## 待制作模板

| 模板文件 | 用途 | 时长 | 规格 |
|----------|------|------|------|
| `price_popup.webm` | 价格弹出动画(红底白字) | 3s | 1080x1920, VP9+Alpha |
| `cta_button.webm` | "左下角囤券"按钮动画 | 2s | 1080x1920, VP9+Alpha |
| `location_pin.webm` | 定位标记脉冲动画 | 2s | 1080x1920, VP9+Alpha |
| `flash_sale.webm` | 限时抢购闪烁标签 | 3s | 1080x1920, VP9+Alpha |
| `new_store.webm` | 新店开业爆炸贴 | 3s | 1080x1920, VP9+Alpha |

## 制作方法

用AE/剪映制作动画 → 导出为带Alpha通道的WebM:
```bash
ffmpeg -i template.mov -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 template.webm
```

## 设计原则

- 动画简洁，0.3-0.5秒完成主体动作
- 红(#DC143C)/黄(#FFD700)/白 三色为主
- 适配1080x1920竖屏
- Alpha通道透明，便于叠加
