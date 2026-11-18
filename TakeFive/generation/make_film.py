"""Render an English short film from a paragraph using the installed local models."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import re
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0,str(ROOT))
import h3
import opening_frames
from inspect_take import defects, inspect
from story_pictures import STYLE, recipes, seed_for
from takefive.director import draft
from takefive.finishing import checksum, finish
from takefive.production import staging, verify_film
from takefive.script import WORK, binary, digest, dump, file_stamp
from takefive.story_audio import write_audio


@contextmanager
def exclusive(project):
    """Let a second launch of the same job wait or reuse its result. OS releases on exit."""
    import msvcrt
    with (project/".lock").open("a+b") as handle:
        if handle.tell()==0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        waiting = False
        while True:
            try:
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                break
            except OSError:
                if not waiting:
                    print("Waiting for the other instance working on this film.",flush=True)
                    waiting = True
                time.sleep(2)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)


def inputs_signature(runtime):
    source = [Path(__file__),*(HERE/f for f in ("story_pictures.py","inspect_take.py","opening_frames.py",
              "h3.py","prepare.py","workflows.py","local_engine.py","realistic.py","setup_h3.py","machine.json")),
              *(ROOT/"takefive"/f for f in ("director.py","story_audio.py","audio.py","script.py","production.py","finishing.py"))]
    photos = ["diffusion_models/flux-2-klein-4b-fp8.safetensors","text_encoders/qwen_3_4b.safetensors",
              "vae/flux2-vae.safetensors"]
    model = Path(os.environ.get("TAKEFIVE_MODEL",runtime/"planner.gguf"))
    files = [model,*(runtime/"h3-models"/p for p in h3.WEIGHTS),
             *(runtime/"generation-models"/p for p in photos),*sorted((runtime/"voices").glob("*.onnx*")),
             *(Path(binary(name)) for name in ("llama-completion","piper","rhubarb","ffmpeg","ffprobe"))]
    return digest({p.name:checksum(p) for p in source},[file_stamp(p) for p in files],h3.WEIGHTS)


def compile_story(story, count, seed, style, project):
    print("Planning cast, locations, action and dialogue on the CPU.",flush=True)
    plan = draft(story,count,seed,WORK/"story-plans")
    names = [f"shot{i:02}" for i in range(1,len(plan["shots"])+1)]
    dump(project/"director.json",plan)
    print(f"Synthesizing the dialogue and scheduling {len(names)} shots.",flush=True)
    timing = write_audio(plan,names,project,WORK/"story-voices",seed)
    scene = {k:plan[k] for k in ("title","people","places")}
    scene["shots"] = []
    for key,s in zip(names,plan["shots"],strict=True):
        dialogue = ([{"speaker":s["speaker"],"text":s["line"],
                      "source":"on_screen" if s["mode"]=="onscreen" else s["mode"]}] if s["line"] else [])
        scene["shots"].append({"id":key,**s,"dialogue":dialogue})
    dump(project/"scene.json",scene)
    dump(project/"render.json",{"format":1,"renderer":"Unattended local text film","width":1280,
                                "timing":timing,"shot_keys":{}})
    (project/"edit.ffconcat").write_text("ffconcat version 1.0\n"+"".join(f"file shots/{n}.mp4\n" for n in names),
                                         encoding="ascii")
    stills,direction = recipes(plan,names,timing,seed,style)
    dump(project/"opening-frames.json",stills)
    dump(project/"motion.json",direction)
    return direction, timing


def choose_takes(project, runtime, direction, seed):
    looks = project/"looks"
    keys = list(direction["shots"])
    jobs = WORK/"story-motion"
    models, nodes = runtime/"h3-models", runtime/"h3-nodes"
    machine = h3.read(HERE/"machine.json")
    job, plan = h3.prepare(project,looks,direction,jobs,machine)
    takes = h3.render_takes(job,plan,models,nodes,keys)
    attempts = {}
    selected = {}
    def assess(name, path, receipt):
        shot = receipt["shots"][name]
        return {"seed":receipt["direction"]["shots"][name]["seed"],"graph_key":shot["key"],
                "sha256":checksum(path),"inspection":inspect(path,shot["frames"])}
    for name,path in takes.items():
        attempts[name] = [assess(name,path,plan)]
        selected[name] = 0
    flagged = [name for name in keys if any(defects(attempts[name][0]["inspection"]))]
    plans = [job]
    if flagged:
        print(f"Automatic second takes for {len(flagged)} clips with a freeze, black picture or possible internal cut.",flush=True)
        alternate = deepcopy(direction)
        for name in flagged:
            alternate["shots"][name]["seed"] = seed_for(seed,"second-take",name)
        altjob, altplan = h3.prepare(project,looks,alternate,jobs,machine)
        plans.append(altjob)
        for name,path in h3.render_takes(altjob,altplan,models,nodes,flagged).items():
            choice = assess(name,path,altplan)
            attempts[name].append(choice)
            if defects(choice["inspection"]) < defects(attempts[name][0]["inspection"]):
                takes[name], selected[name] = path, 1
    report = {"plans":[str(p/"plan.json") for p in plans],"attempts":attempts,"selected":selected,
              "flagged_after_selection":[n for n in keys if any(defects(attempts[n][selected[n]]["inspection"]))]}
    dump(project/"take-selection.json",report)
    return takes


def make(story, label, seed, count, style, output):
    runtime = ROOT/"runtime"
    signature = inputs_signature(runtime)
    key = digest(story,seed,count,style,signature)
    slug = re.sub(r"[^A-Za-z0-9_-]+","-",label).strip("-")[:60] or "film"
    project = output/(slug+"-"+key[:12])
    project.mkdir(parents=True,exist_ok=True)
    movie, receipt = project/"film.mp4", project/"run.json"
    with exclusive(project):
        if movie.is_file() and receipt.is_file():
            previous = h3.read(receipt)
            if previous["key"]==key and checksum(movie)==previous["sha256"]:
                verify_film(movie,previous["media"]["frames"],1280)
                print("Verified existing film. Reusing the finished render.",flush=True)
                return movie
        begin = time.monotonic()
        (project/"input.txt").write_text(story,encoding="utf-8")
        direction,timing = compile_story(story,count,seed,style,project)
        gpu_queue = WORK/"story-gpu"
        gpu_queue.mkdir(parents=True,exist_ok=True)
        with exclusive(gpu_queue):
            print("Generating local cast portraits, locations and opening frames.",flush=True)
            opening_frames.render(project,runtime)
            print("Rendering audio-conditioned MiniMax H3 footage.",flush=True)
            takes = choose_takes(project,runtime,direction,seed)
        cut = finish(project,project/"edits",takes,"Automatically directed local MiniMax H3 / Piper film")
        with staging(project) as temporary:
            ready = temporary/"film.mp4"
            shutil.copyfile(cut/"film.mp4",ready)
            media = verify_film(ready,timing["frames"],1280)
            os.replace(ready,movie)
            shutil.copyfile(cut/"board.jpg",project/"board.jpg")
            dump(temporary/"run.json",{"key":key,"sha256":checksum(movie),"input_sha256":checksum(project/"input.txt"),
                 "seed":seed,"style":style,"implementation":signature,"media":media,"shots":len(takes),
                 "seconds_to_render":round(time.monotonic()-begin,1),"edit":str(cut.relative_to(project)),
                 "take_selection":"take-selection.json","dialogue":"dialogue.json","opening_frames":"opening-takes.json"})
            os.replace(temporary/"run.json",receipt)
    return movie


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("story",nargs="?",type=Path,help="Plain UTF-8 text file, optionally with quoted dialogue")
    cli.add_argument("--seed",type=int,default=41,help="Repeatable starting seed")
    cli.add_argument("--shots",type=int,help="Number of camera shots, 1 to 16")
    cli.add_argument("--style",default=STYLE,help="Visual direction applied consistently across the film")
    cli.add_argument("--out",type=Path,default=ROOT/"output"/"text-films")
    args = cli.parse_args()
    if not 0 <= args.seed <= 2147483647:
        cli.error("--seed must be between 0 and 2147483647")
    if args.story:
        story, label = args.story.read_text(encoding="utf-8-sig"), args.story.stem
    elif sys.stdin.isatty():
        reply = input("Paste a story paragraph or enter its text file path:\n").strip()
        candidate = Path(reply.removeprefix('"').removesuffix('"'))
        try:
            file = candidate.is_file()
        except OSError:
            file = False
        story,label = (candidate.read_text(encoding="utf-8-sig"),candidate.stem) if file else (reply,"film")
    else:
        story,label = sys.stdin.read(),"film"
    if not story.strip():
        cli.error("Supply a nonempty film brief")
    print(make(story,label,args.seed,args.shots,args.style,args.out.resolve()),flush=True)


if __name__ == "__main__":
    main()
