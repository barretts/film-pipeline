"""Generate one live-action shot from a screenplay and its moving Blender guide."""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from steering.openrouter_client import HEYGEN, LUNA, OpenRouter, RouterError, safe_message, save
from steering.reference_link import temporary_link, verify_url
from takefive.finishing import checksum
from takefive.production import ffmpeg, probe, staging
from takefive.script import binary, digest


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def direction(plan, shot, audit):
    place = plan["sets"][shot["set"]]
    setting = re.sub(r"[;,]?\s*\bempty of people\b[.]?", "", place["description"], flags=re.I).rstrip(" .")
    lines = [
        "Re-film the supplied reference video as one continuous shot of a photorealistic live-action film. "
        "Use its camera framing, spatial relationships, blocking and action timing throughout. "
        "Replace the schematic figures and materials with real performers, clothing and practical scenery.",
        f"Location: {shot['set']}. {setting}.",
        f"Camera: {shot['camera']['view']}. Script beat: {shot['script']}",
    ]
    for name, actor in shot["actors"].items():
        first = next((s for s in audit["samples"] if name in s["cast"]), None)
        position = ""
        if first:
            x = round(100 * first["cast"][name]["center_x"])
            position = f" At {first['frame']/plan['fps']:.2f}s their center is {x}% across the reference from the left."
        lines.append(f"{name}: {plan['cast'][name]['description']} Action: {actor['action'].replace('_',' ')}.{position}")
        for pose in actor["poses"]:
            lines.append(f"At {pose['frame']/plan['fps']:.2f}s {name} performs this gesture: {pose['pose'].replace('_',' ')}.")
        if actor["action"] == "open":
            lines.append(f"{name} reaches the door handle and grasps it before the door starts to swing. "
                         "Show the contact and the resulting movement in this camera setup.")
    lines.append(f"Visible cast count for this shot: {len(shot['actors'])}. "
                 "Use natural lighting, weight, and diegetic sound. Only speak dialogue quoted in the beat. "
                 "Keep the frame free of text, graphics and subtitles.")
    return "\n".join(lines)


def guide_clip(take, plan, audit, target):
    # Fit the complete Blender frame to the requested aspect ratio without cropping blocking at the edges.
    ffmpeg("-framerate", plan["fps"], "-start_number", audit["start_frame"], "-i", take/"clay"/"frame-%04d.png",
           "-frames:v", audit["frames"], "-vf",
           "scale=768:432:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=768:432:(ow-iw)/2:(oh-ih)/2,setsar=1",
           "-an", "-c:v", "libx264", "-threads", 4, "-crf", 14, "-pix_fmt", "yuv420p", "-movflags", "+faststart", target)


def job_fields(reply):
    result = {k: reply[k] for k in ("id", "generation_id", "status", "usage") if reply.get(k) is not None}
    if reply.get("error"):
        result["error"] = safe_message(reply["error"])
    return result


def ensure_job(router, folder, request, url, receipt):
    path = folder/"receipt.json"
    if path.exists():
        return read(path)
    marker = folder/"submit.started"
    try:
        with marker.open("x", encoding="utf-8") as file:
            file.write(datetime.now(timezone.utc).isoformat())
    except FileExistsError:
        if path.exists():
            return read(path)
        raise RuntimeError(f"Submission already started in {folder}. Check your OpenRouter activity before resubmitting.")
    payload = {**request, "input_references":[{"type":"video_url","video_url":{"url":url}}]}
    try:
        reply = router.json("/videos", payload)
    except RouterError as error:
        receipt["submission_http_error"] = str(error)
        if error.code in (400, 401, 402, 403, 404, 413, 415, 422, 429):
            save(folder/("rejected-" + str(time.time_ns()) + ".json"), receipt)
            marker.unlink()
        else:
            save(path, receipt)
        raise
    receipt["job"] = job_fields(reply)
    save(path, receipt)
    return receipt


def edit_to_timeline(source, target, seconds, meta):
    """Use the first visible frame as time zero and shift its native audio by the same amount."""
    video = next(s for s in meta["streams"] if s["codec_type"] == "video")
    start = float(video.get("start_time", 0))
    frames = seconds * 24
    tracks = ["-map", "0:v:0", "-vf", f"setpts=PTS-STARTPTS,fps=24,trim=end_frame={frames}"]
    if any(s["codec_type"] == "audio" for s in meta["streams"]):
        tracks += ["-map", "0:a:0", "-af",
                   f"asetpts=PTS-({start})/TB,aresample=first_pts=0,apad,atrim=duration={seconds}",
                   "-c:a", "aac", "-b:a", "192k"]
    ffmpeg("-copyts", "-i", source, *tracks, "-t", seconds, "-c:v", "libx264", "-threads", 4, "-crf", 16,
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", target)
    out = probe(target)
    stream = next(s for s in out["streams"] if s["codec_type"] == "video")
    actual = int(stream["nb_frames"])
    if actual != frames or stream["avg_frame_rate"] != "24/1":
        raise ValueError(f"The provider footage yielded {actual} of the requested {frames} editorial frames")
    if any(abs(float(s["duration"])-seconds) > 0.025 for s in out["streams"]):
        raise ValueError("The conformed streams do not end together on the requested cut")
    return {"frames":actual, "fps":24, "seconds":seconds, "source_video_start_seconds":start}


def complete_job(router, folder, receipt, guide):
    path = folder/"receipt.json"
    job = receipt.get("job", {})
    if not job.get("id"):
        raise RuntimeError(receipt.get("submission_http_error", f"Missing job ID in {path}"))
    endpoint = "/videos/" + quote(job["id"], safe="")
    deadline = time.monotonic() + 1800
    print(f"OpenRouter job {job['id']}: {job['status']}", flush=True)
    while job["status"] not in ("completed", "succeeded"):
        if job["status"] in ("failed","cancelled","canceled","expired"):
            raise RuntimeError(f"Video job {job['status']}: {job.get('error', 'see OpenRouter activity')}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Job is still {job['status']}. Rerun this command to resume {job['id']}.")
        time.sleep(8)
        update = job_fields(router.json(endpoint))
        if update.get("status") != job["status"]:
            print(f"OpenRouter job {job['id']}: {update['status']}", flush=True)
        job.update(update)
        save(path, receipt)
    target, edit, comparison = (folder/name for name in ("render.mp4", "edit.mp4", "comparison.mp4"))
    media = receipt.setdefault("media", {})
    if receipt.get("video", {}).get("frames") and all(
            f.is_file() and checksum(f) == media.get(f.name) for f in (target, edit, comparison)):
        return
    with staging(folder) as scratch:
        if not target.is_file() or checksum(target) != media.get(target.name):
            result = scratch/"render.mp4"
            router.download(endpoint + "/content?index=0", result)
            subprocess.run([binary("ffmpeg"), "-v", "error", "-xerror", "-i", str(result), "-f", "null", "-"], check=True)
            os.replace(result, target)
            media[target.name] = checksum(target)
            save(path, receipt)
        meta = probe(target)
        video = next(s for s in meta["streams"] if s["codec_type"] == "video")
        duration = float(video.get("duration") or meta["format"]["duration"])
        frame_count = video.get("nb_frames")
        if not str(frame_count).isdigit():
            frame_count = subprocess.check_output([binary("ffprobe"), "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(target)], text=True).strip()
        timing = edit_to_timeline(target, scratch/edit.name, receipt["request"]["duration"], meta)
        tile = "fps=24,scale=768:432:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=768:432:(ow-iw)/2:(oh-ih)/2,setsar=1"
        ffmpeg("-i", guide, "-i", scratch/edit.name, "-filter_complex", f"[0:v]{tile}[a];[1:v]{tile}[b];[a][b]hstack=shortest=1[v]",
               "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-crf", 16, "-threads", 4,
               "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", scratch/"comparison.mp4")
        os.replace(scratch/edit.name, edit)
        os.replace(scratch/"comparison.mp4", comparison)
    media.update({f.name: checksum(f) for f in (edit, comparison)})
    receipt["edit"] = timing
    receipt["video"] = {"seconds": duration, "width":video["width"], "height":video["height"],
                        "fps":video["avg_frame_rate"], "frames":int(frame_count),
                        "audio":[s["codec_name"] for s in meta["streams"] if s["codec_type"]=="audio"]}
    save(path, receipt)


def run(args):
    source = args.source.resolve()
    out = (args.out or ROOT/"output"/"openrouter"/source.stem).resolve()
    # A saved take also accepts local edits to stage.blend when rendered with film.py --blend.
    if source.is_dir():
        take = source
    else:
        cmd = [sys.executable, "-B", "-u", str(Path(__file__).with_name("film.py")), str(source),
               "--out", str(out), "--planner-model", args.planner_model, "--seed", str(args.seed)]
        if args.shots is not None:
            cmd.extend(["--shots", str(args.shots)])
        if args.env_file:
            cmd.extend(["--env-file", str(args.env_file)])
        subprocess.run(cmd, check=True)
        take = out/read(out/"latest.json")["take"]
    plan = read(take/"plan.json")
    shot = next((s for s in plan["shots"] if s["id"] == args.shot), None)
    if shot is None:
        raise ValueError(f"Unknown shot {args.shot}. Available: {', '.join(s['id'] for s in plan['shots'])}")
    audit = next(s for s in read(take/"verification.json")["shots"] if s["id"] == args.shot)
    seconds, remainder = divmod(shot["frames"], plan["fps"])
    if remainder:
        raise ValueError("OpenRouter requires a whole number of seconds per shot")
    request = {"model":args.video_model, "duration":seconds, "aspect_ratio":"16:9", "resolution":args.resolution,
               "seed":args.seed, "prompt":direction(plan, shot, audit)}
    out.mkdir(parents=True, exist_ok=True)
    with staging(out) as scratch:
        guide = scratch/"guide.mp4"
        guide_clip(take, plan, audit, guide)
        guide_hash = checksum(guide)
        folder = out/shot["id"]/digest("https-reference-v1", request, guide_hash)[:16]
        folder.mkdir(parents=True, exist_ok=True)
        os.replace(guide, folder/"guide.mp4")
    guide = folder/"guide.mp4"
    if args.prepare_only:
        print(f"Prepared HTTPS reference source: {guide}\nSHA-256: {guide_hash}", flush=True)
        return
    router = OpenRouter(args.env_file)
    if (folder/"receipt.json").exists():
        receipt = read(folder/"receipt.json")
        complete_job(router, folder, receipt, guide)
    else:
        catalog = router.json("/videos/models")["data"]
        model = next((m for m in catalog if m["id"] == args.video_model), None)
        if (not model or seconds not in model["supported_durations"] or args.resolution not in model["supported_resolutions"]
                or request["aspect_ratio"] not in model["supported_aspect_ratios"]):
            raise ValueError(f"Unsupported model or video settings for {args.video_model}: {seconds}s, 16:9, {args.resolution}")
        receipt = {"request":request, "shot":shot["id"], "plan_sha256":checksum(take/"plan.json"),
                   "guide_sha256":guide_hash,"reference_type":"video_url", "take":os.path.relpath(take, folder),
                   "reference_transport":"temporary-link" if args.temporary_link else "provided-https",
                   "pricing_skus":model.get("pricing_skus", {})}
        if args.reference_url:
            verify_url(args.reference_url, guide)
        link = temporary_link(guide) if args.temporary_link else nullcontext(args.reference_url)
        with link as url:
            print(f"Submitting {args.video_model} with the {seconds}s moving guide: {guide}", flush=True)
            receipt = ensure_job(router, folder, request, url, receipt)
            complete_job(router, folder, receipt, guide)
    print(f"Edited shot: {folder/'edit.mp4'}\nProvider original: {folder/'render.mp4'}\nGuide and render: {folder/'comparison.mp4'}\nReceipt: {folder/'receipt.json'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="UTF-8 script, plan JSON, or an existing Blender take directory")
    parser.add_argument("--shot", required=True, help="Render this shot ID, for example shot05")
    parser.add_argument("--shots", type=int, help="Number of cuts when directing a script")
    parser.add_argument("--seed", type=int, default=71937)
    parser.add_argument("--planner-model", default=LUNA)
    parser.add_argument("--video-model", default=HEYGEN)
    parser.add_argument("--resolution", default="768p")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--env-file", type=Path, help="Read OPENROUTER_API_KEY from this file")
    link = parser.add_mutually_exclusive_group(required=True)
    link.add_argument("--prepare-only", action="store_true", help="Export the exact guide for inspection or hosting")
    link.add_argument("--temporary-link", action="store_true", help="Serve only the guide over a temporary Cloudflare HTTPS link")
    link.add_argument("--reference-url", help="An existing HTTPS link to the exact exported guide")
    run(parser.parse_args())
