"""Build one directed asset or shot; creative inputs are read only from the script."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def publish(target, film, shot, ffmpeg):
    width, height = film["size"]
    scale = f"scale={width}:{height}:flags=bilinear,setsar=1"
    subprocess.run([ffmpeg,"-v","error","-y","-framerate",str(film["fps"]),"-start_number","1",
                    "-i",str(target/"frames/%04d.png"),"-frames:v",str(shot["frames"]),"-vf",scale,
                    "-c:v","libx264","-pix_fmt","yuv420p",str(target/"steering.mp4")],check=True)
    for label, frame in [("first",1),("last",shot["frames"])]:
        subprocess.run([ffmpeg,"-v","error","-y","-i",str(target/"frames"/f"{frame:04d}.png"),
                        "-vf",scale,"-frames:v","1",str(target/(label+".png"))],check=True)


def generate_scenes(source, film, name, blender, model):
    from endpoint_stills import describe_take
    from film_assets import generate
    from scene_planner import plan
    from takefive.script import binary

    shots = film["shots"]
    if name:
        index = next((i for i,s in enumerate(shots) if s["id"] == name), None)
        if index is None:
            raise ValueError(f"Unknown shot {name}")
        shots = shots[:index+1]
    generate(source, None, 1)
    job = source.parent/"takes"/uuid4().hex
    job.mkdir(parents=True)
    scene_file, scene = plan(film, shots, source.parent/"asset-library"/"review.jpg", job, model)
    for shot in scene["shots"]:
        if name and shot["id"] != name:
            continue
        target = job/shot["id"]
        if target.parent != job or target.name in (".",".."):
            raise ValueError("Invalid shot directory")
        target.mkdir()
        subprocess.run([blender or binary("blender"), "-b", "--factory-startup", "-t", "8",
                        "--python-exit-code", "1", "-P", str(Path(__file__).with_name("directed_blender.py")),
                        "--", str(scene_file), shot["id"], str(target)], check=True)
        publish(target, scene, shot, binary("ffmpeg"))
        direction = next(item for item in shots if item["id"] == shot["id"])
        describe_take(film, direction, target, source.parent/"asset-library"/"review.jpg", model)
        print(target/"steering.mp4",flush=True)
    return job


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("script", type=Path)
    cli.add_argument("mode", choices=["asset", "shot", "video"], nargs="?", default="shot")
    cli.add_argument("name", nargs="?")
    cli.add_argument("--blender")
    cli.add_argument("--model", default="gpt-6.1-terra")
    cli.add_argument("--prepare-only",action="store_true",help="Prepare the video graph without starting H3")
    args = cli.parse_args()
    source = args.script.resolve()
    raw = source.read_bytes()
    film = json.loads(raw.decode("utf-8-sig"))
    if args.prepare_only and args.mode != "video":
        cli.error("--prepare-only applies to video")
    if args.mode in ("shot","video"):
        size = film.get("size")
        if (not isinstance(size, list) or len(size) != 2 or
                any(type(n) is not int or n <= 0 or n % 2 for n in size)):
            cli.error('film.json requires "size": [width, height] in positive even pixels')
    if args.mode == "video":
        from directed_video import find_take, video
        shots = [s for s in film["shots"] if not args.name or s["id"]==args.name]
        if not shots:
            cli.error("Unknown shot")
        targets = {s["id"]:find_take(source,film,s["id"]) for s in shots}
        if any(target is None for target in targets.values()):
            job = generate_scenes(source,film,args.name,args.blender,args.model)
            for key in targets:
                if targets[key] is None:
                    targets[key] = job/key
        for shot in shots:
            print(video(source,film,shot,targets[shot["id"]],args.model,args.prepare_only),flush=True)
        return
    if "geometry" not in film:
        if args.mode == "asset":
            from film_assets import generate
            generate(source,args.name,1)
        else:
            generate_scenes(source,film,args.name,args.blender,args.model)
        return
    dest = source.parent / "renders"
    dest.mkdir(exist_ok=True)
    digest = hashlib.sha256(raw).hexdigest()
    lock = dest / "script.sha256"
    if lock.exists() and lock.read_text().strip() != digest:
        raise ValueError("This production already used a different script revision")
    if not lock.exists():
        lock.write_text(digest)
    if args.mode == "asset":
        from opening_frames import render
        prompt = film["assets"][args.name]
        job = dest / "assets" / args.name
        job.mkdir(parents=True, exist_ok=True)
        recipe = {"width":1024,"height":768,"shots":{args.name:{
            "seed":int(hashlib.sha256((digest+args.name).encode()).hexdigest()[:8],16),
            "references":[],"prompt":film["style"]+" "+prompt}}}
        (job/"opening-frames.json").write_text(json.dumps(recipe))
        render(job,Path(__file__).resolve().parents[1]/"runtime")
        print(job/"looks"/(args.name+".png"))
    else:
        shot = next(s for s in film["shots"] if s["id"] == args.name)
        job = dest / "shots" / args.name
        job.mkdir(parents=True,exist_ok=True)
        subprocess.run([args.blender or "blender","-b","--factory-startup","-t","8","--python-exit-code","1","-P",
            str(Path(__file__).with_name("directed_blender.py")),"--",str(source),args.name,str(job)],check=True)
        publish(job, film, shot, "ffmpeg")


if __name__ == "__main__":
    main()
