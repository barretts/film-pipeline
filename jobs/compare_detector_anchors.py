"""CPU-only DWPose versus InsightFace anchor comparison for research."""
import json
from pathlib import Path
import cv2
import numpy as np
from insightface.app import FaceAnalysis

root=Path(r'F:\film-pipeline')
engine=root/'tools/LatentSync'
folder=root/'jobs/anchor-comparison'
data=json.loads((folder/'pose.json').read_text(encoding='utf8'))
app=FaceAnalysis(allowed_modules=['detection','landmark_2d_106'],root=str(engine/'checkpoints/auxiliary'),providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1,det_size=(512,512))
panels=[]; report=[]
for item in data:
    image=cv2.imread(str(folder/item['image']))
    faces=app.get(image)
    if len(faces)!=1:
        report.append({'image':item['image'],'error':f'{len(faces)} detected'})
        continue
    p=np.array(item['points']); q=faces[0].landmark_2d_106
    base=np.array([np.mean(q[[43,48,49,51,50]],axis=0),np.mean(q[101:106],axis=0),np.mean(q[[74,77,83,86]],axis=0)])
    brows=[np.mean(p[17:22],axis=0),np.mean(p[22:27],axis=0)]
    brows.sort(key=lambda x:x[0])
    for indices in ([27,28,29,30,31,32,33,34,35],[29,30,31,32,33,34,35],[30,31,32,33,34,35],[30,33]):
        mapped=np.array([*brows,np.mean(p[indices],axis=0)])
        dist=np.linalg.norm(mapped-base,axis=1)
        report.append({'image':item['image'],'nose_indices':indices,'base':base.tolist(),'mapped':mapped.tolist(),'distance_px':dist.tolist()})
    mapped=np.array([*brows,np.mean(p[[30,31,32,33,34,35]],axis=0)])
    for i,(a,b) in enumerate(zip(base,mapped)):
        cv2.circle(image,tuple(np.round(a).astype(int)),5,(0,0,255),-1)
        cv2.circle(image,tuple(np.round(b).astype(int)),4,(0,255,0),-1)
        cv2.line(image,tuple(np.round(a).astype(int)),tuple(np.round(b).astype(int)),(255,255,255),1)
    cv2.putText(image,item['image'],(10,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2)
    panels.append(image)
(folder/'anchors.json').write_text(json.dumps(report,indent=2),encoding='utf8')
if panels: cv2.imwrite(str(folder/'anchors.jpg'),np.concatenate(panels,axis=1))
print('samples compared',len(panels),'of',len(data),'red=InsightFace green=DWPose')
