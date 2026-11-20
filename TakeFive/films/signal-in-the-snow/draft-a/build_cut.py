"""Rebuild the approved Draft A picture edit and radio mix from sequence.json."""
import json
import subprocess
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.signal import butter, sosfilt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TAKE = ROOT / "TakeFive"
COMFY = ROOT / "comfy-local/output"
OLD = TAKE / "output/signal-in-the-snow/ab4bc60569aef8/shots"
SPEC = json.loads((HERE / "sequence.json").read_text(encoding="utf-8-sig"))
RATE = 48000
FPS = SPEC["fps"]


def ffmpeg(*args):
    return subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)])


def clip_for(shot):
    name = shot["source"]
    if name == "proper-james":
        return COMFY / "phase0/proper-james_00001_.mp4"
    if name == "listen-together":
        return COMFY / "phase0/S1-listen-together_FINAL.mp4"
    if name == "generate":
        job = json.loads((HERE / (shot["id"] + "-job.json")).read_text())
        return COMFY / job["output"]
    return OLD / (name + ".mp4")


def soundtrack(tmp):
    shots = SPEC["shots"]
    starts = {}
    cursor = 0
    for shot in shots:
        starts[shot["id"]] = cursor
        cursor += shot["frames"] * RATE // FPS
    rng = np.random.default_rng(5002)
    noise = rng.normal(size=cursor)
    mix = np.zeros(cursor)
    def add(at, samples):
        end = at + len(samples)
        assert end <= cursor
        mix[at:end] += samples
    def band(low, high):
        return sosfilt(butter(3, [low, high], fs=RATE, btype="bandpass", output="sos"), noise)
    mix[:starts["black"]] += .008 * band(120, 1600)[:starts["black"]]
    wind = band(75, 980)
    a, b = starts["latch"], starts["transmit"]
    envelope = np.interp(np.arange(b-a), [0, RATE*2, starts["outside"]-a, starts["wait"]-a, b-a], [0,.02,.12,.08,.01])
    mix[a:b] += wind[a:b] * envelope
    for shot, at in SPEC["taps"]:
        for spacing in (0, .32, .67):
            t = np.arange(int(RATE*.16))/RATE
            tap = np.exp(-t*47)*(.19*np.sin(2*np.pi*520*t)+.08*np.sin(2*np.pi*1450*t))
            add(starts[shot]+round((at+spacing)*RATE),tap)
    voices = TAKE / "runtime/voices"
    for line in SPEC["dialogue"]:
        voice = "ryan" if line["voice"] == "james" else "kristin"
        wav = tmp / (line["shot"]+".wav")
        subprocess.run([str(TAKE/"runtime/piper/piper.exe"), "--model", str(voices/("en_US-"+voice+"-medium.onnx")), "--output_file",str(wav)],input=(line["text"]+"\n").encode(),check=True)
        effect = "highpass=f=350,lowpass=f=2450" if line["radio"] else "highpass=f=75"
        samples=np.frombuffer(ffmpeg("-i",wav,"-af",effect,"-ac",1,"-ar",RATE,"-f","f32le","pipe:1"),dtype="<f4")
        at=starts[line["shot"]]+round(line["at"]*RATE)
        shot=next(s for s in shots if s["id"]==line["shot"])
        assert at+len(samples)<=starts[line["shot"]]+shot["frames"]*RATE//FPS, line
        add(at,samples*(.53/max(.01,np.abs(samples).max())))
    with wave.open(str(HERE/"radio-mix.wav"),"wb") as out:
        out.setparams((1,2,RATE,0,"NONE",""))
        out.writeframes((np.clip(mix,-1,1)*32767).astype("<i2").tobytes())


def assemble(tmp):
    segments = []
    for shot in SPEC["shots"]:
        out=tmp/(shot["id"]+".mp4")
        source=["-f","lavfi","-i","color=black:s=1024x576:r=24"] if shot["source"]=="black" else ["-ss",str(shot.get("source_in_frame",0)/FPS),"-i",clip_for(shot)]
        ffmpeg(*source,"-an","-vf","fps=24,scale=1024:576:force_original_aspect_ratio=increase,crop=1024:576,setsar=1","-frames:v",shot["frames"],"-c:v","libx264","-crf",16,"-pix_fmt","yuv420p",out)
        n=subprocess.check_output(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=nb_frames","-of","csv=p=0",str(out)],text=True)
        assert int(n)==shot["frames"],shot
        segments.append("file '"+out.name+"'")
    listing=tmp/"edit.txt"
    listing.write_text("\n".join(segments))
    ffmpeg("-f","concat","-safe",0,"-i",listing,"-i",HERE/"radio-mix.wav","-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-movflags","+faststart",HERE/"Three Taps.mp4")


if __name__=="__main__":
    import sys
    with TemporaryDirectory() as folder:
        tmp=Path(folder)
        if "--picture-only" not in sys.argv:
            soundtrack(tmp)
        if "--sound-only" not in sys.argv:
            assemble(tmp)
