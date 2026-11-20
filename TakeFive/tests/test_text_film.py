from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"generation"))
from story_pictures import recipes
from takefive.audio import read_wav, save_wav
from takefive.director import delivery_modes, dialogue_slots
from takefive.story_audio import FRAME, RATE, write_audio


class TextFilmTests(unittest.TestCase):
    def test_receiver_and_face_to_face_dialogue_use_different_guides(self):
        self.assertEqual(delivery_modes("The baker hands over the parcel. The customer asks, "),["onscreen"])
        self.assertIn("radio",delivery_modes("A message crackles on the intercom. It says, "))
        self.assertEqual(delivery_modes("The presenter speaks into the microphone, "),["onscreen"])
        self.assertIn("offscreen",delivery_modes("A woman calls from behind the screen, "))

    def test_repeated_quotes_have_distinct_ordered_places(self):
        story = 'Lena whispers “Ready?” She waits. A light flashes across the harbor. Omar replies "Ready?"'
        quoted = list(re.finditer(r'["“]([^"“”]+)["”]',story))
        slots = dialogue_slots(story,quoted,5)
        self.assertEqual(list(slots.values()),quoted)
        self.assertGreater(max(slots),min(slots))

    def test_crosscut_dialogue_is_audible_and_the_listener_gets_a_dry_guide(self):
        people = [dict(name="Lena",appearance="Black bob and red jacket",voice="Kristin"),
                  dict(name="Omar",appearance="Grey beard and boots",voice="Ryan")]
        sample = np.sin(2*np.pi*300*np.arange(RATE*2)/RATE)*.6
        def shot(person,delivery,mode):
            return dict(seconds=5,line="Wait.",speaker=person,mode=mode,visible=[person],delivery=delivery,
                        cue="none",place="Ferry",camera="medium",opening="The ferry rocks.",action="Looks up.")
        shots = [shot("Lena","across_cut","onscreen"),shot("Omar","after_beat","onscreen"),
                 shot("Lena","early","radio")]
        scene = dict(people=people,places=[dict(name="Ferry",appearance="Steel cabin.")],shots=shots)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            source = out/"raw.wav"
            save_wav(source,sample)
            with patch("takefive.story_audio.speech",return_value=(source,sample,[])):
                timing = write_audio(scene,["a","b","c"],out,out/"cache",7)
            cut = timing["starts"][1]*FRAME
            self.assertLess(timing["speech_samples"][0],cut)
            self.assertGreater(timing["speech_samples"][0]+len(sample),cut+RATE//3)
            self.assertGreater(np.abs(read_wav(out/"mix.wav")[0][cut:cut+RATE//3]).max(),.35)
            self.assertEqual(np.abs(read_wav(out/"b-camera.wav")[0][:RATE//2]).max(),0)
            self.assertEqual(np.abs(read_wav(out/"c-camera.wav")[0]).max(),0)
            stills,motion = recipes(scene,["a","b","c"],timing,7,"Soft daylight.")
            available = set()
            for key,item in stills["shots"].items():
                self.assertTrue(set(item["references"])<=available)
                available.add(key)
            self.assertEqual(stills["shots"]["c"]["references"],["set01","person01"])
            self.assertNotEqual(motion["shots"]["a"]["seed"],motion["shots"]["b"]["seed"])
            self.assertEqual(motion["shots"]["b"]["cast"],["person02"])


if __name__ == "__main__":
    unittest.main()
