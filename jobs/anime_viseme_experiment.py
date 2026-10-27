"""Experimental hand-drawn mouth driven by approximate word timing, not a phoneme aligner."""
from pathlib import Path
import json, pickle, subprocess
import cv2
import numpy as np
root=Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
with (root/'mouths.pkl').open('rb') as f: mouths=pickle.load(f)
words=json.loads((root/'character.json').read_text(encoding='utf8'))['segments'][0]['words']
# Rough articulatory classes, divided within Whisper word intervals; these are
# approximate rather than measured phonemes, so this is not verified lip sync.
shapes=[['mid','wide','round'],['closed','wide'],['mid','wide','closed'],['wide','mid'],['wide','mid','wide'],['mid','wide','closed','mid'],['mid','round','mid','wide'],['wide','mid'],['mid','wide'],['closed','mid','wide','mid'],['closed','wide','mid','wide','mid'],['mid','round'],['mid','closed','wide','mid']]
assert len(words)==len(shapes) and len(mouths)==112
events=[]
for word, seq in zip(words,shapes):
    start,end=float(word['start']),float(word['end'])
    for i,state in enumerate(seq): events.append((start+(end-start)*i/len(seq),start+(end-start)*(i+1)/len(seq),state))
values={'closed':(0.0,1.0),'mid':(.20,1.0),'wide':(.55,1.0),'round':(.72,.60)}
raw=[]
for n in range(112):
    t=(n+.5)/25
    hit=next((s for a,b,s in events if a<=t<b),'closed')
    raw.append(values[hit])
raw=np.array(raw)
smooth=np.array([np.mean(raw[max(0,n-1):min(112,n+2)],axis=0) for n in range(112)])
cap=cv2.VideoCapture(str(root/'full-source.mp4'))
out=root/'full-scene-viseme-experiment.mp4'
cmd=['ffmpeg','-v','error','-nostdin','-y','-f','rawvideo','-pix_fmt','bgr24','-s','704x1280','-r','25','-i','pipe:0','-i',str(root/'voice.wav'),'-map','0:v','-map','1:a','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(out)]
proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
for n,pts in enumerate(mouths):
    ok,frame=cap.read()
    if not ok: raise ValueError(f'frame missing {n}')
    pts=pts.astype(float)*.875+np.array([128,24])
    left,right=pts[0],pts[6]
    center=(left+right)/2
    width=np.linalg.norm(right-left)
    angle=float(np.degrees(np.arctan2(right[1]-left[1],right[0]-left[0])))
    opening,span=smooth[n]
    if opening>0.04:
        # Restrict inpainting to the original mouth line and feather its edge.
        mask=np.zeros(frame.shape[:2],np.uint8)
        cv2.ellipse(mask,tuple(np.round(center).astype(int)),(int(width*.56),max(3,int(width*.13))),angle,0,360,255,-1)
        repaired=cv2.inpaint(frame,mask,3,cv2.INPAINT_TELEA)
        feather=cv2.GaussianBlur(mask,(9,9),2).astype(float)[:,:,None]/255
        frame=np.clip(repaired*feather+frame*(1-feather),0,255).astype(np.uint8)
        cx,cy=np.round(center).astype(int)
        half=max(4,int(width*.43*span)); height=max(1,int(width*.19*opening))
        cv2.ellipse(frame,(cx,cy),(half,height),angle,0,360,(51,38,59),-1,cv2.LINE_AA)
        if height>=4:
            cv2.ellipse(frame,(cx,cy+max(1,height//3)),(max(1,half-3),max(1,height//3)),angle,0,180,(99,92,150),-1,cv2.LINE_AA)
    proc.stdin.write(frame.tobytes())
proc.stdin.close()
if proc.wait()!=0: raise RuntimeError('ffmpeg failed')
print(out)
