"""Replace selected picture takes while preserving the scene's sample-accurate sound."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave
from PIL import Image, ImageDraw, ImageFilter

from .production import assemble, extract_board, ffmpeg, probe, staging
from .script import FPS, SHOTS, WORK, digest, dump, file_stamp, shot_ids


def checksum(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def normalize(source, out, width, frames, framing=None):
    info=probe(source)
    video=next((s for s in info["streams"] if s["codec_type"]=="video"),None)
    if video is None:
        raise ValueError(f"No video in {source.name}")
    sw,sh=video["width"],video["height"]
    settings=framing if isinstance(framing,dict) else {"crop":framing}
    crop=""
    if settings.get("crop") is not None:
        left,top,w,h=settings["crop"]
        if not (0 <= left < left+w <= 1 and 0 <= top < top+h <= 1):
            raise ValueError(f"Framing is outside the picture in {source.name}.")
        x,y,cw,ch=(2*int(n/2) for n in (left*sw,top*sh,w*sw,h*sh))
        if min(cw,ch)<2:
            raise ValueError(f"Framing is too small in {source.name}.")
        crop=f"crop={cw}:{ch}:{x}:{y},"
    vf=(f"fps={FPS},{crop}scale={width}:{width*9//16}:force_original_aspect_ratio=increase,"
        f"crop={width}:{width*9//16},setsar=1")
    encode=["-an","-frames:v",str(frames),"-c:v","libx264","-preset","fast","-crf","17",
            "-pix_fmt","yuv420p","-video_track_timescale","24000",out]
    prefix, picture = "", "0:v"
    lead = settings.get("reaction_lead")
    if lead is not None:
        start, resume, blend = (lead[k] for k in ("source_frame","resume_frame","blend_frames"))
        count = int(video["nb_frames"])
        if not (all(type(n) is int for n in (start,resume,blend)) and
                0 < blend < resume < frames and 0 <= start <= count-resume-blend and
                video["avg_frame_rate"] == f"{FPS}/1"):
            raise ValueError(f"Invalid reaction lead for {source.name}.")
        # Reuse a silent reaction from this take while keeping the spoken frames on their timeline.
        prefix = (f"[0:v]split[listen][speak];"
                  f"[listen]trim=start_frame={start}:end_frame={start+resume+blend},settb=1/{FPS},setpts=PTS-STARTPTS[a];"
                  f"[speak]trim=start_frame={resume},settb=1/{FPS},setpts=PTS-STARTPTS[b];"
                  f"[a][b]xfade=transition=fade:duration={blend/FPS:.9f}:offset={resume/FPS:.9f}[performance];")
        picture = "performance"
    region=settings.get("moving_region")
    if region is None:
        if prefix:
            ffmpeg("-i",source,"-filter_complex_threads","2","-filter_complex",prefix+f"[{picture}]{vf}[cut]",
                   "-map","[cut]",*encode)
        else:
            ffmpeg("-i",source,"-map","0:v:0","-vf",vf,*encode)
    else:
        if len(region)<3 or any(not (0<=x<=1 and 0<=y<=1) for x,y in region):
            raise ValueError(f"The moving region is outside the picture in {source.name}.")
        mask=Image.new("L",(sw,sh))
        ImageDraw.Draw(mask).polygon([(round(x*(sw-1)),round(y*(sh-1))) for x,y in region],fill=255)
        mask=mask.filter(ImageFilter.GaussianBlur(min(sw,sh)*.009))
        with staging(out.parent) as scratch:
            matte=scratch/"moving-region.png"
            mask.convert("RGB").save(matte)
            graph=(prefix+f"[{picture}]format=gbrp,split[live][first];"
                   f"[first]trim=end_frame=1,tpad=stop_mode=clone:stop_duration={frames/FPS+1}[plate];"
                   f"[1:v]format=gbrp[matte];[plate][live][matte]maskedmerge,{vf}[picture]")
            ffmpeg("-i",source,"-loop","1","-framerate",str(FPS),"-i",matte,
                   "-filter_complex_threads","2","-filter_complex",graph,"-map","[picture]",*encode)
    video=next(s for s in probe(out)["streams"] if s["codec_type"]=="video")
    if int(video.get("nb_frames",0))!=frames:
        raise ValueError(f"{source.name} is too short for its {frames}-frame shot.")


def finish(bundle,out,takes,description,framing=None):
    bundle,out=bundle.resolve(),out.resolve()
    if not takes:
        raise ValueError("Supply at least one replacement named after its shot, such as manager.mp4.")
    spec=json.loads((bundle/"render.json").read_text(encoding="utf-8"))
    names=shot_ids(json.loads((bundle/"scene.json").read_text(encoding="utf-8-sig")))
    available=set(names)
    if any(name not in available for name in takes):
        raise ValueError("Unexpected shot name.")
    if framing and set(framing)-available:
        raise ValueError("Unexpected shot name in edit framing.")
    out.mkdir(parents=True,exist_ok=True)
    hashes={k:checksum(path) for k,path in takes.items()}
    crops={}
    for name,settings in (framing or {}).items():
        if name in hashes and (not isinstance(settings,dict) or settings.get("for_take",hashes[name])==hashes[name]):
            crops[name]=settings
    cut_key=digest("finish-v4",spec,checksum(bundle/"mix.wav"),checksum(bundle/"scene.json"),hashes,description)
    version=(digest("framed-edit-v1",cut_key,crops) if crops else cut_key)[:14]
    target=out/version
    if target.exists():
        from .production import verify_film
        verify_film(target/"film.mp4",spec["timing"]["frames"],spec["width"])
        return target
    with staging(out) as scratch:
        tmp=scratch/"cut"
        tmp.mkdir()
        for name in ("scene.json","mix.wav","edit.ffconcat"):
            shutil.copy2(bundle/name,tmp/name)
        for path in (*bundle.glob("input.*"),*bundle.glob("*-camera.wav"),*bundle.glob("scene.blend")):
            shutil.copy2(path,tmp/path.name)
        if (bundle/"voices").is_dir():
            shutil.copytree(bundle/"voices",tmp/"voices")
        (tmp/"shots").mkdir()
        shot_keys=dict(spec["shot_keys"])
        for i,name in enumerate(names):
            dst=tmp/"shots"/(name+".mp4")
            if name in takes:
                normalize(takes[name],dst,spec["width"],spec["timing"]["lengths"][i],crops.get(name))
                shot_keys[name]=hashes[name]
            else:
                shutil.copy2(bundle/"shots"/(name+".mp4"),dst)
        spec.setdefault("guide_keys",dict(spec["shot_keys"]))
        spec.update(renderer=description,shot_keys=shot_keys)
        if crops:
            spec["picture_framing"]=crops
        dump(tmp/"render.json",spec)
        extract_board(tmp,spec["timing"],names)
        dump(tmp/"verification.json",{**assemble(tmp,tmp/"film.mp4"),"replaced":list(takes)})
        try:
            tmp.rename(target)
        except OSError:
            if not (target/"film.mp4").is_file():
                raise
    return target


def neural(bundle,config_path,out,looks,selected):
    # The native upstream CLI takes local file paths. It does not use the Desktop cloud API.
    cfg=json.loads(config_path.read_text(encoding="utf-8-sig"))
    def local_file(key,folder=False):
        result=(config_path.resolve().parent/cfg[key]).resolve()
        if not (result.is_dir() if folder else result.is_file()):
            raise ValueError(f"Missing local LTX {key}: {result}")
        return result
    python=local_file("python")
    model=local_file("checkpoint")
    gemma=local_file("gemma",True)
    upscaler=local_file("upscaler")
    adapter=local_file("layout_lora")
    width,height=cfg.get("width",1024),cfg.get("height",576)
    if any(isinstance(n,bool) or not isinstance(n,int) or n<64 or n%64 for n in (width,height)):
        raise ValueError("LTX width and height must be positive multiples of 64.")
    env=dict(os.environ,HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",HF_HUB_DISABLE_TELEMETRY="1")
    backend=[str(python),"-m","ltx_pipelines.ic_lora"]
    check=subprocess.run(backend+["--help"],capture_output=True,text=True,errors="replace",env=env,timeout=180)
    flags=("--distilled-checkpoint-path","--video-conditioning","--audio-path","--no-refine-audio","--stage-2-ic-lora")
    if check.returncode or any(flag not in check.stdout for flag in flags):
        raise ValueError("The local ltx_pipelines.ic_lora installation lacks the required layout/audio CLI. See README.md.")
    spec=json.loads((bundle/"render.json").read_text(encoding="utf-8"))
    scene=json.loads((bundle/"scene.json").read_text(encoding="utf-8"))
    cache=WORK/"neural"
    cache.mkdir(parents=True,exist_ok=True)
    actions=("The employee enters the dispatch office through the street door.",
             "The employee speaks to the manager across the desk.",
             "The seated manager listens, then replies to the employee.",
             "The employee turns and exits through the street door while the manager remains seated.",
             "The employee is already walking along the street outside the same door.")
    takes={}
    seed=int(cfg.get("seed",7624))
    model_stamp=[file_stamp(path) for path in (python,model,adapter,upscaler)]
    encoder_stamp=[file_stamp(path) for path in sorted(gemma.rglob("*.safetensors"))]
    for i,name in enumerate(SHOTS):
        if selected and name not in selected:
            continue
        source=bundle/"shots"/(name+".mp4")
        image=(looks/(name+".png") if looks else bundle/"stills"/(name+"-start.png")).resolve()
        if not image.is_file():
            raise ValueError(f"Missing look image: {image}")
        audio=bundle/(name+"-camera.wav") if name in ("employee","manager") else None
        frames=spec["timing"]["lengths"][i]
        model_frames=((frames-1+7)//8)*8+1
        prompt=(cfg.get("style","Tactile stop-motion film, soft daylight.")+" "+actions[i]+
                " Keep the camera, office, identities and wardrobe from the references. The employee wears "+
                scene["cast"]["employee"]["coat"]+" and the manager wears "+scene["cast"]["manager"]["coat"]+".")
        ident=digest("layout-v1",name,cfg,model_stamp,encoder_stamp,checksum(source),checksum(image),
                     checksum(audio) if audio else "",prompt,frames)
        target=cache/(ident+".mp4")
        if not target.exists():
            with tempfile.TemporaryDirectory(dir=cache) as temporary:
                tmp=Path(temporary)
                guide=tmp/"guide.mp4"
                vf=f"fps={FPS},scale={width}:{height},tpad=stop_mode=clone:stop_duration=1"
                ffmpeg("-i",source,"-an","-vf",vf,"-frames:v",str(model_frames),"-crf","13",guide)
                args=backend+["--distilled-checkpoint-path",str(model),"--gemma-root",str(gemma),
                              "--spatial-upsampler-path",str(upscaler),"--lora",str(adapter),
                              "--stage-2-ic-lora","--video-conditioning",str(guide),"1.0",
                              "--image",str(image),"-1","1.0","--prompt",prompt,"--seed",str(seed+i),
                              "--width",str(width),"--height",str(height),"--num-frames",str(model_frames),
                              "--frame-rate",str(FPS),"--offload","cpu","--output-path",str(tmp/"raw.mp4")]
                if audio:
                    # Align to the model's 8k+1 frames, then trim back to the exact edit duration.
                    padded=tmp/"voice.wav"
                    with wave.open(str(audio),"rb") as voice:
                        params=voice.getparams()
                        samples=voice.readframes(voice.getnframes())
                    need=(model_frames*(params.framerate//FPS))*params.sampwidth*params.nchannels
                    with wave.open(str(padded),"wb") as voice:
                        voice.setparams(params)
                        voice.writeframes(samples.ljust(need,b"\0"))
                    args.extend(["--audio-path",str(padded),"--no-refine-audio"])
                print("Rendering local LTX shot "+name,flush=True)
                subprocess.run(args,env=env,check=True)
                normalize(tmp/"raw.mp4",tmp/"complete.mp4",spec["width"],frames)
                os.replace(tmp/"complete.mp4",target)
        takes[name]=target
    return finish(bundle,out,takes,"LTX layout-to-render with original scene dialogue")
