import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HF_HOME'] = r'F:\film-pipeline\venvs\hf-cache'
import cv2
import numpy as np
import pickle
import torch
from mmpose.apis import inference_topdown, init_model
from mmpose.structures import merge_data_samples

torch.set_num_threads(6)
root = r'F:\film-pipeline\jobs\anime_pose_experiment'
config = './musetalk/utils/dwpose/rtmpose-l_8xb32-270e_coco-ubody-wholebody-384x288.py'
model = init_model(config, './models/dwpose/dw-ll_ucoco_384.pth', device='cpu')
cap = cv2.VideoCapture(root + r'\source.mp4')
coords, panels, centers, minscores, mouths = [], [], [], [], []
while True:
    ok, frame = cap.read()
    if not ok:
        break
    index = len(coords)
    result = merge_data_samples(inference_topdown(model, frame)).pred_instances
    if len(result.keypoints) != 1:
        raise ValueError(f'Expected one pose for frame {index}')
    pts = result.keypoints[0][23:91]
    scores = result.keypoint_scores[0][23:91]
    if pts.shape != (68, 2) or not np.isfinite(pts).all() or not np.isfinite(scores).all() or min(scores) < 0.5:
        raise ValueError(f'Invalid or weak face landmarks on frame {index}: {min(scores)}')
    pts = pts.astype(np.int32)
    mid = pts[29, 1]
    upper = max(0, mid - (np.max(pts[:,1]) - mid))
    x1, x2 = int(pts[:,0].min()), int(pts[:,0].max())
    y1, y2 = int(upper), int(pts[:,1].max())
    if not (0 <= x1 < x2 <= 512 and 0 <= y1 < y2 <= 512 and x2-x1 >= 80 and y2-y1 >= 80):
        raise ValueError(f'Invalid face bounds on frame {index}: {(x1,y1,x2,y2)}')
    center = pts[48:68].mean(axis=0)
    if centers and np.linalg.norm(center - centers[-1]) > 18:
        raise ValueError(f'Sudden mouth landmark jump on frame {index}')
    centers.append(center)
    mouths.append(pts[48:68])
    minscores.append(float(min(scores)))
    coords.append((x1,y1,x2,y2))
    for pt in pts:
        cv2.circle(frame, tuple(pt), 2, (0,255,0), -1)
    cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,255), 2)
    cv2.putText(frame, str(index), (10,30), cv2.FONT_HERSHEY_SIMPLEX, .8, (0,255,255), 2)
    panels.append(cv2.resize(frame, (256,256)))
    if len(coords) % 20 == 0:
        print('processed', len(coords), flush=True)
cap.release()
if len(coords) != 112:
    raise ValueError(f'Expected 112 complete forward frames, got {len(coords)}')
with open(root + r'\source.pkl', 'wb') as f:
    pickle.dump(coords, f)
with open(root + r'\mouth-centers.pkl', 'wb') as f:
    pickle.dump(centers, f)
with open(root + r'\mouths.pkl', 'wb') as f:
    pickle.dump(mouths, f)
for batch in range(4):
    rows=[]
    for row in range(4):
        offset = batch*28+row*7
        rows.append(np.concatenate(panels[offset:offset+7],axis=1))
    cv2.imwrite(root + f'\\pose-sheet-{batch}.jpg', np.concatenate(rows,axis=0))
print('frames',len(coords),'min score',min(minscores),'max mouth step',max(np.linalg.norm(centers[i]-centers[i-1]) for i in range(1,len(centers))), flush=True)
