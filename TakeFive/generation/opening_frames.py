"""Create a film's directed photographic starting frames using the installed local FLUX model."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from local_engine import private_engine
from realistic import accept, saved
from takefive.finishing import checksum
from takefive.production import staging
from takefive.script import digest, dump
from workflows import Graph, flux_still


def graph_for(name, cfg, width, height):
    g = Graph()
    model = g.add("UNETLoader", unet_name="flux-2-klein-4b-fp8.safetensors", weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name="qwen_3_4b.safetensors", type="flux2", device="default")
    vae = g.add("VAELoader", vae_name="flux2-vae.safetensors")
    views = (g.add("LoadImage", image=ref+".png") for ref in cfg["references"])
    image = flux_still(g,model,clip,vae,views,cfg["prompt"],cfg["seed"],width,height)
    node = g.add("SaveImage", images=image, filename_prefix="look-"+name)
    return g.nodes, node[0]


def render(project, runtime):
    recipe = json.loads((project/"opening-frames.json").read_text(encoding="utf-8"))
    looks = project/"looks"
    looks.mkdir(exist_ok=True)
    manifest = project/"opening-takes.json"
    receipts = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    jobs = HERE.parent/"work"/"opening-frames"
    jobs.mkdir(parents=True, exist_ok=True)
    runs = jobs/"runs"
    runs.mkdir(exist_ok=True)
    machine = {"python":str(runtime/"inference-env/Scripts/python.exe"),"comfy_directory":str(runtime/"comfyui")}
    with staging(jobs) as scratch:
        inputs = scratch/"input"
        inputs.mkdir()
        references = {r for shot in recipe["shots"].values() for r in shot["references"]}
        for ref in references-set(recipe["shots"]):
            shutil.copyfile(looks/(ref+".png"), inputs/(ref+".png"))
        with ExitStack() as session:
            engine = None
            for name, shot in recipe["shots"].items():
                width, height = shot.get("size", [recipe["width"], recipe["height"]])
                graph, output = graph_for(name, shot, width, height)
                sigs = {r:checksum(inputs/(r+".png")) for r in shot["references"]}
                key = digest(graph, sigs)
                cache = jobs/key[:18]
                photo = looks/(name+".png")
                take = saved(cache, "look", name)
                receipt = receipts.get(name,{})
                if not take and receipt.get("key")==key and photo.is_file() and checksum(photo)==receipt.get("sha256"):
                    take = photo
                if not take:
                    if engine is None:
                        engine = session.enter_context(private_engine(machine,runtime/"generation-models",scratch,runs))
                    print("Generating photographic opening",name,flush=True)
                    result = engine.run(graph, {output:("look",name)})[("look",name)]
                    take = accept(result,cache,"look",name,{})
                if take != photo:
                    with staging(looks) as temporary:
                        staged = temporary/photo.name
                        shutil.copyfile(take,staged)
                        os.replace(staged,photo)
                if name in references:
                    shutil.copyfile(take,inputs/(name+".png"))
                    if engine is not None:
                        shutil.copyfile(take,engine.inputs/(name+".png"))
                print("Saved",photo,flush=True)
                receipts[name] = {"key":key,"sha256":checksum(photo),"references":sigs}
                if cache.is_dir():
                    dump(cache/"graph.json",{"graph":graph,"references":sigs})
            with staging(project) as temporary:
                staged=temporary/manifest.name
                dump(staged,receipts)
                os.replace(staged,manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--runtime",type=Path,default=HERE.parent/"runtime")
    args = parser.parse_args()
    render(args.project.resolve(), args.runtime.resolve())
