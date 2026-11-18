"""Regressions for dialogue crossing a cut and for editing a single take."""
import copy
import unittest

from takefive.audio import RATE, timeline
from takefive.comfy import graph
from takefive.production import shot_key
from takefive.script import FPS, SHOTS


def scene():
    return {
        "bridge": .95, "reply_beat": .55, "exit_crossing": .75, "door": "blue",
        "cast": {"employee": {"coat": "rust"}, "manager": {"coat": "teal"}},
        "shots": [{"id": name, "seconds": seconds, "lens": 40}
                  for name, seconds in zip(SHOTS, (5, 5, 8, 5, 5))]
    }


def voices(visitor_seconds, manager_seconds):
    return {role: (None, range(round(RATE * duration)), [{"start": 0, "end": duration, "value": "C"}])
            for role, duration in (("employee", visitor_seconds), ("manager", manager_seconds))}


class ContinuityTests(unittest.TestCase):
    def test_question_finishes_on_reverse_and_reply_waits(self):
        plan = scene()
        audio = voices(3.3, 2.1)
        t = timeline(plan, audio)
        cut_sample = t["starts"][2] * RATE // FPS
        question_end = t["speech_samples"]["employee"] + len(audio["employee"][1])
        self.assertEqual(question_end - cut_sample, round(.95 * RATE))
        self.assertEqual(t["speech_samples"]["manager"] - question_end, round(.55 * RATE))
        self.assertEqual(t["frames"], 28 * FPS)

    def test_long_dialogue_expands_both_closeups(self):
        plan = scene()
        audio = voices(12.25, 16.5)
        t = timeline(plan, audio)
        manager_end = t["speech_samples"]["manager"] + len(audio["manager"][1])
        self.assertGreater(t["lengths"][1], 5 * FPS)
        self.assertGreater(t["lengths"][2], 8 * FPS)
        self.assertGreaterEqual(t["speech_samples"]["employee"], t["starts"][1] * RATE // FPS)
        self.assertLess(manager_end, t["starts"][3] * RATE // FPS)

    def test_changed_manager_viseme_invalidates_only_her_closeup(self):
        plan = scene()
        audio = voices(3, 2)
        t = timeline(plan, audio)
        revised = copy.deepcopy(audio)
        revised["manager"][2][0]["value"] = "F"
        def keys(speech):
            return [shot_key(i, plan, t, speech, 1280, "test-renderer") for i in range(len(SHOTS))]
        changed = [name for name, old, new in zip(SHOTS, keys(audio), keys(revised)) if old != new]
        self.assertEqual(changed, ["manager"])

    def test_comfy_graph_retains_layout_and_both_cast_references(self):
        refs = ["layout.png", "employee.png", "manager.png"]
        nodes, last = graph(refs, "Painted daylight", 21, 768, ("model", "encoder", "vae"))
        self.assertEqual(nodes[last]["class_type"], "SaveImage")
        guider = next(n["inputs"] for n in nodes.values() if n["class_type"] == "CFGGuider")
        for key in ("positive", "negative"):
            current = nodes[guider[key][0]]
            used = []
            while current["class_type"] == "ReferenceLatent":
                latent = nodes[current["inputs"]["latent"][0]]
                source = nodes[latent["inputs"]["pixels"][0]]
                used.append(source["inputs"]["image"])
                current = nodes[current["inputs"]["conditioning"][0]]
            self.assertEqual(used[::-1], refs)


if __name__ == "__main__":
    unittest.main()
