"""Render a film's full asset catalog, or one ID; alternate takes go in separate directories."""
import argparse
import hashlib
import json
import re
import secrets
import shutil
from graphlib import TopologicalSorter
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from opening_frames import render
from make_film import exclusive

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def generate(script, selected, take, seed=None):
    film = json.loads(script.read_text(encoding="utf-8-sig"))
    assets = film["assets"]
    if not all(re.fullmatch(r"[a-zA-Z0-9_-]+", key) for key in assets):
        raise ValueError("Invalid asset ID")
    if selected and selected not in assets:
        raise ValueError(f"Unknown asset {selected}")
    if take < 1 or (take > 1 and not selected):
        raise ValueError("Select one asset when creating an alternate take")
    for key, asset in assets.items():
        for ref in asset["references"] + ([asset["parent"]] if asset["parent"] else []):
            if ref not in assets:
                raise ValueError(f"{key} references unknown {ref}")
    order = list(TopologicalSorter({k:v["references"] for k,v in assets.items()}).static_order())
    root = script.parent/"asset-library"
    root.mkdir(exist_ok=True)
    with exclusive(root):
        digest = sha(script)
        lock = root/"script.sha256"
        defaults = {"width":1024,"height":768}
        fmt = defaults | film.get("asset_format", {})
        if lock.exists() and lock.read_text().strip() != digest:
            snapshot = root/"source-at-generation.json"
            if not snapshot.exists() or sha(snapshot) != lock.read_text().strip():
                raise ValueError("Cannot verify the original asset specifications")
            original = json.loads(snapshot.read_text(encoding="utf-8-sig"))
            if (original["style"] != film["style"] or
                    any(assets.get(k) != v for k,v in original["assets"].items())):
                raise ValueError("Asset definitions changed after generation")
            original_fmt = defaults | original.get("asset_format", {})
            if any(fmt[key] != original_fmt[key] for key in defaults):
                raise ValueError("Asset generation settings changed")
        elif not lock.exists():
            shutil.copyfile(script, root/"source-at-generation.json")
            lock.write_text(digest)
        job = root if take==1 else root/"alternates"/selected/str(take)
        job.mkdir(parents=True,exist_ok=True)
        looks=job/"looks"
        looks.mkdir(exist_ok=True)
        manifest=job/"assets.json"
        records=json.loads(manifest.read_text()) if manifest.exists() else {}
        for name,rec in records.items():
            if "definition" in rec and rec["definition"] != assets.get(name):
                raise ValueError(f"Frozen asset definition changed: {name}")
            if sha(looks/(name+".png"))!=rec["sha256"]:
                raise ValueError(f"Frozen image changed: {name}")
        keys=[selected] if selected else order
        recipe={}
        base_seed = seed if seed is not None else fmt.get("seed")
        for name in keys:
            if name in records:
                continue
            a=assets[name]
            for ref in a["references"]:
                if ref in recipe:
                    continue
                source=root/"looks"/(ref+".png")
                if not source.is_file():
                    raise ValueError(f"Generate dependency {ref} before {name}")
                if job!=root:
                    shutil.copyfile(source,looks/source.name)
            asset_seed = secrets.randbits(32) if base_seed is None else int(
                hashlib.sha256(f"{base_seed}/{name}/{take}".encode()).hexdigest()[:8],16)
            recipe[name]=dict(prompt=film["style"]+" "+a["description"],references=a["references"],seed=asset_seed)
        if recipe:
            (job/"opening-frames.json").write_text(json.dumps(dict(width=fmt["width"],height=fmt["height"],shots=recipe),indent=2))
            render(job,Path(__file__).resolve().parents[1]/"runtime")
            for key in recipe:
                path=looks/(key+".png")
                with Image.open(path) as im:
                    im.verify()
                records[key]=dict(sha256=sha(path),seed=recipe[key]["seed"],script_sha256=digest,definition=assets[key])
            manifest.write_text(json.dumps(records,indent=2))
        ids=[k for k in assets if k in records]
        board=Image.new("RGB",(900,((len(ids)+2)//3)*250),"#16191c")
        draw=ImageDraw.Draw(board)
        for i,key in enumerate(ids):
            x,y=i%3*300,i//3*250
            with Image.open(looks/(key+".png")) as im:
                board.paste(ImageOps.contain(im.convert("RGB"),(296,220)),(x+2,y+2))
            draw.text((x+8,y+225),assets[key]["label"],fill="white")
        board.save(job/"review.jpg",quality=92)
        print(job/"review.jpg",flush=True)

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("script",type=Path)
    cli.add_argument("--asset")
    cli.add_argument("--seed",type=int,help="Optional base seed for new asset sheets")
    cli.add_argument("--take",type=int,default=1)
    args=cli.parse_args()
    generate(args.script.resolve(),args.asset,args.take,args.seed)
