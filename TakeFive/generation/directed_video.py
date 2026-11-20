"""Produce a guided H3 clip from a rendered take, its script and frozen assets."""
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

from h3 import ROOT, read
from local_engine import private_engine
from make_film import exclusive
from workflows import Graph, slot


def find_take(source, film, name):
    for request in sorted((source.parent/"takes").glob("*/request.txt"),
                          key=lambda p:p.stat().st_mtime_ns, reverse=True):
        target = request.parent/name
        if not (target/"steering.mp4").is_file():
            continue
        try:
            payload = json.loads(request.read_text(encoding="utf-8").splitlines()[-1])
        except (ValueError, IndexError):
            continue
        if payload.get("film") == film:
            return target
    return None


def direction(film, shot, target, board, model):
    prompt = """Direct this shot for MiniMax H3 reference-to-video. Select the visible
cast and one finished location image from the available asset IDs. Use other assets
only when essential. Return JSON with references (ordered list of asset IDs, maximum
9) and prompt (string). Assign each <Picture N> its role and <Video 1> camera,
screen positions, timing, blocking and marker replacement. Describe a continuous
finished shot including the specified sound cues. Verbatim spoken lines may appear
only if the shot explicitly supplies them. For a shot without lines keep the people
silent, without speech or lip movement. The attached images show
the guide endpoints and the available asset board. Use the film as creative source.
""" + json.dumps(dict(shot=shot, style=film["style"], location=film["locations"][shot["set"]],
                      assets=film["assets"]),ensure_ascii=False)
    cli = shutil.which("codex.cmd") or shutil.which("codex")
    if not cli:
        raise RuntimeError("Codex CLI is required for H3 direction")
    with tempfile.TemporaryDirectory() as scratch:
        output = Path(scratch)/"direction.json"
        args = [cli,"exec","--ephemeral","--skip-git-repo-check","--sandbox","read-only","-m",model]
        for image in [target/"first.png",target/"last.png",board]:
            args.extend(["-i",str(image)])
        subprocess.run([*args,"-o",str(output),"-"],input=prompt.encode(),cwd=scratch,check=True)
        result = read(output)
    refs = result["references"]
    if (not isinstance(refs,list) or len(refs)>9 or len(set(refs))!=len(refs)
            or any(r not in film["assets"] for r in refs) or not result["prompt"].strip()):
        raise ValueError("Invalid H3 reference selection or prompt")
    return result


def build_graph(plan, size, frames):
    g = Graph()
    model = g.add("UNETLoader", unet_name="minimax_h3_ref2va_pruned_int8_convrot.safetensors",weight_dtype="default")
    clip = g.add("CLIPLoader",clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",type="minimax",device="default")
    vae = g.add("VAELoader",vae_name="minimax_h3_video_vae_fp16.safetensors")
    audio_vae = g.add("VAELoader",vae_name="minimax_h3_audio_vae_fp32.safetensors")
    refs = {f"ref_images.ref_image_{i}":g.add("LoadImage",image=key+".png")
            for i,key in enumerate(plan["references"])}
    guide = g.add("GetVideoComponents",video=g.add("LoadVideo",file="steering.mp4"))
    ref = g.add("MiniMaxH3ReferenceToVideo",clip=clip,vae=vae,audio_vae=audio_vae,
                width=size[0],height=size[1],length=frames,ref_image_size="match",
                prompt=plan["prompt"],**refs,**{"ref_videos.ref_video_0":guide})
    samples = g.add("SamplerCustomAdvanced",noise=g.add("RandomNoise",noise_seed=plan["seed"]),
                    guider=g.add("BasicGuider",model=model,conditioning=ref),
                    sampler=g.add("KSamplerSelect",sampler_name="res_multistep"),
                    sigmas=g.add("BasicScheduler",model=model,scheduler="simple",steps=20,denoise=1.0),
                    latent_image=slot(ref,1))
    video = g.add("CreateVideo",images=g.add("VAEDecode",samples=samples,vae=vae),
                  audio=g.add("VAEDecodeAudio",samples=samples,vae=audio_vae),fps=24.0)
    output = g.add("SaveVideo",video=video,filename_prefix="shot",format="mp4",**{"format.codec":"h264"})
    return g.nodes, output[0]


def video(source, film, shot, target, model, prepare_only):
    library = source.parent/"asset-library"
    job = target/"guided-h3"
    job.mkdir(exist_ok=True)
    with exclusive(job):
        final = job/"video.mp4"
        if final.exists():
            return final
        config = job/"direction.json"
        inputs = job/"input"
        inputs.mkdir(exist_ok=True)
        if not config.exists():
            plan = direction(film,shot,target,library/"review.jpg",model)
            plan["seed"] = secrets.randbits(48)
            temp = config.with_suffix(".tmp")
            temp.write_text(json.dumps(plan,indent=2),encoding="utf-8")
            temp.replace(config)
        plan = read(config)
        for key in plan["references"]:
            shutil.copyfile(library/"looks"/(key+".png"),inputs/(key+".png"))
        shutil.copyfile(target/"steering.mp4",inputs/"steering.mp4")
        scene = read(target.parent/"scene.json")
        frames = next(s["frames"] for s in scene["shots"] if s["id"]==shot["id"])
        width,height = film["size"]
        ratio = min(1,1024/max(width,height))
        size = [max(32,round(n*ratio/32)*32) for n in (width,height)]
        graph, output = build_graph(plan,size,round(frames*24/film["fps"]))
        graph_file = job/"graph.json"
        graph_file.write_text(json.dumps(graph,indent=2))
        if prepare_only:
            return graph_file
        rt = ROOT/"runtime"
        machine = {"python":str(rt/"inference-env/Scripts/python.exe"),"comfy_directory":str(rt/"comfyui")}
        with private_engine(machine,rt/"h3-models",job,job) as engine:
            path = engine.run(graph,{output:"video"})["video"]
            tmp = job/"encoded.mp4"
            subprocess.run(["ffmpeg","-v","error","-y","-i",str(path),"-vf",
                            f"fps={film['fps']},scale={width}:{height},setsar=1",
                            "-t",str(frames/film["fps"]),"-c:v","libx264","-pix_fmt","yuv420p",
                            "-c:a","aac",str(tmp)],check=True)
            tmp.replace(final)
        return final
