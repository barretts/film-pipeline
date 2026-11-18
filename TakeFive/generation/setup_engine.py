"""Install a private pinned Windows ComfyUI environment using CPU, disk and network."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
REVISION="65787d668397d230bf5839d69a0a7239e2dad378"


def install(root, checkout):
    if sys.version_info[:2] != (3,13) or os.name!="nt":
        raise ValueError("The pinned inference wheels are for Windows x64 and Python 3.13.")
    uv=shutil.which("uv")
    if not uv:
        raise ValueError("Install the uv Python package manager to restore this environment.")
    env=dict(os.environ,CUDA_VISIBLE_DEVICES="-1",HIP_VISIBLE_DEVICES="-1",ROCR_VISIBLE_DEVICES="-1",
             UV_NO_CONFIG="1",UV_NO_PROGRESS="1",PYTHONDONTWRITEBYTECODE="1")
    root.mkdir(parents=True,exist_ok=True)
    engine=root/"comfyui"
    stamp=engine/".takefive-revision"
    if not stamp.is_file():
        if engine.exists():
            raise ValueError(f"Preserving an existing unrecognized engine in {engine}")
        with tempfile.TemporaryDirectory(dir=root) as td:
            folder=Path(td)
            archive=folder/"comfy.zip"
            if checkout:
                subprocess.run(["git","-c","safe.directory="+checkout.resolve().as_posix(),"-C",str(checkout),
                                "archive","--format=zip","--prefix=source/","--output="+str(archive),REVISION],
                               env=env,check=True)
            else:
                with urlopen("https://codeload.github.com/Comfy-Org/ComfyUI/zip/"+REVISION,timeout=90) as response, archive.open("wb") as out:
                    shutil.copyfileobj(response,out)
            with ZipFile(archive) as zipfile:
                zipfile.extractall(folder)
            staging=next(p for p in folder.iterdir() if p.is_dir() and (p/"main.py").is_file())
            # Create the installed tree with the project's normal desktop read permissions.
            shutil.copytree(staging,engine)
            stamp.write_text(REVISION+"\n",encoding="ascii")
    if stamp.read_text().strip()!=REVISION:
        raise ValueError("The local engine has a different pinned revision.")
    env_dir=root/"inference-env"
    python=env_dir/"Scripts"/"python.exe"
    if not python.is_file():
        subprocess.run([uv,"venv","--python",sys.executable,str(env_dir)],env=env,check=True)
    requirements=[str(HERE/"engine-requirements.txt"),str(engine/"requirements.txt")]
    args=[uv,"--no-cache","pip","install","--python",str(python),"--default-index","https://pypi.org/simple","--link-mode","copy"]
    for req in requirements:
        args.extend(["-r",req])
    subprocess.run(args,env=env,check=True)
    result=subprocess.check_output([uv,"pip","freeze","--python",str(python)],env=env,text=True)
    (root/"inference-packages.txt").write_text(result,encoding="utf-8")
    print("Installed",python,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=HERE.parent/"runtime")
    parser.add_argument("--from-checkout",type=Path,help="Use this checkout as the source of the pinned upstream commit.")
    args=parser.parse_args()
    install(args.root.resolve(),args.from_checkout)
