from pathlib import Path
import json
import cv2
import numpy as np
root=Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
cues=json.loads((root/'rhubarb-cues.json').read_text())['mouthCues']
selected=[]
for cue in ['X','A','B','C','D','E','F','G']:
    e=next(e for e in cues if e['value']==cue)
    index=min(111,int((e['start']+e['end'])*12.5))
    selected.append((cue,index))
source=cv2.VideoCapture(str(root/'full-source.mp4'))
output=cv2.VideoCapture(str(root/'full-scene-rhubarb-experiment.mp4'))
panels=[]
for cue,index in selected:
    source.set(cv2.CAP_PROP_POS_FRAMES,index);output.set(cv2.CAP_PROP_POS_FRAMES,index)
    oka,a=source.read(); okb,b=output.read()
    if not oka or not okb:raise ValueError(f'Cannot decode frame {index}')
    a=cv2.resize(a[170:420,160:450],(290,250));b=cv2.resize(b[170:420,160:450],(290,250))
    panel=np.concatenate([a,b],axis=1)
    cv2.putText(panel,f'{cue}  {(index+.5)/25:.2f}s  original  /  test',(5,22),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,255,255),1,cv2.LINE_AA)
    panels.append(panel)
rows=[np.concatenate(panels[i:i+2],axis=1) for i in range(0,len(panels),2)]
cv2.imwrite(str(root/'rhubarb-cue-sheet.jpg'),np.concatenate(rows,axis=0))
print('cues and frames:',selected)
