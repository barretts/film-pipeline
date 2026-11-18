"""Prepare an immutable five-shot input package using software video codecs."""
from pathlib import Path
import json
import math
import shutil
import subprocess
import uuid
import wave
from array import array
from PIL import Image

from takefive.finishing import checksum
from takefive.production import probe
from takefive.script import SHOTS, binary, digest, dump
from workflows import build_graph

HERE = Path(__file__).resolve().parent


def verify_guide(path, frames, width, height):
    v = next(s for s in probe(path)["streams"] if s["codec_type"]=="video")
    if (int(v["nb_frames"]), v["width"], v["height"], v["avg_frame_rate"]) != (frames, width, height, "24/1"):
        raise ValueError(f"Guide timebase or size mismatch: {path}")


def software_video(source, target, filters, frames):
    subprocess.run([binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                    "-hwaccel", "none", "-threads", "2", "-filter_threads", "2", "-i", str(source),
                    "-an", "-vf", filters, "-frames:v", str(frames), "-c:v", "libx264", "-threads", "2",
                    "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", str(target)], check=True)


def voice_stem(source, output, samples):
    # Match the audio VAE's stereo input and preserve every sample on both channels.
    stereo = array("h",[0]) * (2*samples)
    if source:
        with wave.open(str(source), "rb") as voice:
            channels = voice.getnchannels()
            if channels not in (1,2) or (voice.getsampwidth(), voice.getframerate()) != (2,48000):
                raise ValueError(f"Unexpected camera recording: {source}")
            if voice.getnframes()>samples:
                raise ValueError("The voice recording exceeds the guide duration.")
            data = array("h")
            data.frombytes(voice.readframes(voice.getnframes()))
            if channels == 2:
                stereo[:len(data)] = data
            else:
                stereo[:2*len(data):2] = data
                stereo[1:2*len(data):2] = data
    with wave.open(str(output), "wb") as voice:
        voice.setparams((2,2,48000,0,"NONE",""))
        voice.writeframes(stereo.tobytes())


def prepare(bundle, direction_file, jobs):
    cfg = json.loads(direction_file.read_text(encoding="utf-8-sig"))
    width, height, look = (cfg[key] for key in ("camera_width","camera_height","look_width"))
    if width%64 or height%64 or width*9 != height*16 or min(width,height)<64:
        raise ValueError("For this 16:9 Union Control setup use width and height divisible by 64, such as 1024 by 576.")
    if look<256 or look%256 or not 0 < cfg["guide_strength"] <= 1 or int(cfg["steps"])<1:
        raise ValueError("Invalid look width, sampling steps or guide strength.")
    timing = json.loads((bundle/"render.json").read_text(encoding="utf-8"))["timing"]
    scene = json.loads((bundle/"scene.json").read_text(encoding="utf-8"))
    if timing["fps"]!=24 or timing["rate"]!=48000:
        raise ValueError("Expected a 24 fps TakeFive bundle with a 48 kHz soundtrack.")
    sources = [bundle/"shots"/(name+".mp4") for name in SHOTS]
    stills = [bundle/"stills"/(name+"-start.png") for name in SHOTS]
    cameras = [bundle/(name+"-camera.wav") for name in ("employee","manager")]
    model_revision = checksum(HERE/"models.json")
    code_revision = [checksum(HERE/name) for name in ("prepare.py","workflows.py")]
    key = digest(cfg,scene,timing,[checksum(p) for p in sources+stills+cameras],model_revision,code_revision)[:16]
    jobs.mkdir(parents=True, exist_ok=True)
    dest = jobs/key
    if (dest/"plan.json").is_file():
        return dest, json.loads((dest/"plan.json").read_text(encoding="utf-8"))
    staging = jobs/(".preparing-"+uuid.uuid4().hex)
    staging.mkdir()
    try:
        media = staging/"input"
        media.mkdir()
        graphs = staging/"graphs"
        graphs.mkdir()
        plan = {"format":1, "fps":24, "rate":48000, "direction":cfg, "cast":scene["cast"],
                "door":scene["door"], "model_revision":model_revision, "shots":{}}
        for i,name in enumerate(SHOTS):
            frames = timing["lengths"][i]
            padded = 8*math.ceil((frames-1)/8)+1
            base = f"fps=24,scale={width}:{height}:flags=lanczos,tpad=stop_mode=clone:stop_duration=1,setsar=1"
            start = cfg.get("opening_frames", {}).get(name, {}).get("source_start_frame", 0)
            if start:
                if not isinstance(start, int) or not 0 < start < frames-1 or name in ("employee", "manager"):
                    raise ValueError("A trimmed motion guide needs a valid start frame in a silent shot.")
                base = f"trim=start_frame={start},setpts=(PTS-STARTPTS)*{frames-1}/{frames-start-1}," + base
            for label, filters in (("guide", base), ("edges",base+",edgedetect=low=0.1:high=0.25:mode=wires")):
                target = media/f"{label}-{name}.mp4"
                software_video(sources[i],target,filters,padded)
                verify_guide(target,padded,width,height)
            layout = media/f"layout-{name}.png"
            if start:
                subprocess.run([binary("ffmpeg"), "-loglevel", "error", "-nostdin", "-y", "-hwaccel", "none",
                                "-i", str(media/f"guide-{name}.mp4"), "-frames:v", "1", "-vf",
                                f"scale={look}:{look*9//16}:flags=lanczos", "-threads", "1", str(layout)], check=True)
            else:
                with Image.open(stills[i]) as image:
                    image.convert("RGB").resize((look,look*9//16), Image.Resampling.LANCZOS).save(layout)
            camera = bundle/(name+"-camera.wav") if name in ("employee","manager") else None
            voice_stem(camera,media/f"voice-{name}.wav",padded*2000)
            performance = "The visible people are silent."
            offset = None
            if camera:
                offset = (timing["speech_samples"][name] - timing["starts"][i]*2000)/48000
                performance = (f"The speaker listens silently for {offset:.2f} seconds and then speaks this line: "
                               +scene["cast"][name]["line"])
            plan["shots"][name] = {"frames":frames,"guide_frames":padded,"start":timing["starts"][i],
                                   "voice_onset_seconds":offset, "performance":performance}
        for shot in SHOTS:
            graph,_ = build_graph(plan,shot)
            dump(graphs/(shot+".json"),graph)
        dump(staging/"media.json",{p.name:checksum(p) for p in sorted(media.iterdir())})
        dump(staging/"plan.json",plan)
        try:
            staging.rename(dest)
        except OSError:
            if not (dest/"plan.json").is_file():
                raise
        return dest,plan
    finally:
        if staging.is_dir() and staging.resolve().parent==jobs.resolve():
            shutil.rmtree(staging)
