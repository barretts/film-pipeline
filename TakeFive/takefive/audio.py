"""Offline voices, visemes and a continuous sample-aligned scene sound mix."""
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave
import numpy as np

from .script import FPS, ROOT, binary, digest, file_stamp

RATE = 48000


def save_wav(path, samples, rate=RATE):
    with wave.open(str(path), "wb") as f:
        f.setparams((1, 2, rate, 0, "NONE", ""))
        f.writeframes(np.int16(np.clip(samples, -1, 1) * 32767).tobytes())


def read_wav(path):
    with wave.open(str(path), "rb") as f:
        if f.getnchannels() != 1 or f.getsampwidth() != 2:
            raise ValueError(f"Expected mono 16-bit speech from Piper: {path}")
        return np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").astype(float) / 32768, f.getframerate()


def speech(actor, cache):
    model = ROOT / "runtime" / "voices" / (actor["voice"] + ".onnx")
    piper, rhubarb = binary("piper"), binary("rhubarb")
    if not model.is_file():
        raise ValueError(f"Missing local voice {model.name} in runtime/voices")
    key = digest("voice-v2", actor["line"], file_stamp(model), file_stamp(str(model) + ".json"),
                 file_stamp(piper), file_stamp(rhubarb))
    folder = cache / key
    if not (folder / "mouth.json").is_file():
        with tempfile.TemporaryDirectory(dir=cache) as temp:
            d = Path(temp)
            text = actor["line"].strip()
            (d / "line.txt").write_text(text, encoding="utf-8")
            subprocess.run([piper, "--model", str(model), "--output_file", str(d / "raw.wav")],
                           input=(text + "\n").encode(), check=True, stdout=subprocess.DEVNULL)
            arr, sr = read_wav(d / "raw.wav")
            voiced = np.flatnonzero(abs(arr) > .012)
            if not len(voiced):
                raise ValueError("Piper produced silence.")
            arr = arr[max(0, voiced[0]-int(sr*.035)):voiced[-1]+int(sr*.07)]
            save_wav(d / "line.wav", arr, sr)
            subprocess.run([rhubarb, "-f", "json", "--quiet", "--threads", "2", "--dialogFile",
                            str(d / "line.txt"), "-o", str(d / "mouth.json"), str(d / "line.wav")], check=True)
            ready=d/"ready"
            ready.mkdir()
            for name in ("line.wav", "mouth.json"):
                (d/name).rename(ready/name)
            try:
                ready.rename(folder)
            except OSError:
                if not (folder/"mouth.json").is_file():
                    raise
    return saved_speech(folder / "line.wav",folder / "mouth.json")


def saved_speech(wav_path,cue_path):
    arr, sr = read_wav(wav_path)
    resampled = np.interp(np.arange(round(len(arr)*RATE/sr))*sr/RATE, np.arange(len(arr)), arr)
    data = json.loads(cue_path.read_text(encoding="utf-8"))
    cues = data["mouthCues"] if isinstance(data,dict) else data
    return wav_path, resampled, cues


def timeline(plan, speeches):
    seconds = [len(speeches[r][1])/RATE for r in ("employee", "manager")]
    lengths = [round(s["seconds"]*FPS) for s in plan["shots"]]
    bridge = min(plan["bridge"], seconds[0]*.40)
    lengths[1] = max(lengths[1], math.ceil((seconds[0]-bridge+.22)*FPS))
    lengths[2] = max(lengths[2], math.ceil((bridge+plan["reply_beat"]+seconds[1]+.38)*FPS))
    starts = [sum(lengths[:i]) for i in range(len(lengths))]
    cut = starts[2]/FPS
    offsets = {"employee": round((cut+bridge-seconds[0])*RATE),
               "manager": round((cut+bridge+plan["reply_beat"])*RATE)}
    return {"fps": FPS, "rate": RATE, "starts": starts, "lengths": lengths, "frames": sum(lengths),
            "speech_samples": offsets, "bridge_seconds": bridge}


def mix(plan, timing, speeches, bundle):
    n = timing["frames"] * (RATE//FPS)
    t = np.arange(n)/RATE
    rng = np.random.default_rng(521)
    ambient = .0024*np.sin(2*np.pi*59*t) + .0014*np.sin(2*np.pi*119*t)
    hiss = rng.normal(0, .035, n)
    ambient += np.convolve(hiss, np.ones(24)/24, mode="same")*.32
    street = np.clip((t-timing["starts"][4]/FPS+.18)/.65, 0, 1)
    ambient += street*(.004*np.sin(2*np.pi*(78*t+.12*t*t)) + .003*np.sin(2*np.pi*101*t))
    def hit(at, kind):
        duration = .33 if kind == "step" else .65
        u = np.arange(int(RATE*duration))/RATE
        if kind == "step":
            effect = (.11*np.sin(2*np.pi*(94*u-49*u*u))*np.exp(-u*28) +
                      .045*rng.normal(size=len(u))*np.exp(-u*37))
        else:
            effect = (.13*np.sin(2*np.pi*121*u)*np.exp(-u*30) +
                      .038*np.sin(2*np.pi*1260*u)*np.exp(-u*9))
        i = round(at*RATE)
        if 0 <= i < n:
            ambient[i:i+min(n-i,len(u))] += effect[:min(n-i,len(u))]
    for idx in (0, 3, 4):
        a = timing["starts"][idx]/FPS
        length = timing["lengths"][idx]/FPS
        for when in np.arange(.24 if idx != 3 else .68, length*.86 if idx == 0 else length, .49):
            hit(a+when, "step")
    hit(.65, "door")
    hit(timing["starts"][4]/FPS+.98, "door")
    output = ambient
    for role in speeches:
        wave_data = speeches[role][1]
        first = timing["speech_samples"][role]
        output[first:first+len(wave_data)] += wave_data*.83
    output[:960] *= np.linspace(0, 1, 960)
    output[-4800:] *= np.linspace(1, 0, 4800)
    save_wav(bundle / "mix.wav", output / max(1, np.abs(output).max()/.97))
    for i, role in ((1, "employee"), (2, "manager")):
        start = timing["starts"][i]*(RATE//FPS)
        count = timing["lengths"][i]*(RATE//FPS)
        stem = np.zeros(count)
        data = speeches[role][1]
        offset = timing["speech_samples"][role]-start
        dst, src = max(0,offset), max(0,-offset)
        take = min(count-dst,len(data)-src)
        if take > 0:
            stem[dst:dst+take] = data[src:src+take]
        save_wav(bundle / (role+"-camera.wav"), stem)
