"""product_to_video.py 测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestCreateProductVideo:
    def test_missing_image(self):
        from clip_agent.product_to_video import create_product_video
        result = create_product_video("/nonexistent/img.jpg", "68块!", ["十只活虾"])
        assert result["success"] is False
        assert "不存在" in result.get("error", "")

    def test_minimal(self):
        """Test with a real image if available"""
        from clip_agent.product_to_video import create_product_video
        test_img = r"c:\tmp\clip_e2e\test_photo.jpg"
        import os
        if os.path.exists(test_img):
            result = create_product_video(test_img, "68块!", ["十只活虾", "干煸技术"])
            assert isinstance(result["success"], bool)
