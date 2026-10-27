import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import latentsync_lipsync as tool


class LatentSyncTests(unittest.TestCase):
    def test_chunks_cover_every_frame_once(self):
        self.assertEqual(tool.chunks(302, 150), [(0, 101), (101, 202), (202, 302)])
        with self.assertRaises(tool.LatentSyncError):
            tool.chunks(1, 0)

    def test_blend_preserves_pixels_outside_mouth_and_rejects_bad_track(self):
        frame = np.zeros((600, 600, 3), dtype=np.uint8)
        generated = np.full((512, 512, 3), 255, dtype=np.uint8)
        mouth = np.tile([256., 300.], (20, 1))
        out = tool.blend(frame, generated, mouth, (50, 50, 448, 448), cv2)
        self.assertGreater(int(out[312, 274, 0]), 200)
        self.assertEqual(int(out[550, 550, 0]), 0)
        self.assertEqual(int(out[100, 100, 0]), 0)
        with self.assertRaises(tool.LatentSyncError):
            tool.blend(frame, generated, np.tile([0., 0.], (20, 1)), (50, 50, 448, 448), cv2)

    @unittest.skipUnless(tool.PYTHON.is_file() and (tool.ENGINE / 'checkpoints/latentsync_unet.pt').is_file(), 'local LatentSync installation required')
    def test_private_engine_directory_imports_on_cpu(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'jobs') as tmp:
            work = Path(tmp)
            tool.setup_engine(work)
            self.assertTrue((work/'checkpoints/whisper/tiny.pt').is_file())
            self.assertTrue((work/'checkpoints/auxiliary/models/buffalo_l/det_10g.onnx').is_file())
            env = os.environ.copy()
            env.update({'CUDA_VISIBLE_DEVICES':'', 'HF_HOME':str(ROOT/'venvs/hf-cache'), 'HF_HUB_OFFLINE':'1',
                        'NO_ALBUMENTATIONS_UPDATE':'1', 'PYTHONPATH':str(tool.ENGINE)})
            env.pop('TRANSFORMERS_CACHE',None)
            result = subprocess.run([str(tool.PYTHON),'-m','scripts.inference','--help'],cwd=work,env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('--inference_ckpt_path',result.stdout)
        with tempfile.TemporaryDirectory(dir=ROOT / 'jobs') as tmp:
            work=Path(tmp)
            tool.setup_engine(work, use_insightface=False)
            self.assertTrue((work/'checkpoints/whisper/tiny.pt').is_file())
            self.assertFalse((work/'checkpoints/auxiliary/models/buffalo_l').exists())

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
    def test_multi_chunk_timing_and_output_guards_without_gpu(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'jobs') as tmp:
            p = Path(tmp); video = p/'video.mp4'; audio = p/'voice.wav'; out = p/'out.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc=size=128x128:rate=25:duration=2.2','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=2.135','-ar','16000',str(audio)],check=True)
            crop = (0, 0, 128, 128)
            mouths = [np.tile([256., 280.], (20, 1)) for _ in range(54)]
            real_call = tool.call
            spans = []; pose_lengths=[]
            def fake_call(command, **kwargs):
                if len(command) > 2 and (command[1:3] == ['-m','scripts.inference'] or str(command[1]).endswith('latentsync_dwpose_worker.py')):
                    source = Path(command[command.index('--video_path') + 1])
                    output = Path(command[command.index('--video_out_path') + 1])
                    if '--pose-frames' in command:
                        poses=json.loads(Path(command[command.index('--pose-frames') + 1]).read_text(encoding='utf8'))
                        pose_lengths.append(len(poses))
                    spans.append(source.name)
                    shutil.copyfile(source, output)
                    return None
                return real_call(command, **kwargs)
            with patch.object(tool,'setup_engine'), patch.object(tool.tracker,'track',return_value=mouths), patch.object(tool,'call',side_effect=fake_call):
                self.assertEqual(tool.main(['--video',str(video),'--audio',str(audio),'--out',str(out),'--face-crop','0,0,128,128','--research-only','--chunk-seconds','1']),0)
            self.assertEqual(len(spans),3)
            info = tool.tracker.probe(out)
            v = next(s for s in info['streams'] if s['codec_type']=='video')
            self.assertEqual(int(v['nb_frames']),54)
            self.assertEqual(v['avg_frame_rate'],'25/1')
            a = next(s for s in info['streams'] if s['codec_type']=='audio')
            self.assertGreaterEqual(float(a['duration']),2.13)
            out_pose=p/'out-pose.mp4'
            face=np.zeros((68,2),dtype=float)+[250.,250.]
            faces=[face.copy() for _ in range(54)]
            with patch.object(tool,'setup_engine') as setup, patch.object(tool.tracker,'track',return_value=(mouths,faces)), patch.object(tool,'call',side_effect=fake_call):
                self.assertEqual(tool.main(['--video',str(video),'--audio',str(audio),'--out',str(out_pose),'--face-crop','0,0,128,128','--detector','dwpose','--chunk-seconds','1']),0)
                setup.assert_called_once()
                self.assertFalse(setup.call_args.kwargs['use_insightface'])
            self.assertEqual(pose_lengths,[18,18,18])
            existing = out.read_bytes()
            self.assertEqual(tool.main(['--video',str(video),'--audio',str(audio),'--out',str(out),'--face-crop','0,0,128,128']),1)
            self.assertEqual(existing,out.read_bytes())
            self.assertEqual(tool.main(['--video',str(video),'--audio',str(audio),'--out',str(out),'--face-crop','0,0,128,128','--research-only']),1)
            self.assertEqual(existing,out.read_bytes())
            long_audio = p/'too-long.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=3','-ar','16000',str(long_audio)],check=True)
            with patch.object(tool,'setup_engine'), patch.object(tool.tracker,'track') as track:
                self.assertEqual(tool.main(['--video',str(video),'--audio',str(long_audio),'--out',str(out),'--face-crop','0,0,128,128','--research-only','--overwrite']),1)
                track.assert_not_called()
            self.assertEqual(existing,out.read_bytes())


if __name__ == '__main__':
    unittest.main()
