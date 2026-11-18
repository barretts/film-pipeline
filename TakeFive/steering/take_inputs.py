"""Feed an exported Blender shot and its existing timed poses into the local video graph."""
import json
import os
import shutil
import subprocess
import uuid
import wave

from takefive.finishing import checksum
from takefive.script import binary, dump


def frame_map(edit_frames, model_frames, delay):
    if model_frames<edit_frames or not 0 <= delay < edit_frames-1:
        raise ValueError("The hold must leave at least two distinct frames of movement")
    last = edit_frames-1
    return [round(max(0,min(t,last)-delay)*last/(last-delay)) for t in range(model_frames)]


def decoded(path):
    import av
    with av.open(str(path)) as source:
        return [f.to_ndarray(format="yuv420p").tobytes() for f in source.decode(video=0)]


def retime(original, delayed, mapping, width, height, fps):
    frames = decoded(original)
    if len(frames)!=len(mapping):
        raise ValueError("The exported depth video length does not match its receipt")
    tmp = delayed.with_name(uuid.uuid4().hex+".mp4")
    cmd = [binary("ffmpeg"),"-v","error","-nostdin","-f","rawvideo","-pixel_format","yuv420p","-video_size",
           f"{width}x{height}","-framerate",str(fps),"-i","pipe:0","-an","-c:v","libx264",
           "-threads","3","-crf","0","-pix_fmt","yuv420p","-movflags","+faststart",str(tmp)]
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        try:
            for i in mapping:
                proc.stdin.write(frames[i])
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError("Encoding the delayed guide failed")
    actual = decoded(tmp)
    if len(actual)!=len(mapping) or any(f!=frames[i] for f,i in zip(actual,mapping)):
        raise ValueError("The delayed guide changed pixels in addition to changing timing")
    os.replace(tmp,delayed)


def from_take(args):
    take = args.take
    manifest = json.loads((take/"guides.json").read_text(encoding="utf-8"))
    plan = json.loads((take/"plan.json").read_text(encoding="utf-8"))
    shot = next(s for s in plan["shots"] if s["id"]==args.id)
    guide = manifest["shots"][args.id]
    width,height,fps = (manifest[k] for k in ("width","height","fps"))
    length,n = guide["guide_frames"],guide["edit_frames"]
    inputs = args.out/"input"
    inputs.mkdir(exist_ok=True)
    def stage(relative, expected, target):
        path = (take/relative).resolve()
        if not path.is_relative_to(take) or checksum(path)!=expected:
            raise ValueError(f"The stage export does not match its receipt: {relative}")
        shutil.copyfile(path,target)
    original = inputs/"original-depth.mp4"
    stage(guide["depth"],guide["depth_sha256"],original)
    delay = min(args.delay,n-2)
    mapping = frame_map(n,length,delay)
    if delay:
        retime(original,inputs/"delayed-depth.mp4",mapping,width,height,fps)
    with wave.open(str(inputs/"silence.wav"),"wb") as w:
        w.setparams((2,2,48000,0,"NONE","not compressed"))
        w.writeframes(bytes(4*round(48000*length/fps)))
    setting = plan["sets"][shot["set"]]
    cast = " ".join(f"{name}: {plan['cast'][name]['description']}" for name in shot["actors"])
    context = (f"{shot['camera']['view'].capitalize()} view of {shot['set']}, a {setting['kind'].replace('_',' ')}. "
               f"The {setting['door_color']} door is on camera {setting['door_side']}. {cast}")
    verbs = {"open":"opens the door","stand":"stands in place","sit":"stays seated","exit":"walks out",
             "enter":"walks in","walk_away":"walks away","lean":"leans forward","listen":"listens"}
    action = " ".join(f"{name} {verbs.get(b['action'],b['action'].replace('_',' '))}." for name,b in shot["actors"].items())
    prompt = f"Naturalistic live-action film, fixed camera, one uninterrupted take. {context} {action} {shot['script']}"
    keys = []
    # This experiment uses up to two distinct interior poses already exported by the director.
    selected = [k for k in guide["keyframes"] if 0<k["frame"]<n-1][:2]
    for k in selected:
        frame = k["frame"]
        stage(k["image"],k["sha256"],inputs/f"proxy-{frame}.png")
        poses = ", ".join(f"{actor} {pose.replace('_',' ')}" for actor,pose in k["poses"])
        keys.append({"frame":frame,"direction":"Preserve this instant of the directed action: "+poses+"."})
    dump(args.out/"source.json",{"take":str(take),"shot":args.id,"depth_sha256":guide["depth_sha256"],
         "edit_frames":n,"guide_frames":length,"fps":fps,"delay":delay,"delayed_source_frames":mapping,
         "delayed_sha256":checksum(inputs/"delayed-depth.mp4") if delay else None,
         "keyframes":selected,"prompt":prompt,"seed":args.seed})
    return dict(prompt=prompt,still_context=context,keyframes=keys,delay=delay,width=width,height=height,length=length,fps=fps)
