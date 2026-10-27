"""CPU CTC character alignment experiment, using a local Wav2Vec2 ASR model."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['TORCH_HOME']=r'F:\film-pipeline\venvs\torch-cache'
from pathlib import Path
import json
import numpy as np
import torch
import torchaudio

torch.set_num_threads(6)
root=Path(r'F:\film-pipeline\jobs\anime_pose_experiment')
bundle=torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
model=bundle.get_model().to('cpu').eval()
audio,sr=torchaudio.load(root/'voice.wav')
if sr!=bundle.sample_rate: audio=torchaudio.functional.resample(audio,sr,bundle.sample_rate)
with torch.inference_mode():
    emission,_=model(audio)
    logp=torch.log_softmax(emission[0],dim=-1).numpy()
labels=bundle.get_labels()
transcript='HELLO|MY|NAME|IS|EVA|LISTEN|CLOSELY|AS|THE|MACHINE|BEGINS|TO|SPEAK'
ids=[labels.index(c) for c in transcript]
symbols=[0]
for k in ids: symbols.extend([k,0])
T,S=logp.shape[0],len(symbols)
dp=np.full((T,S),-np.inf); parent=np.zeros((T,S),np.int16)
dp[0,0]=logp[0,0];dp[0,1]=logp[0,symbols[1]]
for t in range(1,T):
    for s in range(S):
        options=[(dp[t-1,s],s)]
        if s>0: options.append((dp[t-1,s-1],s-1))
        if s>1 and symbols[s]!=0 and symbols[s]!=symbols[s-2]: options.append((dp[t-1,s-2],s-2))
        value,previous=max(options)
        dp[t,s]=value+logp[t,symbols[s]];parent[t,s]=previous
s=max((S-1,S-2),key=lambda x:dp[-1,x]); states=[s]
for t in range(T-1,0,-1): s=int(parent[t,s]);states.append(s)
states=states[::-1]
events=[]
duration=audio.shape[1]/bundle.sample_rate
for i,c in enumerate(transcript):
    indices=[t for t,v in enumerate(states) if v==2*i+1]
    if not indices: raise ValueError(f'Unaligned character {i}: {c}')
    events.append({'char':c,'start':indices[0]*duration/T,'end':(indices[-1]+1)*duration/T,'confidence':float(np.mean(np.exp(logp[indices,ids[i]])))})
(root/'ctc-alignment.json').write_text(json.dumps({'transcript':transcript,'frame_count':T,'events':events},indent=2),encoding='utf-8')
print('emission frames',T,'duration',duration,'min token confidence',min(x['confidence'] for x in events))
print(' '.join(f"{e['char']}:{e['start']:.2f}-{e['end']:.2f}" for e in events))
