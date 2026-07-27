"""一键同步: 独立项目 → 父项目后端副本

用法: python sync_to_backend.py [--dry-run]
"""
import sys
import shutil
from pathlib import Path

SRC = Path(__file__).parent / "src" / "clip_agent"
DST = Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend\app\services\clip_agent")

EXCLUDE = {"__init__.py", ".env", ".env.example", ".gitignore"}  # 不覆盖敏感/配置

def sync(dry_run=False):
    if not DST.exists():
        print(f"❌ 目标不存在: {DST}")
        return

    synced, skipped = 0, 0
    for src_file in sorted(SRC.glob("*.py")):
        if src_file.name in EXCLUDE:
            continue
        dst_file = DST / src_file.name
        if dry_run:
            print(f"  [DRY] {src_file.name} → {dst_file}")
            synced += 1
        else:
            shutil.copy2(src_file, dst_file)
            synced += 1

    # 递归同步 openmontage_full (Schema + __init__)
    om_src = SRC / "openmontage_full"
    om_dst = DST / "openmontage_full"
    if om_src.exists():
        for src_file in om_src.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(om_src)
                dst_file = om_dst / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                if dry_run:
                    print(f"  [DRY] openmontage/{rel} → {dst_file}")
                else:
                    shutil.copy2(src_file, dst_file)
                synced += 1

    action = "将同步" if dry_run else "已同步"
    print(f"\n✅ {synced} 文件{action}到 {DST}")
    if EXCLUDE:
        print(f"⏭️ 已跳过: {', '.join(sorted(EXCLUDE))}")

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sync(dry_run=dry)
