"""
平台首次登录助手 · 打开浏览器让用户扫码登录 → 保存profile供后续headless使用
"""
import asyncio, logging, os, sys
from pathlib import Path

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "browser_profiles"

PLATFORM_LOGIN_URLS = {
    "douyin": {
        "name": "抖音", "icon": "🎵",
        "login_url": "https://creator.douyin.com/",
        "profile_dir": str(PROFILE_DIR / "douyin"),
        "success_indicator": "抖音创作者中心",
    },
    "channels": {
        "name": "视频号", "icon": "📺",
        "login_url": "https://channels.weixin.qq.com/platform/post/create",
        "profile_dir": str(PROFILE_DIR / "channels"),
        "success_indicator": "视频号助手",
    },
    "xiaohongshu": {
        "name": "小红书", "icon": "📕",
        "login_url": "https://creator.xiaohongshu.com/",
        "profile_dir": str(PROFILE_DIR / "xhs"),
        "success_indicator": "小红书创作服务平台",
    },
    "kuaishou": {
        "name": "快手", "icon": "⚡",
        "login_url": "https://cp.kuaishou.com/",
        "profile_dir": str(PROFILE_DIR / "kuaishou"),
        "success_indicator": "快手创作者平台",
    },
}


async def open_login_browser(platform_key: str) -> dict:
    """打开浏览器让用户扫码登录——首次使用必须运行一次"""
    info = PLATFORM_LOGIN_URLS.get(platform_key)
    if not info:
        return {"success": False, "error": f"未知平台: {platform_key}"}

    profile_path = Path(info["profile_dir"])
    profile_path.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                str(profile_path),
                headless=False,  # 必须可见——用户要扫码
                viewport={"width": 1280, "height": 900},
                locale="zh-CN",
            )
            page = await browser.new_page()
            await page.goto(info["login_url"], timeout=30000, wait_until="domcontentloaded")

            print(f"\n{'='*50}")
            print(f"  {info['icon']} {info['name']} 登录窗口已打开")
            print(f"  请在浏览器中扫码登录")
            print(f"  登录成功后，关闭浏览器窗口即可")
            print(f"  Profile保存在: {profile_path}")
            print(f"{'='*50}\n")

            # 等待用户手动关闭浏览器
            await page.wait_for_event("close", timeout=300000)  # 5分钟超时
            await browser.close()

            # 验证profile是否保存
            if profile_path.exists() and any(profile_path.iterdir()):
                return {"success": True, "platform": platform_key, "profile": str(profile_path)}
            else:
                return {"success": False, "error": "浏览器关闭但profile未保存——登录可能未完成"}

    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def login_platform(platform_key: str):
    """同步包装——在命令行中运行"""
    return asyncio.run(open_login_browser(platform_key))


def login_all_platforms():
    """依次打开所有平台的登录窗口"""
    results = []
    for key in ["douyin", "channels"]:  # 先做已验证的两个
        print(f"\n准备登录 {PLATFORM_LOGIN_URLS[key]['name']}...")
        result = login_platform(key)
        results.append(result)
        if result["success"]:
            print(f"✅ {PLATFORM_LOGIN_URLS[key]['name']} 登录成功")
        else:
            print(f"❌ {PLATFORM_LOGIN_URLS[key]['name']}: {result.get('error','')}")
    return results


def check_login_status(platform_key: str) -> dict:
    """检查平台是否已登录（profile是否存在）"""
    info = PLATFORM_LOGIN_URLS.get(platform_key, {})
    if not info:
        return {"logged_in": False, "error": "未知平台"}
    pp = Path(info["profile_dir"])
    if pp.exists() and any(pp.iterdir()):
        return {"logged_in": True, "profile": str(pp)}
    return {"logged_in": False, "need_login": True}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        platform = sys.argv[1]
        print(f"打开 {PLATFORM_LOGIN_URLS.get(platform,{}).get('name',platform)} 登录窗口...")
        result = login_platform(platform)
        print(result)
    else:
        print("用法: python platform_login.py [douyin|channels|xiaohongshu|kuaishou]")
        print("或: python platform_login.py all  # 依次登录所有平台")
        if sys.argv[-1] == "all" if len(sys.argv) > 1 else False:
            login_all_platforms()
