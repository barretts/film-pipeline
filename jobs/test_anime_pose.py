import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import cv2
import numpy as np
import torch
from mmpose.apis import inference_topdown, init_model
from mmpose.structures import merge_data_samples

torch.set_num_threads(6)
config = './musetalk/utils/dwpose/rtmpose-l_8xb32-270e_coco-ubody-wholebody-384x288.py'
model = init_model(config, './models/dwpose/dw-ll_ucoco_384.pth', device='cpu')
cap = cv2.VideoCapture(r'F:\film-pipeline\video\full_motion\anime-quality.mp4')
frames = []
while True:
    ok, frame = cap.read()
    if not ok:
        break
    frames.append(frame)
cap.release()
panels=[]
for index in [0, 16, 32, 48, 64, 72]:
    crop = cv2.resize(frames[index][24:472, 128:576], (512,512), interpolation=cv2.INTER_CUBIC)
    results = merge_data_samples(inference_topdown(model, crop)).pred_instances
    pts = results.keypoints[0][23:91]
    scores = results.keypoint_scores[0][23:91]
    print(index, 'score min/median/max', np.min(scores), np.median(scores), np.max(scores), 'bounds', np.min(pts, axis=0), np.max(pts, axis=0), flush=True)
    for i, p in enumerate(pts):
        p=tuple(np.round(p).astype(int))
        cv2.circle(crop, p, 2, (0,255,0) if scores[i]>=0.3 else (0,0,255), -1)
        if i in (29, 48, 54, 62, 66):
            cv2.putText(crop, str(i), p, cv2.FONT_HERSHEY_SIMPLEX, .45, (0,255,255), 1)
    cv2.putText(crop, str(index), (10,30), cv2.FONT_HERSHEY_SIMPLEX, .8, (0,255,255), 2)
    panels.append(crop)
cv2.imwrite(r'F:\film-pipeline\logs\anime-pose-landmarks.jpg', np.concatenate(panels, axis=1))
