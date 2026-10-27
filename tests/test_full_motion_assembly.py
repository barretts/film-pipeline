import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location("full_motion_build", ROOT / "reels/full_motion/build.py")
assembly = importlib.util.module_from_spec(loader)
loader.loader.exec_module(assembly)


class FullMotionAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / "logs")
        cls.path = Path(cls.temp.name)
        cls.voice = cls.path / "voice.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=4",
                        "-c:a", "pcm_s16le", str(cls.voice)], check=True)
        for name, visual, sound, seconds in [
            ("moving", "testsrc2=size=180x320:rate=16", "330", "4"),
            ("static", "color=c=blue:size=180x320:rate=16", "330", "4"),
            ("short", "testsrc2=size=180x320:rate=16", "330", "2"),
            ("wrong-audio", "testsrc2=size=180x320:rate=16", "440", "4"),
        ]:
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", visual, "-f", "lavfi", "-i",
                            f"sine=frequency={sound}:duration={seconds}", "-t", seconds,
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.path / f"{name}.mp4")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=16",
                        "-f", "lavfi", "-i", "sine=frequency=330:duration=1", "-t", "4", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.path / "short-audio.mp4")], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_rejects_short_mismatched_and_static_video(self):
        for name, reason in [("short", "shorter"), ("short-audio", "audio is shorter"),
                             ("wrong-audio", "does not match"), ("static", "motion")]:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, reason):
                assembly.validate(self.path / f"{name}.mp4", self.voice, [0, 0, .2, .2])

    def test_accepts_moving_video_with_matching_voice(self):
        seconds, correlation, reports = assembly.validate(self.path / "moving.mp4", self.voice, [0, 0, .2, .2])
        self.assertAlmostEqual(seconds, 4, places=2)
        self.assertGreater(correlation, .9)
        self.assertEqual(len(reports), 2)

    def test_refuses_overwriting_existing_project(self):
        with self.assertRaises(FileExistsError):
            assembly.build({}, self.path / "moving.mp4", self.voice, self.voice, self.path, [0, 0, .2, .2])


if __name__ == "__main__":
    unittest.main()
