"""Display all generated takes at identical frame times alongside their actual model inputs."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import uuid

import av
from PIL import Image, ImageDraw, ImageFont

from takefive.script import binary


def make_comparison(out):
    spec = json.loads((out/"source.json").read_text(encoding="utf-8"))
    cols = [("Original timing",out/"input"/"original-depth.mp4",out/"original.mp4","Depth guide")]
    if spec["delay"] and (out/"delayed.mp4").exists():
        cols.append(("Later timing",out/"input"/"delayed-depth.mp4",out/"delayed.mp4","Retimed depth guide"))
    if spec["keyframes"] and (out/"keyed.mp4").exists():
        f = spec["keyframes"][0]["frame"]
        cols.append(("Original timing + still",out/f"still-{f}.png",out/"keyed.mp4",f"Fixed reference from frame {f}"))
    if len(cols)<2:
        return
    w = 512
    with av.open(str(cols[0][1])) as guide:
        stream = guide.streams.video[0]
        h = 2*round(w*stream.height/(2*stream.width))
    label, footer = 34, 27
    W,H = w*len(cols), (h+label)*2+footer+1
    font_file = Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/"segoeui.ttf"
    font = ImageFont.truetype(str(font_file),18) if font_file.is_file() else ImageFont.load_default()
    tmp = out/("comparison-"+uuid.uuid4().hex+".mp4")
    cmd = [binary("ffmpeg"),"-v","error","-nostdin","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}",
           "-framerate",str(spec["fps"]),"-i","pipe:0","-an","-c:v","libx264","-crf","17","-threads","4",
           "-pix_fmt","yuv420p","-movflags","+faststart",str(tmp)]
    with ExitStack() as stack:
        def reader(path):
            if path.suffix==".png":
                image = stack.enter_context(Image.open(path)).convert("RGB").resize((w,h),Image.Resampling.LANCZOS)
                return lambda: image
            video = stack.enter_context(av.open(str(path)))
            frames = iter(video.decode(video=0))
            return lambda: next(frames).to_image().resize((w,h),Image.Resampling.LANCZOS)
        panels = [(title,reader(a),reader(b),cap) for title,a,b,cap in cols]
        with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
            try:
                for t in range(spec["edit_frames"]):
                    canvas = Image.new("RGB",(W,H),"#171D23")
                    d = ImageDraw.Draw(canvas)
                    for j,(title,top,bottom,cap) in enumerate(panels):
                        x = j*w
                        d.text((x+9,5),cap,font=font,fill="white")
                        canvas.paste(top(),(x,label))
                        d.text((x+9,h+label+5),"LTX  /  "+title,font=font,fill="white")
                        canvas.paste(bottom(),(x,2*label+h))
                    d.text((9,H-footer-1),f"Frame {t:03}    {t/spec['fps']:.2f} s",font=font,fill="#DBE3E6")
                    proc.stdin.write(canvas.tobytes())
            finally:
                proc.stdin.close()
            if proc.wait():
                raise RuntimeError("The side-by-side video could not be encoded")
    os.replace(tmp,out/"comparison.mp4")
