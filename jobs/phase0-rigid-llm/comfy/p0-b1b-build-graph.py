"""Phase 0 Lane B retry (B1b): same graph as p0-b1-build-graph.py, but the guide
video is capped at 22 frames — the value local_film/pipeline.py uses for its
proven motion_ref path (continuation overlap).

Why: the full 124-frame guide run (prompt e055d589, submitted 02:43:14) stalled
in sampler init: 30 min with the progress bar stuck at 0/4 "Model Initializing",
GPU at 38 W / 38 C (idle) with 15.8 GB resident, interrupt ignored, had to
taskkill the ComfyUI process. The 124-frame guide batch is a 32,560-token
prefix (VSA geometry log line); this retry tests whether the guide size is
what stalls init. If B1b renders, the finding is "guide works capped, not full
length"; if it stalls the same way, the blocker is the ReferenceToVideo +
AddGuide combination, not the guide length.
"""
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # jobs/phase0-rigid-llm/comfy -> film-pipeline
BASE = ROOT / "comfy-local"
JOB = ROOT / "jobs" / "phase0-rigid-llm"
ADDRESS = "http://127.0.0.1:8191"
STATE_FILE = BASE / "phase0-b1b-submission.json"
SEED = 5002
FRAMES = 124
GUIDE_CAP = 22  # retry: repo-proven motion_ref overlap value, not the full guide


def api(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        ADDRESS + path, data=body, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=60) as resp:
        return json.load(resp)


def build_graph():
    graph = json.loads((BASE / "ref2va-audio-comparison-graph.json").read_text())
    guide_src = JOB / "guide" / "p0-b1-guide.mp4"
    silence_src = JOB / "audio" / "p0-b1-silence.wav"
    kate_src = ROOT / "series" / "characters" / "kate" / "portrait.png"
    james_src = ROOT / "series" / "characters" / "james" / "portrait.png"
    for p in (guide_src, silence_src, kate_src, james_src):
        if not p.is_file():
            raise FileNotFoundError(f"Phase 0 input missing: {p}")
    (BASE / "input").mkdir(parents=True, exist_ok=True)

    def copy_in(src, name):
        dest = BASE / "input" / name
        if not dest.exists():
            shutil.copyfile(src, dest)
        return name

    guide = copy_in(guide_src, "phase0-b1-guide.mp4")
    silence = copy_in(silence_src, "phase0-b1-silence.wav")
    kate = copy_in(kate_src, "phase0-b1-kate.png")
    james = copy_in(james_src, "phase0-b1-james.png")

    # Reference images for the two characters.
    graph["170"] = {"class_type": "LoadImage", "inputs": {"image": kate}}
    graph["171"] = {"class_type": "LoadImage", "inputs": {"image": james}}
    graph["157"] = {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
        "clip": ["13", 0], "vae": ["11", 0], "audio_vae": ["24", 0],
        "width": 1280, "height": 704, "length": FRAMES,
        "ref_image_size": "match",
        "ref_images.ref_image_0": ["170", 0],
        "ref_images.ref_image_1": ["171", 0],
        "prompt": (
            "James, a man in his late twenties in an orange-red survival suit and "
            "ear-flap hat, enters through the door at frame left and walks across a "
            "polar station radio room to Kate, a woman in her late forties in a navy "
            "wool jacket, seated at the radio desk at frame right. The camera "
            "dollies right, tracking James, keeping him centre frame. Kate turns "
            "her head toward him as he arrives. Keep both characters' faces, hair, "
            "clothing and the room consistent with the reference images. Follow the "
            "supplied guide video for blocking and camera movement.")}}
    graph["160"] = {"class_type": "SenseNovaH3DistilledBridge", "inputs": {
        "conditioning": ["157", 0],
        "distilled_adapter": "MiniMaxH3_SemanticBridge_v1.safetensors",
        "alpha": 0.15, "magnitude_match": "per_token"}}

    # Full-length guide video -> resize -> AddGuide at frame 0.
    graph["162"] = {"class_type": "VHS_LoadVideo", "inputs": {
        "video": guide, "force_rate": 24, "custom_width": 0, "custom_height": 0,
        "frame_load_cap": GUIDE_CAP, "skip_first_frames": 0, "select_every_nth": 1,
        "format": "H3"}}
    graph["142"]["inputs"].update({"image": ["162", 0], "width": 1280, "height": 704})
    graph["163"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
        "positive": ["160", 0], "latent": ["157", 1], "vae": ["11", 0],
        "image": ["142", 0], "frame_idx": 0}}
    graph["19"]["inputs"]["positive"] = ["163", 0]

    # Silent audio track (shot has no dialogue; the sync node needs an input).
    graph["18"]["inputs"]["audio"] = silence
    graph["19"]["inputs"]["start_seconds"] = 0.0
    graph["130"]["inputs"]["noise_seed"] = SEED
    graph["136"]["inputs"]["filename_prefix"] = "phase0/b1b-james-crosses"
    graph.pop("5", None)  # unused once 142 takes its image from the guide video
    return graph


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("submit", "status"):
        print(__doc__)
        return 2
    if sys.argv[1] == "status":
        state = json.loads(STATE_FILE.read_text())
        result = api("/history/" + state["prompt_id"])
        print(json.dumps(result, indent=2))
        return 0
    if STATE_FILE.exists():
        raise RuntimeError(f"State already exists: {STATE_FILE}; inspect it, do not resubmit blindly")
    t0 = time.time()
    try:
        api("/system_stats")
    except Exception as exc:
        raise RuntimeError("ComfyUI is not listening on 127.0.0.1:8191; start it first "
                           "(jobs\\start_comfy_local.py)") from exc
    graph = build_graph()
    state = {"phase": "submitting", "created": t0, "seed": SEED,
             "frames": FRAMES, "graph": graph}
    STATE_FILE.write_text(json.dumps(state, indent=2))
    result = api("/prompt", {"prompt": graph, "client_id": "film-pipeline-phase0-b1b"})
    state.update({"phase": "submitted", "prompt_id": result["prompt_id"],
                  "submit_seconds": time.time() - t0, "response": result})
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(json.dumps({"prompt_id": result["prompt_id"],
                      "submit_seconds": round(time.time() - t0, 1)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
