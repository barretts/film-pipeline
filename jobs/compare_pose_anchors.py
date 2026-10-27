"""CPU-only collection of 68-point landmarks for alignment research."""
import json
import os
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HF_HOME'] = r'F:\film-pipeline\venvs\hf-cache'
import cv2
import numpy as np
import torch
from mmpose.apis import inference_topdown, init_model
from mmpose.structures import merge_data_samples

root = Path(r'F:\film-pipeline')
engine = root/'tools/MuseTalk'
out = root/'jobs/anchor-comparison'
out.mkdir(exist_ok=True)
torch.set_num_threads(6)
model = init_model(str(engine/'musetalk/utils/dwpose/rtmpose-l_8xb32-270e_coco-ubody-wholebody-384x288.py'),str(engine/'models/dwpose/dw-ll_ucoco_384.pth'),device='cpu')
samples = [('anime',root/'jobs/anime_pose_experiment/source.mp4',[0,40,80],None),
           ('mirror',root/'jobs/mirror-track25.mp4',[0,40,80],(128,130,448))]
data=[]
for name,path,frames,crop in samples:
    cap=cv2.VideoCapture(str(path))
    for index in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES,index)
        ok,image=cap.read()
        if not ok: raise RuntimeError(f'Cannot read {name} {index}')
        if crop:
            x,y,size=crop; image=cv2.resize(image[y:y+size,x:x+size],(512,512),interpolation=cv2.INTER_CUBIC)
        results=merge_data_samples(inference_topdown(model,image)).pred_instances
        if len(results.keypoints)!=1: raise RuntimeError('Expected one pose')
        pts=results.keypoints[0][23:91]
        scores=results.keypoint_scores[0][23:91]
        filename=f'{name}-{index}.png'
        cv2.imwrite(str(out/filename),image)
        data.append({'image':filename,'points':pts.tolist(),'scores':scores.tolist()})
    cap.release()
(out/'pose.json').write_text(json.dumps(data),encoding='utf8')
print('wrote',len(data),'samples')
