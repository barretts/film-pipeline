"""Turn a story into cast, locations, and a shot list with the bundled CPU language model."""
import json
import os
from pathlib import Path
import re
import subprocess
from itertools import combinations

from .script import ROOT, binary, digest, dump, file_stamp
from .production import staging


def record(**fields):
    return {"type":"object","properties":fields,"required":list(fields),"additionalProperties":False}


def items(item, minimum=0, maximum=8):
    return {"type":"array","items":item,"minItems":minimum,"maxItems":maximum}


def choice(values):
    return {"type":"string","enum":list(values)}


TEXT = {"type":"string"}
CAST_SCHEMA = record(title=TEXT, people=items(record(name=TEXT, appearance=TEXT, voice=choice(["Kristin","Ryan"]))),
                     places=items(record(name=TEXT, appearance=TEXT),1))
CAST_INSTRUCTION = (
    "You are casting and locating a live-action short film from the user's story. Return JSON. "
    "Use the names from the story. List each distinct person once in people. For each give one "
    "short concrete visual identity: age, face, hair and a specific outfit. Cast a consistent voice "
    "for each performance from the two available recordings: Kristin, a woman's voice, and Ryan, "
    "a man's voice. Follow the character description and any stated voice preference. In places list the physical filming locations. "
    "Give each a short name and a visual description with its layout, light and recurring props. "
    "Describe empty sets without people. Keep the story's actual setting, period and characters."
)
SHOTS_INSTRUCTION = (
    "Direct a live-action short from the supplied story, identities and sets. Make a chronological "
    "edit that tells the given ending. Each shot has one primary action. opening describes the "
    "physical state and composition at frame one; action describes the observable change during "
    "the take. Subjects entering or leaving move in a consistent screen direction. Track which "
    "people and props are still present after a cut. Keep every action in the story. Use inserts "
    "and wide views for physical actions and isolation on the actual speaker for a talking close-up. "
    "visible lists only the named people the camera can see. If the speaker is heard through a "
    "device choose radio; if heard out of frame choose offscreen. For a silent picture choose "
    "mode silent, speaker none, and no line. Pick a practical sound cue only when the story calls "
    "for it. Most shots are 5 seconds; use 8 or rarely 10 for longer action. delivery early is "
    "normal, after_beat allows a reaction, across_cut lets a line finish over the next shot. "
    "Use separate camera setups for successive perspectives. Never add subtitles or titles."
)


def clean(value):
    return " ".join(value.split()).strip()


def ask(system, user, schema, seed, directory, tokens, check):
    model = Path(os.environ.get("TAKEFIVE_MODEL", ROOT/"runtime"/"planner.gguf"))
    exe = binary("llama-completion")
    key = digest("director-v1",system,user,schema,seed,file_stamp(model),file_stamp(exe))
    directory.mkdir(parents=True,exist_ok=True)
    target = directory/(key+".json")
    if target.exists():
        answer=json.loads(target.read_text(encoding="utf-8"))
        check(answer)
        return answer
    message = user
    with staging(directory) as scratch:
        dump(scratch/"schema.json",schema)
        for attempt in range(3):
            prompt = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{message}<|im_end|>\n<|im_start|>assistant\n"
            (scratch/"prompt.txt").write_text(prompt,encoding="utf-8")
            result = subprocess.run([exe,"-m",str(model),"-ngl","0","-t","6","-c","8192","-n",str(tokens),
                                     "--temp","0","--seed",str(seed),"-no-cnv","--no-display-prompt","--no-warmup",
                                     "-jf",str(scratch/"schema.json"),"-f",str(scratch/"prompt.txt")],
                                    capture_output=True,timeout=900)
            if result.returncode:
                raise RuntimeError("Local director failed: "+result.stderr.decode(errors="replace")[-1200:])
            raw = result.stdout.decode("utf-8",errors="replace")
            try:
                answer,_ = json.JSONDecoder().raw_decode(raw[raw.index("{"):])
                check(answer)
            except (ValueError,KeyError,TypeError) as error:
                if attempt == 2:
                    raise ValueError(f"Local director could not compile the story after three attempts: {error}") from error
                print(f"Local director retry {attempt+2}: {error}",flush=True)
                message = f"{user}\n\nCorrect this issue in the previous draft: {error}. Return a complete new JSON object."
                continue
            staged=scratch/"answer.json"
            dump(staged,answer)
            os.replace(staged,target)
            return answer


def check_cast(plan):
    if not clean(plan["title"]) or not plan["places"]:
        raise ValueError("The film needs a title and a location")
    for group in ("people","places"):
        names=[clean(a["name"]).casefold() for a in plan[group]]
        if len(names)!=len(set(names)) or "none" in names or any(not n for n in names):
            raise ValueError(f"Use distinct names in {group}")
        if any(not clean(a["appearance"]) for a in plan[group]):
            raise ValueError(f"A visual description is missing in {group}")


def dialogue_slots(story, matches, count):
    """Keep dialogue verbatim, in reading order, near its relative position in the brief."""
    positions = [(m.start()+m.end())/(2*len(story)) for m in matches]
    placements = min(combinations(range(count),len(matches)),
                     key=lambda slots:sum(((slot+.5)/count-pos)**2 for slot,pos in zip(slots,positions)))
    return dict(zip(placements,matches))


def delivery_modes(context):
    """Reserve receiver audio and offscreen voices for speech with those cues in the brief."""
    clauses = re.split(r"(?<=[.!?])\s+",context.strip())
    current = clauses[-1].lower()
    if re.search(r"\b(it|the voice|the recording|the message)\s+(says|repeats|continues|warns|plays)",current):
        current = " ".join(clauses[-2:]).lower()
    if re.search(r"\b(into|to)\s+(?:a |the |her |his |their )?(?:microphone|mic|radio|transmitter|handset)\b",current):
        return ["onscreen"]
    device = r"(?:radio|recording|intercom|loudspeaker|earpiece|speakerphone|voicemail|receiver|telephone|phone|public address)"
    if re.search(r"\b(?:from|over|through|on) (?:an? |the |her |his |their )?"+device+r"\b",current):
        return ["radio"]
    if re.search(r"\b"+device+r"\b",current):
        return ["radio","onscreen"]
    if re.search(r"off.?screen|out of (?:frame|view|sight)|voice.?over|unseen|from (?:outside|behind|another room)|narrat",current):
        return ["offscreen","onscreen"]
    return ["onscreen"]


def draft(story, count, seed, cache):
    if not story.strip():
        raise ValueError("The story is empty.")
    matches = list(re.finditer(r'["“]([^"“”]+)["”]',story))
    count = count if count is not None else min(16,max(5,len(matches)+1))
    if not 1 <= count <= 16 or len(matches)>count:
        raise ValueError("Choose 1–16 shots and at least one shot per quoted speaking turn.")
    def check_people(answer):
        check_cast(answer)
        if matches and not answer["people"]:
            raise ValueError("The quoted dialogue requires at least one speaking character or narrator")
    cast = ask(CAST_INSTRUCTION,story,CAST_SCHEMA,seed,cache,1400,check_people)
    names = [p["name"] for p in cast["people"]]
    places = [p["name"] for p in cast["places"]]
    slots = dialogue_slots(story,matches,count)
    keys = [f"shot{i:02}" for i in range(1,count+1)]
    fields, assigned = {}, {}
    quote_context = {m.start():story[matches[j-1].end() if j else 0:m.start()] for j,m in enumerate(matches)}
    for i,key in enumerate(keys):
        if matches:
            speaking = i in slots
            modes = delivery_modes(quote_context[slots[i].start()]) if speaking else ["silent"]
            speakers = names if speaking else ["none"]
            assigned[key] = clean(slots[i].group(1)) if speaking else ""
        else:
            modes = ["silent","onscreen","offscreen","radio"] if names else ["silent"]
            speakers = ["none",*names]
        fields[key] = record(place=choice(places),visible=items(choice(names),maximum=len(names)) if names else
                             {"type":"array","items":TEXT,"maxItems":0},camera=choice(["wide","medium","close","insert"]),
                             opening=TEXT,action=TEXT,speaker=choice(speakers),mode=choice(modes),
                             **({} if matches else {"line":TEXT}),
                             delivery=choice(["early","after_beat","across_cut"]),
                             cue=choice(["none","knock","footsteps","door","wind","rain","bell","click","static"]),
                             seconds={"type":"integer","enum":[5,8,10]})
    schema = record(**fields)
    instruction = SHOTS_INSTRUCTION + (" timed_lines fixes the dialogue for each shot. Locate each line "
                  "in the story to identify its speaker, action and source. Empty slots show intervening action."
                  if matches else " Supply a line only if the brief calls for speech. Respect silent action.")
    request=json.dumps({"story":story,"cast_and_locations":cast,"shot_order":keys,"timed_lines":assigned},ensure_ascii=False)
    def check(answer):
        for i,key in enumerate(keys):
            s = answer[key]
            if not clean(s["opening"]) or not clean(s["action"]):
                raise ValueError(f"Shot {i+1} needs a visible opening and action")
            if s.get("line") and (s["speaker"] not in names or s["mode"]=="silent"):
                raise ValueError(f"Shot {i+1} has a line. Assign its speaker and an audible mode")
    shots=ask(instruction,request,schema,seed,cache,min(6250,350*count+280),check)
    result=[]
    for key in keys:
        s=dict(shots[key])
        s["line"]=assigned[key] if matches else clean(s["line"])
        if not s["line"]:
            s.update(mode="silent",speaker="none")
        else:
            if not matches and s["mode"]=="radio" and "radio" not in delivery_modes(s["opening"]+" "+s["action"]):
                s["mode"]="onscreen" if s["speaker"] in s["visible"] else "offscreen"
            if s["mode"]=="onscreen":
                s["visible"]=[s["speaker"]]
        s["visible"]=list(dict.fromkeys(s["visible"]))
        result.append(s)
    return {**cast,"shots":result}
