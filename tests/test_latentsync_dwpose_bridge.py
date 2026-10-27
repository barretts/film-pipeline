import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tools/LatentSync'))
import latentsync_dwpose_bridge as bridge


def sample():
    points=np.full((68,2),[256.,256.])
    points[17:22]=[160.,170.]
    points[22:27]=[350.,175.]
    points[27:36]=[255.,245.]
    return points


class PoseBridgeTests(unittest.TestCase):
    def test_three_anchor_order_and_geometry(self):
        points=sample()
        np.testing.assert_array_equal(bridge.anchors(points),[[160,170],[350,175],[255,245]])
        points[17:22],points[22:27]=points[22:27].copy(),points[17:22].copy()
        np.testing.assert_array_equal(bridge.anchors(points),[[160,170],[350,175],[255,245]])
        for bad in (np.full((68,2),np.nan), np.full((67,2),200.), np.full((68,2),200.),np.full((68,2),600.)):
            with self.assertRaises(bridge.PoseAlignmentError): bridge.anchors(bad)

    @unittest.skipUnless((ROOT/'jobs/anchor-comparison/pose.json').is_file(), 'local CPU landmark fixture required')
    def test_installed_bridge_uses_native_cpu_warp_and_exact_frame_count(self):
        os.environ['CUDA_VISIBLE_DEVICES']=''
        os.environ['HF_HOME']=str(ROOT/'venvs/hf-cache')
        import cv2
        import torch
        from latentsync.utils.affine_transform import AlignRestore
        from latentsync.utils.image_processor import ImageProcessor
        fixture=json.loads((ROOT/'jobs/anchor-comparison/pose.json').read_text(encoding='utf8'))[0]
        image=cv2.imread(str(ROOT/'jobs/anchor-comparison'/fixture['image']))
        state=bridge.install([fixture['points']])
        with patch('latentsync.utils.image_processor.AlignRestore'):
            initialized=ImageProcessor(resolution=256,device='cuda',mask_image=torch.zeros((3,256,256)))
            self.assertIsNotNone(initialized.face_detector)
        with self.assertRaises(bridge.PoseAlignmentError): bridge.assert_complete(state)
        processor=ImageProcessor.__new__(ImageProcessor)
        processor.resolution=256
        processor.restorer=AlignRestore(resolution=256,device='cpu',dtype=torch.float32)
        face,box,matrix=processor.affine_transform(image)
        self.assertEqual(tuple(face.shape),(3,256,256))
        self.assertEqual(len(box),4)
        self.assertEqual(tuple(matrix.shape),(1,2,3))
        bridge.assert_complete(state)
        with self.assertRaises(bridge.PoseAlignmentError): processor.affine_transform(image)

    @unittest.skipUnless((ROOT/'jobs/anchor-comparison/pose.json').is_file(), 'local CPU landmark fixture required')
    def test_worker_dispatches_to_patched_processor_on_cpu(self):
        os.environ['CUDA_VISIBLE_DEVICES']=''
        os.environ['HF_HOME']=str(ROOT/'venvs/hf-cache')
        import cv2
        import torch
        from latentsync.utils.affine_transform import AlignRestore
        from latentsync.utils.image_processor import ImageProcessor
        fixture=json.loads((ROOT/'jobs/anchor-comparison/pose.json').read_text(encoding='utf8'))[0]
        image=cv2.imread(str(ROOT/'jobs/anchor-comparison'/fixture['image']))
        with tempfile.TemporaryDirectory(dir=ROOT/'jobs') as tmp:
            pose=Path(tmp)/'pose.json'; pose.write_text(json.dumps([fixture['points']]),encoding='utf8')
            def simulate_inference(module,run_name):
                self.assertEqual(module,'scripts.inference')
                self.assertEqual(sys.argv[1:],['--video_path','fake.mp4'])
                obj=ImageProcessor.__new__(ImageProcessor)
                obj.resolution=256
                obj.restorer=AlignRestore(resolution=256,device='cpu',dtype=torch.float32)
                face,_,_=obj.affine_transform(image)
                self.assertEqual(tuple(face.shape),(3,256,256))
            with patch.object(sys,'argv',['worker','--pose-frames',str(pose),'--video_path','fake.mp4']), patch.object(runpy,'run_module',side_effect=simulate_inference):
                runpy.run_path(str(ROOT/'tools/latentsync_dwpose_worker.py'),run_name='__main__')


if __name__=='__main__':
    unittest.main()
