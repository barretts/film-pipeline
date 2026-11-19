"""Render the three saved Snow storyboards once and conform them to one sound edit."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from urllib.parse import quote
import base64
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import wave

import numpy as np

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT))
from steering.openrouter_client import OpenRouter, RouterError, safe_message, save
from steering.openrouter_shot import direction, edit_to_timeline, job_fields, read
from steering.reference_link import verify_url
from takefive.audio import RATE, save_wav
from takefive.finishing import checksum
from takefive.production import ffmpeg, probe
from takefive.script import binary
from takefive.story_audio import add_audio, practical

MODEL = "bytedance/seedance-2.0-mini"
KEYFILE = Path("C:/code/heyyyy/image-gen/.env")
FILMS = {"Sol": ("snow-sol-6.2", "2ad398d0767ac4c1"),
         "Terra": ("snow-terra-6.1", "3d1be97bc0bafe8e"),
         "Luna": ("snow", "6d7198fed3eb091b")}
OLD = Path("F:/TakeFive/output/signal-in-the-snow/ab4bc60569aef8")
ROOM = Path("F:/TakeFive/output/text-films/snow-25deed3219ce/looks/set01.png")
SOUND = OUT / "sound"
DIALOGUE = {1: ("warning.wav", 1.20, "offscreen from the radio speaker; Kate listens with her lips still"),
            2: ("kateRecognition.wav", 1.72, "Kate says exactly the recorded line once"),
            4: ("jamesChoice.wav", 1.80, "James says exactly the recorded line once"),
            7: ("warning.wav", 1.50, "Kate speaks the warning into the microphone")}


def soundtrack():
    SOUND.mkdir(exist_ok=True)
    rng = np.random.default_rng(71937)
    t = np.arange(RATE * 35) / RATE
    track = .003 * np.sin(2*np.pi*58*t) + .0018 * np.sin(2*np.pi*116*t)
    track += np.convolve(rng.normal(0, .012, len(t)), np.ones(24)/24, mode="same")
    practical(track, {"cue": "static"}, 0, 4*RATE, rng)
    practical(track, {"cue": "knock"}, 10*RATE, 5*RATE, rng)
    practical(track, {"cue": "door"}, int(21.4*RATE), 3*RATE, rng)
    practical(track, {"cue": "wind"}, int(22.0*RATE), int(12.8*RATE), rng)
    practical(track, {"cue": "click"}, int(30.4*RATE), 3*RATE, rng)
    for index, (name, offset, _) in DIALOGUE.items():
        with wave.open(str(OLD / "voices" / name), "rb") as f:
            assert f.getframerate() == RATE and f.getsampwidth() == 2
            samples = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").astype(float)
            samples = samples.reshape(-1, f.getnchannels()).mean(axis=1)/32768
        if index == 1:
            narrow = np.convolve(samples, np.ones(6)/6, mode="same")
            samples = np.tanh((narrow - np.convolve(narrow, np.ones(90)/90, mode="same")) * 3) * .55
        assert offset + len(samples)/RATE < 5
        add_audio(track, samples, round(((index-1)*5+offset)*RATE), .92)
    track[-4800:] *= np.linspace(1, 0, 4800)
    track /= max(1.0, np.abs(track).max()/.96)
    save_wav(SOUND/"master.wav", track)
    for index in DIALOGUE:
        save_wav(SOUND/f"shot{index:02}.wav", track[(index-1)*5*RATE:index*5*RATE])


def prepare():
    soundtrack()
    specs, assets = [], {}
    sized = OUT/"guides"
    sized.mkdir(exist_ok=True)
    for film, (name, take_id) in FILMS.items():
        root = BASE/name
        take = root/"takes"/take_id
        plan = read(take/"plan.json")
        audits = read(take/"verification.json")["shots"]
        assert len(plan["shots"]) == len(audits) == 7 and plan["fps"] == 24
        for index, (shot, audit) in enumerate(zip(plan["shots"], audits, strict=True), 1):
            sid = f"shot{index:02}"
            assert shot["id"] == audit["id"] == sid and shot["frames"] == 120
            guides = list((root/sid).glob("*/guide.mp4"))
            assert guides and len({checksum(p) for p in guides}) == 1
            guide = guides[0]
            upload_guide = sized/(checksum(guide)+".mp4")
            if not upload_guide.is_file():
                staged = sized/"sizing.work.mp4"
                ffmpeg("-i",guide,"-map","0:v:0","-an","-vf","scale=864:486:flags=lanczos,setsar=1",
                       "-c:v","libx264","-threads",4,"-crf",15,"-pix_fmt","yuv420p","-movflags","+faststart",staged)
                stream = probe(staged)["streams"][0]
                assert (stream["width"], stream["height"], stream["nb_frames"], stream["avg_frame_rate"]) == (864,486,"120","24/1")
                os.replace(staged, upload_guide)
            refs = [("video_url", upload_guide), ("image_url", ROOM)]
            details = ["Video 1 is the moving blocking and camera reference for the entire take. "
                       "Recast the animated shapes as human actors in a live-action polar-station drama. "
                       "Image 1 shows practical room materials only. Follow the layout, lighting and framing in Video 1."]
            for actor, key in (("Kate", "shot02"), ("James", "shot04")):
                if actor in shot["actors"]:
                    refs.append(("image_url", take/"keyframes"/(key+"-060.png")))
                    details.append(f"Image {len(refs)-1} is {actor}'s casting and costume sketch. "
                                   "Use the scripted adult actor and wardrobe in live action; preserve their identity throughout.")
            moment = take/"keyframes"/(sid+"-060.png")
            if index in (6, 7) and moment.is_file():
                refs.append(("image_url", moment))
                details.append(f"At 2.5 seconds use Image {len(refs)-1} for the pose and composition while motion continues.")
            if index in DIALOGUE:
                refs.append(("audio_url", SOUND/(sid+".wav")))
                _, when, action = DIALOGUE[index]
                details.append(f"Audio 1 is the exact timing and performance. At {when:g}s {action}. "
                               "Synchronize visible speech to the supplied recording. No other speech.")
            elif index == 3:
                details.append("Keep the door shut through the three offscreen knocks. The frame contains no people.")
            else:
                details.append("A silent action beat with no spoken words.")
            prompt = direction(plan, shot, audit) + "\n" + " ".join(details)
            request = {"model": MODEL, "resolution": "480p", "aspect_ratio": "16:9", "duration": 5,
                       "seed": 71937, "generate_audio": True, "prompt": prompt}
            refs_record = []
            for typ, p in refs:
                h = checksum(p)
                asset = h + p.suffix.lower()
                assets[asset] = p
                refs_record.append({"type": typ, "asset": asset, "path": str(p), "sha256": h})
            folder = OUT/film/sid
            folder.mkdir(parents=True, exist_ok=True)
            spec = {"film": film, "shot": sid, "plan_sha256": checksum(take/"plan.json"), "request": request,
                    "references": refs_record, "guide": str(guide)}
            path = folder/"inputs.json"
            if path.exists() and read(path) != spec and ((folder/"submit.started").exists() or (folder/"receipt.json").exists()):
                raise ValueError(f"Inputs changed for the one-pass shot {film}/{sid}")
            save(path, spec)
            specs.append((folder, spec))
    return specs, assets


@contextmanager
def serve_inputs(assets):
    prefix = "/" + secrets.token_urlsafe(32) + "/"
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.send_asset(True)
        def do_HEAD(self):
            self.send_asset(False)
        def send_asset(self, body):
            p = assets.get(self.path[len(prefix):]) if self.path.startswith(prefix) else None
            if not p:
                self.send_error(404)
                return
            size = p.stat().st_size
            start, stop = 0, size
            span = self.headers.get("Range")
            if span:
                m = re.fullmatch(r"bytes=(\d*)-(\d*)", span)
                if not m or not any(m.groups()):
                    self.send_error(416)
                    return
                left, right = m.groups()
                if left:
                    start, stop = int(left), min(size, int(right)+1) if right else size
                else:
                    start = max(0, size-int(right))
                if start >= stop:
                    self.send_error(416)
                    return
            self.send_response(206 if span else 200)
            self.send_header("Content-Type", "audio/wav" if p.suffix == ".wav" else mimetypes.guess_type(p.name)[0])
            self.send_header("Content-Length", str(stop-start))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            if span:
                self.send_header("Content-Range", f"bytes {start}-{stop-1}/{size}")
            self.end_headers()
            if body:
                with p.open("rb") as f:
                    f.seek(start)
                    self.wfile.write(f.read(stop-start))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cmd = [shutil.which("cloudflared"), "tunnel", "--no-autoupdate", "--protocol", "http2",
           "--url", f"http://127.0.0.1:{server.server_port}"]
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env={k:v for k,v in os.environ.items() if k.upper() != "OPENROUTER_API_KEY"},
                             creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    links = Queue()
    def logs():
        for line in child.stdout:
            m = re.search(rb"https://[a-z0-9-]+\.trycloudflare\.com\b", line)
            if m:
                links.put(m[0].decode())
        links.put(None)
    threading.Thread(target=logs, daemon=True).start()
    try:
        host = links.get(timeout=60)
        if not host:
            raise RuntimeError("Media tunnel failed before submission")
        origin = host + prefix
        name = next(iter(assets))
        for attempt in range(15):
            try:
                verify_url(origin+name, assets[name], quick_tunnel=True)
                break
            except (OSError, ValueError):
                if attempt == 14:
                    raise
                time.sleep(3)
        yield origin
    finally:
        child.terminate()
        try:
            child.wait(timeout=6)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        child.stdout.close()
        server.shutdown()
        server.server_close()


def get_status(router, endpoint):
    for attempt in range(5):
        try:
            return router.json(endpoint)
        except (OSError, RouterError) as e:
            if isinstance(e, RouterError) and e.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt == 4:
                raise
            time.sleep(2**attempt)


def render_once(item, origin):
    folder, spec = item
    label = spec["film"]+"/"+spec["shot"]
    receipt_file = folder/"receipt.json"
    router = OpenRouter(KEYFILE)
    if receipt_file.is_file():
        receipt = read(receipt_file)
    else:
        if (OUT/"STOP-REQUESTED").exists():
            raise RuntimeError("This batch was stopped by the user.")
        body = dict(spec["request"])
        body["input_references"] = []
        for ref in spec["references"]:
            typ = ref["type"]
            if origin and (typ == "video_url" or "--https-references" in sys.argv):
                url = origin + ref["asset"]
            else:
                path = Path(ref["path"])
                mime = "audio/wav" if typ == "audio_url" else mimetypes.guess_type(path.name)[0]
                data = base64.b64encode(path.read_bytes()).decode("ascii")
                url = f"data:{mime};base64,{data}"
            body["input_references"].append({"type":typ, typ:{"url":url}})
        marker = folder/"submit.started"
        with marker.open("x") as f:
            f.write(datetime.now(timezone.utc).isoformat())
        try:
            reply = router.json("/videos", body)
        except RouterError as e:
            save(folder/"submission-error.json", {"code": e.code, "error": safe_message(str(e))})
            if e.code in (400, 401, 402, 403, 404, 413, 415, 422, 429):
                marker.unlink()
            raise
        receipt = {"model": MODEL, "film": spec["film"], "shot": spec["shot"], "job": job_fields(reply)}
        save(receipt_file, receipt)
        print(label, "accepted", receipt["job"].get("id"), flush=True)
    job = receipt["job"]
    endpoint = "/videos/"+quote(job["id"], safe="")
    last = job["status"]
    deadline = time.monotonic()+2700
    while job["status"] not in ("completed","succeeded"):
        if job["status"] in ("failed","cancelled","canceled","expired"):
            raise RuntimeError(f"{label} {job['status']}: {job.get('error','provider returned no details')}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"{label} awaiting {job['id']}")
        time.sleep(8)
        job.update(job_fields(get_status(router, endpoint)))
        save(receipt_file, receipt)
        if job["status"] != last:
            print(label, job["status"], flush=True)
            last = job["status"]
    if not receipt.get("billed_usd"):
        value = job.get("usage",{}).get("cost")
        if value is None:
            ledger = get_status(router, "/generation?id="+quote(job.get("generation_id") or job["id"], safe=""))
            value = ledger["data"]["total_cost"]
        receipt["billed_usd"] = str(value)
        save(receipt_file, receipt)
    native, edit = folder/"render.mp4", folder/"edit.mp4"
    if native.is_file() and edit.is_file() and receipt.get("edit_sha256") == checksum(edit):
        return Decimal(receipt["billed_usd"])
    if not native.is_file() or receipt.get("native_sha256") != checksum(native):
        temp = folder/"download.part"
        router.download(endpoint+"/content?index=0", temp)
        subprocess.run([binary("ffmpeg"), "-v", "error", "-xerror", "-i", str(temp), "-f", "null", "-"], check=True)
        os.replace(temp, native)
        receipt["native_sha256"] = checksum(native)
        save(receipt_file, receipt)
    meta = probe(native)
    v = next(s for s in meta["streams"] if s["codec_type"] == "video")
    receipt["provider_size"] = [v["width"],v["height"]]
    receipt["edit"] = edit_to_timeline(native, folder/"edit.work.mp4", 5, meta)
    os.replace(folder/"edit.work.mp4", edit)
    receipt["edit_sha256"] = checksum(edit)
    save(receipt_file, receipt)
    print(label, "saved", receipt["provider_size"], "$"+receipt["billed_usd"], flush=True)
    return Decimal(receipt["billed_usd"])


def assemble():
    summary = {"model": MODEL, "sound_sha256": checksum(SOUND/"master.wav"), "films": {}}
    for film in FILMS:
        folder = OUT/film
        if not all((folder/f"shot{i:02}"/"edit.mp4").is_file() for i in range(1,8)):
            continue
        receipts = [read(folder/f"shot{i:02}"/"receipt.json") for i in range(1,8)]
        assert len({r["job"]["id"] for r in receipts}) == 7
        for i,r in enumerate(receipts,1):
            assert r["edit_sha256"]==checksum(folder/f"shot{i:02}"/"edit.mp4")
        final = folder/f"Snow-{film}-480p.mp4"
        temp = folder/"film.work.mp4"
        # Concatenating containers also imports their AAC priming timestamps. Use only the 120 picture frames of each cut.
        source_args = [arg for i in range(1,8) for arg in ("-i",folder/f"shot{i:02}"/"edit.mp4")]
        parts = [f"[{i}:v]trim=end_frame=120,settb=1/24,setpts=N[v{i}]" for i in range(7)]
        parts.append("".join(f"[v{i}]" for i in range(7))+"concat=n=7:v=1:a=0,settb=1/24,setpts=N,"
                     "scale=854:480:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                     "pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1[picture]")
        ffmpeg(*source_args,"-i",SOUND/"master.wav","-filter_complex_threads",2,"-filter_complex",";".join(parts),
               "-map","[picture]","-map","7:a:0","-fps_mode","cfr","-r",24,"-c:v","libx264",
               "-threads",4,"-crf",16,"-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-movflags","+faststart",temp)
        meta = probe(temp)
        v, a = [next(s for s in meta["streams"] if s["codec_type"]==kind) for kind in ("video","audio")]
        if (int(v["nb_frames"]),v["avg_frame_rate"],int(v["height"]),float(v["duration"]),
            int(a["sample_rate"]),float(a["duration"])) != (840,"24/1",480,35,48000,35):
            raise RuntimeError(f"Unexpected finished timeline: {[(x.get('nb_frames'),x.get('duration'),x.get('height'),x.get('avg_frame_rate')) for x in (v,a)]}")
        subprocess.run([binary("ffmpeg"),"-v","error","-xerror","-i",str(temp),"-f","null","-"],check=True)
        os.replace(temp,final)
        price = sum(Decimal(r["billed_usd"]) for r in receipts)
        summary["films"][film] = {"file":str(final), "sha256":checksum(final),"seconds":35,"frames":840,
                                  "size":[v["width"],v["height"]],"usd":str(price),
                                  "jobs":[r["job"]["id"] for r in receipts]}
        print("FILM",film,final,"$"+str(price),flush=True)
    assert len({j for f in summary["films"].values() for j in f["jobs"]}) == 7*len(summary["films"])
    summary["total_usd"] = str(sum(Decimal(v["usd"]) for v in summary["films"].values()))
    save(OUT/"summary.json",summary)


def main():
    if (OUT/"STOP-REQUESTED").exists() and "--assemble" not in sys.argv and "--prepare" not in sys.argv:
        raise SystemExit("Stopped by the user.")
    specs, assets = prepare()
    router = OpenRouter(KEYFILE)
    listing = next(m for m in router.json("/videos/models")["data"] if m["id"]==MODEL)
    rate = Decimal(listing["pricing_skus"]["video_tokens_with_video_input"])
    assert rate <= Decimal("0.0000021") and "480p" in listing["supported_resolutions"]
    assert 5 in listing["supported_durations"] and "16:9" in listing["supported_aspect_ratios"]
    print(f"Prepared {len(specs)} shots, {len(assets)} distinct media inputs",flush=True)
    if "--prepare" in sys.argv:
        return
    if "--assemble" in sys.argv:
        assemble()
        return
    # The first billed take counts as one of the 21 and establishes the account's effective price.
    first = next(item for item in specs if item[1]["film"]=="Sol" and item[1]["shot"]=="shot02")
    rest = [item for item in specs if item != first]
    guides = {key:value for key,value in assets.items() if value.suffix == ".mp4"}
    if "--https-references" in sys.argv:
        transport = serve_inputs(assets)
    elif "--https-guides" in sys.argv:
        transport = serve_inputs(guides)
    else:
        transport = nullcontext(None)
    with transport as origin:
        first_cost = render_once(first, origin)
        if first_cost * 21 > Decimal("4.45"):
            raise RuntimeError(f"First receipt was ${first_cost}; projected spend exceeds $4.45")
        waiting = [i for i in rest if not (i[0]/"edit.mp4").is_file()]
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                while waiting:
                    batch, waiting = waiting[:2], waiting[2:]
                    work = {pool.submit(render_once,item,origin): item for item in batch}
                    deferred = []
                    for future in as_completed(work):
                        try:
                            future.result()
                        except RouterError as err:
                            if err.code != 402 and not (err.code == 403 and "key limit exceeded" in str(err).lower()):
                                raise
                            deferred.append(work[future])
                    if len(deferred) == len(batch):
                        raise RuntimeError("OpenRouter declined every new request for insufficient credits after the preceding jobs settled.")
                    waiting = deferred + waiting
        finally:
            assemble()


if __name__ == "__main__":
    main()
