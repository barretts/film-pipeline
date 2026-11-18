"""Compile cast, locations and story beats into local FLUX and H3 conditioning."""
from takefive.script import digest


CAMERAS = {"close":"eye-level close-up","medium":"medium shot","wide":"wide establishing shot",
           "insert":"tight detail insert"}
STYLE = "Naturalistic live-action cinema, plausible materials, practical light, realistic proportions."


def seed_for(seed, stage, name):
    return int(digest(seed,stage,name)[:8],16)


def recipes(plan, names, timing, seed, style):
    photos = {}
    people = {p["name"]:(f"person{i:02}",p["appearance"]) for i,p in enumerate(plan["people"],1)}
    locations = {p["name"]:(f"set{i:02}",p["appearance"]) for i,p in enumerate(plan["places"],1)}

    def photo(key, prompt, refs=(), size=None):
        photos[key] = {"references":list(refs),"seed":seed_for(seed,"photo",key),"prompt":f"{prompt} {style}"}
        if size:
            photos[key]["size"] = size

    for name,(key,appearance) in people.items():
        photo(key,f"Single casting photograph of {name}. {appearance}. Face and full hairstyle clearly visible, "
              "upper torso, relaxed closed mouth, simple background, no text or collage.",size=[512,704])
    for name,(key,appearance) in locations.items():
        photo(key,f"Wide interior or exterior location photograph of the empty {name}. {appearance}. "
              "Show the architecture, spatial relationships and practical objects, unoccupied, no people.")
    motion = {"camera_width":1280,"camera_height":704,"steps":4,"sparsity":.75,
              "bridge_alpha":.15,"shift_video":6.0,"shift_audio":3.0,
              "cast_crops":{key:[0,0,1,1] for key,_ in people.values()},"shots":{}}
    for i,(key,s) in enumerate(zip(names,plan["shots"],strict=True)):
        location,setting = locations[s["place"]]
        cast = [people[p][0] for p in s["visible"]]
        framing = CAMERAS[s["camera"]]
        if s["mode"] == "onscreen":
            framing = "single chest-up speaking shot, three-quarter or frontal face, mouth unobstructed"
        layout = f"Image 1 establishes the layout, fixtures and light of {s['place']}. {setting}."
        identity = " ".join(f"Image {j+2} identifies {p}: {people[p][1]}." for j,p in enumerate(s["visible"]))
        occupants = ("The only visible people are "+", ".join(s["visible"])+".") if cast else "The camera sees no people."
        photo(key,f"One complete cinematic frame, {framing}. {s['opening']}. {occupants} {layout} {identity} "
              "Use the reference photos to stage this new camera angle. No printed words, borders, inset pictures or captions.",
              [location,*cast])
        refs = " ".join(f"{p} matches <Picture {j+1}>, {people[p][1]}." for j,p in enumerate(s["visible"]))
        if not refs:
            refs = "Preserve the scene and objects established in <Picture 1>."
        performance = "Visible mouths remain at rest; the shot plays without on-camera dialogue."
        if s["mode"] == "onscreen":
            onset = timing["speech_samples"][i]/48000 - timing["starts"][i]/24
            performance = (f"At {onset:.2f} seconds {s['speaker']} says \"{{line}}\" following the supplied recording. "
                           "Facial articulation follows the words. Keep the mouth quiet before and after the line.")
        prompt = (f"A single continuous {framing} in {s['place']}. {refs} {occupants} "
                  f"At the opening: {s['opening']}. During the take: {s['action']}. {performance} "
                  f"Keep subjects and props in their established positions as the action develops. {style} "
                  "Play action at natural speed through the edit, one camera angle, no titles, no captions.")
        motion["shots"][key] = {"cast":cast,"seed":seed_for(seed,"motion",key),"photo_frames":[0],"prompt":prompt}
    return {"width":896,"height":512,"shots":photos}, motion
