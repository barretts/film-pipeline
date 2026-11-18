"""Render a prepared film with local MiniMax H3 reference-to-video and recorded dialogue."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from local_engine import private_engine
from prepare import voice_stem
from realistic import accept, saved
from setup_h3 import EXTENSIONS, NODES, WEIGHTS
from takefive.finishing import checksum, finish
from takefive.production import staging
from takefive.script import SHOTS, digest, dump, shot_ids
from workflows import Graph, slot


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model_frames(frames):
    return 5 + 17 * max(0, math.ceil((frames - 5) / 17))


def crop_photo(source, target, crop):
    with Image.open(source) as im:
        x, y, w, h = crop
        if not (0 <= x < x+w <= 1 and 0 <= y < y+h <= 1):
            raise ValueError(f"Crop outside {source.name}")
        box = tuple(round(n) for n in (x*im.width, y*im.height, (x+w)*im.width, (y+h)*im.height))
        im.convert("RGB").crop(box).save(target)


def graph_for(direction, name, shot, length, cast):
    g = Graph()
    model = g.add("UNETLoader", unet_name="minimax_h3_ref2va_pruned_int8_convrot.safetensors", weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", type="minimax", device="default")
    vae = g.add("VAELoader", vae_name="minimax_h3_video_vae_fp16.safetensors")
    audio_vae = g.add("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors")
    refs = {f"ref_images.ref_image_{i}": g.add("LoadImage", image=f"cast-{role}.png")
            for i, role in enumerate(shot["cast"])}
    if not refs:
        refs["ref_images.ref_image_0"] = g.add("LoadImage", image=f"layout-{name}.png")
    text = shot["prompt"].replace("{line}", shot.get("line", cast.get(name, {}).get("line", "")))
    reference = g.add("MiniMaxH3ReferenceToVideo", clip=clip, vae=vae, audio_vae=audio_vae,
                      width=direction["camera_width"], height=direction["camera_height"],
                      length=length, ref_image_size="match", prompt=text, **refs)
    conditioning = g.add("SenseNovaH3DistilledBridge", conditioning=reference,
                         distilled_adapter="MiniMaxH3_SemanticBridge_v1.safetensors",
                         alpha=direction["bridge_alpha"], magnitude_match="per_token")
    photo_frames = shot.get("photo_frames", [0])
    if photo_frames:
        image = g.add("LoadImage", image=f"layout-{name}.png")
        for index in photo_frames:
            if not isinstance(index, int) or not 0 <= index < length:
                raise ValueError(f"Photographic anchor outside the {name} shot: {index}")
            conditioning = g.add("MiniMaxH3AddGuide", positive=conditioning, latent=slot(reference, 1),
                                 vae=vae, image=image, frame_idx=index)
    voice = g.add("LoadAudio", audio=f"voice-{name}.wav")
    conditioned_audio = g.add("LCH3AudioSync", latent=slot(reference, 1), positive=conditioning,
                              audio_vae=audio_vae, audio=voice, start_seconds=0.0, when_short="silence")
    turbo = g.add("LoraLoaderModelOnly", model=model, lora_name="minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", strength_model=1.0)
    sparse = g.add("Ref2VAVSAGatePatch", model=turbo, gate_file="fasth3_vsa_gate.safetensors", sparsity=direction["sparsity"])
    shifted = g.add("MiniMaxH3SigmaShift", model=sparse, shift_video=direction["shift_video"], shift_audio=direction["shift_audio"])
    schedule = g.add("BasicScheduler", model=shifted, scheduler="sgm_uniform", steps=direction["steps"], denoise=1.0)
    guider = g.add("BasicGuider", model=shifted, conditioning=slot(conditioned_audio, 3))
    noise = g.add("RandomNoise", noise_seed=shot["seed"])
    sampler = g.add("KSamplerSelect", sampler_name="er_sde")
    samples = g.add("SamplerCustomAdvanced", noise=noise, guider=guider, sampler=sampler,
                    sigmas=schedule, latent_image=conditioned_audio)
    picture = g.add("VAEDecode", samples=samples, vae=vae)
    video = g.add("CreateVideo", images=picture, fps=24)
    dest = g.add("SaveVideo", video=video, filename_prefix="h3-"+name, format="mp4", **{"format.codec": "auto"})
    return g.nodes, dest[0]


def prepare(bundle, looks, direction, jobs, machine):
    scene, timing = read(bundle/"scene.json"), read(bundle/"render.json")["timing"]
    names = shot_ids(scene)
    if timing["fps"] != 24 or timing["rate"] != 48000 or len(timing["lengths"]) != len(names):
        raise ValueError("H3 requires a frame count per shot at 24 fps with 48 kHz audio.")
    if set(direction["shots"]) != set(names):
        raise ValueError("The H3 direction file must name every shot in the edit.")
    jobs.mkdir(parents=True, exist_ok=True)
    with staging(jobs) as scratch:
        stage = scratch/"job"
        inputs = stage/"input"
        inputs.mkdir(parents=True)
        for role, crop in direction["cast_crops"].items():
            crop_photo(looks/(role+".png"), inputs/f"cast-{role}.png", crop)
        plan = {"direction": direction, "shots": {}, "runtime": machine, "weights": WEIGHTS}
        for name, scripted, frames in zip(names, scene["shots"], timing["lengths"], strict=True):
            shot = direction["shots"][name].copy()
            if "dialogue" in scripted:
                shot["line"] = " ".join(d["text"] for d in scripted["dialogue"] if d["source"]=="on_screen")
            target = inputs/f"layout-{name}.png"
            source = looks/(name+".png")
            if "opening_crop" in shot:
                crop_photo(source, target, shot["opening_crop"])
            else:
                shutil.copyfile(source, target)
            length = model_frames(frames)
            voice = bundle/(name+"-camera.wav")
            cast = scene.get("cast", {})
            speaking = name in cast or bool(shot.get("line"))
            voice_stem(voice if speaking or voice.is_file() else None, inputs/f"voice-{name}.wav", length * 2000)
            graph, output = graph_for(direction, name, shot, length, cast)
            assets = {n["inputs"][field] for n in graph.values() for kind,field in
                      (("LoadAudio","audio"),("LoadImage","image")) if n["class_type"] == kind}
            media = {filename: checksum(inputs/filename) for filename in sorted(assets)}
            key = digest("h3-reference-v1", graph, media, WEIGHTS, NODES, machine["tested_comfy_commit"])
            plan["shots"][name] = {"frames": frames, "guide_frames": length, "graph": graph,
                                   "output": output, "media": media, "key": key}
        job = jobs/digest(plan)[:16]
        if not job.is_dir():
            (stage/"runs").mkdir()
            dump(stage/"plan.json", plan)
            try:
                stage.rename(job)
            except FileExistsError:
                if not (job/"plan.json").is_file():
                    raise
        for shot in plan["shots"].values():
            for filename, expected in shot["media"].items():
                if checksum(job/"input"/filename) != expected:
                    raise ValueError(f"Prepared H3 input changed: {filename}")
    return job, plan


def render_takes(job, plan, models, nodes, selected):
    if read(models/"installed.json") != WEIGHTS:
        raise ValueError("Install the pinned H3 weights using generation/setup_h3.py first.")
    for rel, (_, expected) in NODES.items():
        if checksum(nodes/rel) != expected:
            raise ValueError(f"H3 node implementation changed: {rel}")
    if any(name not in plan["shots"] for name in selected):
        raise ValueError(f"Unknown shot. Choose from {', '.join(plan['shots'])}.")
    cache = job.parent/"shot-cache"
    missing = []
    for name in selected:
        if saved(job, "picture", name):
            continue
        previous = saved(cache/plan["shots"][name]["key"], "picture", name)
        if previous:
            accept(previous, job, "picture", name, plan)
        else:
            missing.append(name)
    if missing:
        machine = dict(plan["runtime"])
        for field in ("python", "comfy_directory"):
            machine[field] = str((ROOT/machine[field]).resolve())
        with private_engine(machine, models, job, job/"runs", node_directory=nodes, extensions=EXTENSIONS) as engine:
            print("Inference log", engine.log, flush=True)
            for name in missing:
                shot = plan["shots"][name]
                print(f"Generating {name} with MiniMax H3, {shot['guide_frames']} frames", flush=True)
                result = engine.run(shot["graph"], {shot["output"]: ("picture", name)})[("picture", name)]
                take = accept(result, cache/shot["key"], "picture", name, plan)
                print("Saved", accept(take, job, "picture", name, plan), flush=True)
    takes = {name: saved(job, "picture", name) for name in selected}
    if not all(takes.values()):
        raise RuntimeError("A MiniMax H3 take is missing from the edit.")
    return takes


def render(job, plan, models, nodes, bundle, selection, out, framing=None):
    selected = list(plan["shots"]) if selection == "all" else [selection]
    takes = render_takes(job,plan,models,nodes,selected)
    if selection != "all":
        return takes[selection]
    cut = finish(bundle, out, takes, "Local MiniMax H3 Ref2VA INT8 / four-step Turbo / original dialogue", framing)
    # Keep the exact graphs and source fingerprints beside the portable edit.
    provenance = cut/"h3-generation.json"
    if not provenance.exists():
        with staging(cut) as temporary:
            staged = temporary/provenance.name
            dump(staged, plan)
            staged.replace(provenance)
    return cut/"film.mp4"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "render"))
    parser.add_argument("--shot", default="all", help="A shot ID from the screenplay, or all.")
    parser.add_argument("--bundle", type=Path, default=ROOT/"films"/"office")
    parser.add_argument("--looks", type=Path, default=ROOT/"films"/"dispatch-looks")
    parser.add_argument("--direction", type=Path, default=HERE/"h3-office.json")
    parser.add_argument("--jobs", type=Path, default=HERE/"h3-ready")
    parser.add_argument("--out", type=Path, default=ROOT/"output"/"minimax-h3")
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    job, plan = prepare(bundle, args.looks.resolve(), read(args.direction), args.jobs.resolve(), read(HERE/"machine.json"))
    print("H3 shot package", job, flush=True)
    if args.action == "render":
        edit = args.direction.with_suffix(".framing.json")
        print(render(job, plan, ROOT/"runtime"/"h3-models", ROOT/"runtime"/"h3-nodes",
                     bundle, args.shot, args.out.resolve(), read(edit) if edit.is_file() else None), flush=True)


if __name__ == "__main__":
    main()
