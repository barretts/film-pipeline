"""Experimental child-process entry point for DWPose-aligned LatentSync."""
import argparse
import json
import runpy
import sys
from pathlib import Path

import latentsync_dwpose_bridge as bridge

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pose-frames', type=Path, required=True)
args, remaining = parser.parse_known_args()
frames = json.loads(args.pose_frames.read_text(encoding='utf8'))
if not isinstance(frames, list):
    raise bridge.PoseAlignmentError('Pose-frame file must be a JSON list')
state = bridge.install(frames)
sys.argv = ['scripts.inference', *remaining]
runpy.run_module('scripts.inference', run_name='__main__')
bridge.assert_complete(state)
print(f'DWPose bridge consumed {state["total"]} tracked frames', flush=True)
