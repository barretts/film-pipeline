from pathlib import Path
import cv2
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate
root = Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
rate, ref = wavfile.read(root/'voice.wav')
rate2, actual = wavfile.read(root/'decoded-speech.wav')
assert rate == rate2 and ref.ndim == actual.ndim == 1
ref = ref.astype(float); actual = actual.astype(float)
cor = correlate(actual, ref, mode='full', method='fft')
lag = int(np.argmax(cor) - len(ref) + 1)
n = min(len(ref), len(actual)-max(lag,0))
score = np.corrcoef(ref[:n], actual[max(lag,0):max(lag,0)+n])[0,1]
print('audio samples source',len(ref),'decoded',len(actual),'rate',rate,'lag samples',lag,'correlation',score)
a=cv2.VideoCapture(str(root/'full-source.mp4')); b=cv2.VideoCapture(str(root/'full-scene-speaking.mp4'))
source=[]; output=[]
while True:
    ok,x=a.read(); ok2,y=b.read()
    if not ok or not ok2:
        if ok != ok2: raise RuntimeError('frame-count mismatch')
        break
    source.append(x[500:1100,100:600]); output.append(y[500:1100,100:600])
assert len(source)==112
mae=lambda x,y: float(np.abs(x.astype(np.int16)-y.astype(np.int16)).mean())
print('frames',len(source),'body match mean MAE',np.mean([mae(x,y) for x,y in zip(source,output)]),'body motion first-vs-last MAE',mae(source[0],source[-1]))
