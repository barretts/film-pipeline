import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import sys
import time
import cv2
import numpy as np
import torch
sys.path.insert(0, r'F:\film-pipeline\tools\MuseTalk\musetalk\utils')
from face_detection import FaceAlignment, LandmarksType

torch.set_num_threads(6)
fa = FaceAlignment(LandmarksType._2D, flip_input=False, device='cpu')
cap = cv2.VideoCapture(r'F:\film-pipeline\video\full_motion\anime-quality.mp4')
frames = []
while True:
    ok, frame = cap.read()
    if not ok:
        break
    frames.append(frame)
cap.release()
print('decoded', len(frames), flush=True)
candidates = [(128, 24, 448, 512), (128, 24, 448, 768), (160, 80, 384, 512), (160, 80, 384, 768)]
for x, y, size, scale in candidates:
    start = time.time()
    hits = []
    for index in [0, 16, 32, 48, 64, 72]:
        crop = frames[index][y:y+size, x:x+size]
        crop = cv2.resize(crop, (scale, scale), interpolation=cv2.INTER_CUBIC)
        hits.append(fa.get_detections_for_batch(np.asarray([crop]))[0])
    print('candidate', (x, y, size, scale), 'hits', hits, 'seconds', round(time.time()-start, 1), flush=True)
