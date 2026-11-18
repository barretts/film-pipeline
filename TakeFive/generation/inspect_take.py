"""Deterministic local checks for defects measurable in a single uncut take."""
import av
import numpy as np


def inspect(path, expected):
    previous = None
    steps, means, spreads = [], [], []
    with av.open(str(path)) as movie:
        for frame in movie.decode(video=0):
            if len(means) >= expected:
                break
            thumb = frame.reformat(width=128,height=72,format="gray").to_ndarray().astype(np.float32)
            if previous is not None:
                steps.append(float(np.sqrt(np.mean(np.square(thumb-previous)))))
            means.append(float(thumb.mean()))
            spreads.append(float(thumb.std()))
            previous = thumb
    if len(means) != expected:
        raise ValueError(f"Only {len(means)} of {expected} required frames decoded in {path}")
    typical = float(np.median(steps)) if steps else 0.0
    jumps = [i+1 for i,delta in enumerate(steps) if delta>max(37,typical*7)]
    blank = max(means)<5 and max(spreads)<4
    frozen = bool(steps) and max(steps)<.32
    return {"decoded_frames":len(means),"black":blank,"frozen":frozen,"possible_cuts":jumps,
            "median_frame_change":round(typical,3),"maximum_frame_change":round(max(steps,default=0),3)}


def defects(assessment):
    return (int(assessment["black"]),int(assessment["frozen"]),len(assessment["possible_cuts"]))
