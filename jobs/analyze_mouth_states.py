from pathlib import Path
import pickle
import cv2
import numpy as np
root=Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
with (root/'mouth-centers.pkl').open('rb') as f: centers=pickle.load(f)
a=cv2.VideoCapture(str(root/'source.mp4'))
b=cv2.VideoCapture(str(root/'result/v15/talking-crop.mp4'))
panels=[]; metrics=[]
for n,c in enumerate(centers):
    ok,x=a.read(); ok2,y=b.read()
    if not ok or not ok2: raise ValueError(f'missing {n}')
    cx,cy=np.round(c).astype(int)
    u=x[cy-20:cy+21,cx-36:cx+37]; v=y[cy-20:cy+21,cx-36:cx+37]
    if u.shape != (41,73,3) or v.shape != (41,73,3): raise ValueError('mouth bounds')
    lum0=cv2.cvtColor(u,cv2.COLOR_BGR2GRAY).astype(float)
    lum1=cv2.cvtColor(v,cv2.COLOR_BGR2GRAY).astype(float)
    mask=np.zeros((41,73),np.uint8);cv2.ellipse(mask,(36,20),(28,13),0,0,360,1,-1)
    delta=(lum0-lum1)[mask!=0]
    score=np.mean(np.clip((delta-8)/35,0,1))
    metrics.append(score)
    pair=np.concatenate([u,v],axis=0)
    panel=cv2.resize(pair,(146,164),interpolation=cv2.INTER_NEAREST)
    cv2.putText(panel,f'{n} {score:.2f}',(2,14),cv2.FONT_HERSHEY_SIMPLEX,.42,(0,255,255),1)
    panels.append(panel)
for i in range(4):
    rows=[np.concatenate(panels[i*28+r*7:i*28+(r+1)*7],axis=1) for r in range(4)]
    cv2.imwrite(str(root/f'mouth-states-{i}.jpg'),np.concatenate(rows,axis=0))
print('min',min(metrics),'max',max(metrics),'per 5 frames:',[(i,round(metrics[i],3)) for i in range(0,len(metrics),5)])
np.save(root/'mouth-scores.npy',np.array(metrics))
