"""Compile a script into shared sets, one cast registry, camera cuts, blocking and pose beats."""
import json
import math
import re

from takefive.director import CAST_INSTRUCTION, CAST_SCHEMA, ask, check_cast, choice, record


PALETTE = {"orange": "B85931", "teal": "318780", "blue": "426582", "navy": "35455D", "olive": "626E47",
           "gray": "76838A", "brown": "76513C", "black": "303238", "red": "AD4941", "yellow": "C69D42",
           "cream": "DBCCAB", "white": "DEE2DE", "purple": "755E80"}
ROLES = ["absent","stand","sit","talk","talk_seated","listen","listen_seated","enter","exit","walk","walk_away","open","lean"]
MARKS = ["carry","door","outside","visitor","staff","work","center","left","right","far"]
POSES = ["none","nod","look","lean","point","raise_hand","talk"]
VIEWS = ["wide","medium","close","insert"]


def directed_poses(text, length):
    signals = [(r"rais\w* (?:\w+ )?hand","raise_hand"),(r"\bpoints?\b","point"),
               (r"\bnods?\b","nod"),(r"looks? (?:over|back)","look"),(r"looks? up","look_up"),(r"\bleans? in","lean")]
    cues = []
    for clause in re.split(r"(?<!\d)\.|\.(?!\d)|;|\band then\b|\band\s+(?=at\b)",text.lower()):
        for pattern,kind in signals:
            if not re.search(pattern,clause):
                continue
            at_frame = re.search(r"\b(?:at )?frame\s+(\d+)\b",clause)
            at_time = re.search(r"\bat\s+(\d+(?:\.\d+)?)\s*(?:seconds?|s)\b",clause)
            f = int(at_frame[1]) if at_frame else round(24*float(at_time[1])) if at_time else length//2
            if not 0<=f<length:
                raise ValueError(f"A directed pose at frame {f} falls outside a {length}-frame shot")
            cues.append({"frame":f,"pose":kind,"weight":1.})
    return cues


def split_cuts(text):
    # Protect dialogue containing an editorial term, maintaining the original offsets.
    clean = re.sub(r'["“][^"”]*["”]', lambda m: "@"*(len(m[0])-1)+".", text)
    starts = {0}
    for pattern in (r"(?im)^\s*(?=(?:SHOT\s+\d+\b|(?:INT|EXT)\.\s))",
                    r"(?i)(?<=[.!?])\s+(?=(?:cut\s+(?:to|back|wide|outside|inside)|(?:outside|inside)\s*,))"):
        for m in re.finditer(pattern, clean):
            starts.add(m.end())
    positions = sorted(starts | {len(text)})
    return [text[a:b].strip() for a,b in zip(positions, positions[1:]) if text[a:b].strip()]


def get_beats(story, count, seed, cache, planner=None):
    ask_model = planner or ask
    explicit = split_cuts(story)
    cast = ask_model(CAST_INSTRUCTION, story, CAST_SCHEMA, seed, cache, 1400, check_cast)
    if len(explicit) > 1 or count == 1:
        if count and len(explicit) != count:
            raise ValueError(f"The script supplies {len(explicit)} cuts; --shots requests {count}")
        return cast, explicit
    # Partition the author's actual sentences. Every word and quoted line belongs to exactly one shot.
    masked = re.sub(r'["“][^"”]*["”]',lambda m:"@"*(len(m[0])-1)+".",story)
    ends = [m.end() for m in re.finditer(r"(?<=[.!?])\s+|\n+",masked)]
    pos = [0,*ends,len(story)]
    sentences = [story[a:b].strip() for a,b in zip(pos,pos[1:]) if story[a:b].strip()]
    n = count if count is not None else min(len(sentences),max(5,len(re.findall(r'["“][^"”]*["”]',story))+1))
    if not 1<=n<=24:
        raise ValueError("Use between one and 24 shots for a single steering draft")
    if n>len(sentences):
        keys = [f"shot{i:02}" for i in range(1,n+1)]
        schema = record(**{k:{"type":"string"} for k in keys})
        instruction = ("Break the given short script into exactly the requested camera shots. "
                       "Use each field for a concrete visible beat. Keep the action order, character names and "
                       "quoted dialogue from the original. Use reactions or closer views to give an action coverage.")
        def check_coverage(answer):
            if not all(isinstance(answer[k],str) and answer[k].strip() for k in keys):
                raise ValueError("Every shot needs a visible direction")
        expanded = ask_model(instruction,story,schema,seed,cache,160*n,check_coverage)
        return cast,[expanded[k] for k in keys]
    # Prefer cutting before a new named action, keeping an attributed voice or pronoun with its antecedent.
    boundaries = [0]
    for i in range(1,n):
        lo,hi = boundaries[-1]+1,len(sentences)-(n-i)
        def cost(j):
            attachment = 0.
            if re.match(r"(?i)^it (?:says|reads)\b",sentences[j]):
                attachment = 3.
            elif re.match(r"(?i)^(he|she|they|and|then)\b",sentences[j]):
                attachment = 1.
            return abs(j-len(sentences)*i/n)+attachment
        boundaries.append(min(range(lo,hi+1),key=cost))
    boundaries.append(len(sentences))
    return cast,[" ".join(sentences[a:b]) for a,b in zip(boundaries,boundaries[1:])]


def setup(cast, story, seed, cache, planner=None):
    ask_model = planner or ask
    people, places = [a["name"] for a in cast["people"]], [a["name"] for a in cast["places"]]
    wardrobe = record(coat=choice(PALETTE), hair=choice(["black","brown","gray"]), cap=choice(["none",*PALETTE]))
    space = record(kind=choice(["office","radio_room","interior","street","snow_exterior"]),
                   door_side=choice(["left","right"]), door_color=choice(PALETTE))
    schema = record(cast=record(**{p:wardrobe for p in people}), sets=record(**{p:space for p in places}))
    instruction = ("Choose a simple physical set for each named place and stable wardrobe for each visible actor. "
                   "Honor explicitly stated garment and door colors. Use cap none unless headwear is described. "
                   "street is outdoors; snow_exterior is outdoors in snow. Use the same door color on both sides.")
    answer = ask_model(instruction, json.dumps({"script":story,"people":cast["people"],"places":cast["places"]}),
                 schema, seed, cache, 650, lambda s: None)
    looks = {}
    for p in cast["people"]:
        k = p["name"]
        a = answer["cast"][k]
        looks[k] = {"description":p["appearance"],"coat":PALETTE[a["coat"]],"hair":PALETTE[a["hair"]],
                    "cap":PALETTE.get(a["cap"]), "skin":"B8876E", "pants":"394955", "boots":"333237",
                    "glasses":bool(re.search(r"\bglasses\b",p["appearance"],re.I)),
                    "bun":bool(re.search(r"\bbun\b",p["appearance"],re.I))}
    sets = {p["name"]:{**answer["sets"][p["name"]],"description":p["appearance"],
                       "door_hex":PALETTE[answer["sets"][p["name"]]["door_color"]]} for p in cast["places"]}
    for name,v in sets.items():
        if not re.search(r"\b(street|outside|exterior|sidewalk|outdoors)\b",name,re.I):
            if re.search(r"\b(radio|transceiver)\b",v["description"],re.I) and re.search(
                    r"\b(room|kitchen|walls|office|workbench)\b",v["description"],re.I):
                v["kind"] = "radio_room"
    indoors = [p for p,v in sets.items() if v["kind"] not in ("street","snow_exterior")]
    for p,v in sets.items():
        v["door_id"] = indoors[0] if len(indoors)==1 else p
    return looks, sets


def direct(story, count, seed, cache, planner=None):
    ask_model = planner or ask
    cast, beats = get_beats(story, count, seed, cache, planner)
    people, sets = setup(cast, story, seed, cache, planner)
    actor = record(action=choice(ROLES), mark=choice(MARKS), to=choice(MARKS),
                   face=choice(["carry","front","door","work","left","right",*people]),
                   pose=choice(POSES))
    shot = record(place=choice(sets), camera=choice(VIEWS), focus=choice(["room",*people]),
                  cast=record(**{name:actor for name in people}))
    keys = [f"shot{i:02}" for i in range(1,len(beats)+1)]
    instruction = ("Block the supplied numbered beats in order. Preserve exactly what happens in each beat. "
                   "An entrance through a door uses enter. A departure through a door uses exit. "
                   "Already walking outdoors uses walk_away. Do not add people from dialogue. Camera wide shows physical "
                   "actions or multiple performers; close singles frame the named speaker. A camera cut alone never moves "
                   "a person. The staff mark is seated behind the desk, visitor is in front. Use carry for an established "
                   "position. Face the conversation partner. Choose absent for an offscreen voice or an absent person. "
                   "Use action talk_seated or listen_seated for seated performers. Use one interior pose when called "
                   "for. Return only the bounded JSON. 'Cut to X' makes X the focus.")
    source = {"whole_script":story, "sets":{k:{a:b for a,b in v.items() if a not in ("door_hex","door_id")} for k,v in sets.items()},
              "cast":list(people), "beats":dict(zip(keys,beats))}
    def check(answer):
        for k in keys:
            s = answer[k]
            if s["focus"] in people and s["cast"][s["focus"]]["action"]=="absent":
                raise ValueError(f"{k}: the camera's subject must be present")
    choices = ask_model(instruction, json.dumps(source), record(**{k:shot for k in keys}), seed, cache,
                  250+len(keys)*(100+72*len(people)), check)
    shots, continuity, last_subject = [], {}, None
    for k, beat in zip(keys,beats):
        s = choices[k]
        duration = re.search(r"\b(5|8|10)\s*(?:s\b|seconds?\b)",beat,re.I)
        length = 24*(int(duration[1]) if duration else 5)
        view, focus = s["camera"], s["focus"]
        if re.match(r"(?i)cut wide\b",beat):
            view, focus = "wide", "room"
        for name in people:
            if re.match(r"(?i)cut to\s+"+re.escape(name)+r"\b",beat):
                view, focus = "close", name
        directions = re.sub(r'["“][^"”]*["”]', '', beat)
        named = sorted((m.start(),m.end(),name) for name in people for m in
                       re.finditer(r"\b"+re.escape(name)+r"\b",directions,re.I))
        clauses = {}
        for i,(start,end,name) in enumerate(named):
            time_prefix = re.search(r"\bat\s+(?:frame\s+\d+|\d+(?:\.\d+)?\s*(?:seconds?|s))\s*,?\s*$",
                                    directions[:start],re.I)
            clause = (time_prefix[0] if time_prefix else "")+" "+directions[end:named[i+1][0] if i+1<len(named) else len(directions)]
            clauses[name] = clauses.get(name,"")+" "+clause
        if not clauses and last_subject and re.search(r"\b(she|he|they)\b",directions,re.I):
            clauses[last_subject] = directions
        place = s["place"]
        if shots and re.match(r"(?i)^cut\s+(?:wide\b|to\s+(?:"+ "|".join(map(re.escape,people)) +r")\b)",beat):
            place = shots[-1]["set"]
        elif re.match(r"(?i)^(outside\b|ext\.)",beat):
            place = next((k for k,v in sets.items() if v["kind"] in ("street","snow_exterior")),place)
        elif shots and not re.search(r"(?i)^(?:at |in |int\.|ext\.|outside\b|inside\b|back at )",beat):
            place = shots[-1]["set"]
        solo_cut = view=="close" and focus in people and (len(clauses)<=1 or re.match(r"(?i)^cut to\b",beat))
        sound_insert = not clauses and bool(re.search(r"\bknocks?\b",directions,re.I))
        if sound_insert:
            view,focus = "insert","door"
        actors, prop_in_frame = {}, None
        for name,b in s["cast"].items():
            last = continuity.get((place,name))
            if sound_insert:
                continue
            if solo_cut and name!=focus or (clauses and name not in clauses and not last):
                continue
            words = clauses.get(name,"").lower()
            action, mark, dest, gesture = b["action"],b["mark"],b["to"],b["pose"]
            if re.search(r"\b(is (?:already )?gone|disappears?|has vanished|is missing)\b",words):
                continuity[(place,name)] = {"seated":False,"present":False}
                continue
            if re.search(r"\balone\b",directions,re.I) and clauses and name not in clauses:
                continue
            if name not in clauses and last and last["present"]:
                action = "sit" if last["seated"] else "stand"
                mark = "carry"
            if last and not last["present"] and name not in clauses:
                continue
            # Literal stage directions override a model's invented move on a camera cut.
            seated = bool(last and last["seated"])
            if re.search(r"\b(seated|sitting|sits)\b", words):
                seated = True
            if re.search(r"\b(stands|standing|gets up|rises)\b", words):
                seated = False
            device_voice = re.search(r"\b(hears?|listen\w*)\b.*\b(radio|speaker|intercom|receiver)\b",words)
            if device_voice:
                action,mark,gesture = "listen","work","look"
            elif re.search(r"\b(enters?|walks? in(?:to)?|steps? in(?:to)?|comes? in)\b",words):
                action,mark,dest = "enter","outside","visitor"
            elif re.search(r"\b(exits?|leaves?|(?:goes|walks?|steps?|heads?) (?:back )?out)\b",words):
                action,mark,dest = "exit","carry","outside"
            elif re.search(r"\bwalk(?:s|ing)? away\b",words):
                action,mark,dest = "walk_away","door","far"
            elif re.search(r"\bopens?\b.*\bdoor\b",words):
                action,mark = "open","door"
            elif re.search(r"\b(asks?|says?|repl(?:y|ies)|speaks?|answers?)\b",words):
                action = "talk_seated" if seated else "talk"
            elif re.search(r"\b(leans?|leaning)\b",words):
                action = "lean"
            elif re.search(r"\b(seated|sitting|sits|stays|stands|standing|listen(?:s|ing)?)\b",words):
                action = ("listen_seated" if seated else "listen") if "listen" in words else ("sit" if seated else "stand")
            if action in ("talk","talk_seated","stand","sit","listen","listen_seated","lean"):
                if last and last["present"]:
                    mark = "carry"
                    if action in ("talk","talk_seated","listen","listen_seated"):
                        action = action.split("_")[0]+("_seated" if seated else "")
                if re.search(r"behind (?:the |her |his |a )?(?:desk|counter)",words) or (seated and not last):
                    mark = "staff"
            if action=="absent":
                continue
            through = action=="walk_away" or bool(re.search(r"\balready walking\b", beat, re.I) and action=="walk")
            if action in ("talk","talk_seated","lean"):
                gesture = "lean" if action=="lean" else "talk"
            poses = [] if gesture=="none" else [{"frame":length//2,"pose":gesture,"weight":1.0}]
            if "listen" in words and action.startswith("talk"):
                poses = [{"frame":length//4,"pose":"nod","weight":.65},
                         {"frame":2*length//3,"pose":"talk","weight":1.}]
            authored = directed_poses(words,length)
            if authored:
                poses = authored
            if action=="lean" and re.search(r"\b(microphone|mic)\b",words) and sets[place]["kind"]=="radio_room":
                if not re.search(r"\bwide\b",beat,re.I):
                    view,focus,prop_in_frame = "medium",name,"microphone"
                for cue in poses:
                    if cue["pose"]=="lean":
                        cue["hold_frames"] = length-1-cue["frame"]
            actors[name] = {"action":action,"from":mark,"to":dest,"face":"work" if device_voice or action=="lean" else b["face"],
                            "start_frame":0 if through else round(.07*length),
                            "end_frame":length-1 if through or action=="exit" else round(.87*length),
                            "moving_at_start":through,"moving_at_end":through or action=="exit",
                            "poses":poses}
            continuity[(place,name)] = {"seated":action in ("sit","talk_seated","listen_seated") or (action=="lean" and seated),
                                        "present":action!="exit"}
        visible_mentions = [n for _,_,n in named if n in actors]
        if visible_mentions:
            last_subject = visible_mentions[-1]
        if focus not in ("room","door","work") and focus not in actors:
            focus = next(iter(actors),"room")
        camera = {"view":view,"focus":focus}
        if prop_in_frame:
            camera["include_prop"] = prop_in_frame
        shots.append({"id":k,"script":beat,"set":place,"frames":length,"camera":camera,"actors":actors})
    plan = {"version":1,"title":cast["title"],"fps":24,"width":640,"height":384,
            "cast":people,"sets":sets,"shots":shots}
    validate(plan)
    return plan


def validate(plan):
    if plan["version"]!=1 or not plan["shots"] or not plan["sets"] or plan["fps"]!=24:
        raise ValueError("Expected a version 1 steering film with sets and shots at 24 fps")
    if any(type(plan[k]) is not int or not 64 <= plan[k] <= 4096 or plan[k]%2 for k in ("width","height")):
        raise ValueError("Use even dimensions from 64 to 4096 pixels")
    ids = set()
    for shot in plan["shots"]:
        ident, n, cam = shot["id"], shot["frames"], shot["camera"]
        if ident in ids or not re.fullmatch(r"[A-Za-z0-9_-]+",ident) or type(n) is not int or not 2 <= n <= 480:
            raise ValueError(f"Invalid or duplicate shot ID or frame count: {ident}")
        ids.add(ident)
        if (shot["set"] not in plan["sets"] or cam["view"] not in VIEWS
                or cam["focus"] not in ["room","door","work",*shot["actors"]]):
            raise ValueError(f"{ident}: invalid set, camera or focus")
        for name,b in shot["actors"].items():
            if (name not in plan["cast"] or b["action"] not in ROLES[1:] or b["from"] not in MARKS
                    or b["to"] not in MARKS or b["face"] not in ["carry","front","door","work","left","right",*plan["cast"]]):
                raise ValueError(f"{ident}: invalid actor or blocking for {name}")
            if not (type(b["start_frame"]) is int and type(b["end_frame"]) is int and 0<=b["start_frame"]<b["end_frame"]<n):
                raise ValueError(f"{ident}: {name}'s action needs increasing frame indices inside the shot")
            for p in b["poses"]:
                if (type(p["frame"]) is not int or not 0<=p["frame"]<n or p["pose"] not in [*POSES[1:],"look_up"]
                        or not math.isfinite(p["weight"]) or not 0<=p["weight"]<=1
                        or type(p.get("hold_frames",0)) is not int or not 0<=p.get("hold_frames",0)<n-p["frame"]):
                    raise ValueError(f"{ident}: invalid timed pose for {name}")
