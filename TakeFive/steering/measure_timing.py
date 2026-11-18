"""Optional CPU check of a lateral move using rendered object IDs and independent person detections."""
import argparse
from collections import Counter
import json
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.python import resource_util
import numpy as np


def centers(movie, sample_frames):
    resource_util.set_resource_dir(str(Path(mp.__file__).resolve().parents[1]))
    graph = mp.CalculatorGraph(graph_config=(
        'input_stream:"rgb" output_stream:"people" node { calculator:"PoseDetectionCpu" '
        'input_stream:"IMAGE:rgb" output_stream:"DETECTIONS:people" }'))
    packets = {}
    def collect(_,packet):
        packets[packet.timestamp.value] = mp.packet_getter.get_proto_list(packet)
    graph.observe_output_stream("people",collect)
    graph.start_run()
    cap, observations = cv2.VideoCapture(str(movie)), {}
    try:
        for t in range(max(sample_frames)+1):
            ok,bgr = cap.read()
            if not ok:
                raise ValueError(f"{movie} ended on frame {t}")
            if t not in sample_frames:
                continue
            rgb = cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
            width = rgb.shape[1]
            candidates = []
            # The same windows run on every frame of every take. No Blender positions enter detection.
            for j,(lo,hi) in enumerate(((0,1),(0,.65),(.35,1),(.18,.82))):
                left,right = round(lo*width),round(hi*width)
                img = np.ascontiguousarray(rgb[:,left:right])
                timestamp = 10*t+j
                graph.add_packet_to_input_stream("rgb",mp.packet_creator.create_image_frame(
                    image_format=mp.ImageFormat.SRGB,data=img).at(timestamp))
                graph.wait_until_idle()
                for d in packets.pop(timestamp,()):
                    hip = d.location_data.relative_keypoints[0]
                    candidates.append((d.score[0],(left+hip.x*(right-left))/width,hip.y))
            people = []
            for conf,x,y in sorted(candidates,reverse=True):
                if not any(abs(x-a)<.055 and abs(y-b)<.10 for a,b in people):
                    people.append((x,y))
            observations[t] = sorted(round(x,5) for x,_ in people)
    finally:
        graph.close_input_stream("rgb")
        graph.wait_until_done()
        cap.release()
    return observations


def crossing(track, threshold, direction):
    pairs = sorted(track.items())
    for i in range(1,len(pairs)-1):
        before,x = pairs[i-1]
        after,y = pairs[i]
        if ((x-threshold)*direction < 0 <= (y-threshold)*direction
                and (pairs[i+1][1]-threshold)*direction>=0):
            return {"frames":[before,after],"interpolated":round(before+(threshold-x)*(after-before)/(y-x),2)}
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path)
    p.add_argument("--actor",required=True)
    args = p.parse_args()
    out = args.output
    src = json.loads((out/"source.json").read_text())
    take = Path(src["take"])
    guide = json.loads((take/"guides.json").read_text())["shots"][src["shot"]]
    plan = json.loads((take/"plan.json").read_text())
    names = guide["actors"]
    n,fps = guide["edit_frames"],src["fps"]
    cast = list(plan["cast"])
    curves = {k:{} for k in names}
    for t in range(n):
        ids = cv2.imread(str(take/"ids"/f"frame-{guide['first_edit_frame']+t:04}.png"),cv2.IMREAD_UNCHANGED)
        peak = np.iinfo(ids.dtype).max
        for name in names:
            code = round(peak*(cast.index(name)+1)/(len(cast)+1))
            _,xx = np.where(np.abs(ids.astype(np.int32)-code)<=1)
            if len(xx):
                curves[name][t] = float(xx.mean()/ids.shape[1])
    order = sorted(names,key=lambda k:curves[k][0])
    for t in range(n):
        if any(t not in curves[k] for k in names) or sorted(names,key=lambda k:curves[k][t])!=order:
            raise ValueError("Visibility or screen ordering changes; this lateral-motion check cannot identify the track")
    moving = curves[args.actor]
    threshold = (moving[0]+moving[n-1])/2
    direction = np.sign(moving[n-1]-moving[0])
    if abs(moving[n-1]-moving[0])<.10:
        raise ValueError("The actor has too little lateral travel for this check")
    delayed = {t:moving[src["delayed_source_frames"][t]] for t in range(n)}
    guide_crossings = {"original":crossing(moving,threshold,direction),"delayed":crossing(delayed,threshold,direction)}
    samples = set(range(0,n,3))|{n-1}
    result = {"actor_by_screen_order":args.actor,"screen_order":order,"frame_rate":fps,
              "normalized_midpoint_x":round(threshold,5),"guides":guide_crossings,"takes":{}}
    for name in ("original","delayed","keyed"):
        film = out/(name+".mp4")
        if not film.is_file():
            continue
        obs = centers(film,samples)
        track = {t:xs[order.index(args.actor)] for t,xs in obs.items() if len(xs)==len(order)}
        result["takes"][name] = {
            "person_counts":dict(Counter(len(xs) for xs in obs.values())),"sample_count":len(samples),
            "crossing":crossing(track,threshold,direction),
            "mean_absolute_x_error":{k:round(sum(abs(x-v[t]) for t,x in track.items())/len(track),5) if track else None
                                     for k,v in (("original",moving),("delayed",delayed))},
            "detections":obs}
    (out/"timing.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Blender crossings:",guide_crossings)
    for k,v in result["takes"].items():
        print(k,v["crossing"],"person counts",v["person_counts"],"mean x error",v["mean_absolute_x_error"])


if __name__=="__main__":
    main()
