"""Measure timing and preservation in the one-shot LatentSync composite."""
from pathlib import Path
import subprocess
import cv2
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate, correlation_lags

root = Path(r"F:\film-pipeline\jobs\anime_pose_experiment")
clip = root / "latentsync-full-scene-test.mp4"
decoded = root / "latentsync-decoded-audio.wav"
reference = root / "latentsync-reference-audio.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ac", "1", "-ar", "16000", str(decoded)], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(root / "voice.wav"), "-ac", "1", "-ar", "16000", str(reference)], check=True)
_, original_audio = wavfile.read(reference)
_, output_audio = wavfile.read(decoded)
original_audio = original_audio.astype(np.float64)
output_audio = output_audio.astype(np.float64)
if original_audio.ndim == 2:
    original_audio = original_audio.mean(axis=1)
corr = correlate(output_audio, original_audio, mode="full", method="fft")
lag = correlation_lags(len(output_audio), len(original_audio), mode="full")[np.argmax(corr)]
local_lags = []
for start in (0, 16000, 32000, 48000, 60000):
    a_window = original_audio[start : start + 8000]
    b_window = output_audio[start : start + 8000]
    local_corr = correlate(b_window, a_window, mode="full", method="fft")
    candidates = correlation_lags(len(b_window), len(a_window), mode="full")
    near = np.abs(candidates) <= 1600
    local_lags.append(candidates[near][np.argmax(local_corr[near])] / 16)
a = cv2.VideoCapture(str(root / "full-source.mp4"))
b = cv2.VideoCapture(str(clip))
if int(a.get(cv2.CAP_PROP_FRAME_COUNT)) != 112 or int(b.get(cv2.CAP_PROP_FRAME_COUNT)) != 112:
    raise RuntimeError("Unexpected frame count")
errors = []
sheet = []
for i in range(112):
    oka, original = a.read()
    okb, result = b.read()
    if not oka or not okb:
        raise RuntimeError(f"Frame decode failed at {i}")
    errors.append(np.abs(original[500:].astype(np.int16) - result[500:].astype(np.int16)).mean())
    if i in (10, 35, 60, 85, 105):
        sheet.append(np.hstack([cv2.resize(original, (352, 640)), cv2.resize(result, (352, 640))]))
cv2.imwrite(str(root / "latentsync-full-comparison.jpg"), np.vstack(sheet))
print(f"frames=112 fps=25 audio_source_samples={len(original_audio)} audio_output_samples={len(output_audio)} audio_lag_ms={lag / 16:.2f} body_mean_abs_error_8bit={np.mean(errors):.3f} body_max_mean_error_8bit={np.max(errors):.3f}")
print(f"half-second audio window offsets in milliseconds: {local_lags}")
