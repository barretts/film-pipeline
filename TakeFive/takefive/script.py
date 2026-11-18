"""Compile prose locally and validate the director-editable production plan."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("TAKEFIVE_WORK", ROOT / "work")).resolve()
FPS = 24
COLORS = {"rust": "C65C37", "teal": "287978", "navy": "334860", "olive": "7B8051",
          "ochre": "C89B4B", "plum": "87536F", "blue": "3376A0", "cream": "DFCFAB"}
SHOTS = ("arrival", "employee", "manager", "departure", "street")
CAMERAS = ("wide", "employee", "manager", "wide", "exterior")
VOICES = {"employee": "en_US-ryan-medium", "manager": "en_US-kristin-medium"}


def shot_ids(scene):
    names = [shot["id"] for shot in scene["shots"]]
    if (not names or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", n) for n in names)
            or len({n.casefold() for n in names}) != len(names)):
        raise ValueError("Each shot needs a unique filename-safe ID.")
    return names


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(*items):
    return hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def binary(name):
    exe = name + (".exe" if os.name == "nt" else "")
    groups = {"piper": "piper", "rhubarb": "rhubarb", "llama-completion": "llama"}
    override = os.environ.get("TAKEFIVE_" + name.replace("-", "_").upper())
    if override:
        path = Path(override)
        if not path.is_file():
            raise ValueError(f"Configured {name} does not exist: {path}")
        return str(path.resolve())
    if name in groups:
        path = ROOT / "runtime" / groups[name] / exe
        if path.is_file():
            return str(path)
    found = shutil.which(name)
    if found:
        return found
    if name == "blender" and os.name == "nt":
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as base:
                    for i in range(winreg.QueryInfoKey(base)[0]):
                        try:
                            with winreg.OpenKey(base, winreg.EnumKey(base, i)) as key:
                                if winreg.QueryValueEx(key, "DisplayName")[0] == "Blender":
                                    path = Path(winreg.QueryValueEx(key, "InstallLocation")[0]) / exe
                                    if path.is_file():
                                        return str(path)
                        except OSError:
                            continue
            except OSError:
                pass
    raise ValueError(f"Missing {name}. See README.md or set TAKEFIVE_{name.replace('-', '_').upper()}.")


def file_stamp(path):
    path = Path(path)
    info = path.stat()
    return [path.name, info.st_size, info.st_mtime_ns]


def number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be a number from {low} to {high}")
    return value


def validate(plan):
    if plan.get("format") != 1:
        raise ValueError("Expected a TakeFive scene JSON with format 1.")
    if not isinstance(plan.get("title"), str) or not plan["title"].strip():
        raise ValueError("The scene needs a title.")
    for role in VOICES:
        actor = plan["cast"][role]
        if not all(isinstance(actor.get(k), str) and actor[k].strip() for k in ("name", "line", "voice", "coat")):
            raise ValueError(f"Missing name, line, voice or coat for {role}")
        if actor["coat"] not in COLORS or not re.fullmatch(r"[\w-]+", actor["voice"]):
            raise ValueError(f"Invalid coat or voice name for {role}")
        if len(actor["line"]) > 600:
            raise ValueError("A speaking turn is limited to 600 characters in this scene.")
    if plan["door"] not in COLORS:
        raise ValueError("Unknown door color.")
    if [s["id"] for s in plan["shots"]] != list(SHOTS):
        raise ValueError("The office coverage is arrival, employee, manager, departure, street.")
    for shot in plan["shots"]:
        number(shot["seconds"], 2, 30, "shot seconds")
        number(shot["lens"], 18, 90, "camera lens")
    number(plan["bridge"], .1, 3, "speech overlap")
    number(plan["reply_beat"], .1, 3, "listening beat")
    number(plan["exit_crossing"], .35, .94, "door crossing as a fraction of the departure shot")
    return plan


def from_prose(source, cache):
    model = Path(os.environ.get("TAKEFIVE_MODEL", ROOT / "runtime" / "planner.gguf"))
    if not model.is_file():
        raise ValueError("A local GGUF planner is required for plain text. See setup_runtime.py.")
    colors = list(COLORS)
    fields = {"supported": {"type": "boolean"}}
    for key in ("reason", "title", "employee_name", "manager_name", "employee_line", "manager_line"):
        fields[key] = {"type": "string"}
    for key in ("employee_coat", "manager_coat", "door"):
        fields[key] = {"type": "string", "enum": colors}
    schema = {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}
    instruction = (
        "Adapt the user's scene to a short animated dispatch-office visit. Supported blocking: "
        "one visitor enters, exchanges one speaking turn each with a seated manager, then leaves; "
        "outside we see the visitor walk away. If the requested location, number of speakers, or "
        "essential action is incompatible, set supported false and give the reason. Otherwise set true. "
        "Extract names, wardrobe and dialogue from the text. If no dialogue is given, write short "
        "natural lines that express the actual purpose of this visit. Use rust for employee coat, teal "
        "for manager coat and blue for door unless specified. Preserve quoted wording exactly. "
        "Return only a JSON object. Output fields in this order: " + ", ".join(fields) + "."
    )
    stamp = digest("prose-v1", instruction, schema, file_stamp(model), file_stamp(binary("llama-completion")), source)
    cached = cache / (stamp + ".json")
    if cached.exists():
        return validate(json.loads(cached.read_text(encoding="utf-8")))
    prompt = "<|im_start|>system\n" + instruction + "<|im_end|>\n<|im_start|>user\n" + source + "<|im_end|>\n<|im_start|>assistant\n"
    with tempfile.TemporaryDirectory(dir=cache) as folder:
        d = Path(folder)
        dump(d / "schema.json", schema)
        (d / "prompt.txt").write_text(prompt, encoding="utf-8")
        result = subprocess.run([binary("llama-completion"), "-m", str(model), "-ngl", "0",
                                 "-t", "6", "-c", "3072", "-n", "680", "--temp", "0",
                                 "--seed", "7", "-no-cnv", "--no-display-prompt", "--no-warmup",
                                 "-jf", str(d / "schema.json"), "-f", str(d / "prompt.txt")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        out = result.stdout.decode("utf-8", errors="replace")
        if result.returncode or "{" not in out:
            raise ValueError(f"Local planner failed ({result.returncode}): " +
                             (result.stderr + result.stdout).decode(errors="replace")[-1500:])
        raw, _ = json.JSONDecoder().raw_decode(out[out.index("{"):])
    if not raw["supported"]:
        raise ValueError("This production cannot stage that request: " + raw["reason"])
    lines = re.findall(r'["“]([^"“”]+)["”]', source)
    if len(lines) > 2:
        raise ValueError("The office visit supports two speaking turns. Give one line to each character.")
    roles = list(VOICES)
    cast = {role: {"name": raw[role + "_name"], "line": raw[role + "_line"], "voice": VOICES[role],
                   "coat": raw[role + "_coat"]} for role in roles}
    if len(lines) == 2:
        for role, line in zip(roles, lines):
            cast[role]["line"] = line
    plan = validate({"format": 1, "title": raw["title"], "door": raw["door"], "cast": cast,
                     "bridge": .95, "reply_beat": .55, "exit_crossing": .75,
                     "shots": [{"id": key, "seconds": sec, "lens": lens} for key, sec, lens in
                               zip(SHOTS, (5, 5, 8, 5, 5), (30, 52, 55, 30, 34))]})
    with tempfile.NamedTemporaryFile(dir=cache, suffix=".tmp", delete=False) as tmp:
        tmp.write(json.dumps(plan, ensure_ascii=False).encode())
    os.replace(tmp.name, cached)
    return plan
