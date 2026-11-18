"""Schedule dialogue once on the film clock and derive the dry camera guides from it."""
import math
import shutil

import numpy as np

from .audio import RATE, save_wav, speech
from .script import FPS, dump


FRAME = RATE // FPS
VOICES = {"Kristin":"en_US-kristin-medium","Ryan":"en_US-ryan-medium"}


def timing_for(shots, recordings):
    lengths, starts, offsets = [], [], []
    first = previous_end = 0
    for index, (shot, recording) in enumerate(zip(shots, recordings, strict=True)):
        duration = shot["seconds"] * FPS
        size = len(recording) if recording is not None else 0
        onset = None
        if size:
            across = shot["delivery"] == "across_cut" and index+1 < len(shots)
            delay = round((1.0 if shot["delivery"] == "after_beat" else .4)*RATE)
            earliest = max(first+delay, previous_end+round(.22*RATE))
            tail = min(round(.65*RATE), size//3) if across else 0
            duration = max(duration, math.ceil((earliest-first+size-tail)/FRAME))
            onset = first+duration*FRAME+tail-size if across else earliest
            previous_end = onset+size
        # A line can bridge into a silent last shot.
        if index+1 == len(shots):
            duration = max(duration, math.ceil((previous_end-first+RATE*.2)/FRAME))
        starts.append(first//FRAME)
        lengths.append(duration)
        offsets.append(onset)
        first += duration*FRAME
    return {"fps":FPS,"rate":RATE,"lengths":lengths,"starts":starts,"frames":first//FRAME,
            "speech_samples":offsets}


def add_audio(track, source, start, gain=1.0):
    left, right = max(0,start), min(len(track),start+len(source))
    if right > left:
        track[left:right] += source[left-start:right-start]*gain


def practical(track, shot, first, length, rng):
    cue = shot["cue"]
    if cue == "none":
        return
    if cue in ("rain","wind","static"):
        noise = rng.normal(0,.07,length)
        window = {"rain":8,"wind":160,"static":3}[cue]
        sound = np.convolve(noise,np.ones(window)/math.sqrt(window),mode="same")*.36
        fade = min(RATE//3, length//2)
        sound[:fade] *= np.linspace(0,1,fade)
        sound[-fade:] *= np.linspace(1,0,fade)
        add_audio(track,sound,first)
        return
    hz, decay, volume = {"knock":(142,15,.18),"footsteps":(84,16,.12),
                         "door":(103,9,.13),"bell":(820,4,.09),"click":(420,45,.09)}[cue]
    t = np.arange(round(RATE*.65))/RATE
    hit = (np.sin(2*np.pi*hz*t)+.39*rng.normal(size=len(t)))*np.exp(-t*decay)*volume
    offsets = [.45,.80,1.16] if cue=="knock" else (np.arange(.35,length/RATE-.20,.54)
                                                     if cue=="footsteps" else [.65])
    for delay in offsets:
        add_audio(track,hit,first+round(delay*RATE))


def write_audio(plan, names, output, cache, seed):
    cache.mkdir(parents=True,exist_ok=True)
    voices = output/"voices"
    voices.mkdir(exist_ok=True)
    by_person = {p["name"]:VOICES[p["voice"]] for p in plan["people"]}
    shots = plan["shots"]
    recordings = []
    for name, shot in zip(names,shots,strict=True):
        if not shot["line"]:
            recordings.append(None)
            continue
        path, samples, visemes = speech({"voice":by_person[shot["speaker"]],"line":shot["line"]},cache)
        recordings.append(samples)
        shutil.copyfile(path,voices/(name+".wav"))
        dump(voices/(name+".mouth.json"),visemes)
    timing = timing_for(shots,recordings)
    rng = np.random.default_rng(seed)
    mix = np.convolve(rng.normal(0,.008,timing["frames"]*FRAME),np.ones(24)/24,mode="same")
    events = []
    for i,(shot, recording) in enumerate(zip(shots,recordings,strict=True)):
        first, length = timing["starts"][i]*FRAME, timing["lengths"][i]*FRAME
        practical(mix,shot,first,length,rng)
        if recording is None:
            continue
        onset = timing["speech_samples"][i]
        signal = recording
        if shot["mode"] == "radio":
            # Only the audible receiver is filtered. The sender's dry recording stays intact.
            low = np.convolve(recording,np.ones(6)/6,mode="same")
            high = low-np.convolve(low,np.ones(92)/92,mode="same")
            signal = np.tanh(high*3.0)*.56
        add_audio(mix,signal,onset,.84)
        events.append({"shot":names[i],"speaker":shot["speaker"],"mode":shot["mode"],
                       "text":shot["line"],"voice":by_person[shot["speaker"]],
                       "at_sample":onset,"samples":len(recording)})
    mix[-2400:] *= np.linspace(1,0,2400)
    save_wav(output/"mix.wav",mix/max(1.0,float(np.abs(mix).max())/.96))
    for i,(name,shot) in enumerate(zip(names,shots,strict=True)):
        start = timing["starts"][i]*FRAME
        guide = np.zeros(timing["lengths"][i]*FRAME)
        for j,source in enumerate(shots):
            if source["mode"]=="onscreen" and (j==i or shot["visible"]==[source["speaker"]]):
                add_audio(guide,recordings[j],timing["speech_samples"][j]-start)
        save_wav(output/(name+"-camera.wav"),guide)
    dump(output/"dialogue.json",events)
    return timing
