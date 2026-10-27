"""Create original, deterministic accents and a short crossfaded local music bed."""

from pathlib import Path
import subprocess

import numpy as np
from scipy import signal
import soundfile as sf

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RATE = 48000
SOURCE = ROOT / "audio" / "pilot" / "stable-audio-music-smoke.wav"


def limit_peak(audio, peak):
    highest = np.max(np.abs(audio))
    if highest < 1e-8:
        raise RuntimeError("generated audio is silent")
    return np.asarray(audio * (peak / highest), dtype=np.float32)


def write(name, audio, peak):
    sf.write(OUT / name, limit_peak(audio, peak), RATE, subtype="PCM_16")


def main():
    files = [OUT / name for name in ("heartbeat.wav", "door.wav", "chime.wav", "ambient.wav")]
    if any(path.exists() for path in files):
        raise RuntimeError("one or more output files exist; refusing to overwrite")
    if not SOURCE.is_file():
        raise RuntimeError(f"music source missing: {SOURCE}")
    rng = np.random.default_rng(7426)

    # A subdued double pulse, with a short low-passed noise transient.
    t = np.arange(int(1.2 * RATE)) / RATE
    heart = np.zeros_like(t)
    for start, amp in ((0.04, 1.0), (0.32, 0.7)):
        local = t - start
        on = local >= 0
        x = local[on]
        heart[on] += amp * np.exp(-15 * x) * np.sin(2 * np.pi * (58 * x - 12 * x * x))
    noise = signal.sosfilt(signal.butter(3, 120, fs=RATE, output="sos"), rng.standard_normal(len(t)))
    heart += noise * 0.25 * np.exp(-30 * np.maximum(t - 0.04, 0)) * (t >= 0.04)
    write("heartbeat.wav", heart, 0.55)

    # A low wooden hinge-like groan: bowed partials, filtered texture and a soft echo.
    t = np.arange(int(1.15 * RATE)) / RATE
    freq = 135 + 70 * t + 12 * np.sin(2 * np.pi * 4.7 * t)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    env = np.sin(np.pi * np.clip((t - 0.03) / 1.07, 0, 1)) ** 1.5
    grit = signal.sosfilt(signal.butter(3, (250, 1800), btype="bandpass", fs=RATE, output="sos"), rng.standard_normal(len(t)))
    door = env * (np.sin(phase) + 0.38 * np.sin(2.02 * phase) + 0.08 * grit)
    delay = int(0.065 * RATE)
    door[delay:] += 0.22 * door[:-delay].copy()
    write("door.wav", door, 0.4)

    # A delicate inharmonic glass-like strike with a short controlled decay.
    t = np.arange(int(1.2 * RATE)) / RATE
    chime = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-decay * t)
                for f, a, decay in ((660, 1.0, 5.0), (1043, 0.42, 7.0), (1638, 0.19, 10.0)))
    chime *= np.minimum(t / 0.006, 1)
    write("chime.wav", chime, 0.4)

    # Reuse the existing locally generated eight-second score; crossfade its seam.
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                    "-i", str(SOURCE), "-i", str(SOURCE), "-filter_complex",
                    "[0:a][1:a]acrossfade=d=1.2:c1=tri:c2=tri,aresample=48000[a]",
                    "-map", "[a]", "-c:a", "pcm_s16le", str(OUT / "ambient.wav")], check=True)
    for path in files:
        info = sf.info(path)
        print(f"{path.name}: {info.duration:.3f}s, {info.samplerate} Hz, {info.channels} channels")


if __name__ == "__main__":
    main()
