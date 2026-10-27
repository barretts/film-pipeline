"""Generate three original local first frames for motion testing."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from studio_mcp import Studio, key_from_environment, record_call

MODEL = "unsloth/FLUX.2-klein-4B"
PROMPTS = [
    "Vertical cinematic frame from an original hand-drawn anime short. An original adult woman with short dark-blue hair, "
    "wearing a loose rust-red cardigan over a modest ink-blue dress, is framed from mid-thigh up in a dim bedroom. "
    "She is standing three-quarters toward the camera and looking at an old brass pocket watch in one hand, "
    "while the other hand holds a folded letter. Both complete hands and her full expressive face are unobstructed. "
    "Sophisticated anime linework, soft painted shadows, moonlight and a warm lamp, cinematic composition, "
    "natural adult proportions, original character, no text, no watermark.",
    "Vertical cinematic frame from an original hand-drawn 2D animated feature. An adult woman with auburn hair, "
    "wearing a modest forest-green coat, is framed from mid-thigh up beside a slightly open wooden door. "
    "She is looking back at the camera; one hand rests on the door handle while the other holds a small lantern. "
    "Her entire face and both complete hands are visible. Beautiful traditional inked cel-animation and painted "
    "storybook backgrounds, expressive adult features, textured brushwork, deep green and warm ivory light, "
    "Disney-inspired feature-animation mood, original character, no text, no watermark.",
    "Vertical cinematic frame from an original stylized 3D animated feature. An adult woman with dark curly hair "
    "wearing a modest violet jacket is framed from mid-thigh up beside an old oval mirror. She looks toward the "
    "mirror and lifts one hand toward it; the other hand rests at her side. Her full expressive face and both complete "
    "hands are visible. Polished expressive stylized 3D animation, appealing adult character design, dimensional "
    "lighting, warm light on her face against deep teal shadows, DreamWorks-inspired feature-animation energy, "
    "original character, no text, no watermark.",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-job", help="poll an existing Studio load job without starting another")
    args = parser.parse_args()
    outdir = ROOT / "stills" / "reels" / "full-motion"
    paths = [outdir / f"{i:02d}.png" for i in range(1, 4)]
    if any(p.exists() for p in paths):
        raise RuntimeError("A target image already exists; refusing to overwrite")
    outdir.mkdir(parents=True, exist_ok=True)
    key = key_from_environment()
    studio = Studio(key, timeout=300)

    def call(name, arguments):
        start = time.time()
        try:
            response = studio.rpc("tools/call", {"name": name, "arguments": arguments})
            ok = not response.get("isError", False)
        except Exception as exc:
            response, ok = {"error": str(exc).replace(key, "<redacted>")}, False
        seq = record_call(name, arguments, response, start, time.time(), key, ok)
        print(f"{name}: seq={seq} ok={ok} elapsed={time.time()-start:.1f}s", flush=True)
        if not ok:
            raise RuntimeError(f"{name} failed; inspect redacted evidence seq {seq}")
        return response.get("structuredContent", {})

    loaded = False
    try:
        job = args.resume_job
        response = {"status": "loading", "job_id": job} if job else call(
            "load_model", {"kind": "image", "model": MODEL, "memory_mode": "low_vram",
                           "transformer_quant": "auto", "wait_s": 50})
        while response.get("status") in ("loading", "running", "pending"):
            job = response.get("job_id") or response.get("id") or job
            if not job:
                raise RuntimeError("Model load still active without job ID; inspect Studio before retrying")
            print(f"load job: {job}", flush=True)
            response = call("get_job", {"kind": "load", "id": job, "wait_s": 50})
            if response.get("status") == "completed":
                response = response.get("load") or {}
        if not response.get("loaded"):
            raise RuntimeError("Image model did not report a completed load")
        loaded = True
        print("model loaded; advertised workflows:", response.get("workflows"), flush=True)
        for i, (path, prompt) in enumerate(zip(paths, PROMPTS), 1):
            response = call("generate_image", {"prompt": prompt, "width": 704, "height": 1280,
                "steps": 4, "guidance": 1.0, "seed": 5100 + i, "return_media": "link"})
            images = response.get("images") or []
            if len(images) != 1:
                raise RuntimeError(f"Expected one image for {i}; got {len(images)}")
            url = images[0].get("url") or images[0].get("download_url")
            parsed = urllib.parse.urlsplit(url or "")
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != 8888:
                raise RuntimeError("Unexpected image URL; refusing nonlocal transfer")
            request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
            with studio.opener.open(request, timeout=120) as server:
                content = server.read()
            fd, name = tempfile.mkstemp(prefix=".first-frame-", suffix=".png", dir=outdir)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                with Image.open(name) as image:
                    if image.size != (704, 1280):
                        raise RuntimeError(f"Unexpected image dimensions {image.size}")
                    image.verify()
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            print(f"saved {path}", flush=True)
    finally:
        if loaded:
            call("unload_model", {"kind": "image"})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
