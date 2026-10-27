from pathlib import Path
import cv2
import numpy as np
root=Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
a=cv2.VideoCapture(str(root/'full-source.mp4'))
b=cv2.VideoCapture(str(root/'full-scene-viseme-experiment.mp4'))
panels=[]; errors=[]; source=[]
for n in range(112):
    ok1,x=a.read(); ok2,y=b.read()
    if not ok1 or not ok2: raise ValueError(f'missing {n}')
    src=x[500:1100,100:600].astype(np.int16); dst=y[500:1100,100:600].astype(np.int16)
    errors.append(np.abs(src-dst).mean()); source.append(src)
    if n in (0,10,20,30,40,50,60,70,80,90,100,111):
        p=cv2.resize(x[170:420,160:450],(464,400)); q=cv2.resize(y[170:420,160:450],(464,400))
        cv2.putText(p,f'{n} source',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
        cv2.putText(q,f'{n} viseme',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2)
        panels.append(np.concatenate([p,q],axis=1))
for i in range(3):cv2.imwrite(str(root/f'viseme-comparison-{i}.jpg'),np.concatenate(panels[i*4:i*4+4],axis=0))
print('frames',len(errors),'body MAE',np.mean(errors),'source motion first/last MAE',np.abs(source[0]-source[-1]).mean())
