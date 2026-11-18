"""Continuity constraints unique to the generative video workflow."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave
from array import array

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"generation"))
from prepare import voice_stem
from realistic import accept, saved
from takefive.finishing import normalize
from takefive.production import ffmpeg
from takefive.script import binary
from workflows import build_graph


class GenerationTests(unittest.TestCase):
    def setUp(self):
        cfg=json.loads((ROOT/"generation"/"office.json").read_text())
        cast={"employee":{"coat":"rust"},"manager":{"coat":"teal"}}
        self.plan={"fps":24,"direction":cfg,"cast":cast,"door":"blue",
                   "shots":{s:{"guide_frames":193 if s=="manager" else 121,"performance":"Test line."} for s in cfg["shots"]}}

    def test_camera_audio_frozen_alongside_motion_guide(self):
        g,_=build_graph(self.plan,"manager",{"manager"})
        def node(kind):
            return next(item["inputs"] for item in g.values() if item["class_type"]==kind)
        self.assertEqual(node("LoadAudio")["audio"],"voice-manager.wav")
        self.assertEqual(node("LoadVideo")["file"],"edges-manager.mp4")
        self.assertEqual(node("EmptyLTXVLatentVideo")["length"],193)
        joint=node("LTXVConcatAVLatent")
        frozen=g[joint["audio_latent"][0]]
        self.assertEqual(frozen["class_type"],"SetLatentNoiseMask")
        self.assertEqual(g[frozen["inputs"]["mask"][0]]["inputs"]["value"],0.)
        self.assertEqual(g[joint["video_latent"][0]]["class_type"],"LTXVAddGuide")
        self.assertEqual(node("LoadImage")["image"],"look-manager.png")
        self.assertFalse(any(v["class_type"]=="UNETLoader" for v in g.values()))

    def test_wide_uses_both_recurring_people_and_same_interior(self):
        g,outputs=build_graph(self.plan,"departure",{"employee","manager","arrival"},only_look=True)
        images=[n["inputs"]["image"] for n in g.values() if n["class_type"]=="LoadImage"]
        self.assertEqual(images,["layout-departure.png","look-employee.png","look-manager.png","look-arrival.png"])
        self.assertEqual(list(outputs.values()),[("look","departure")])
        crops = [n["inputs"] for n in g.values() if n["class_type"] == "ImageCrop"]
        self.assertEqual([g[c["image"][0]]["inputs"]["image"] for c in crops], images[1:])
        self.assertTrue(all(c["width"] < self.plan["direction"]["look_width"] / 2 for c in crops))

    def test_exterior_gets_one_actor_and_an_exterior_layout(self):
        g, _ = build_graph(self.plan, "street", {"employee", "arrival"}, only_look=True)
        images = [n["inputs"]["image"] for n in g.values() if n["class_type"] == "LoadImage"]
        self.assertEqual(images, ["layout-street.png", "look-employee.png"])

    def test_voice_track_preserves_pause_and_exact_samples_on_both_channels(self):
        with tempfile.TemporaryDirectory() as temp:
            src,dest=(Path(temp)/n for n in ("in.wav","out.wav"))
            with wave.open(str(src),"wb") as w:
                w.setparams((1,2,48000,0,"NONE",""))
                w.writeframes(array("h",[0,0,2,-100,0]).tobytes())
            voice_stem(src,dest,8)
            with wave.open(str(dest),"rb") as w:
                self.assertEqual((w.getframerate(),w.getnchannels(),w.getnframes()),(48000,2,8))
                a=array("h")
                a.frombytes(w.readframes(8))
            self.assertEqual(a[::2].tolist(),[0,0,2,-100,0,0,0,0])
            self.assertEqual(a[1::2],a[::2])

    def test_completed_picture_is_saved_and_can_be_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            movie = root / "engine-take.mp4"
            ffmpeg("-f", "lavfi", "-i", "color=black:s=64x64:r=24", "-frames:v", "9",
                   "-an", "-c:v", "libx264", "-threads", "1", movie)
            self.plan["direction"].update(camera_width=64, camera_height=64)
            self.plan["shots"]["manager"].update(frames=8, guide_frames=9)
            take = accept(movie, root, "picture", "manager", self.plan)
            self.assertEqual(take, root / "accepted" / "picture" / "manager.mp4")
            self.assertEqual(take.read_bytes(), movie.read_bytes())
            self.assertEqual(saved(root, "picture", "manager"), take)

    def test_edit_framing_selects_the_requested_part_of_the_take(self):
        with tempfile.TemporaryDirectory() as folder:
            source, cut = (Path(folder) / name for name in ("source.mp4", "cut.mp4"))
            ffmpeg("-f", "lavfi", "-i", "color=red:s=128x72:r=24",
                   "-vf", "drawbox=x=64:y=0:w=64:h=72:color=blue:t=fill",
                   "-frames:v", "4", "-c:v", "libx264", "-threads", "1", source)
            normalize(source, cut, 128, 4, [0.5, 0, 0.5, 1])
            pixel = subprocess.check_output([binary("ffmpeg"), "-v", "error", "-i", str(cut),
                                            "-vf", "scale=1:1", "-frames:v", "1", "-pix_fmt",
                                            "rgb24", "-f", "rawvideo", "-"])
            self.assertLess(pixel[0], 15)
            self.assertGreater(pixel[2], 240)

    def test_locked_background_preserves_motion_only_inside_the_outline(self):
        with tempfile.TemporaryDirectory() as folder:
            source, cut = (Path(folder) / name for name in ("source.mp4", "cut.mp4"))
            ffmpeg("-f", "lavfi", "-i", "color=red:s=128x72:r=24",
                   "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=blue:t=fill:enable='gte(n,1)'",
                   "-frames:v", "4", "-c:v", "libx264", "-threads", "1", source)
            normalize(source, cut, 128, 4, {"moving_region": [[0,0],[.5,0],[.5,1],[0,1]]})
            pixels = subprocess.check_output([binary("ffmpeg"), "-v", "error", "-i", str(cut),
                                             "-vf", r"select=eq(n\,3)", "-frames:v", "1",
                                             "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
            left, right = ((36*128+x)*3 for x in (20,106))
            self.assertGreater(pixels[left+2], 235)
            self.assertLess(pixels[left], 20)
            self.assertGreater(pixels[right], 235)
            self.assertLess(pixels[right+2], 20)

    def test_reaction_lead_preserves_the_spoken_frames_and_edit_length(self):
        with tempfile.TemporaryDirectory() as folder:
            source, cut = (Path(folder)/name for name in ("raw.mp4","cut.mp4"))
            ffmpeg("-f","lavfi","-i","nullsrc=s=64x64:r=24","-vf","geq=lum='16+12*N':cb=128:cr=128",
                   "-frames:v","16","-c:v","libx264","-threads","1",source)
            normalize(source, cut, 64, 12, {"reaction_lead":{"source_frame":8,"resume_frame":4,"blend_frames":2}})
            def levels(p):
                return subprocess.check_output([binary("ffmpeg"),"-v","error","-i",str(p),"-vf","scale=1:1",
                                                "-pix_fmt","gray","-f","rawvideo","-"])
            original, edited = levels(source), levels(cut)
            self.assertEqual(len(edited), 12)
            for i in range(4):
                self.assertAlmostEqual(edited[i], original[8+i], delta=3)
            for i in range(6,12):
                self.assertAlmostEqual(edited[i], original[i], delta=3)
