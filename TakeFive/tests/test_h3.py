"""Regressions for the local H3 edit grid and per-shot audio and picture controls."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from array import array

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"generation"))
import h3


class H3Tests(unittest.TestCase):
    def setUp(self):
        self.direction = h3.read(ROOT/"generation"/"h3-office.json")
        self.cast = {"employee": {"line": "My question."}, "manager": {"line": "My answer."}}

    def test_frame_grid_covers_both_edit_lengths(self):
        self.assertEqual([h3.model_frames(n) for n in (5, 120, 192, 240)], [5, 124, 192, 243])

    def test_seven_shot_edit_keeps_radio_speech_off_camera(self):
        bundle = ROOT/"films"/"signal-in-the-snow"
        direction = h3.read(ROOT/"generation"/"h3-snow.json")
        with tempfile.TemporaryDirectory() as temp:
            job, plan = h3.prepare(bundle,bundle/"looks",direction,Path(temp),h3.read(ROOT/"generation"/"machine.json"))
            self.assertEqual(list(plan["shots"]),h3.shot_ids(h3.read(bundle/"scene.json")))
            self.assertEqual(sum(s["frames"] for s in plan["shots"].values()),912)
            for name, audible in (("radioWarning",False),("emptyDoorway",False),("warningReturns",True)):
                with wave.open(str(job/"input"/f"voice-{name}.wav"),"rb") as recording:
                    self.assertEqual(recording.getnframes(),plan["shots"][name]["guide_frames"]*2000)
                    self.assertEqual(any(recording.readframes(recording.getnframes())),audible)
            graph = plan["shots"]["warningReturns"]["graph"]
            prompt = next(n["inputs"]["prompt"] for n in graph.values() if n["class_type"]=="MiniMaxH3ReferenceToVideo")
            self.assertIn("James. Don't open the door.",prompt)

    def test_stereo_guide_keeps_channels_and_adds_only_trailing_silence(self):
        with tempfile.TemporaryDirectory() as temp:
            source, out = (Path(temp)/n for n in ("source.wav","out.wav"))
            with wave.open(str(source),"wb") as f:
                f.setparams((2,2,48000,0,"NONE",""))
                f.writeframes(array("h",[1,-2,3,-4]).tobytes())
            h3.voice_stem(source,out,3)
            with wave.open(str(out),"rb") as f:
                self.assertEqual(array("h",f.readframes(3)).tolist(),[1,-2,3,-4,0,0])

    def test_manager_audio_and_photograph_both_reach_the_sampler(self):
        graph, output = h3.graph_for(self.direction, "manager", self.direction["shots"]["manager"], 192, self.cast)
        def node(kind):
            return next(n["inputs"] for n in graph.values() if n["class_type"] == kind)
        def inputs(edge):
            return graph[edge[0]]["inputs"]
        self.assertEqual(graph[output]["class_type"], "SaveVideo")
        ref = node("MiniMaxH3ReferenceToVideo")
        self.assertEqual(ref["length"], 192)
        self.assertIn("My answer.", ref["prompt"])
        self.assertEqual(inputs(ref["ref_images.ref_image_0"])["image"], "cast-manager.png")
        audio = node("LCH3AudioSync")
        self.assertEqual(inputs(audio["audio"])["audio"], "voice-manager.wav")
        self.assertEqual(inputs(inputs(audio["positive"])["image"])["image"], "layout-manager.png")
        sampler = node("SamplerCustomAdvanced")
        self.assertEqual(inputs(sampler["latent_image"]), audio)
        conditioning = inputs(sampler["guider"])["conditioning"]
        self.assertEqual((inputs(conditioning), conditioning[1]), (audio, 3))

    def test_retaking_an_entrance_reuses_the_other_four_performances(self):
        bundle, looks = ROOT/"films"/"office", ROOT/"films"/"dispatch-looks"
        machine = h3.read(ROOT/"generation"/"machine.json")
        with tempfile.TemporaryDirectory() as temp:
            jobs = Path(temp)
            original_job, first = h3.prepare(bundle, looks, self.direction, jobs, machine)
            new_direction = copy.deepcopy(self.direction)
            new_direction["shots"]["arrival"]["seed"] += 1
            changed_job, second = h3.prepare(bundle, looks, new_direction, jobs, machine)
            self.assertNotEqual(original_job, changed_job)
            changed = [name for name in h3.SHOTS if first["shots"][name]["key"] != second["shots"][name]["key"]]
            self.assertEqual(changed, ["arrival"])

    def test_listening_pose_is_chained_into_the_employee_audio_guide(self):
        graph, _ = h3.graph_for(self.direction, "employee", self.direction["shots"]["employee"], 124, self.cast)
        audio = next(n["inputs"] for n in graph.values() if n["class_type"] == "LCH3AudioSync")
        index = audio["positive"][0]
        anchors = []
        while graph[index]["class_type"] == "MiniMaxH3AddGuide":
            anchor = graph[index]["inputs"]
            anchors.append(anchor["frame_idx"])
            self.assertEqual(graph[anchor["image"][0]]["inputs"]["image"], "layout-employee.png")
            index = anchor["positive"][0]
        self.assertEqual(list(reversed(anchors)), self.direction["shots"]["employee"]["photo_frames"])


if __name__ == "__main__":
    unittest.main()
