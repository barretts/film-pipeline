from pathlib import Path
import cv2
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate, correlation_lags

root=Path(r'F:\film-pipeline\jobs')
a=cv2.VideoCapture(str(root/'handdrawn-normalized-reference.mp4'))
b=cv2.VideoCapture(str(root/'handdrawn-dwpose-latentsync.mp4'))
indices=(20,70,99,100,101,102,105,145,190)
panels=[]; full=[]; errors=[]
for i in range(201):
    ok1,x=a.read(); ok2,y=b.read()
    if not ok1 or not ok2: raise RuntimeError(f'failed to decode frame {i}')
    errors.append(np.abs(x[600:].astype(np.int16)-y[600:].astype(np.int16)).mean())
    if i in indices:
        left=x[100:500,150:550].copy();right=y[100:500,150:550].copy()
        cv2.putText(left,str(i)+' original',(8,26),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
        cv2.putText(right,str(i)+' DWPose',(8,26),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
        panels.append(np.hstack((left,right)))
    if i in (20,100,101,145,190):
        full.append(np.hstack((cv2.resize(x,(352,640)),cv2.resize(y,(352,640)))))
cv2.imwrite(str(root/'handdrawn-dwpose-faces.jpg'),np.vstack(panels))
cv2.imwrite(str(root/'handdrawn-dwpose-full.jpg'),np.vstack(full))
_,voice=wavfile.read(root/'handdrawn-voice-reference.wav')
_,result=wavfile.read(root/'handdrawn-dwpose-audio.wav')
lags=[]
for start in (0,16000,48000,80000,112000):
    x=voice[start:start+8000].astype(float); y=result[start:start+8000].astype(float)
    c=correlate(y,x,mode='full',method='fft'); candidates=correlation_lags(len(y),len(x),mode='full')
    keep=np.abs(candidates)<=1600
    lags.append(candidates[keep][np.argmax(c[keep])]/16)
print('frames=201 body_mean_abs_error=',np.mean(errors),'body_max_mean_abs_error=',np.max(errors),'audio_window_lag_ms=',lags)
