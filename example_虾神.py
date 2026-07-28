"""
虾神龙虾 · 完整示例
直接运行: python example_虾神.py
输出: 剪映草稿 + SRT字幕 + 使用说明
"""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
_backend = Path(r"c:\Users\wangzibo\enterprise-agent-content\acquisition-backend")
if _backend.exists():
    sys.path.insert(0, str(_backend))

try:
    from dotenv import load_dotenv
    for ep in [_backend / ".env", _backend.parent / ".env"]:
        if ep.exists():
            load_dotenv(ep)
            break
except ImportError:
    pass

from clip_agent.four_category_pipeline import run_four_category_pipeline, CategoryMaterials
from clip_agent.jianying_timeline_builder import export_draft_zip

# ═══════════════════════════════════════════════
# 配置: 修改这里的路径即可适配你的素材
# ═══════════════════════════════════════════════

# 虾神老板口播脚本
SCRIPT = """哎！玉田的！龙虾别瞎吃啊！

我啊，把盱眙那的龙虾技术弄来玉田，一干，三年了都。好多朋友说，外头的龙虾，要么不干净，要么就没那味儿。

我这儿的虾，都是活蹦乱跳的，干煸得用香茅草，花雕酒腌，八小时。现在团购，人均几十块，真的，吃个够！

来虾神，我请你吃盱眙味儿的！左下角团购！"""

# 四类素材（修改为你的实际路径）
BASE = r"c:\Users\wangzibo\Desktop\测试视频"
MATERIALS = CategoryMaterials(
    talking=[os.path.join(BASE, "_a1_x264.mp4")],      # 口播出镜
    environment=[                                        # 店铺环境
        os.path.join(BASE, "空镜", "DJI_20260716140503_0111_D.MP4"),
        os.path.join(BASE, "空镜", "DJI_20260716140724_0118_D.MP4"),
    ],
    product=[os.path.join(BASE, "_dji_x264.mp4")],     # 产品展示
    cta=[],                                              # 引导CTA(可选)
)

OUTPUT = os.path.join(BASE, "虾神龙虾_成片")

# ═══════════════════════════════════════════════
# 执行（无需修改以下代码）
# ═══════════════════════════════════════════════

print("🦞 虾神龙虾 · 智能剪辑")
print(f"   脚本: {len(SCRIPT)}字")
print(f"   口播: {len(MATERIALS.talking)}个")
print(f"   环境: {len(MATERIALS.environment)}个")
print(f"   产品: {len(MATERIALS.product)}个")
print()

timeline = run_four_category_pipeline(SCRIPT, MATERIALS, output_dir=OUTPUT)

print(f"✅ {len(timeline.segments)}段 · {timeline.total_duration:.0f}秒")
for s in timeline.segments:
    b = "🎬B-roll" if s.is_broll else "🎤口播"
    print(f"  {b} {s.start_sec:.1f}s [{s.material_category}] {s.script_text[:30]}")

if timeline.draft_path:
    zip_path = export_draft_zip(timeline.draft_path)
    print(f"\n📥 草稿ZIP: {zip_path}")
    print(f"📁 输出目录: {OUTPUT}")
    print("💡 解压 → 拖入剪映 → 字幕就位 → 智能包装 → 出片")
