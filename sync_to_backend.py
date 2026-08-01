"""一键同步: 独立项目 → 父项目后端副本

用法: python sync_to_backend.py [--dry-run]
"""
import sys
import shutil
from pathlib import Path

SRC = Path(__file__).parent / "src" / "clip_agent"
DST = Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend\app\services\clip_agent")

# __init__.py: 后端有独立兼容导入层
# digital_human.py: 后端独立开发(不在d:\clip-agent维护)
EXCLUDE = {"__init__.py", "digital_human.py", ".env", ".env.example", ".gitignore"}
SUBDIRS = {"openmontage_full", "vfx"}  # 递归同步这些子目录

def _sync_dir(src_dir: Path, dst_dir: Path, dry_run: bool) -> int:
    """递归同步子目录所有文件"""
    count = 0
    if not src_dir.exists():
        return count
    for src_file in src_dir.rglob("*"):
        if src_file.is_file() and not src_file.name.startswith("."):
            rel = src_file.relative_to(src_dir)
            dst_file = dst_dir / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if dry_run:
                print(f"  [DRY] {src_dir.name}/{rel} → {dst_file}")
            else:
                shutil.copy2(src_file, dst_file)
            count += 1
    return count

def sync(dry_run=False):
    if not DST.exists():
        print(f"❌ 目标不存在: {DST}")
        return

    synced, skipped = 0, 0

    # .py 文件
    for src_file in sorted(SRC.glob("*.py")):
        if src_file.name in EXCLUDE:
            skipped += 1
            continue
        dst_file = DST / src_file.name
        if dry_run:
            print(f"  [DRY] {src_file.name} → {dst_file}")
        else:
            shutil.copy2(src_file, dst_file)
        synced += 1

    # 子目录（递归）
    for sub in SUBDIRS:
        n = _sync_dir(SRC / sub, DST / sub, dry_run)
        synced += n

    action = "将同步" if dry_run else "已同步"
    print(f"\n✅ {synced} 文件{action}到 {DST}")
    if skipped:
        print(f"⏭️ 已跳过 {skipped} 文件: {', '.join(sorted(EXCLUDE))}")

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sync(dry_run=dry)
