"""CPU comparison of LatentSync's native affine warp using two landmark sets."""
import json
from pathlib import Path
import sys
import cv2
import numpy as np
import torch

root=Path(r'F:\film-pipeline')
sys.path.insert(0,str(root/'tools'))
sys.path.insert(0,str(root/'tools/LatentSync'))
from latentsync_dwpose_bridge import anchors
from latentsync.utils.affine_transform import AlignRestore
folder=root/'jobs/anchor-comparison'
poses=json.loads((folder/'pose.json').read_text(encoding='utf8'))
records=json.loads((folder/'anchors.json').read_text(encoding='utf8'))
panels=[]; distances=[]
for item in poses:
    matching=next(r for r in records if r.get('image')==item['image'] and r.get('nose_indices')==list(range(27,36)))
    image=cv2.imread(str(folder/item['image']))
    original=np.round(np.asarray(matching['base'])).astype(np.float32)
    alternative=anchors(item['points'])
    a=AlignRestore(resolution=256,device='cpu',dtype=torch.float32)
    b=AlignRestore(resolution=256,device='cpu',dtype=torch.float32)
    warp1,m1=a.align_warp_face(image,original,smooth=True)
    warp2,m2=b.align_warp_face(image,alternative,smooth=True)
    warp1=np.ascontiguousarray(warp1); warp2=np.ascontiguousarray(warp2)
    # Compare the same landmarks after each warp in native affine coordinates.
    selected=np.asarray(item['points'])[[27,30,33,48,54,57]]
    h=np.column_stack((selected,np.ones(len(selected))))
    pa=h@m1[0].numpy().T; pb=h@m2[0].numpy().T
    distances.extend(np.linalg.norm(pa-pb,axis=1))
    cv2.putText(warp1,item['image']+' insight',(3,18),cv2.FONT_HERSHEY_SIMPLEX,.42,(0,255,255),1)
    cv2.putText(warp2,'DWPose',(3,18),cv2.FONT_HERSHEY_SIMPLEX,.42,(0,255,255),1)
    panels.append(np.hstack((warp1,warp2)))
cv2.imwrite(str(folder/'affine-comparison.jpg'),np.vstack(panels))
print('aligned landmark px mean',round(float(np.mean(distances)),2),'max',round(float(np.max(distances)),2),'samples',len(poses))
