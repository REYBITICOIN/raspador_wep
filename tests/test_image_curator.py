import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from services.api.app.agents import enhance_with_realesrgan, prepare_image, source_correlation


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

    def test_realesrgan_records_model_and_scale(self):
        source = Image.new("RGB", (20, 30), "white")
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "realesrgan"
            (home / "models").mkdir(parents=True)
            (home / "realesrgan-ncnn-vulkan.exe").touch()

            def fake_run(command, **kwargs):
                output = Path(command[command.index("-o") + 1])
                Image.new("RGB", (80, 120), "white").save(output)
                return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            with patch.dict("os.environ", {"REALESRGAN_HOME": str(home)}), patch("subprocess.run", side_effect=fake_run):
                enhanced, report = enhance_with_realesrgan(source)
        self.assertEqual(enhanced.size, (80, 120))
        self.assertEqual(report["engine"], "Real-ESRGAN NCNN Vulkan")
        self.assertEqual(report["model"], "realesrgan-x4plus")
        self.assertEqual(report["scale"], 4)
        self.assertGreaterEqual(report["source_correlation"], 0.85)

    def test_correlation_detects_spatially_broken_output(self):
        source = Image.new("L", (40, 40), 0)
        source.paste(255, (0, 0, 20, 40))
        broken = Image.new("L", (40, 40), 0)
        broken.paste(255, (0, 0, 40, 20))
        self.assertLess(source_correlation(source, broken), 0.85)

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
