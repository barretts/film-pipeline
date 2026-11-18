"""Mix the latch and the wind through the open polar-station door into the timed production sound."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import wave
import numpy as np
from scipy.signal import butter, sosfilt

HERE = Path(__file__).resolve().parent


def mix():
    edit = json.loads((HERE/"sound-edit.json").read_text(encoding="utf-8"))
    with wave.open(str(HERE/"production-sound.wav"),"rb") as source:
        rate = source.getframerate()
        if (source.getnchannels(),source.getsampwidth(),rate) != (2,2,48000):
            raise ValueError("Expected 48 kHz stereo production sound.")
        base = np.frombuffer(source.readframes(source.getnframes()),dtype="<i2").reshape(-1,2)
    time = np.arange(len(base))/rate
    rng = np.random.default_rng(edit["seed"])
    def wind_layer(lo, hi):
        band = butter(2,[lo,hi],fs=rate,btype="bandpass",output="sos")
        noise = sosfilt(band,rng.standard_normal(len(base)))
        return noise/max(noise.std(),1e-9)
    body = .72*wind_layer(65,420) + .21*wind_layer(410,1700)
    air = np.column_stack([body+.21*wind_layer(300,2600) for _ in range(2)])
    times, volumes = zip(*edit["wind_envelope"])
    envelope = np.interp(time,times,volumes)
    gusts = .81 + .17*np.sin(time*1.38) + .12*np.sin(time*2.67+.6)
    effects = air*(envelope*gusts)[:,None]
    at = round(edit["latch_seconds"]*rate)
    u = np.arange(round(.28*rate))/rate
    click = (.065*np.sin(2*np.pi*136*u)*np.exp(-u*48)
             + .045*np.sin(2*np.pi*1470*u)*np.exp(-u*33)
             + .055*rng.standard_normal(len(u))*np.exp(-u*100))
    effects[at:at+len(u)] += click[:,None]*[.9,1.]
    pcm = np.rint(base.astype(np.float64)+32767*effects)
    if np.max(np.abs(pcm)) > 32767:
        raise ValueError("The new sound cues clip the mix.")
    with NamedTemporaryFile(dir=HERE,suffix=".wav",delete=False) as handle:
        staged=Path(handle.name)
    try:
        with wave.open(str(staged),"wb") as output:
            output.setparams((2,2,rate,0,"NONE",""))
            output.writeframes(pcm.astype("<i2").tobytes())
        os.replace(staged,HERE/"mix.wav")
    finally:
        staged.unlink(missing_ok=True)


if __name__ == "__main__":
    mix()
