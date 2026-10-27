"""One-shot experiment for the verified 112-frame anime test, not a pipeline API."""
from pathlib import Path
import pickle
import subprocess
import cv2
import numpy as np

root = Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
out = root / 'full-scene-speaking.mp4'
full = cv2.VideoCapture(str(root / 'full-source.mp4'))
talk = cv2.VideoCapture(str(root / 'result' / 'v15' / 'talking-crop.mp4'))
with (root / 'mouth-centers.pkl').open('rb') as f:
    centers = pickle.load(f)
if len(centers) != 112 or int(full.get(cv2.CAP_PROP_FRAME_COUNT)) != 112 or int(talk.get(cv2.CAP_PROP_FRAME_COUNT)) != 112:
    raise RuntimeError('Unexpected frame count: do not loop or guess alignment')
command = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '704x1280', '-r', '25', '-i', 'pipe:0', '-i', str(root / 'voice.wav'), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', str(out)]
proc = subprocess.Popen(command, stdin=subprocess.PIPE)
for index, center in enumerate(centers):
    ok_a, a = full.read()
    ok_b, b = talk.read()
    if not ok_a or not ok_b or a.shape != (1280,704,3) or b.shape != (512,512,3):
        proc.stdin.close()
        proc.wait()
        raise RuntimeError(f'Invalid image stream at frame {index}')
    patch = cv2.resize(b, (448,448), interpolation=cv2.INTER_AREA)
    center = np.asarray(center) * 448 / 512
    mask = np.zeros((448,448), dtype=np.float32)
    cv2.ellipse(mask, tuple(np.round(center).astype(int)), (35, 22), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (31,31), 8)[:,:,None]
    roi = a[24:472,128:576].astype(np.float32)
    a[24:472,128:576] = np.clip(patch.astype(np.float32)*mask + roi*(1-mask),0,255).astype(np.uint8)
    proc.stdin.write(a.tobytes())
proc.stdin.close()
if proc.wait() != 0:
    raise RuntimeError('Encoding failed')
full.release()
talk.release()
print(out)
