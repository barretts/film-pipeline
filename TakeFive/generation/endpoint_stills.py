"""Re-render an existing endpoint recipe using Terra's descriptions of its Blender frames."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import uuid4

from opening_frames import HERE, render


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("film", type=Path)
    parser.add_argument("shot")
    parser.add_argument("recipe", type=Path, help="Existing still recipe, or Blender shot folder for --describe-only")
    parser.add_argument("--describe-only", action="store_true")
    parser.add_argument("--model", default="gpt-6.1-terra")
    args = parser.parse_args()
    film = json.loads(args.film.read_text(encoding="utf-8-sig"))
    shot = next(s for s in film["shots"] if s["id"] == args.shot)
    board = args.film.resolve().parent/"asset-library"/"review.jpg"
    if args.describe_only:
        describe_take(film, shot, args.recipe.resolve(), board, args.model)
        return
    recipe = json.loads(args.recipe.read_text(encoding="utf-8-sig"))
    previous = args.recipe.resolve().parent
    job = previous.parent/("endpoint-"+uuid4().hex[:12])
    looks = job/"looks"
    looks.mkdir(parents=True)
    endpoints = ("first", "last")
    images = []
    for name in endpoints:
        refs = recipe["shots"][name]["references"]
        for ref in refs:
            if ref not in endpoints:
                shutil.copyfile(previous/"looks"/(ref+".png"), looks/(ref+".png"))
        images.append(looks/(refs[0]+".png"))
    refs = {key:recipe["shots"][key]["references"] for key in endpoints}
    prompts = describe(film, shot, job, board, args.model, images, refs)
    for name in endpoints:
        recipe["shots"][name]["prompt"] = prompts[name]
    (job/"opening-frames.json").write_text(json.dumps(recipe,indent=2), encoding="utf-8")
    render(job,HERE.parent/"runtime")


def describe_take(film, shot, target, board, model):
    images = [target/"first.png", target/"last.png"]
    return describe(film, shot, target, board, model, images,
                    {"first":"first.png","last":"last.png"})


def describe(film, shot, job, board, model, images, refs):
    context = dict(style=film["style"], location=film["locations"][shot["set"]], shot=shot,
                   assets={key:film["assets"][key] for key in shot.get("assets", [])},
                   image_references=refs)
    prompt = """Write the two final photographic image-generation prompts for this shot.
Attached images in order: first Blender blocking frame, last Blender blocking frame,
labeled asset library. Translate each marker into the corresponding actor. Describe
each endpoint as one standalone camera view at one instant. Specify screen positions,
scale, count of visible people, posture, gaze, clothing, landmarks, and visible prop
states. Carry identity, set layout and equipment across both. Resolve gestures from
the shot action. Distinguish reference sheets from what appears on camera. Give the
image model concise concrete visual instructions. Return only JSON with two nonempty
string fields first and last. Do not use tools.\n""" + json.dumps(context, ensure_ascii=False)
    (job/"request.txt").write_text(prompt, encoding="utf-8")
    output = job/"endpoint-prompts.json"
    cli = shutil.which("codex.cmd") or shutil.which("codex")
    if not cli:
        raise RuntimeError("Codex CLI required for endpoint planning")
    with tempfile.TemporaryDirectory() as scratch:
        command = [cli,"exec","--ephemeral","--skip-git-repo-check","--sandbox","read-only","-m",model]
        for image in [*images,board]:
            command.extend(["-i",str(image)])
        subprocess.run([*command,"-o",str(output),"-"], input=prompt.encode(), cwd=scratch, check=True)
    prompts = json.loads(output.read_text(encoding="utf-8-sig"))
    for name in ("first","last"):
        if not isinstance(prompts[name], str) or not prompts[name].strip():
            raise ValueError(f"Missing Terra prompt for {name}")
    return prompts


if __name__ == "__main__":
    main()
