"""Export a cut's full depth movement and exact interior frames for a local video model."""
from takefive.finishing import checksum
from takefive.production import ffmpeg, probe
from takefive.script import dump


def guide_length(frames):
    return 1+8*((frames-1+7)//8)


def export(take, plan, report):
    clips = take/"guides"
    clips.mkdir(exist_ok=True)
    index = {"version":1,"fps":plan["fps"],"width":plan["width"],"height":plan["height"],"shots":{}}
    for shot,checks in zip(plan["shots"],report["shots"],strict=True):
        name,n = shot["id"],shot["frames"]
        model_frames = guide_length(n)
        target = clips/(name+"-depth.mp4")
        # Trim before padding so the first frame after a cut can never enter the previous guide.
        filters = f"trim=end_frame={n},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop={model_frames-n}"
        ffmpeg("-framerate",plan["fps"],"-start_number",checks["start_frame"],"-i",take/"depth"/"frame-%04d.png",
               "-vf",filters,"-frames:v",model_frames,"-an","-c:v","libx264","-threads",3,"-crf",0,
               "-pix_fmt","yuv420p","-movflags","+faststart",target)
        stream = probe(target)["streams"][0]
        if int(stream["nb_frames"])!=model_frames or stream["avg_frame_rate"] != f"{plan['fps']}/1":
            raise ValueError(f"{name}: the depth guide did not retain the requested timebase")
        keys = []
        for frame, actions in sorted(checks["keyframes"].items(),key=lambda item:int(item[0])):
            frame = int(frame)
            png = take/"keyframes"/f"{name}-{frame:03}.png"
            keys.append({"frame":frame,"image":png.relative_to(take).as_posix(),"poses":actions,"sha256":checksum(png)})
        index["shots"][name] = {"script":shot["script"],"set":shot["set"],"camera":shot["camera"],
                                "actors":list(shot["actors"]),"first_edit_frame":checks["start_frame"],
                                "edit_frames":n,"guide_frames":model_frames,"depth":target.relative_to(take).as_posix(),
                                "depth_sha256":checksum(target),"keyframes":keys}
    dump(take/"guides.json",index)
    return index
