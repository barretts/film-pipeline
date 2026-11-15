"""Lane B fix run — parametrized local MiniMax H3 ReferenceToVideo + AddGuide builder.

Usage on file-cabinet (from F:\\film-pipeline, SwarmUI venv python):
  python jobs\\phase0-rigid-llm\\comfy\\lane-b-variant.py submit --variant V1-prompt-map --guide jobs/phase0-rigid-llm/guide/p0-b1-guide.mp4 --cap 22 --prompt-file jobs/phase0-rigid-llm/prompts/V1.txt --take phase0/V1-prompt-map --bridge-alpha 0.15 --mode full
  python ... lane-b-variant.py status --variant V1-prompt-map

Modes:
  full      — one AddGuide, guide clip (cap frames) anchored at frame 0 (B1b baseline)
  start_end — two AddGuide nodes: 1-frame first guide frame at 0, 1-frame last at 123
  chunked   — two AddGuide nodes: 22f guide at 0, 22f guide (frames 103-124) at 102
  none      — no AddGuide; conditioning straight from the bridge (prompt + refs only)
Guide can be any mp4 under film-pipeline; it is copied into comfy-local/input.
Prompt is read from --prompt-file (UTF-8). Seed default 5002.
"""
import argparse, json, shutil, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "comfy-local"
JOB = ROOT / "jobs" / "phase0-rigid-llm"
ADDRESS = "http://127.0.0.1:8191"
SEED = 5002
FRAMES = 124

def api(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(ADDRESS + path, data=body, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=60) as resp:
        return json.load(resp)

def copy_in(src, name):
    dest = BASE / "input" / name
    if not dest.exists():
        shutil.copyfile(src, dest)
    return name

def build_graph(args, prompt):
    graph = json.loads((BASE / "ref2va-audio-comparison-graph.json").read_text())
    guide_src = ROOT / args.guide
    silence_src = JOB / "audio" / "p0-b1-silence.wav"
    kate_src = ROOT / "series" / "characters" / "kate" / "portrait.png"
    james_src = ROOT / "series" / "characters" / "james" / "portrait.png"
    for p in (guide_src, silence_src, kate_src, james_src):
        if not p.is_file():
            raise FileNotFoundError(f"input missing: {p}")
    (BASE / "input").mkdir(parents=True, exist_ok=True)
    guide = copy_in(guide_src, f"lane-b-{args.variant}-guide.mp4")
    silence = copy_in(silence_src, "phase0-b1-silence.wav")
    kate = copy_in(kate_src, "phase0-b1-kate.png")
    james = copy_in(james_src, "phase0-b1-james.png")

    graph["170"] = {"class_type": "LoadImage", "inputs": {"image": kate}}
    graph["171"] = {"class_type": "LoadImage", "inputs": {"image": james}}
    graph["157"] = {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
        "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
        "width": 1280, "height": 704, "length": FRAMES,
        "ref_image_size": "match",
        "ref_images.ref_image_0": ["170", 0],
        "ref_images.ref_image_1": ["171", 0],
        "prompt": prompt}}
    graph["160"] = {"class_type": "SenseNovaH3DistilledBridge", "inputs": {
        "conditioning": ["157", 0],
        "distilled_adapter": "MiniMaxH3_SemanticBridge_v1.safetensors",
        "alpha": args.bridge_alpha, "magnitude_match": "per_token"}}
    if args.denoise is not None:
        graph["9"]["inputs"]["denoise"] = args.denoise
    if args.steps is not None:
        graph["9"]["inputs"]["steps"] = args.steps

    def vhs(node_id, cap, skip):
        graph[node_id] = {"class_type": "VHS_LoadVideo", "inputs": {
            "video": guide, "force_rate": 24, "custom_width": 0, "custom_height": 0,
            "frame_load_cap": cap, "skip_first_frames": skip, "select_every_nth": 1,
            "format": "H3"}}
    def resize(node_id, src_node):
        graph[node_id] = {"class_type": "ImageResizeKJv2", "inputs": {
            "image": [src_node, 0], "width": 1280, "height": 704,
            "upscale_method": "lanczos", "keep_proportion": "crop",
            "pad_color": "0, 0, 0", "crop_position": "center",
            "divisible_by": 32, "device": "cpu"}}
    def addguide(node_id, positive_src, resize_node, frame_idx):
        graph[node_id] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
            "positive": [positive_src, 0], "latent": ["157", 1], "vae": ["11", 0],
            "image": [resize_node, 0], "frame_idx": frame_idx}}

    if args.mode == "full":
        vhs("162", args.cap, 0)
        resize("142", "162")
        addguide("163", "160", "142", 0)
        graph["19"]["inputs"]["positive"] = ["163", 0]
    elif args.mode == "start_end":
        # VHS_LoadVideo with cap 1 returns an empty batch (V5 failed in ImageResizeKJv2:
        # "stack expects a non-empty TensorList"). Use LoadImage on the guide PNGs instead.
        first_src = JOB / "guide" / "frames" / "frame_0001.png"
        last_src = JOB / "guide" / "frames" / "frame_0124.png"
        for pth in (first_src, last_src):
            if not pth.is_file():
                raise FileNotFoundError(f"guide frame missing: {pth}")
        first = copy_in(first_src, f"lane-b-{args.variant}-first.png")
        last = copy_in(last_src, f"lane-b-{args.variant}-last.png")
        graph["180"] = {"class_type": "LoadImage", "inputs": {"image": first}}
        resize("142", "180")
        addguide("163", "160", "142", 0)
        graph["181"] = {"class_type": "LoadImage", "inputs": {"image": last}}
        resize("143", "181")
        addguide("164", "163", "143", 123)
        graph["19"]["inputs"]["positive"] = ["164", 0]
    elif args.mode == "chunked":
        vhs("162", 22, 0)
        resize("142", "162")
        addguide("163", "160", "142", 0)
        vhs("165", 22, 102)
        resize("143", "165")
        addguide("164", "163", "143", 102)
        graph["19"]["inputs"]["positive"] = ["164", 0]
    elif args.mode == "none":
        graph["19"]["inputs"]["positive"] = ["160", 0]
    else:
        raise ValueError("unknown mode: " + args.mode)

    graph["18"]["inputs"]["audio"] = silence
    graph["19"]["inputs"]["start_seconds"] = 0.0
    graph["130"]["inputs"]["noise_seed"] = args.seed
    graph["136"]["inputs"]["filename_prefix"] = args.take
    graph.pop("5", None)
    return graph

def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["submit", "status"])
    p.add_argument("--variant", required=True)
    p.add_argument("--guide", default="jobs/phase0-rigid-llm/guide/p0-b1-guide.mp4")
    p.add_argument("--cap", type=int, default=22)
    p.add_argument("--prompt-file")
    p.add_argument("--take", required=True)
    p.add_argument("--bridge-alpha", type=float, default=0.15)
    p.add_argument("--mode", choices=["full", "start_end", "chunked", "none"], default="full")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--denoise", type=float, default=None)
    p.add_argument("--steps", type=int, default=None)
    args = p.parse_args()
    state_file = BASE / f"phase0-{args.variant}-submission.json"
    if args.cmd == "status":
        state = json.loads(state_file.read_text())
        print(json.dumps(api("/history/" + state["prompt_id"]), indent=2))
        return 0
    if state_file.exists():
        raise RuntimeError(f"State already exists: {state_file}; inspect it, do not resubmit blindly")
    prompt = (ROOT / args.prompt_file).read_text(encoding="utf-8").strip() if args.prompt_file else ""
    if not prompt:
        raise RuntimeError("prompt file required and must be non-empty")
    t0 = time.time()
    try:
        api("/system_stats")
    except Exception as exc:
        raise RuntimeError("ComfyUI is not listening on 127.0.0.1:8191; start it first (jobs\\start_comfy_local.py)") from exc
    graph = build_graph(args, prompt)
    state = {"phase": "submitting", "created": t0, "seed": args.seed, "frames": FRAMES,
             "variant": args.variant, "mode": args.mode, "guide": args.guide, "cap": args.cap,
             "bridge_alpha": args.bridge_alpha, "denoise": args.denoise, "steps": args.steps,
             "prompt": prompt, "take": args.take, "graph": graph}
    state_file.write_text(json.dumps(state, indent=2))
    result = api("/prompt", {"prompt": graph, "client_id": f"film-pipeline-lane-b-{args.variant}"})
    state.update({"phase": "submitted", "prompt_id": result["prompt_id"],
                  "submit_seconds": time.time() - t0, "response": result})
    state_file.write_text(json.dumps(state, indent=2))
    print(json.dumps({"variant": args.variant, "prompt_id": result["prompt_id"],
                      "submit_seconds": round(time.time() - t0, 1)}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
