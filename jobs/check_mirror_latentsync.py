from pathlib import Path
import cv2
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate, correlation_lags

root = Path(r'F:\film-pipeline\jobs')
a = cv2.VideoCapture(str(root/'mirror-normalized-reference.mp4'))
b = cv2.VideoCapture(str(root/'mirror-latentsync-research.mp4'))
panels, full, errors = [], [], []
indices = (25, 75, 102, 104, 105, 106, 108, 150, 195)
for i in range(210):
    ok1, x = a.read(); ok2, y = b.read()
    if not ok1 or not ok2:
        raise RuntimeError(f'decoding failed at {i}')
    errors.append(np.abs(x[600:].astype(np.int16)-y[600:].astype(np.int16)).mean())
    if i in indices:
        left, right = x[200:550,175:525].copy(), y[200:550,175:525].copy()
        cv2.putText(left, str(i)+' original', (8,26), cv2.FONT_HERSHEY_SIMPLEX, .65, (255,255,255), 2)
        cv2.putText(right, str(i)+' result', (8,26), cv2.FONT_HERSHEY_SIMPLEX, .65, (255,255,255), 2)
        panels.append(np.hstack((left,right)))
    if i in (25, 104, 105, 150, 195):
        full.append(np.hstack((cv2.resize(x,(352,640)),cv2.resize(y,(352,640)))))
cv2.imwrite(str(root/'mirror-latentsync-faces.jpg'),np.vstack(panels))
cv2.imwrite(str(root/'mirror-latentsync-full.jpg'),np.vstack(full))
_, voice = wavfile.read(root/'mirror-voice-reference.wav')
_, output = wavfile.read(root/'mirror-latentsync-audio.wav')
lags=[]
for start in (0, 16000, 48000, 80000, 112000):
    x=voice[start:start+8000].astype(float); y=output[start:start+8000].astype(float)
    corr=correlate(y,x,mode='full',method='fft'); possible=correlation_lags(len(y),len(x),mode='full')
    valid=np.abs(possible)<=1600
    lags.append(possible[valid][np.argmax(corr[valid])]/16)
print('frames=210 body_mean_abs_error=',np.mean(errors),'body_max_mean_abs_error=',np.max(errors),'audio_window_lag_ms=',lags)
