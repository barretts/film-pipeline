"""Turn a screenplay or an edited stage plan into a CPU-rendered Blender animatic."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0,str(ROOT))
from blocking import direct, validate
from guide_bundle import export
from takefive.finishing import checksum
from takefive.production import ffmpeg, probe, staging
from takefive.script import binary, digest, dump


def encode(folder, dest, plan):
    total = sum(s["frames"] for s in plan["shots"])
    ffmpeg("-framerate",plan["fps"],"-start_number",0,"-i",folder/"frame-%04d.png","-frames:v",total,
           "-an","-c:v","libx264","-threads",4,"-preset","fast","-crf",12,"-pix_fmt","yuv420p",
           "-movflags","+faststart",dest)
    stream = next(s for s in probe(dest)["streams"] if s["codec_type"]=="video")
    if (int(stream["nb_frames"]),stream["width"],stream["height"],stream["avg_frame_rate"]) != (
            total,plan["width"],plan["height"],f"{plan['fps']}/1"):
        raise ValueError(f"Wrong frame count, dimensions or cadence in {dest}")
    subprocess.run([binary("ffmpeg"),"-v","error","-xerror","-i",str(dest),"-f","null","-"],check=True)


def audit(dest, plan):
    settings = json.loads((dest/"blender-settings.json").read_text())
    names = list(plan["cast"])
    if (set(settings["rigs"])!=set(names) or len(settings["rigs"])!=len(names) or
            settings["cycles_device"]!="CPU" or settings["compositor_device"]!="CPU"):
        raise ValueError(f"Unexpected scene devices or actor rigs: {settings}")
    report = {"settings":settings,"shots":[],"warnings":[]}
    tile = 240
    tile_h = round(tile*plan["height"]/plan["width"])
    board = Image.new("RGB",(3*tile,len(plan["shots"])*(tile_h+24)), "#1D2227")
    draw = ImageDraw.Draw(board)
    first = 0
    (dest/"keyframes").mkdir(exist_ok=True)
    for row,shot in enumerate(plan["shots"]):
        length = shot["frames"]
        visible, samples, stat = set(),[],{}
        for t in range(length):
            people = {}
            if names:
                with Image.open(dest/"ids"/f"frame-{first+t:04}.png") as img:
                    raw_ids = np.asarray(img)
                    peak = np.iinfo(raw_ids.dtype).max
                    ids = raw_ids.astype(np.int32)
                for i,name in enumerate(names,1):
                    code = round(peak*i/(len(names)+1))
                    ys,xs = np.where(abs(ids-code)<=1)
                    if len(xs)<24:
                        continue
                    visible.add(name)
                    people[name] = {"pixels":len(xs),"center_x":round(float(xs.mean())/ids.shape[1],4),
                                    "bounds":[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]}
            if t in (0,length//2,length-1) or t % 12==0:
                samples.append({"frame":t,"cast":people})
            if t==length//2:
                stat = people
        expected = set(shot["actors"])
        if visible-expected:
            raise ValueError(f"{shot['id']}: unexpected visible character IDs {visible-expected}")
        if expected-visible:
            report["warnings"].append(f"{shot['id']}: no visible pixels from {', '.join(sorted(expected-visible))}")
        keyframes = {}
        for name,b in shot["actors"].items():
            for k in b["poses"]:
                keyframes.setdefault(k["frame"],[]).append([name,k["pose"]])
        for t in keyframes:
            shutil.copyfile(dest/"clay"/f"frame-{first+t:04}.png",dest/"keyframes"/f"{shot['id']}-{t:03}.png")
        report["shots"].append({"id":shot["id"],"start_frame":first,"frames":length,"visible":sorted(visible),
                                "midpoint":list(stat),"samples":samples,"keyframes":keyframes})
        for j,t in enumerate((length//8,length//2,length*7//8)):
            with Image.open(dest/"clay"/f"frame-{first+t:04}.png") as pic:
                board.paste(pic.convert("RGB").resize((tile,tile_h),Image.Resampling.LANCZOS),
                            (j*tile,row*(tile_h+24)+24))
        draw.text((8,row*(tile_h+24)+5),f"{shot['id']}   {shot['set']}   /   {shot['camera']['view']}   /   "
                  +", ".join(stat),fill="white")
        first += length
    board.save(dest/"storyboard.jpg",quality=91)
    report["media"] = {f:checksum(dest/f) for f in ("draft.mp4","depth.mp4","stage.blend","storyboard.jpg")}
    dump(dest/"verification.json",report)
    return report


def build(plan, out, blend=None):
    validate(plan)
    blender = binary("blender")
    version = subprocess.check_output([blender,"--version"],text=True).splitlines()[0]
    sources = [HERE/n for n in ("film.py","guide_bundle.py","sets.py","blender_film.py","blender_stage.py")] + [ROOT/"takefive"/"stage.py"]
    key = digest(plan,version,[checksum(f) for f in sources],checksum(blend) if blend else "")[:16]
    takes = out/"takes"
    takes.mkdir(exist_ok=True)
    dest = takes/key
    if dest.exists():
        report = json.loads((dest/"verification.json").read_text())
        if all((dest/f).is_file() and checksum(dest/f)==h for f,h in report["media"].items()):
            return dest,report
    with staging(takes) as transaction, staging(out) as userdir:
        tmp = transaction/"take"
        tmp.mkdir()
        dump(tmp/"plan.json",plan)
        env = dict(os.environ,CUDA_VISIBLE_DEVICES="-1",HIP_VISIBLE_DEVICES="-1",ROCR_VISIBLE_DEVICES="-1",
                   BLENDER_USER_RESOURCES=str(userdir),XDG_CACHE_HOME=str(userdir))
        cmd = [blender,"-b","-noaudio","--factory-startup"]
        if blend:
            shutil.copyfile(blend,tmp/"stage.blend")
            cmd.append(str(tmp/"stage.blend"))
        cmd.extend(["--python-exit-code","1","--python",str(HERE/"blender_film.py"),
                    "--",str(tmp/"plan.json"),str(tmp),"existing" if blend else "build"])
        log = tmp/"blender.log"
        with log.open("wb") as stream:
            result = subprocess.run(cmd,cwd=userdir,env=env,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            shutil.copyfile(log,out/"last-blender-error.log")
            raise RuntimeError(log.read_text(encoding="utf-8",errors="replace")[-3000:])
        encode(tmp/"clay",tmp/"draft.mp4",plan)
        encode(tmp/"depth",tmp/"depth.mp4",plan)
        report = audit(tmp,plan)
        guides = export(tmp,plan,report)
        report["media"]["guides.json"] = checksum(tmp/"guides.json")
        for guide in guides["shots"].values():
            report["media"][guide["depth"]] = guide["depth_sha256"]
            report["media"].update({k["image"]:k["sha256"] for k in guide["keyframes"]})
        dump(tmp/"verification.json",report)
        if dest.exists():
            # Preserve a previously edited take, even when its original receipt no longer matches.
            from uuid import uuid4
            dest = takes/(key+"-"+uuid4().hex[:8])
        try:
            tmp.rename(dest)
        except FileExistsError:
            competing = json.loads((dest/"verification.json").read_text())
            if all(checksum(dest/f)==h for f,h in competing["media"].items()):
                return dest,competing
            raise
    return dest,report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path,help="UTF-8 script (.txt) or editable plan (.json)")
    p.add_argument("--out",type=Path,help="Output project directory")
    p.add_argument("--shots",type=int,help="Shot count for prose without written cuts")
    p.add_argument("--seed",type=int,default=71937)
    p.add_argument("--runtime",type=Path,default=Path(os.environ.get("TAKEFIVE_RUNTIME",ROOT/"runtime")))
    p.add_argument("--plan-only",action="store_true")
    p.add_argument("--blend",type=Path,help="Render edited rigs or cameras from this existing stage.blend")
    args = p.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES="-1",HIP_VISIBLE_DEVICES="-1",ROCR_VISIBLE_DEVICES="-1")
    rt = args.runtime.resolve()
    os.environ.setdefault("TAKEFIVE_MODEL",str(rt/"planner.gguf"))
    os.environ.setdefault("TAKEFIVE_LLAMA_COMPLETION",str(rt/"llama"/"llama-completion.exe"))
    out = (args.out or ROOT/"output"/"steering"/args.source.stem).resolve()
    out.mkdir(parents=True,exist_ok=True)
    raw = args.source.read_text(encoding="utf-8-sig")
    if args.source.suffix.lower()==".json":
        plan = json.loads(raw)
    else:
        if not raw.strip():
            p.error("The script is empty")
        print("Directing the script with the local CPU planner.",flush=True)
        plan = direct(raw,args.shots,args.seed,ROOT/"work"/"steering-language")
    validate(plan)
    plan_path = out/("plan-"+digest(plan)[:12]+".json")
    dump(plan_path,plan)
    print(f"Editable plan: {plan_path}",flush=True)
    if args.plan_only:
        return
    print("Building the animation with CPU Cycles and CPU compositing.",flush=True)
    dest,report = build(plan,out,args.blend.resolve() if args.blend else None)
    with staging(out) as publish:
        for filename in ("draft.mp4","depth.mp4","storyboard.jpg"):
            shutil.copyfile(dest/filename,publish/filename)
            os.replace(publish/filename,out/filename)
        dump(publish/"latest.json",{"take":str(dest.relative_to(out)),"plan":str(plan_path.relative_to(out)),
                                    "frames":report["settings"]["frames"],"warnings":report["warnings"]})
        os.replace(publish/"latest.json",out/"latest.json")
    print(f"Draft: {dest/'draft.mp4'}\nStage: {dest/'stage.blend'}",flush=True)
    for warning in report["warnings"]:
        print(warning)


if __name__=="__main__":
    main()
