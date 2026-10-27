"""Generate three local SDXL reel backgrounds without logging download tokens."""
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from studio_mcp import Studio, key_from_environment, record_call
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = [
    "Vertical cinematic still, a lonely hand-painted bedroom at night, old brass bedside clock beside a tiny dim amber lamp, one thin line of warm light crossing the blue-black walls like a heartbeat, empty rumpled bed receding into shadow, intimate strange quiet, visible brush texture, restrained ink-blue, bone-white, rust and deep-green palette, dramatic composition with empty dark upper area, no writing.",
    "Vertical cinematic illustration of a single narrow antique wooden doorway, standing slightly open within a dark empty room, a second empty room visible beyond with another smaller open door, light spilling across worn floorboards, eerie calm, hand-painted 2D texture, muted ink blue and deep green shadows, bone-white light and a small rust-red accent, architectural depth, no writing.",
    "Vertical cinematic hand-painted illustration, an antique oval mirror on a dark wall, its glass reflecting an empty room and a small solitary lit chair that is not present outside the mirror, a thin rust-red thread tied to the mirror frame, moonlit ink blue and bone white, deep green shadows, subtle brush grain, unsettling dreamlike stillness, no writing.",
]
NEGATIVE = "people, person, woman, man, face, figure, silhouette, hands, letters, words, numbers, text, watermark, logo, duplicate objects, distorted anatomy, neon, oversaturated, photography"


def main():
    key = key_from_environment()
    studio = Studio(key, timeout=300)
    def call(name, args):
        started = time.time()
        try:
            result = studio.rpc("tools/call", {"name": name, "arguments": args})
            ok = not result.get("isError", False)
        except Exception as exc:
            result, ok = {"error": str(exc).replace(key, "<redacted>")}, False
        seq = record_call(name, args, result, started, time.time(), key, ok)
        print(f"{name}: seq={seq} ok={ok}", flush=True)
        if not ok:
            raise RuntimeError(f"{name} failed; see redacted MCP evidence seq {seq}")
        return result.get("structuredContent", {})
    target = ROOT / "stills" / "reels"
    target.mkdir(parents=True, exist_ok=True)
    for i in range(1, 4):
        if (target / f"{i:02}.png").exists():
            raise RuntimeError("output exists; refusing to overwrite existing art")
    loaded = False
    try:
        result = call("load_model", {"model": "unsloth/stable-diffusion-xl-base-1.0", "kind": "image", "memory_mode": "low_vram", "wait_s": 50})
        while result.get("status") == "loading":
            job = result.get("job_id")
            if not job:
                raise RuntimeError("model load running without an observable job id")
            result = call("get_job", {"kind": "load", "id": job, "wait_s": 50})
            if result.get("status") == "completed":
                result = result.get("load") or {}
        if not result.get("loaded"):
            raise RuntimeError("image model did not load")
        loaded = True
        for i, prompt in enumerate(PROMPTS, 1):
            result = call("generate_image", {"prompt": prompt, "negative_prompt": NEGATIVE,
                "width": 576, "height": 1024, "steps": 24, "guidance": 6.5,
                "seed": 2100 + i, "return_media": "link"})
            item = result.get("images", [])[0]
            url = item["url"]
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.port != 8888:
                raise RuntimeError("refusing to send local Studio key to nonlocal image URL")
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
            with studio.opener.open(req, timeout=120) as response:
                data = response.read()
            out = target / f"{i:02}.png"
            out.write_bytes(data)
            with Image.open(out) as image:
                if image.size != (576, 1024):
                    raise RuntimeError(f"unexpected image dimensions: {image.size}")
                image.verify()
            print(f"saved {out}", flush=True)
    finally:
        if loaded:
            call("unload_model", {"kind": "image"})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"reel background generation failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
