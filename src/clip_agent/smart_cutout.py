"""
智能抠图/换背景 · 多层次方案 — rembg(通用) + MediaPipe(人像) + OpenCV(精细) + FFmpeg(绿幕)

实现抖音剪映级别的智能抠图能力: 人物抠图→换背景→视频去背景
"""
from __future__ import annotations
import base64, io, logging, os, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class CutoutResult:
    """抠图结果"""
    success: bool
    output_path: str          # 抠图后PNG(透明背景)或视频路径
    mask_path: str = ""       # 遮罩图路径
    method: str = ""          # 使用的方法: rembg/mediapipe/grabcut/chromakey
    confidence: float = 0.0   # 置信度
    processing_time: float = 0.0
    error: str = ""


# ================================================================
# 方法1: rembg — 通用背景去除(U2-Net深度学习)
# ================================================================

def _cutout_rembg(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """rembg U2-Net背景去除——适用性最广,人物/产品/物体都能抠"""
    from rembg import remove, new_session
    # U2-Net模型(平衡精度和速度)
    session = new_session("u2net")
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    output = remove(pil_img, session=session, post_process_mask=True)
    # 转换为numpy
    output_rgba = np.array(output)
    alpha = output_rgba[:, :, 3]  # 透明度通道
    rgb = output_rgba[:, :, :3]
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), alpha


# ================================================================
# 方法2: MediaPipe — 人像分割(专门针对人物)
# ================================================================

def _cutout_mediapipe(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """MediaPipe Selfie Segmentation——人物抠图精度最高"""
    import mediapipe as mp
    mp_selfie = mp.solutions.selfie_segmentation
    with mp_selfie.SelfieSegmentation(model_selection=1) as selfie_seg:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = selfie_seg.process(rgb)
        mask = (results.segmentation_mask * 255).astype(np.uint8)
        # 二值化+边缘平滑
        _, mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        return image, mask


# ================================================================
# 方法3: OpenCV GrabCut — 交互式精细抠图
# ================================================================

def _cutout_grabcut(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OpenCV GrabCut——精细抠图,适合产品/物体"""
    mask = np.zeros(image.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    h, w = image.shape[:2]
    # 自动估计前景区域(中心80%)
    rect = (int(w * 0.1), int(h * 0.05), int(w * 0.8), int(h * 0.9))

    cv2.grabCut(image, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
    mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    mask_final = (mask2 * 255).astype(np.uint8)

    # 边缘羽化
    mask_final = cv2.GaussianBlur(mask_final, (3, 3), 0)
    return image, mask_final


# ================================================================
# 方法4: FFmpeg Chromakey — 绿幕抠像
# ================================================================

def _cutout_chromakey_video(video_path: str, output_path: str,
                             color: str = "0x00FF00", similarity: float = 0.3,
                             blend: float = 0.1) -> dict:
    """FFmpeg绿幕抠像——视频专用,适合专业拍摄素材"""
    try:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vf", f"chromakey={color}:{similarity:.2f}:{blend:.2f}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "copy",
            output_path,
        ]
        subprocess.run(cmd, timeout=120, check=True)
        return {"success": True, "output": output_path, "method": "chromakey"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ================================================================
# 智能抠图主函数 — 自动选择最佳方法
# ================================================================

def smart_cutout_image(
    image_path: str,
    output_path: str = "",
    method: str = "auto",     # auto/rembg/mediapipe/grabcut
    replace_bg_color: str = "",  # 替换背景色 如"#FFFFFF"白色
    replace_bg_image: str = "",  # 替换背景图路径
) -> CutoutResult:
    """智能抠图——对图片自动选择最佳方法

    Args:
        image_path: 输入图片路径
        output_path: 输出PNG路径(透明背景)
        method: auto=自动选择最佳 / rembg / mediapipe / grabcut
        replace_bg_color: 替换为纯色背景(#FFFFFF=白色)
        replace_bg_image: 替换为背景图路径
    """
    if not os.path.exists(image_path):
        return CutoutResult(False, "", error="图片不存在")

    t0 = time.time()
    image = cv2.imread(image_path)
    if image is None:
        return CutoutResult(False, "", error="无法读取图片")

    h, w = image.shape[:2]

    # 自动选择: 优先rembg(通用) → MediaPipe(人物) → GrabCut(产品)
    try:
        if method == "auto" or method == "rembg":
            img, mask = _cutout_rembg(image)
            method_used = "rembg"
        elif method == "mediapipe":
            img, mask = _cutout_mediapipe(image)
            method_used = "mediapipe"
        elif method == "grabcut":
            img, mask = _cutout_grabcut(image)
            method_used = "grabcut"
        else:
            return CutoutResult(False, "", error=f"未知方法: {method}")
    except ImportError as e:
        # rembg失败→降级MediaPipe
        try:
            img, mask = _cutout_mediapipe(image)
            method_used = "mediapipe(fallback)"
        except Exception:
            try:
                img, mask = _cutout_grabcut(image)
                method_used = "grabcut(fallback)"
            except Exception as e2:
                return CutoutResult(False, "", error=f"所有抠图方法失败: {e2}")

    # 计算置信度(基于mask中非零像素比例)
    confidence = round(np.count_nonzero(mask) / mask.size, 2)

    # 构建透明背景的RGBA图像
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = img
    rgba[:, :, 3] = mask

    # 替换背景
    if replace_bg_color or replace_bg_image:
        if replace_bg_color:
            # 纯色背景
            color_hex = replace_bg_color.lstrip('#')
            r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
            bg = np.full((h, w, 3), (b, g, r), dtype=np.uint8)
        elif replace_bg_image and os.path.exists(replace_bg_image):
            bg = cv2.imread(replace_bg_image)
            bg = cv2.resize(bg, (w, h))
        else:
            bg = None

        if bg is not None:
            # Alpha混合: 前景*mask + 背景*(1-mask)
            mask_3ch = np.stack([mask/255.0]*3, axis=-1)
            result = (img * mask_3ch + bg * (1 - mask_3ch)).astype(np.uint8)
            rgba[:, :, :3] = result
            rgba[:, :, 3] = 255  # 不透明背景

    # 保存结果
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"cutout_{Path(image_path).stem}_{int(time.time())}.png")

    pil_result = Image.fromarray(rgba, 'RGBA')
    pil_result.save(output_path, 'PNG')

    elapsed = time.time() - t0
    logger.info("抠图完成: %s → %s (置信度%.0f%%, %.1fs)", method_used, output_path, confidence*100, elapsed)

    return CutoutResult(
        success=True, output_path=output_path, method=method_used,
        confidence=confidence, processing_time=round(elapsed, 1),
    )


def smart_cutout_video(
    video_path: str,
    output_path: str = "",
    method: str = "auto",
) -> CutoutResult:
    """智能抠图——对视频提取关键帧抠图,或绿幕抠像

    Args:
        video_path: 视频路径
        method: auto=自动 / chromakey=绿幕 / frame=逐帧抠关键帧
    """
    if not os.path.exists(video_path):
        return CutoutResult(False, "", error="视频不存在")

    t0 = time.time()
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"cutout_video_{Path(video_path).stem}_{int(time.time())}.mp4")

    if method == "chromakey" or method == "auto":
        # 尝试绿幕抠像(检测是否含绿色背景)
        result = _cutout_chromakey_video(video_path, output_path)
        if result.get("success"):
            return CutoutResult(
                success=True, output_path=output_path, method="chromakey",
                processing_time=round(time.time()-t0, 1),
            )

    # 降级: 提取中间帧抠图
    try:
        # 提取中间帧
        frame_path = os.path.join(tempfile.gettempdir(), f"midframe_{int(time.time())}.jpg")
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path, "-vframes", "1", "-ss", "1", frame_path,
        ], timeout=15, check=True)

        cutout_frame = smart_cutout_image(frame_path)
        if cutout_frame.success:
            return CutoutResult(
                success=True, output_path=cutout_frame.output_path,
                method=f"frame_cutout({cutout_frame.method})",
                confidence=cutout_frame.confidence,
                processing_time=round(time.time()-t0, 1),
            )
    except Exception as e:
        logger.warning("视频帧抠图失败: %s", e)

    return CutoutResult(False, "", error="视频抠图失败——尝试使用绿幕素材或先转图片")


def apply_background_replacement(
    foreground_path: str, background_path: str, output_path: str = ""
) -> CutoutResult:
    """换背景——先抠前景,再叠加到新背景上"""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(),
            f"bg_replace_{int(time.time())}.png")
    return smart_cutout_image(foreground_path, output_path, replace_bg_image=background_path)


def generate_blank_background(width: int = 1080, height: int = 1920,
                              color: str = "gradient") -> str:
    """生成空白背景图——用于抠图后替换"""
    bg_path = os.path.join(tempfile.gettempdir(), f"bg_{int(time.time())}.png")

    if color == "gradient":
        # 渐变背景(从上到下)
        gradient = np.zeros((height, width, 3), dtype=np.uint8)
        for i in range(height):
            ratio = i / height
            # 深蓝→红渐变
            r = int(26 * (1-ratio) + 233 * ratio)
            g = int(26 * (1-ratio) + 69 * ratio)
            b_val = int(46 * (1-ratio) + 96 * ratio)
            gradient[i, :] = (b_val, g, r)
        cv2.imwrite(bg_path, gradient)
    else:
        # 纯色背景
        color_hex = color.lstrip('#')
        r, g, b = int(color_hex[0:2],16), int(color_hex[2:4],16), int(color_hex[4:6],16)
        bg = np.full((height, width, 3), (b, g, r), dtype=np.uint8)
        cv2.imwrite(bg_path, bg)

    return bg_path
