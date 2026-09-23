import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.api.app.agents import prepare_image


class ImageCuratorTests(unittest.TestCase):
    def test_preserves_entire_source_and_removes_metadata(self):
        source = Image.new("RGB", (600, 900), "red")
        source.paste("blue", (0, 450, 600, 900))
        exif = Image.Exif()
        exif[0x010E] = "metadata de teste"
        source.info["exif"] = exif.tobytes()
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "prepared.jpg"
            result = prepare_image(source, target, 1200, 94)
            with Image.open(target) as saved:
                output_size = saved.size
                output_exif = len(saved.getexif())
        self.assertEqual(output_size, (1200, 1540))
        self.assertEqual(result["crop"], "none")
        self.assertTrue(result["content_preserved"])
        self.assertTrue(result["output_verified"])
        self.assertEqual(output_exif, 0)
        self.assertEqual(result["quality_state"], "source_limited")

    def test_high_resolution_source_is_ready_for_visual_review(self):
        source = Image.new("RGB", (1200, 1540), "white")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "prepared.jpg"
            result = prepare_image(source, target, 1200, 94)
        self.assertEqual(result["quality_state"], "ready_for_visual_review")
        self.assertEqual(result["warnings"], [])
        self.assertTrue(result["metadata_removed"])
        self.assertTrue(result["visual_review_required"])


if __name__ == "__main__":
    unittest.main()
