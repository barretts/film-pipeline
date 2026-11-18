"""Publish complete, movable film bundles. Cache approved shots independently."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
from PIL import Image, ImageDraw

from .audio import mix, saved_speech, speech, timeline
from .script import FPS, ROOT, SHOTS, WORK, binary, digest, dump, file_stamp, from_prose, validate


@contextmanager
def staging(parent):
    # Windows Python 3.13 gives TemporaryDirectory a private ACL. Output media
    # published from it would be unreadable from the owner's normal desktop.
    parent=parent.resolve()
    folder=parent/(".building-"+uuid.uuid4().hex)
    folder.mkdir()
    try:
        yield folder
    finally:
        if folder.resolve().parent==parent and not folder.is_symlink():
            shutil.rmtree(folder)


def run(args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def ffmpeg(*args):
    run([binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args])


def probe(path):
    data = subprocess.check_output([binary("ffprobe"), "-v", "error", "-show_streams",
                                    "-show_format", "-of", "json", str(path)])
    return json.loads(data)


def verify_film(path, frames, width):
    info=probe(path)
    video=next(s for s in info["streams"] if s["codec_type"]=="video")
    audio=next(s for s in info["streams"] if s["codec_type"]=="audio")
    if int(video["nb_frames"])!=frames or video["width"]!=width or video["height"]!=width*9//16:
        raise ValueError("Exported picture does not match the scene timeline.")
    if video["r_frame_rate"]!="24/1" or abs(float(audio["duration"])-frames/FPS)>.04:
        raise ValueError("Exported soundtrack or frame rate does not match the scene timeline.")
    return {"frames":frames,"seconds":frames/FPS,"fps":FPS,"width":width,"height":video["height"],
            "audio":audio["codec_name"],"sample_rate":int(audio["sample_rate"])}


def source_hash(*names):
    return [hashlib.sha256((ROOT / "takefive" / n).read_bytes()).hexdigest() for n in names]


def assemble(bundle, dest):
    spec=json.loads((bundle/"render.json").read_text(encoding="utf-8"))
    dest.parent.mkdir(parents=True,exist_ok=True)
    # The list lives beside the shots. Its fixed relative paths are portable, including on Windows.
    with staging(dest.parent) as folder:
        tmp=folder/"film.mp4"
        ffmpeg("-f","concat","-safe","1","-i",bundle/"edit.ffconcat","-i",bundle/"mix.wav",
               "-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","128k",
               "-movflags","+faststart",tmp)
        measured=verify_film(tmp,spec["timing"]["frames"],spec["width"])
        os.replace(tmp,dest)
    return measured


def extract_board(bundle, timing, names=SHOTS):
    folder=bundle/"stills"
    folder.mkdir()
    tiles=[]
    for i,name in enumerate(names):
        n=timing["lengths"][i]
        ffmpeg("-i",bundle/"shots"/(name+".mp4"),"-vf",
               f"select=eq(n\\,0)+eq(n\\,{n//2})+eq(n\\,{n-1})","-fps_mode","vfr",
               "-threads","1",folder/(name+"-%d.png"))
        for idx,label in enumerate(("start","middle","end"),1):
            (folder/f"{name}-{idx}.png").rename(folder/f"{name}-{label}.png")
        with Image.open(folder/f"{name}-middle.png") as im:
            tiles.append(im.convert("RGB").resize((320,180),Image.Resampling.LANCZOS))
    board=Image.new("RGB",(960,206*((len(names)+2)//3)),(31,46,47))
    draw=ImageDraw.Draw(board)
    for i,tile in enumerate(tiles):
        x,y=(i%3)*320,(i//3)*206
        board.paste(tile,(x,y))
        draw.text((x+8,y+184),f"{i+1}  {names[i].upper()}    {timing['lengths'][i]/FPS:g} s",fill=(241,225,192))
    board.save(bundle/"board.jpg",quality=92)


def shot_key(i,plan,timing,speeches,width,renderer):
    name=SHOTS[i]
    parts=[renderer,width,[(r,plan["cast"][r]["coat"]) for r in ("employee","manager")],plan["door"],name,
           plan["shots"][i]["lens"],timing["starts"][i],timing["lengths"][i]]
    if name in ("employee","manager"):
        parts.extend([speeches[name][2], timing["speech_samples"][name]])
    if name in ("departure","street"):
        parts.append(plan["exit_crossing"])
    if name=="street":
        parts.append(timing["lengths"][3])
    return digest(parts)


def render(src,out,width=1280,fresh=False,reuse=None):
    begin=time.monotonic()
    src,out=src.resolve(),out.resolve()
    if width < 320 or width>2560 or width%32:
        raise ValueError("Width must be 320–2560 and divisible by 32.")
    out.mkdir(parents=True,exist_ok=True)
    cache=WORK/"cache"
    cache.mkdir(parents=True,exist_ok=True)
    source=src.read_text(encoding="utf-8-sig")
    print("Reading scene on this computer...",flush=True)
    plan=validate(json.loads(source)) if src.suffix.lower()==".json" else from_prose(source,cache)
    if reuse is None and src.name=="scene.json" and (src.parent/"render.json").is_file():
        reuse=src.parent
    old_plan=json.loads((reuse/"scene.json").read_text(encoding="utf-8")) if reuse else {}
    old_render=json.loads((reuse/"render.json").read_text(encoding="utf-8")) if reuse else {}
    old_keys=old_render.get("shot_keys",{})
    old_guides=old_render.get("guide_keys",old_keys)
    speeches={}
    for role in ("employee","manager"):
        actor=plan["cast"][role]
        old=old_plan.get("cast",{}).get(role,{})
        if reuse and all(old.get(prop)==actor[prop] for prop in ("line","voice")):
            speeches[role]=saved_speech(reuse/"voices"/(role+".wav"),reuse/"voices"/(role+".mouth.json"))
        else:
            speeches[role]=speech(actor,cache)
    timing=timeline(plan,speeches)
    renderer=["picture-v2",source_hash("stage.py","blender_scene.py"),file_stamp(binary("blender")),
              file_stamp(binary("ffmpeg"))]
    keys=[shot_key(i,plan,timing,speeches,width,renderer) for i in range(len(SHOTS))]
    voice_hashes={r:hashlib.sha256(a[0].read_bytes()).hexdigest() for r,a in speeches.items()}
    guide_keys=dict(zip(SHOTS,keys))
    takes={}
    if reuse and not fresh:
        for name,k in guide_keys.items():
            if old_guides.get(name)==k and (reuse/"shots"/(name+".mp4")).is_file():
                takes[name]=old_keys[name]
    picture_keys={**guide_keys,**takes}
    overrides=[picture_keys] if picture_keys!=guide_keys else []
    version=digest(plan,source,keys,timing,voice_hashes,source_hash("audio.py"),*overrides)[:14]
    bundle=out/version
    if bundle.is_dir() and not fresh:
        verify_film(bundle/"film.mp4",timing["frames"],width)
        return bundle
    if fresh:
        version+="-"+str(time.time_ns())
        bundle=out/version
    with staging(out) as temporary:
        tmp=Path(temporary)/"cut"
        tmp.mkdir()
        (tmp/"shots").mkdir()
        (tmp/"voices").mkdir()
        (tmp/("input"+src.suffix.lower())).write_text(source,encoding="utf-8")
        dump(tmp/"scene.json",plan)
        mix(plan,timing,speeches,tmp)
        for role,(wav_path,_,cues) in speeches.items():
            shutil.copy2(wav_path,tmp/"voices"/(role+".wav"))
            dump(tmp/"voices"/(role+".mouth.json"),cues)
        sources={}
        for i,k in enumerate(keys):
            name=SHOTS[i]
            if name in takes:
                sources[i]=reuse/"shots"/(name+".mp4")
            elif (cache/(k+".mp4")).is_file():
                sources[i]=cache/(k+".mp4")
        missing=[i for i in range(len(keys)) if fresh or i not in sources]
        d={"plan":plan,"timing":timing,"width":width,"cues":{r:v[2] for r,v in speeches.items()},
           "render_indices":missing,"target":str(tmp)}
        job=Path(temporary)/"stage.json"
        dump(job,d)
        print(f"Staging {plan['title']} — {len(missing)} of five camera shots to render.",flush=True)
        env=os.environ.copy()
        blender_data=WORK/"blender"
        blender_data.mkdir(exist_ok=True)
        env.update(BLENDER_USER_RESOURCES=str(blender_data),XDG_CACHE_HOME=str(blender_data))
        log=Path(temporary)/"blender.log"
        with log.open("wb") as stream:
            result=subprocess.run([binary("blender"),"-b","-noaudio","--factory-startup","--python-exit-code","1",
                                   "--python",str(ROOT/"takefive"/"blender_scene.py"),"--",str(job)],
                                  env=env,cwd=blender_data,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            details=log.read_text(encoding="utf-8",errors="replace")[-2400:]
            raise RuntimeError("Blender could not render the scene.\n"+details)
        for i,name in enumerate(SHOTS):
            shot=tmp/"shots"/(name+".mp4")
            cached=cache/(keys[i]+".mp4")
            if i in missing:
                start=timing["starts"][i]+1
                frames=tmp/"frames"/name
                ffmpeg("-framerate",str(FPS),"-start_number",str(start),"-i",frames/"f%04d.jpg",
                       "-frames:v",str(timing["lengths"][i]),"-an","-c:v","libx264","-preset","fast",
                       "-crf","17","-pix_fmt","yuv420p","-video_track_timescale","24000",shot)
                if not cached.exists():
                    tempcache=Path(temporary)/(name+"-cached.mp4")
                    shutil.copy2(shot,tempcache)
                    try:
                        os.link(tempcache,cached)
                    except FileExistsError:
                        pass
                    except OSError:
                        with tempfile.NamedTemporaryFile(dir=cache,suffix=".mp4",delete=False) as f:
                            with shot.open("rb") as reader:
                                shutil.copyfileobj(reader,f)
                        os.replace(f.name,cached)
            else:
                shutil.copy2(sources[i],shot)
        frames_dir=tmp/"frames"
        if frames_dir.exists() and frames_dir.resolve().parent==tmp.resolve():
            shutil.rmtree(frames_dir)
        (tmp/"edit.ffconcat").write_text("ffconcat version 1.0\n"+"".join(f"file shots/{s}.mp4\n" for s in SHOTS),encoding="ascii")
        spec={"format":1,"renderer":"Blender Workbench","width":width,"timing":timing,"shot_keys":picture_keys}
        if overrides:
            spec.update(renderer="Blender Workbench with approved replacements",guide_keys=guide_keys)
        dump(tmp/"render.json",spec)
        extract_board(tmp,timing)
        measured=assemble(tmp,tmp/"film.mp4")
        dump(tmp/"verification.json",{**measured,"rendered_shots":[SHOTS[i] for i in missing],
                                     "elapsed_seconds":round(time.monotonic()-begin,1)})
        try:
            tmp.rename(bundle)
        except OSError:
            if not bundle.is_dir():
                raise
            verify_film(bundle/"film.mp4",timing["frames"],width)
    return bundle
