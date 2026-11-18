"""Install the exact local models and node implementations used in the MiniMax reference shots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = {
    "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors": "9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779",
    "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors": "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6",
    "vae/minimax_h3_video_vae_fp16.safetensors": "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522",
    "vae/minimax_h3_audio_vae_fp32.safetensors": "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48",
    "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors": "5b9ab5ade15d0775676d01a907268a69a1468dc6033b3b0d3ded5502f3ebb84c",
    "loras/fasth3_vsa_gate.safetensors": "bf95408e335c4b0d6a1a44946a428a3e12849e6eab2de9566ecedae4a0043420",
    "semantic_bridge/MiniMaxH3_SemanticBridge_v1.safetensors": "ac0dc8ac05f545ebdee12e2fcebe4515b049f9cfd9558eb4887a9bf3fd6d562e",
}
VSA = "ComfyUI-Ref2VA-VSA"
BRIDGE = "MiniMax_H3_Semantic_Bridge"
AUDIO = "takefive_h3_audio"
EXTENSIONS = (VSA, BRIDGE, AUDIO)
INIT_HASH = "4c0f96b0f0006df5a559d09d44b8d521a32d7992383223310b5ba2a3f88e3e42"
NODES = {
    VSA+"/nodes.py": (VSA+"/nodes.py", "3df014ae5b6c8d23af84d2c49e57eaa663649bc9931d204b6c17e7955ebfe358"),
    VSA+"/__init__.py": (VSA+"/__init__.py", INIT_HASH),
    BRIDGE+"/nodes.py": (BRIDGE+"/nodes.py", "2b4ebe79f1bdddd8d9ea7cf77d5d7dad1cabc909da4a5d808a0f87b3caf0c445"),
    BRIDGE+"/__init__.py": (BRIDGE+"/__init__.py", INIT_HASH),
    AUDIO+"/__init__.py": ("ComfyUI_LC_AV_nodes/lc_h3_audio_sync.py", "6716976b9d35e1ac59a75517aedc04ab7f1051cc44f436576b3f37a5a9f2c670"),
}


def install_file(source, target, expected, link=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name+"."+uuid.uuid4().hex+".part")
    try:
        candidate = target
        if not target.exists():
            candidate = staged
            if link:
                try:
                    os.link(source, staged)
                except OSError:
                    shutil.copyfile(source, staged)
            else:
                shutil.copyfile(source, staged)
        with candidate.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError(f"Unexpected SHA-256 for {candidate}")
        if candidate == staged:
            os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)
    print("Verified", target.name, flush=True)


def install(library):
    runtime = ROOT/"runtime"
    for name, signature in WEIGHTS.items():
        install_file(library/"models"/name, runtime/"h3-models"/name, signature, link=True)
    for dest, (src, signature) in NODES.items():
        install_file(library/"custom_nodes"/src, runtime/"h3-nodes"/dest, signature)
    for source, destination in ((VSA+"/LICENSE", VSA+"/LICENSE"),
                                ("ComfyUI_LC_AV_nodes/LICENSE", AUDIO+"/LICENSE"),
                                (BRIDGE+"/README.txt", BRIDGE+"/README.txt")):
        shutil.copyfile(library/"custom_nodes"/source, runtime/"h3-nodes"/destination)
    (runtime/"h3-models"/"installed.json").write_text(json.dumps(WEIGHTS, indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path, help="Local Comfy library containing models and custom_nodes.")
    install(parser.parse_args().library.resolve())
