"""
定时发布调度器 · 剪辑Agent→多平台自动推送

已对接: 抖音(Playwright) + 视频号(Playwright)
待测试: 小红书(API?) + 快手(API?)
"""
from __future__ import annotations
import asyncio, json, logging, os, time, threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "browser_profiles"

PLATFORMS = {
    "douyin": {
        "name": "抖音", "icon": "🎵",
        "publisher_class": "DouyinPublisher",
        "profile_dir": str(PROFILE_DIR / "douyin"),
        "status": "verified",  # 已验证
        "tested_at": "2026-07-10",
    },
    "channels": {
        "name": "视频号", "icon": "📺",
        "publisher_class": "ChannelsPublisher",
        "profile_dir": str(PROFILE_DIR / "channels"),
        "status": "verified",
        "tested_at": "2026-07-10",
    },
    "xiaohongshu": {
        "name": "小红书", "icon": "📕",
        "publisher_class": None,
        "profile_dir": str(PROFILE_DIR / "xhs"),
        "status": "untested",
        "tested_at": None,
        "note": "待测试API可用性——可能需Playwright或官方API",
    },
    "kuaishou": {
        "name": "快手", "icon": "⚡",
        "publisher_class": "KuaishouPublisher",
        "profile_dir": str(PROFILE_DIR / "kuaishou"),
        "status": "verified",
        "tested_at": "2026-07-23",
        "note": "快手开放平台API + Playwright兜底——需配置KUAISHOU_APP_KEY",
    },
}

@dataclass
class PublishTask:
    """一次发布任务"""
    task_id: str
    platform: str              # douyin/channels/xiaohongshu/kuaishou
    video_path: str
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    scheduled_at: float = 0.0  # Unix timestamp, 0=立即
    status: str = "pending"    # pending/uploading/published/failed
    result: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

@dataclass
class PublishResult:
    """批量发布结果"""
    total: int
    success: int
    failed: int
    tasks: list[PublishTask]
    summary: str


def test_platform(platform_key: str) -> dict:
    """测试平台API连通性"""
    info = PLATFORMS.get(platform_key, {})
    if not info:
        return {"platform": platform_key, "available": False, "error": "未知平台"}

    result = {
        "platform": platform_key,
        "name": info["name"],
        "status": info["status"],
        "available": False,
        "error": "",
        "tested_at": datetime.now().isoformat(),
    }

    if info["status"] == "verified":
        # 已验证平台: 检查profile目录是否存在(表示已登录过)
        pd = Path(info["profile_dir"])
        if pd.exists() and any(pd.iterdir()):
            result["available"] = True
            result["note"] = "profile存在,已登录"
        else:
            result["available"] = False
            result["error"] = f"未登录——请在浏览器中扫码登录{info['name']}"
            result["note"] = "需要首次扫码登录创建profile"
    else:
        result["available"] = False
        result["error"] = info.get("note", "未测试")
        result["note"] = info.get("note", "")

    return result


def test_all_platforms() -> list[dict]:
    """测试所有平台连通性"""
    results = []
    for key in PLATFORMS:
        results.append(test_platform(key))
    return results


async def _publish_douyin(video_path: str, title: str) -> dict:
    from app.services.douyin_publisher import DouyinPublisher
    publisher = DouyinPublisher(profile_dir=PLATFORMS["douyin"]["profile_dir"], headless=True)
    return await publisher.publish(video_path, title)


async def _publish_channels(video_path: str, title: str) -> dict:
    from app.services.channels_publisher import ChannelsPublisher
    publisher = ChannelsPublisher(profile_dir=PLATFORMS["channels"]["profile_dir"], headless=True)
    return await publisher.publish(video_path, title)


async def _publish_kuaishou(video_path: str, title: str) -> dict:
    from app.services.kuaishou_publisher import KuaishouPublisher
    publisher = KuaishouPublisher(headless=True)
    return await publisher.publish(video_path, title)


async def publish_to_platform(platform_key: str, video_path: str, title: str) -> dict:
    """发布视频到指定平台"""
    if platform_key == "douyin":
        return await _publish_douyin(video_path, title)
    elif platform_key == "channels":
        return await _publish_channels(video_path, title)
    elif platform_key == "kuaishou":
        return await _publish_kuaishou(video_path, title)
    else:
        return {"success": False, "error": f"平台{platform_key}发布器未实现——待测试API"}


def publish_sync(video_path: str, title: str, platforms: list[str] = None) -> PublishResult:
    """同步发布到多个平台(包装asyncio)"""
    if platforms is None:
        platforms = ["douyin", "channels"]

    tasks = []
    for pk in platforms:
        task = PublishTask(
            task_id=f"{pk}_{int(time.time())}",
            platform=pk, video_path=video_path, title=title,
        )
        tasks.append(task)

    async def _run():
        for task in tasks:
            task.status = "uploading"
            try:
                result = await publish_to_platform(task.platform, task.video_path, task.title)
                task.result = result
                task.status = "published" if result.get("success") else "failed"
            except Exception as e:
                task.status = "failed"
                task.result = {"success": False, "error": str(e)[:200]}

    asyncio.run(_run())

    success = sum(1 for t in tasks if t.status == "published")
    failed = len(tasks) - success
    return PublishResult(
        total=len(tasks), success=success, failed=failed,
        tasks=tasks,
        summary=f"发布完成: {success}/{len(tasks)}成功" + (f", {failed}失败" if failed else ""),
    )


def schedule_publish(
    video_path: str,
    title: str,
    platforms: list[str] = None,
    delay_minutes: int = 0,
    scheduled_time: str = "",  # "2026-07-23 20:00"
) -> list[PublishTask]:
    """定时发布——延迟N分钟或指定时间"""
    if platforms is None:
        platforms = ["douyin", "channels"]

    if scheduled_time:
        scheduled_at = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M").timestamp()
    elif delay_minutes > 0:
        scheduled_at = time.time() + delay_minutes * 60
    else:
        scheduled_at = 0  # 立即

    tasks = []
    for pk in platforms:
        task = PublishTask(
            task_id=f"{pk}_{int(time.time())}",
            platform=pk, video_path=video_path, title=title,
            scheduled_at=scheduled_at,
        )
        tasks.append(task)

    if scheduled_at > 0:
        delay_sec = scheduled_at - time.time()
        if delay_sec > 0:
            logger.info("定时发布: %s后发布到%s",
                       f"{delay_sec/60:.0f}分钟" if delay_sec>60 else f"{delay_sec:.0f}秒",
                       ",".join(platforms))
            # 后台线程等待后发布
            def _delayed_publish():
                time.sleep(delay_sec)
                publish_sync(video_path, title, platforms)
            threading.Thread(target=_delayed_publish, daemon=True).start()
    else:
        # 立即发布
        publish_sync(video_path, title, platforms)

    return tasks


def get_platform_status() -> list[dict]:
    """获取所有平台状态(供前端展示)"""
    results = test_all_platforms()
    for r in results:
        info = PLATFORMS.get(r["platform"], {})
        r["icon"] = info.get("icon", "?")
        r["name"] = info.get("name", r["platform"])
    return results
