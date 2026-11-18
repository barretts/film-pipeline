import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/"generation")]
from steering.blocking import directed_poses, get_beats, split_cuts
from steering.guide_bundle import guide_length
from steering.take_inputs import frame_map
from workflows import Graph, motion_graph


class SteeringTests(unittest.TestCase):
    def test_retimed_control_keeps_endpoints_and_padded_tail(self):
        original = frame_map(120,121,0)
        delayed = frame_map(120,121,42)
        self.assertEqual(original,list(range(120))+[119])
        self.assertEqual(delayed[:43],[0]*43)
        self.assertGreater(delayed[43],0)
        self.assertEqual(delayed[-2:],[119,119])
        self.assertEqual(delayed,sorted(delayed))
        with self.assertRaises(ValueError):
            frame_map(120,121,119)

    def test_model_padding_preserves_the_edit_lengths(self):
        self.assertEqual([guide_length(n) for n in (1,120,121,192,240)],[1,121,121,193,241])

    def test_explicit_cuts_ignore_camera_words_in_spoken_lines(self):
        text = 'INT. ROOM\nNia says, "Cut to me. Outside, now." Cut to Ren. He nods. Outside, Ren walks away.'
        beats = split_cuts(text)
        self.assertEqual(len(beats),3)
        self.assertIn('"Cut to me. Outside, now."',beats[0])
        self.assertTrue(beats[2].startswith("Outside,"))

    def test_prose_partition_preserves_every_sentence_and_quote(self):
        text = 'Nia hears a radio. It says, "Stop. Now." She looks up. Ren opens the door.'
        with patch("steering.blocking.ask",return_value={"people":[],"places":[]}):
            _, beats = get_beats(text,3,1,Path("."))
        self.assertEqual(" ".join(beats),text)
        self.assertIn('It says, "Stop. Now."',beats[0])

    def test_explicit_times_and_interior_poses(self):
        cues = directed_poses("at frame 19 she raises her hand and then she points at 2.5 seconds",120)
        self.assertEqual([(k["pose"],k["frame"]) for k in cues],[("raise_hand",19),("point",60)])
        with self.assertRaises(ValueError):
            directed_poses("at frame 120 she nods",120)

    def test_timed_images_are_optional_and_keep_the_full_motion_guide(self):
        for keys in ([],[(49,"pose-a.png",.9),(81,"pose-b.png",.8)]):
            graph = Graph()
            motion_graph(graph,"a walker","",640,384,24,121,"guide.mp4",1.,"silent.wav",9,8,"test",keyframes=keys)
            nodes = list(graph.nodes.values())
            guide = [n["inputs"] for n in nodes if n["class_type"]=="LTXVAddGuide"]
            self.assertEqual([g["frame_idx"] for g in guide],[0]+[k[0] for k in keys])
            self.assertIn("iclora_parameters",guide[0])
            self.assertTrue(all("iclora_parameters" not in g for g in guide[1:]))
            self.assertEqual([n["inputs"]["image"] for n in nodes if n["class_type"]=="LoadImage"],[k[1] for k in keys])
            self.assertFalse(any(n["class_type"]=="LTXVImgToVideoInplace" for n in nodes))
