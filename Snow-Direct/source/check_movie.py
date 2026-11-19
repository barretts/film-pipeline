"""Verify the finished watch copy against native shot frames and the continuous WAV."""
from array import array
from math import sqrt
from pathlib import Path
import json
import subprocess
import wave
from PIL import Image
from contact_sheet import frames
from render import frame_cache

base=Path(__file__).resolve().parent.parent
movie=base/'Snow.mp4'
def capture(args):return subprocess.check_output(args)
meta=json.loads(capture(['ffprobe','-v','error','-count_frames','-show_entries',
    'stream=codec_name,codec_type,width,height,nb_read_frames,avg_frame_rate,channels,sample_rate,duration:format=duration',
    '-of','json',str(movie)]))
video=next(s for s in meta['streams'] if s['codec_type']=='video')
audio=next(s for s in meta['streams'] if s['codec_type']=='audio')
assert (video['nb_read_frames'],video['avg_frame_rate'],video['width'],video['height'])==('840','24/1',704,396)
assert abs(float(meta['format']['duration'])-35)<.001 and abs(float(audio['duration'])-35)<.001
with wave.open(str(base/'assets/radio-drama.wav'),'rb') as w:
    ref=array('h',w.readframes(w.getnframes()));rate=w.getframerate()
pcm=array('h',capture(['ffmpeg','-v','error','-i',str(movie),'-map','0:a:0','-f','s16le','-c:a','pcm_s16le','-']))
assert len(pcm)>=len(ref) and int(audio['sample_rate'])==rate and int(audio['channels'])==1
corr=[]
for shot in range(7):
    a=ref[shot*5*rate:(shot+1)*5*rate:7];b=pcm[shot*5*rate:(shot+1)*5*rate:7]
    corr.append(round(sum(i*j for i,j in zip(a,b))/sqrt(sum(i*i for i in a)*sum(j*j for j in b)),5))
assert min(corr)>.85,corr
selected='+'.join(f'eq(n,{f-1})' for f,_ in frames)
raw=capture(['ffmpeg','-v','error','-i',str(movie),'-an','-vf',f"select='{selected}',scale=176:99:flags=area",
             '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'])
size=176*99*3;assert len(raw)==len(frames)*size
errors=[]
for i,(f,_) in enumerate(frames):
    files=[frame_cache(step)/f'snow-{f:04}.png' for step in (1,2)]
    original=next(p for p in files if p.is_file())
    with Image.open(original) as im:a=im.convert('RGB').resize((176,99),Image.Resampling.BOX).tobytes()
    b=raw[i*size:(i+1)*size];err=sum(abs(u-v) for u,v in zip(a,b))/size
    errors.append(dict(frame=f,mean_channel_error_out_of_255=round(err,3)))
assert max(x['mean_channel_error_out_of_255'] for x in errors)<4,errors
print(json.dumps(dict(container=meta,audio_correlation_in_five_second_segments=corr,image_comparisons=errors),indent=2))
