"""Prepare, validate or explicitly render a locally generated version of the office film."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import uuid
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0,str(ROOT))
from takefive.finishing import checksum, finish
from takefive.production import probe, staging
from takefive.script import binary, dump, SHOTS
from prepare import prepare
from workflows import build_graph
from local_engine import private_engine


def check_models(models, full_hash, looks_only=False):
    result = []
    for item in json.loads((HERE/"models.json").read_text(encoding="utf-8")):
        name = Path(item["path"]).name
        if looks_only and name not in ("flux-2-klein-4b-fp8.safetensors","qwen_3_4b.safetensors","flux2-vae.safetensors"):
            continue
        path = models/item["folder"]/name
        if not path.is_file() or path.stat().st_size!=item["bytes"]:
            raise ValueError(f"Missing or incomplete model: {path}")
        with path.open("rb") as f:
            size, = struct.unpack("<Q",f.read(8))
            if not 2<size<100_000_000:
                raise ValueError(f"Invalid safetensors header: {name}")
            header = json.loads(f.read(size))
        ends = [tensor["data_offsets"][1] for key,tensor in header.items() if key!="__metadata__"]
        if not ends or 8+size+max(ends)!=item["bytes"]:
            raise ValueError(f"Incomplete tensor storage: {name}")
        if item["folder"]=="checkpoints":
            blocks={k.split(".",1)[0] for k in header}
            if not {"model","vae","audio_vae","vocoder","text_embedding_projection"}.issubset(blocks):
                raise ValueError(f"LTX checkpoint lacks a required video, audio or text component: {name}")
        if item["folder"]=="loras" and header.get("__metadata__",{}).get("reference_downscale_factor")!="2":
            raise ValueError("The control adapter is incompatible with the prepared reference dimensions.")
        if full_hash and checksum(path)!=item["sha256"]:
            raise ValueError(f"Published checksum mismatch: {name}")
        result.append({"name":name,"bytes":item["bytes"],"tensors":len(ends),"sha256":item["sha256"],"sha256_checked":full_hash})
    return result


def saved(job, kind, name):
    out = job/"accepted"/kind/(name+(".png" if kind=="look" else ".mp4"))
    receipt = out.with_suffix(".json")
    if out.is_file() and receipt.is_file() and json.loads(receipt.read_text(encoding="utf-8"))["sha256"]==checksum(out):
        return out
    return None


def accept(source, job, kind, name, plan):
    d = job/"accepted"/kind
    d.mkdir(parents=True,exist_ok=True)
    ext = ".png" if kind=="look" else ".mp4"
    target = d/(name+ext)
    tmp = d/(uuid.uuid4().hex+ext)
    try:
        if kind=="look":
            with Image.open(source) as im:
                im.verify()
            shutil.copyfile(source,tmp)
        else:
            spec = next(s for s in probe(source)["streams"] if s["codec_type"]=="video")
            shot = plan["shots"][name]
            if not shot["frames"]<=int(spec["nb_frames"])<=shot["guide_frames"]:
                raise ValueError("Generated frame count differs from the prepared cut for "+name)
            if (spec["width"],spec["height"],spec["avg_frame_rate"]) != (plan["direction"]["camera_width"],plan["direction"]["camera_height"],"24/1"):
                raise ValueError("Generated framing or rate differs from the prepared shot "+name)
            shutil.copyfile(source,tmp)
        sig = checksum(tmp)
        os.replace(tmp,target)
        record = d/(uuid.uuid4().hex+".json")
        dump(record,{"sha256":sig,"original":source.name})
        os.replace(record,target.with_suffix(".json"))
    finally:
        tmp.unlink(missing_ok=True)
    return target


def render(machine, models, job, plan, bundle, out, selection, looks_only, framing=None):
    wanted = list(SHOTS) if selection=="all" else [selection]
    phase = "look" if looks_only else "picture"
    missing = [name for name in wanted if not saved(job,phase,name)]
    if missing:
        with private_engine(machine,models,job,job/"runs") as engine:
            known = {}
            for name in SHOTS:
                image = saved(job,"look",name)
                if image:
                    shutil.copyfile(image,engine.inputs/f"look-{name}.png")
                    known[name]=image
            for name in missing:
                if looks_only and name in known:
                    continue
                if name not in known:
                    graph, labels = build_graph(plan,name,known,only_look=True)
                    for (kind,role),result in engine.run(graph,labels).items():
                        image = accept(result,job,kind,role,plan)
                        shutil.copyfile(image,engine.inputs/f"look-{role}.png")
                        known[role]=image
                if not looks_only:
                    graph,labels = build_graph(plan,name,known)
                    for (kind,role),result in engine.run(graph,labels).items():
                        accept(result,job,kind,role,plan)
    if looks_only:
        return job/"accepted"/"look"
    takes = {n:p for n in SHOTS if (p:=saved(job,"picture",n))}
    return finish(bundle,out,takes,"Local LTX-2.3 FP8 / Union Control / original dialogue",framing)/"film.mp4"


def check_edit(job, plan, bundle, scratch, framing=None):
    """Exercise acceptance, cache lookup and final assembly using the staged guides as pictures."""
    def audio_hash(movie):
        return subprocess.check_output([
            binary("ffmpeg"), "-v", "error", "-nostdin", "-hwaccel", "none", "-i", str(movie),
            "-map", "0:a:0", "-c:a", "pcm_s16le", "-f", "hash", "-hash", "sha256", "-"
        ], text=True).strip().split("=", 1)[1]

    with staging(scratch) as temporary:
        takes = {}
        for name in SHOTS:
            take = accept(job / "input" / f"guide-{name}.mp4", temporary, "picture", name, plan)
            if saved(temporary, "picture", name) != take:
                raise ValueError(f"The completed {name} picture could not be recovered.")
            takes[name] = take
        cut = finish(bundle, temporary / "edit", takes, "CPU verification with the staged motion guides", framing)
        result = json.loads((cut / "verification.json").read_text(encoding="utf-8"))
        soundtrack = audio_hash(cut / "film.mp4")
        if soundtrack != audio_hash(bundle / "film.mp4"):
            raise ValueError("The finished film changed the decoded master soundtrack.")
        return {"picture_source": "staged guides", "soundtrack_pcm_sha256": soundtrack, **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["prepare","check","looks","render"])
    parser.add_argument("--shot",choices=[*SHOTS,"all"],default="manager")
    parser.add_argument("--bundle",type=Path,default=ROOT/"films"/"office")
    parser.add_argument("--direction",type=Path,default=HERE/"office.json")
    parser.add_argument("--machine",type=Path,default=HERE/"machine.json")
    parser.add_argument("--models",type=Path,default=ROOT/"runtime"/"generation-models")
    parser.add_argument("--jobs",type=Path,default=HERE/"ready")
    parser.add_argument("--out",type=Path,default=ROOT/"output"/"realistic")
    parser.add_argument("--hash-models",action="store_true",help="Compare every model byte with the upstream LFS checksum.")
    parser.add_argument("--cpu-smoke",action="store_true",help="Test local CPU video export and five-shot assembly with the staged motion guides.")
    args = parser.parse_args()
    bundle, models = args.bundle.resolve(), args.models.resolve()
    job,plan = prepare(bundle,args.direction.resolve(),args.jobs.resolve())
    print("Shot package",job,flush=True)
    if args.action=="prepare":
        return
    framing_file=args.direction.with_suffix(".framing.json")
    framing=json.loads(framing_file.read_text(encoding="utf-8-sig")) if framing_file.is_file() else {}
    machine = json.loads(args.machine.read_text(encoding="utf-8"))
    for path in ("python","comfy_directory"):
        machine[path] = str((ROOT / machine[path]).resolve())
    if args.action=="check":
        os.environ.update(CUDA_VISIBLE_DEVICES="-1",HIP_VISIBLE_DEVICES="-1",ROCR_VISIBLE_DEVICES="-1",
                          HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",PYTHONDONTWRITEBYTECODE="1")
        weights = check_models(models,args.hash_models)
        for name,expected in json.loads((job/"media.json").read_text(encoding="utf-8")).items():
            if checksum(job/"input"/name)!=expected:
                raise ValueError("Prepared input changed: "+name)
        scratch=job/"validation"
        scratch.mkdir(exist_ok=True)
        subprocess.run([machine["python"],"-B",str(HERE/"cpu_validate.py"),machine["comfy_directory"],
                        str(job),str(models),str(scratch)], check=True)
        report=json.loads((scratch/"validation.json").read_text(encoding="utf-8"))
        if args.cpu_smoke:
            with private_engine(machine,models,job,scratch,cpu=True) as engine:
                graph = {"1":{"class_type":"LoadImage","inputs":{"image":"layout-manager.png"}},
                         "2":{"class_type":"CreateVideo","inputs":{"images":["1",0],"fps":24}},
                         "3":{"class_type":"SaveVideo","inputs":{"video":["2",0],"filename_prefix":"cpu_transport","format":"mp4","format.codec":"auto"}}}
                movie = engine.run(graph,{"3":("smoke","manager")})[("smoke","manager")]
                video = next(s for s in probe(movie)["streams"] if s["codec_type"]=="video")
                if int(video["nb_frames"])!=1:
                    raise ValueError("CPU transport smoke test did not export one frame.")
                report["cpu_transport"]={"codec":video["codec_name"],"frames":int(video["nb_frames"])}
            report["cpu_edit"] = check_edit(job, plan, bundle, scratch, framing)
        report.update(models=weights,prepared_shots=list(plan["shots"]),inference_executed=False)
        dump(job/"readiness.json",report)
        print("Verified",job/"readiness.json")
        return
    check_models(models,False,looks_only=args.action=="looks")
    print(render(machine,models,job,plan,bundle,args.out.resolve(),args.shot,args.action=="looks",framing))


if __name__=="__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as e:
        sys.exit("TakeFive: "+str(e))
