"""Install the local Windows tools, voices and planner used by TakeFive."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def install(piper, voices, rhubarb, llama, model, target=ROOT / "runtime"):
    runtime = target.resolve()
    packages = (
        (piper, "piper.exe", "piper", ("*.dll", "*.ort", "espeak-ng-data", "LICENSE*")),
        (rhubarb, "rhubarb.exe", "rhubarb", ("res", "*.dll", "LICENSE*")),
        (llama, "llama-completion.exe", "llama", ("llama-completion-impl.dll", "llama-common.dll", "llama.dll",
             "ggml.dll", "ggml-base.dll", "ggml-cpu*.dll", "mtmd.dll", "libomp.dll", "LICENSE*")),
    )
    for source, binary, folder, patterns in packages:
        if not (source / binary).is_file():
            raise ValueError(f"Missing {source / binary}")
        dest = runtime / folder
        dest.mkdir(parents=True, exist_ok=True)
        for pattern in (binary, *patterns):
            for item in source.glob(pattern):
                if item.resolve() == (dest / item.name).resolve():
                    continue
                if item.is_dir():
                    shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest / item.name)
    dest = runtime / "voices"
    dest.mkdir(exist_ok=True)
    for name in ("en_US-ryan-medium", "en_US-kristin-medium"):
        for suffix in (".onnx", ".onnx.json"):
            voice = voices / (name + suffix)
            if voice.resolve() != (dest / voice.name).resolve():
                shutil.copy2(voice, dest)
    if model.resolve() != (runtime / "planner.gguf").resolve():
        shutil.copy2(model, runtime / "planner.gguf")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("piper", "voices", "rhubarb", "llama", "model"):
        p.add_argument("--" + arg, type=Path, required=True)
    p.add_argument("--target", type=Path, default=ROOT / "runtime")
    install(**vars(p.parse_args()))
