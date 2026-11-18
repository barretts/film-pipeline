"""Plan, prepare or locally generate the single-shot steering experiment."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"generation"))
from local_engine import private_engine
from opening_frames import graph_for
from workflows import Graph, motion_graph
from takefive.director import ask, choice, items, record
from takefive.finishing import checksum
from takefive.production import probe, staging
from takefive.script import binary, digest, dump

FPS, LENGTH, WIDTH, HEIGHT = 24, 121, 640, 384
STYLE = ("A naturalistic live-action 35mm film. Cold daylight comes through frosted glass. "
         "Worn industrial materials, accurate human anatomy, an uninterrupted steady camera.")
NEGATIVE = "Illustration, plastic mannequin, duplicate people, cuts, camera zoom, captions."


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    tmp = path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    dump(tmp, value)
    os.replace(tmp, path)


def shot_schema(stage, key_count=None):
    frame = {"type": "integer", "minimum": 0, "maximum": LENGTH-1}
    text = {"type": "string"}
    mark = choice(stage["marks"])
    return record(actor=choice(stage["cast"]), camera=choice(stage["cameras"]), from_mark=mark, to_mark=mark,
                  start_frame=frame, arrive_frame=frame, description=text,
                  keyframes=items(record(frame=frame, direction=text), key_count or 0, 2 if key_count is None else key_count))


def validate(s, stage):
    fields = shot_schema(stage)["properties"]
    if set(s) != set(fields):
        raise ValueError("Use exactly the fields in the shot schema")
    for name in ("actor", "camera", "from_mark", "to_mark"):
        if s[name] not in fields[name]["enum"]:
            raise ValueError(f"Unknown {name}: {s[name]}")
    if (stage["marks"][s["from_mark"]][:2] == stage["marks"][s["to_mark"]][:2]
            or type(s["start_frame"]) is not int or type(s["arrive_frame"]) is not int
            or not 0 <= s["start_frame"] < s["arrive_frame"] < LENGTH):
        raise ValueError("The walk needs two distinct floor marks and increasing frame numbers from 0 to 120")
    if not isinstance(s["description"], str) or not s["description"].strip():
        raise ValueError("A visible action description is required")
    ks = s["keyframes"]
    if (not isinstance(ks, list) or len(ks) > 2
            or any(not isinstance(k, dict) or set(k) != {"frame", "direction"} or type(k["frame"]) is not int
                   or not 0 < k["frame"] < LENGTH-1 or not isinstance(k["direction"], str)
                   or not k["direction"].strip() for k in ks)
            or len({k["frame"] for k in ks}) != len(ks)):
        raise ValueError("Use zero, one or two distinct interior stills with frame and direction")


def timing(shot, offset):
    return [min(shot["arrive_frame"], max(shot["start_frame"], f-offset)) for f in range(LENGTH)]


def encode_sequence(files, dest):
    tmp = dest.with_name(dest.stem+"."+uuid.uuid4().hex+".mp4")
    args = [binary("ffmpeg"), "-v", "error", "-nostdin", "-f", "image2pipe", "-framerate", str(FPS),
            "-vcodec", "png", "-i", "pipe:0", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-threads", "3", "-crf", "10", "-movflags", "+faststart", str(tmp)]
    with subprocess.Popen(args, stdin=subprocess.PIPE) as proc:
        try:
            for file in files:
                proc.stdin.write(file.read_bytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError(f"Could not encode {dest}")
    os.replace(tmp, dest)


def video_check(path, width=WIDTH, height=HEIGHT, length=LENGTH, fps=FPS):
    stream = next(s for s in probe(path)["streams"] if s["codec_type"] == "video")
    actual = (stream["width"], stream["height"], int(stream["nb_frames"]), stream["avg_frame_rate"])
    if actual != (width, height, length, f"{fps}/1"):
        raise ValueError(f"Unexpected video dimensions or timebase in {path}: {actual}")
    subprocess.run([binary("ffmpeg"), "-v", "error", "-xerror", "-i", str(path),
                    "-map", "0:v:0", "-f", "null", "-"], check=True)


def prepare(args, shot):
    out = args.out
    scene, inputs = out/"stage", out/"input"
    inputs.mkdir(parents=True, exist_ok=True)
    scene.mkdir(exist_ok=True)
    stamp = digest(read(args.set), shot, checksum(HERE/"blender_stage.py"), checksum(ROOT/"takefive"/"stage.py"))
    stampfile = scene/"prepared.json"
    prior = read(stampfile) if stampfile.exists() else {}
    delay = min(args.delay, LENGTH-1-shot["arrive_frame"])
    if delay <= 0 and args.task in ("motion", "all"):
        print("The blocking fills the shot. Only the original timing will be generated.", flush=True)
    if prior.get("stage") != stamp or not (scene/"stage.blend").is_file():
        log = out/"blender.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([binary("blender"), "-b", "-noaudio", "--factory-startup", "--python-exit-code", "1",
                                     "--python", str(HERE/"blender_stage.py"), "--", str(args.set), str(args.shot),
                                     str(scene), "full"], stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(log.read_text(encoding="utf-8", errors="replace")[-2400:])
    files = {}
    for name, shift in (("original", 0), ("delayed", delay)):
        frames = timing(shot, shift)
        for kind in ("depth", "clay"):
            target = inputs/f"{name}-{kind}.mp4"
            if (prior.get("stage") != stamp or prior.get("delay") != delay or not target.exists()
                    or prior.get("media", {}).get(target.name) != checksum(target)):
                encode_sequence([scene/kind/f"frame-{f:04}.png" for f in frames], target)
                video_check(target)
            files[target.name] = checksum(target)
    for k in shot["keyframes"]:
        frame = k["frame"]
        source = scene/"clay"/f"frame-{timing(shot, 0)[frame]:04}.png"
        shutil.copyfile(source, inputs/f"proxy-{frame}.png")
    with wave.open(str(inputs/"silence.wav"), "wb") as w:
        w.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        w.writeframes(bytes(4*48000*LENGTH//FPS))
    save(stampfile, {"stage": stamp, "delay": delay, "media": files})
    save(out/"shot.json", shot)
    save(out/"set.json", read(args.set))
    return delay


def model_files(graph, runtime):
    groups = {"ckpt_name": "checkpoints", "text_encoder": "text_encoders", "lora_name": "loras",
              "unet_name": "diffusion_models", "clip_name": "text_encoders", "vae_name": "vae"}
    refs = {}
    for node in graph.values():
        for key, group in groups.items():
            if key in node["inputs"]:
                name = node["inputs"][key]
                stat = (runtime/"generation-models"/group/name).stat()
                refs[name] = [stat.st_size, stat.st_mtime_ns]
    return refs


def run_graph(engine, args, name, graph, node_id, extension, *, width=WIDTH, height=HEIGHT, length=LENGTH, fps=FPS):
    inputs, target, receipt = args.out/"input", args.out/(name+extension), args.out/(name+".json")
    media = {n["inputs"][k] for n in graph.values() for k in ("image", "file", "audio")
             if isinstance(n["inputs"].get(k), str)}
    fingerprint = {"inputs": {f: checksum(inputs/f) for f in sorted(media)}, "weights": model_files(graph,args.runtime),
                   "engine": read(ROOT/"generation"/"machine.json")["tested_comfy_commit"], "graph": graph}
    cache_key = digest(fingerprint)
    if target.exists() and receipt.exists():
        old = read(receipt)
        if old.get("key") == cache_key and old.get("sha256") == checksum(target):
            print(f"Reusing {target.name}", flush=True)
            return target
    local = engine()
    for f in media:
        if not (local.inputs/f).exists() or checksum(local.inputs/f) != fingerprint["inputs"][f]:
            shutil.copyfile(inputs/f, local.inputs/f)
    print(f"Generating {name}", flush=True)
    raw = local.run(graph, {node_id: ("render", name)})[("render", name)]
    if extension == ".mp4":
        video_check(raw, width, height, length, fps)
    else:
        from PIL import Image
        with Image.open(raw) as pic:
            pic.load()
            if pic.size != (width, height):
                raise ValueError(f"Unexpected keyframe size: {pic.size}")
    with staging(args.out) as scratch:
        tmp = scratch/target.name
        shutil.copyfile(raw, tmp)
        os.replace(tmp, target)
    save(receipt, {"key": cache_key, "sha256": checksum(target), **fingerprint})
    print(f"Saved {target}", flush=True)
    return target


@contextmanager
def engine_for(args):
    from contextlib import ExitStack
    with ExitStack() as stack:
        instance = None
        def get():
            nonlocal instance
            if instance is None:
                machine = {"comfy_directory": str(args.runtime/"comfyui"),
                           "python": str(args.runtime/"inference-env"/"Scripts"/"python.exe")}
                instance = stack.enter_context(private_engine(machine, args.runtime/"generation-models", args.out, args.out))
            return instance
        yield get


def render(args, prompt, still_context, keyframes, delay, *, width=WIDTH, height=HEIGHT, length=LENGTH, fps=FPS):
    def take(engine, name, guide_name, keys=()):
        g = Graph()
        saved = motion_graph(g, prompt, NEGATIVE, width, height, fps, length, guide_name+"-depth.mp4",
                             args.strength, "silence.wav", args.seed, args.steps, name, keyframes=keys)
        return run_graph(engine, args, name, g.nodes, saved[0], ".mp4",width=width,height=height,length=length,fps=fps)
    with engine_for(args) as engine:
        if args.task in ("motion", "all"):
            take(engine, "original", "original")
            if delay:
                take(engine, "delayed", "delayed")
        if args.task in ("key", "all") and keyframes:
            keys = []
            for k in keyframes:
                f = k["frame"]
                instruction = (f"Recreate this exact 3D blocking frame as a realistic live-action movie still. "
                               f"{still_context} "
                               f"Keep the exact camera, actor count, location, scale and limb positions. "
                               f"Natural wool, fabric, skin, worn steel and frost. {k['direction']}")
                spec = {"seed": args.seed+f, "references": [f"proxy-{f}"], "prompt": instruction}
                graph, node = graph_for(f"still-{f}", spec, width, height)
                pic = run_graph(engine, args, f"still-{f}", graph, node, ".png",width=width,height=height)
                shutil.copyfile(pic, args.out/"input"/pic.name)
                keys.append((f, pic.name, args.key_strength))
            take(engine, "keyed", "original", keys)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("task", choices=["plan", "prepare", "motion", "key", "all"])
    p.add_argument("--set", type=Path, default=HERE/"station.json")
    p.add_argument("--shot", type=Path, default=HERE/"snow-walk.json")
    p.add_argument("--take", type=Path, help="Blender take directory containing guides.json")
    p.add_argument("--id", help="Shot ID inside --take")
    p.add_argument("--text", help="Plain-language direction for the bundled CPU planner")
    p.add_argument("--keys", type=int, choices=[0,1,2], default=0, help="Number of requested image anchors for plan")
    p.add_argument("--out", type=Path)
    p.add_argument("--runtime", type=Path, default=Path(os.environ.get("TAKEFIVE_RUNTIME", ROOT/"runtime")))
    p.add_argument("--seed", type=int, default=71937)
    p.add_argument("--steps", type=int, default=8)
    p.add_argument("--strength", type=float, default=1.)
    p.add_argument("--key-strength", type=float, default=.91)
    p.add_argument("--delay", type=int, default=42)
    args = p.parse_args()
    if args.steps < 1 or not 0 < args.strength <= 1 or not 0 < args.key_strength <= 1 or args.delay < 0 or args.seed < 0:
        p.error("Use positive step count and strengths up to 1, and nonnegative seed and delay")
    if bool(args.take) != bool(args.id) or args.take and args.task=="plan":
        p.error("--take and --id select an existing Blender shot for prepare, motion, key or all")
    if args.take:
        args.take = args.take.resolve()
        if not re.fullmatch(r"[A-Za-z0-9_-]+",args.id) or args.id not in read(args.take/"guides.json")["shots"]:
            p.error("The selected shot is absent from this take's guides.json")
    if not args.out:
        args.out = (ROOT/"output"/"steering"/"snow-door" if not args.take else
                    ROOT/"output"/"steering"/"generated"/args.take.name/args.id)
    for key in ("set", "shot", "out", "runtime"):
        setattr(args, key, getattr(args, key).resolve())
    args.out.mkdir(exist_ok=True, parents=True)
    if args.take:
        from take_inputs import from_take
        case = from_take(args)
        if args.task=="key" and not case["keyframes"]:
            p.error("This Blender shot has no interior pose stills to apply")
        if args.task!="prepare":
            render(args,**case)
            if args.task=="all":
                from compare_takes import make_comparison
                make_comparison(args.out)
        return
    stage = read(args.set)
    if args.task == "plan":
        if not args.text:
            p.error("plan needs --text")
        os.environ.setdefault("TAKEFIVE_MODEL", str(args.runtime/"planner.gguf"))
        os.environ.setdefault("TAKEFIVE_LLAMA_COMPLETION", str(args.runtime/"llama"/"llama-completion.exe"))
        instruction = ("Direct one 5-second locked-off full-body walk, frames 0 through 120 at 24 fps. "
                       "Use the supplied actor, camera and two different marks. start_frame is when walking begins; "
                       "arrive_frame is when they reach their destination. Use only specifically requested interior "
                       "keyframes, up to two. description describes the visible physical action. Return the shot JSON.")
        catalogue = {k: stage[k] for k in ("description", "cast", "cameras", "marks")}
        def check_planned(s):
            validate(s, stage)
            if len(s["keyframes"]) != args.keys:
                raise ValueError(f"This pass requests exactly {args.keys} interior keyframes")
        shot = ask(instruction, json.dumps(catalogue)+"\n"+args.text+f"\nExactly {args.keys} image anchors.",
                   shot_schema(stage, args.keys), args.seed, args.out/"planner-cache", 650, check_planned)
        save(args.out/"planned-shot.json", shot)
        print(args.out/"planned-shot.json")
        return
    shot = read(args.shot)
    validate(shot, stage)
    delay = prepare(args, shot)
    if args.task != "prepare":
        context = stage["description"]+" "+stage["cast"][shot["actor"]]["description"]
        render(args, " ".join((STYLE, context, shot["description"])), context, shot["keyframes"], delay)


if __name__ == "__main__":
    main()
