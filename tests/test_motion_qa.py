import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from motion_qa import analyze_frames, rectangle

FACE = [0.30, 0.05, 0.40, 0.30]


class MotionAnalysisTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(227)
        self.background = rng.integers(25, 170, size=(128, 128), dtype=np.uint8)

    def test_static_and_face_only_do_not_count_as_body_motion(self):
        still = np.stack([self.background.copy() for _ in range(6)])
        self.assertEqual(analyze_frames(still, FACE)["classification"], "no_localized_change_detected")
        face_only = still.copy()
        for index, frame in enumerate(face_only):
            frame[20:35, 50:72] = 220 if index % 2 else 20
        result = analyze_frames(face_only, FACE)
        self.assertEqual(result["classification"], "no_localized_change_detected")
        self.assertEqual(result["active_pairs"], 0)

    def test_global_pan_alone_is_not_mistaken_for_body_movement(self):
        frames = np.stack([np.roll(self.background, 2 * i, axis=1) for i in range(6)])
        result = analyze_frames(frames, FACE)
        self.assertEqual(result["classification"], "no_localized_change_detected", result)
        self.assertTrue(all(pair["translation_pixels_xy"] == [-2, 0] for pair in result["pairs"]))

    def test_local_object_motion_outside_face_is_detected(self):
        frames = np.stack([self.background.copy() for _ in range(6)])
        for index, frame in enumerate(frames):
            frame[75:104, 5 + index * 5:25 + index * 5] = 235
        result = analyze_frames(frames, FACE, [0, 0.5, 1, 0.5])
        self.assertEqual(result["classification"], "localized_change_detected", result)
        self.assertGreaterEqual(result["active_pairs"], 2)

    def test_scene_cut_is_not_treated_as_sustained_motion(self):
        rng = np.random.default_rng(81)
        other = rng.integers(25, 170, size=(128, 128), dtype=np.uint8)
        frames = np.stack([self.background] * 3 + [other] * 3)
        result = analyze_frames(frames, FACE)
        self.assertNotEqual(result["classification"], "localized_change_detected", result)
        self.assertTrue(any(pair.get("scene_cut_suspected") for pair in result["pairs"]))

    def test_invalid_rectangle_is_rejected(self):
        with self.assertRaises(Exception):
            rectangle("0.9,0.0,0.2,0.2")

    def test_uniform_brightness_change_is_not_body_motion(self):
        base = self.background.astype(np.int16)
        frames = np.stack([np.clip(base + i * 4, 0, 255).astype(np.uint8) for i in range(6)])
        result = analyze_frames(frames, FACE)
        self.assertEqual(result["classification"], "no_localized_change_detected", result)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe required")
    def test_cli_on_encoded_local_motion(self):
        frames = np.stack([self.background.copy() for _ in range(8)])
        for index, frame in enumerate(frames):
            frame[75:104, 5 + index * 5:25 + index * 5] = 235
        with tempfile.TemporaryDirectory(prefix="motion-test-") as temp:
            clip = Path(temp) / "local-motion.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s",
                            "128x128", "-r", "4", "-i", "-", "-an", "-c:v", "libx264", "-qp", "0",
                            "-pix_fmt", "yuv420p", str(clip)], input=frames.tobytes(), check=True, capture_output=True)
            result = subprocess.run([sys.executable, str(ROOT / "tools" / "motion_qa.py"), str(clip),
                                     "--exclude", "0.3,0.05,0.4,0.3", "--region", "0,0.5,1,0.5",
                                     "--duration", "2", "--sample-fps", "4", "--max-width", "128"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["classification"], "localized_change_detected", report)
            self.assertGreaterEqual(report["active_pairs"], 2)
            self.assertTrue(report["limitations"])

            incomplete = subprocess.run([sys.executable, str(ROOT / "tools" / "motion_qa.py"), str(clip),
                                         "--exclude", "0.3,0.05,0.4,0.3", "--duration", "5"],
                                        capture_output=True, text=True)
            self.assertEqual(incomplete.returncode, 2)
            self.assertIn("video ended before", incomplete.stderr)


if __name__ == "__main__":
    unittest.main()
