"""Render the native Blender cameras on CPU and mux the existing radio play."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent.parent
def frame_cache(step):
    with (ROOT/'Snow.blend').open('rb') as f:
        digest=hashlib.file_digest(f,'sha256').hexdigest()[:16]
    return ROOT/'work'/('frames' if step==1 else 'twos')/digest

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--blender',default=shutil.which('blender') or r'F:\ue\Blender 5.2\blender.exe')
    ap.add_argument('--threads',type=int,default=12)
    ap.add_argument('--step',type=int,choices=(1,2),default=1,
                    help='Render every frame, or hold each alternate animation frame for two ticks.')
    ap.add_argument('--render-only',action='store_true')
    ap.add_argument('--mux-only',action='store_true')
    opt=ap.parse_args()
    folder=frame_cache(opt.step)
    folder.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env['BLENDER_USER_RESOURCES']=str(ROOT/'work/blender')
    frames=range(1,841,opt.step)
    def image(f):return folder/f'snow-{f:04}.png'
    def ready(f):
        p=image(f)
        if not p.is_file() or p.stat().st_size<2000:return False
        with p.open('rb') as fh:
            fh.seek(-8,2)
            return fh.read(4)==b'IEND'
    if not opt.mux_only:
        missing=[f for f in frames if not ready(f)]
        # Blender accepts comma-separated frames and reuses the loaded scene.
        for i in range(0,len(missing),120):
            batch=missing[i:i+120]
            print('Rendering',batch[0],'through',batch[-1],flush=True)
            name=folder/f'blender-{batch[0]:04}.log'
            with name.open('w',encoding='utf8') as log:
                sub=subprocess.run([opt.blender,'-b',str(ROOT/'Snow.blend'),'-noaudio','-t',str(opt.threads),
                                    '-o',str(folder/'snow-####'),'-F','PNG','-f',','.join(map(str,batch))],
                                    stdout=log,stderr=subprocess.STDOUT,env=env)
            if sub.returncode or any(not ready(f) for f in batch):
                raise SystemExit('Blender did not complete the requested frames. See '+str(name))
    if opt.render_only:return
    missing=[f for f in frames if not ready(f)]
    if missing:raise SystemExit(f'{len(missing)} frames missing, first is {missing[0]}')
    # image2 cannot index a range with a stride. Pipe the original PNGs in order.
    temp=ROOT/'work'/'assembly.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(24//opt.step),
         '-f','image2pipe','-vcodec','png','-i','-','-i',str(ROOT/'assets/radio-drama.wav'),
         '-map','0:v','-map','1:a','-c:v','libx264','-preset','fast','-crf','17',
         '-pix_fmt','yuv420p','-r','24','-c:a','aac','-b:a','160k','-t','35',
         '-movflags','+faststart',str(temp)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        for f in frames:proc.stdin.write(image(f).read_bytes())
        proc.stdin.close()
        if proc.wait():raise SystemExit("FFmpeg assembly failed")
    temp.replace(ROOT/'Snow.mp4')
    print(ROOT/'Snow.mp4')
if __name__=='__main__':main()
