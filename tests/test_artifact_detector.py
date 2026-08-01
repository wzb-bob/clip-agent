"""artifact_detector 纯函数单测(合成图像·不依赖视频)"""
import numpy as np
from src.clip_agent.artifact_detector import (
    _flat_grid, _iter_regions, _is_suspicious_color,
)


def _largest(flat, means):
    return max(_iter_regions(flat, means), key=lambda r: r["area"], default=None)


def _img_with_block(color, box=(0.0, 0.0, 1.0, 0.5), base=(120, 100, 90)):
    """160x284图·box=(x0,y0,x1,y1)相对坐标内填color, 其余加噪声"""
    img = np.random.normal(base, 30, (284, 160, 3)).clip(0, 255).astype(np.uint8)
    x0, y0 = int(box[0]*160), int(box[1]*284)
    x1, y1 = int(box[2]*160), int(box[3]*284)
    img[y0:y1, x0:x1] = color
    return img


def test_detects_red_block():
    """上半屏大红块(模拟v1 hook遮挡)→应检出saturated_block"""
    img = _img_with_block((248, 0, 0))
    flat, means = _flat_grid(img)
    region = _largest(flat, means)
    assert region and region["area"] > 0.4
    assert _is_suspicious_color(region["color"]) == "saturated_block"


def test_detects_black_box_when_not_largest():
    """右上角黑块+画面里另有更大自然色块→黑块仍应被检出(遍历全部连通区)"""
    img = _img_with_block((150, 148, 145), box=(0.0, 0.6, 1.0, 1.0))  # 底部大灰区
    img[23:100, 104:160] = (5, 5, 5)  # 右上角黑块(非最大)
    flat, means = _flat_grid(img)
    types = [_is_suspicious_color(r["color"]) for r in _iter_regions(flat, means)
             if r["area"] > 0.05]
    assert "black_box" in types


def test_natural_image_clean():
    """全图噪声(无纯色块)→无大于15%的可疑连通区"""
    img = np.random.normal(128, 40, (284, 160, 3)).clip(0, 255).astype(np.uint8)
    flat, means = _flat_grid(img)
    big = [r for r in _iter_regions(flat, means) if r["area"] > 0.15]
    assert not big


def test_skin_tone_exempt():
    """肤色大块(人脸近景)→豁免不报"""
    assert _is_suspicious_color(np.array([200.0, 160.0, 130.0])) is None


def test_dark_saturated_exempt():
    """暗饱和色(实测绿色沙发[0,122,97])→豁免不报(只报亮饱和)"""
    assert _is_suspicious_color(np.array([0.0, 122.0, 97.0])) is None


def test_gray_wall_exempt():
    """低饱和灰墙→豁免不报"""
    assert _is_suspicious_color(np.array([150.0, 148.0, 145.0])) is None


def test_white_not_reported():
    """纯白不算suspicious(白墙壁常见)·黑才算"""
    assert _is_suspicious_color(np.array([240.0, 240.0, 240.0])) is None
    assert _is_suspicious_color(np.array([10.0, 10.0, 10.0])) == "black_box"
