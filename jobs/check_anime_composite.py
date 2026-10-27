from pathlib import Path
import cv2
import numpy as np
root=Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
a=cv2.VideoCapture(str(root/'full-source.mp4'))
b=cv2.VideoCapture(str(root/'full-scene-speaking.mp4'))
panels=[]
outside=[]
inside=[]
for n in range(112):
    ok1,x=a.read(); ok2,y=b.read()
    if not ok1 or not ok2: raise RuntimeError(f'Missing frame {n}')
    diff=np.abs(x.astype(np.int16)-y.astype(np.int16))
    inside.append(float(diff[230:410,210:440].mean()))
    outside.append(float(diff[500:1100,100:600].mean()))
    if n in (0,10,20,30,40,50,60,70,80,90,100,111):
        src=cv2.resize(x[170:420,160:450],(464,400))
        dst=cv2.resize(y[170:420,160:450],(464,400))
        cv2.putText(src, f'{n} source', (8,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
        cv2.putText(dst, f'{n} speaking', (8,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
        panels.append(np.concatenate([src,dst],axis=1))
for i in range(3): cv2.imwrite(str(root/f'comparison-{i}.jpg'),np.concatenate(panels[i*4:i*4+4],axis=0))
print('frames',len(outside),'mean absolute color difference inside face region',np.mean(inside),'outside face region',np.mean(outside))
