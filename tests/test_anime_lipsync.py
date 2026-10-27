"""CPU-only boundary tests for the experimental mouth compositor."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import anime_lipsync as a


def sample_points():
    # A coherent face and separate eyes/mouth in crop coordinates.
    p=np.tile([250.,250.],(68,1))
    p[0]=[140,240];p[16]=[360,400]
    p[36:48]=[250,220]
    p[48:68]=[250,330]
    p[48]=[220,330];p[54]=[280,330]
    return p


class ValidationTests(unittest.TestCase):
    def test_cues_must_cover_audio_without_gaps_or_unknown_shapes(self):
        valid={'mouthCues':[{'start':0,'end':.5,'value':'A'}, {'start':.5,'end':1,'value':'X'}]}
        cues=a.validate_cues(valid,1.003)
        self.assertEqual(a.cue_at(cues,.25),'A')
        self.assertEqual(a.cue_at(cues,.75),'X')
        for change in ({'start':.6,'end':1,'value':'X'}, {'start':.4,'end':1,'value':'X'},
                       {'start':.5,'end':1,'value':'Q'}):
            with self.subTest(change=change), self.assertRaises(a.AnimationError):
                a.validate_cues({'mouthCues':[valid['mouthCues'][0],change]},1)
        with self.assertRaisesRegex(a.AnimationError,'does not match'):
            a.validate_cues(valid,1.2)

    def test_landmarks_reject_missing_scores_and_jumps(self):
        pts=sample_points();scores=np.ones(68)
        mouth,center=a.validate_landmarks(pts,scores,None,0)
        self.assertEqual(mouth.shape,(20,2))
        with self.assertRaisesRegex(a.AnimationError,'low-confidence'):
            invalid=scores.copy();invalid[55]=.1
            a.validate_landmarks(pts,invalid,None,1)
        with self.assertRaisesRegex(a.AnimationError,'jumped'):
            a.validate_landmarks(pts,scores,center+np.array([30,0]),2)
        with self.assertRaisesRegex(a.AnimationError,'outside'):
            invalid=pts.copy();invalid[55]=[600,330]
            a.validate_landmarks(invalid,scores,None,3)
        with self.assertRaisesRegex(a.AnimationError,'mouth is above'):
            invalid=pts.copy();invalid[48:68,1]=200
            a.validate_landmarks(invalid,scores,None,4)

    def test_crop_requires_valid_square(self):
        self.assertEqual(a.parse_crop('128,24,448,448'),(128,24,448,448))
        for crop in ['1,2,70,90', '-1,2,70,70','1,2,3','x,2,70,70']:
            with self.subTest(crop=crop), self.assertRaises(Exception):a.parse_crop(crop)

    @unittest.skipUnless(cv2 is not None, 'OpenCV is required for artwork tests')
    def test_custom_art_requires_alpha_and_changes_only_the_mouth(self):
        cues=[(0,1,'C')]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with self.assertRaisesRegex(a.AnimationError,'RGBA PNG'):
                a.load_art(p,cues,cv2)
            bad=np.full((64,128,4),255,np.uint8)
            cv2.imwrite(str(p/'C.png'),bad)
            with self.assertRaisesRegex(a.AnimationError,'RGBA PNG'):
                a.load_art(p,cues,cv2)
            good=np.zeros((64,128,4),np.uint8)
            cv2.ellipse(good,(64,32),(40,10),0,0,360,(30,20,100,255),-1)
            cv2.imwrite(str(p/'C.png'),good)
            artwork=a.load_art(p,cues,cv2)
            source=np.full((512,512,3),180,np.uint8)
            result=a.overlay(source.copy(),sample_points()[48:68],(0,0,512,512),'C',artwork,cv2,1.0)
            self.assertTrue(np.any(source != result))
            self.assertTrue(np.array_equal(source[:260],result[:260]))
            self.assertTrue(np.array_equal(source[400:],result[400:]))
            self.assertTrue(np.array_equal(a.overlay(source.copy(),sample_points()[48:68],(0,0,512,512),'X',artwork,cv2,1),source))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe') and
                         (ROOT/'venvs/musetalk/Scripts/python.exe').is_file(), 'local CPU media tools required')
    def test_short_video_preserves_existing_output_and_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); video=p/'scene.mp4'; audio=p/'speech.wav'; out=p/'out.mp4'; cues=p/'cues.json'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc=size=128x128:rate=25:duration=0.5',
                            '-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=1',str(audio)],check=True)
            cues.write_text(json.dumps({'mouthCues':[{'start':0,'end':1,'value':'X'}]}))
            out.write_bytes(b'existing')
            before=[hashlib.sha256(p.read_bytes()).digest() for p in (video,audio)]
            result=subprocess.run([str(ROOT/'venvs/musetalk/Scripts/python.exe'),str(ROOT/'tools/anime_lipsync.py'),
                '--video',str(video),'--audio',str(audio),'--out',str(out),'--face-crop','0,0,128,128',
                '--cues',str(cues),'--demo-shapes','--overwrite'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('shorter than speech',result.stderr)
            self.assertEqual(out.read_bytes(),b'existing')
            self.assertEqual(before,[hashlib.sha256(p.read_bytes()).digest() for p in (video,audio)])


if __name__ == '__main__':unittest.main()
