"""Create three original portraits and matching backgrounds with local SDXL."""
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from studio_mcp import Studio, key_from_environment, record_call
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NEGATIVE = ("child, teenager, minor, baby, boy, man, male, profile, side view, looking away, open mouth, "
            "teeth, hand over face, cropped face, extra faces, multiple people, "
            "existing character, copyrighted character, distorted anatomy, text, words, letters, watermark, logo")
SCENE_NEGATIVE = "people, person, woman, man, face, figure, silhouette, child, hands, letters, words, numbers, text, watermark, logo, distorted anatomy, neon, oversaturated"
JOBS = [
    ("characters/01.png", 768, 768, 3601, "Original adult woman in hand-drawn Japanese anime style, an expressive young adult woman with a short dark-blue bob haircut and warm gray eyes, face straight toward the camera, natural adult face proportions, from shoulders up, symmetrical eyes and nose and closed relaxed lips fully visible, gentle serious expression, soft cinematic lighting, clean linework and subtle cel shading, muted ink-blue and warm ivory, sophisticated atmospheric 2D feature animation, plain dark background, no words, no famous character"),
    ("characters/02.png", 768, 768, 3602, "Original adult woman in a Disney-inspired hand-drawn 2D animation feature visual style, face straight toward the camera, confident young adult woman with auburn shoulder-length hair and green eyes, believable adult facial proportions, from shoulders up, symmetrical eyes and nose and closed relaxed lips fully visible, gentle serious expression, soft light, expressive but natural features, rich hand-painted texture, muted deep green, warm ivory and rust, plain dark background, no words, no famous character"),
    ("characters/03.png", 768, 768, 3603, "Original adult woman in a DreamWorks-inspired 3D animated feature visual style, face straight toward the camera, adult woman with dark curly shoulder-length hair and hazel eyes, natural adult facial proportions, from shoulders up, symmetrical eyes and nose and closed relaxed lips fully visible, serious expressive gaze, refined 3D character sculpt and gentle cinematic light, muted ink blue, bone white and rust, plain dark background, no words, no famous character"),
    ("styled/01.png", 576, 1024, 3701, "Vertical 9:16 cinematic hand-drawn anime background, an empty haunted bedroom at night, an old clock and dim lamp on the bedside table, a soft thin red line of light suggesting a heartbeat, blue black shadows, visible clean ink lines and gentle cel shading, dark ink blue, muted rust and warm ivory, original background art, no text or characters"),
    ("styled/02.png", 576, 1024, 3702, "Vertical 9:16 cinematic background in a Disney-inspired hand-drawn 2D feature animation style, a narrow antique wooden door slightly open in an empty dark room, beyond it another doorway and warm light across aged floorboards, mysterious but beautiful, rich hand-painted texture, ink blue, deep green, rust and bone white palette, original background art, no text or characters"),
    ("styled/03.png", 576, 1024, 3703, "Vertical 9:16 cinematic 3D animated feature background in a DreamWorks-inspired style, an ornate oval mirror on a dark wall above a small chair, glass reflects an empty moonlit room, a thin rust-red thread tied to the mirror frame, softly detailed sculpted surfaces, deep green and ink blue shadows with bone-white light, eerie wonder, original background art, no text or characters"),
]


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
    for relative, *_ in JOBS:
        if (target / relative).exists():
            raise RuntimeError("output exists; refusing to overwrite")
    loaded = False
    try:
        result = call("load_model", {"model": "unsloth/stable-diffusion-xl-base-1.0", "kind": "image", "memory_mode": "low_vram", "wait_s": 50})
        while result.get("status") == "loading":
            job = result.get("job_id")
            if not job:
                raise RuntimeError("load is active without an observable job id")
            result = call("get_job", {"kind": "load", "id": job, "wait_s": 50})
            if result.get("status") == "completed":
                result = result.get("load") or {}
        if not result.get("loaded"):
            raise RuntimeError("image model did not load")
        loaded = True
        for relative, width, height, seed, prompt in JOBS:
            result = call("generate_image", {"prompt": prompt, "negative_prompt": NEGATIVE if relative.startswith("characters/") else SCENE_NEGATIVE,
                "width": width, "height": height, "steps": 28, "guidance": 6.5, "seed": seed, "return_media": "link"})
            url = result["images"][0]["url"]
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.port != 8888:
                raise RuntimeError("refusing to send Studio key to a nonlocal URL")
            request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
            with studio.opener.open(request, timeout=120) as response:
                content = response.read()
            out = target / relative
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)
            with Image.open(out) as image:
                if image.size != (width, height):
                    raise RuntimeError("unexpected image dimensions")
                image.verify()
            print(f"saved {out}", flush=True)
    finally:
        if loaded:
            call("unload_model", {"kind": "image"})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"reel style generation failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
