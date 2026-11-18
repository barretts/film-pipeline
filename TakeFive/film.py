"""TakeFive: turn a dispatch-office scene into a local film."""
import argparse
from pathlib import Path
import sys
from takefive.production import assemble, render


def main():
    p=argparse.ArgumentParser(description=__doc__)
    cmd=p.add_subparsers(dest="action",required=True)
    film=cmd.add_parser("render",help="Render a prose scene or a previously saved scene.json")
    film.add_argument("script",type=Path)
    film.add_argument("--out",type=Path,default=Path(__file__).resolve().parent/"output")
    film.add_argument("--width",type=int,default=1280)
    film.add_argument("--fresh",action="store_true",help="Render fresh picture from the saved inputs")
    film.add_argument("--reuse",type=Path,help="Reuse matching voices and approved takes from this bundle")
    cut=cmd.add_parser("assemble",help="Rebuild the exact edit from a finished bundle")
    cut.add_argument("bundle",type=Path)
    cut.add_argument("output",type=Path)
    replace=cmd.add_parser("finish",help="Cut in locally produced replacement pictures over the same soundtrack")
    replace.add_argument("bundle",type=Path)
    replace.add_argument("--takes",type=Path,required=True,help="Folder with one or more named shot MP4s")
    replace.add_argument("--out",type=Path,required=True)
    frames=cmd.add_parser("looks",help="Generate five reference stills using FLUX.2 klein in local ComfyUI")
    frames.add_argument("bundle",type=Path)
    frames.add_argument("--out",type=Path,required=True)
    frames.add_argument("--port",type=int,default=8188)
    frames.add_argument("--width",type=int,default=768)
    frames.add_argument("--seed",type=int,default=7624)
    frames.add_argument("--style",default="Handcrafted stop-motion film, warm daylight and painted wood.")
    frames.add_argument("--model",default="flux-2-klein-4b-fp8.safetensors")
    frames.add_argument("--encoder",default="qwen_3_4b.safetensors")
    frames.add_argument("--vae",default="flux2-vae.safetensors")
    ai=cmd.add_parser("neural",help="Render guided takes with a local LTX-2.5 installation")
    ai.add_argument("bundle",type=Path)
    ai.add_argument("--config",type=Path,required=True)
    ai.add_argument("--out",type=Path,required=True)
    ai.add_argument("--looks",type=Path,help="Folder of actor/layout-conditioned look PNGs")
    ai.add_argument("--shot",action="append",choices=("arrival","employee","manager","departure","street"))
    options=p.parse_args()
    if options.action=="assemble":
        assemble(options.bundle.resolve(),options.output.resolve())
        print(options.output.resolve())
    elif options.action=="render":
        result=render(options.script,options.out,options.width,options.fresh,options.reuse)
        print(result/"film.mp4")
    elif options.action=="finish":
        from takefive.finishing import finish
        result=finish(options.bundle,options.out,{p.stem:p for p in options.takes.glob("*.mp4")},"Imported local picture")
        print(result/"film.mp4")
    elif options.action=="looks":
        from takefive.comfy import looks
        from urllib.error import URLError
        try:
            looks(options.bundle.resolve(),options.out.resolve(),options.port,options.width,options.style,
                  (options.model,options.encoder,options.vae),options.seed)
        except URLError as error:
            raise ValueError(f"Cannot generate stills on the local ComfyUI port {options.port}: {error}") from error
        print(options.out.resolve())
    else:
        from takefive.finishing import neural
        result=neural(options.bundle.resolve(),options.config,options.out,options.looks,options.shot)
        print(result/"film.mp4")


if __name__=="__main__":
    import subprocess
    try:
        main()
    except (ValueError, KeyError, FileNotFoundError, RuntimeError, subprocess.SubprocessError) as error:
        sys.exit(f"TakeFive: {error}")
