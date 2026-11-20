"""Translate a narrative film and its generated asset board into Blender scene data."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


CONTRACT = """You are the scene planner for a Blender steering animatic. Use the supplied film
as direction for screen position, movement and framing. Make the moving lead a single
orange egg-shaped sphere, and use one contrasting marker per other visible person.
Translate markers as whole objects. Include only simple landmark blocks needed to
identify the start and destination or frame the action. Omit anatomy, gait, gestures,
wardrobe, decorative set dressing and props immaterial to the shot. The asset board
identifies the subjects; the later stills supply their appearance. Choose dimensions,
positions, motion timing, lighting and camera so the path reads clearly on screen.
For an interior viewpoint build an enclosing room (floor, ceiling and walls) and keep
the entire camera path inside its clear volume. Every edge of the picture must show
the interior: the floor extends under the camera and beyond the bottom corners.
Check the lens field of view at both ends. For a lateral follow shot, translate eye
with the action. Choose the aim and amount of camera travel to suit the shot direction;
the subject can move within the frame as the composition changes.
Preserve relevant spatial relationships and continuity across cuts.
Return only JSON, without Markdown. Do not use tools. The renderer accepts this format:
Top-level geometry, lights, shots and fps. The renderer takes its resolution directly from film.size.
geometry is an array of {id,parent,loc,parts}. Unique ids, parent is another id or null,
loc is a parent-local XYZ vector, Z up. Each part is [kind,localCenter,dimensions,color],
kind box or sphere, color six hex digits without #.
lights is an array of {location,aim,watts,size,rgb}, rgb in [0,1].
Each shot is {id,set,frames,camera,tracks,sound}. camera has lens in mm and XYZ vectors
eye,end_eye,aim,end_aim. tracks are {id,prop,keys}. prop is location, rotation_euler (radians),
scale, or attach. Keys are ascending [frame,localVector] pairs or [frame,newParentId]
for attachment. Frames start at 1 per shot. State carries over. Preserve authored beats,
frame locks and IDs. Assign a frame to each sound cue. Keep generated steering renders
economical. Supply exactly the requested shot sequence."""


def plan(film, shots, board, job, model):
    payload = dict(film=film, requested_shots=[s["id"] for s in shots])
    prompt = CONTRACT + "\n" + json.dumps(payload, ensure_ascii=False)
    (job/"request.txt").write_text(prompt, encoding="utf-8")
    shutil.copyfile(board, job/"references.jpg")
    output = job/"scene.json"
    cli = shutil.which("codex.cmd") or shutil.which("codex")
    if not cli:
        raise RuntimeError("Install and sign in to the Codex CLI to generate a scene.")
    with tempfile.TemporaryDirectory() as scratch:
        subprocess.run([cli, "exec", "--ephemeral", "--skip-git-repo-check",
                        "--sandbox", "read-only", "-m", model, "-i", str(job/"references.jpg"),
                        "-o", str(output), "-"], input=prompt.encode(), cwd=scratch, check=True)
    scene = json.loads(output.read_text(encoding="utf-8-sig"))
    scene["size"] = film["size"]
    output.write_text(json.dumps(scene, indent=2), encoding="utf-8")
    if scene["fps"] != film["fps"] or [s["id"] for s in scene["shots"]] != payload["requested_shots"]:
        raise ValueError("Generated scene changed the film rate or requested shot sequence")
    for source, shot in zip(shots, scene["shots"]):
        if shot["set"] != source["set"] or shot["frames"] < 1 or source.get("frames", shot["frames"]) != shot["frames"]:
            raise ValueError(f"Invalid set or duration for {source['id']}")
    return output, scene
