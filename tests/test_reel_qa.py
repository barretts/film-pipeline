import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from reel_qa import best_audio_match


class ReelAudioMatchTests(unittest.TestCase):
    def test_locates_narration_with_offset_and_music(self):
        random = np.random.default_rng(20261027)
        voice = random.normal(0, 0.1, 16000).astype(np.float32)
        music = random.normal(0, 0.04, 24000).astype(np.float32)
        music[2400:18400] += voice
        result = best_audio_match(music, voice, rate=8000)
        self.assertAlmostEqual(result["offset_seconds"], 0.3, delta=0.001)
        self.assertGreater(result["correlation"], 0.9)

    def test_silence_and_audio_shorter_than_narration_cannot_match(self):
        self.assertIsNone(best_audio_match(np.zeros(100), np.zeros(20)))
        self.assertIsNone(best_audio_match(np.ones(10), np.ones(20)))


if __name__ == "__main__":
    unittest.main()
