"""Build, keyframe, and CPU-render a whole continuity edit in one Blender scene."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE),str(HERE.parent)]
from takefive import stage
from blender_stage import apply_pose, build_rig, outputs
from sets import build as build_set


def unit(v):
    return v.normalized() if v.length > 1.e-7 else Vector((0,-1,0))


def setup_actors(shot, room, previous, distance):
    marks, result = room["marks"], {}
    for index,(name,b) in enumerate(shot["actors"].items()):
        last = previous.get((shot["set"],name))
        action = b["action"]
        seated = action in ("sit","talk_seated","listen_seated") or (
            last and last["seated"] and action in ("talk","listen","lean"))
        fallback = "staff" if seated else ("visitor" if index==0 else "center")
        def locate(key, default):
            if key=="carry":
                return last["position"].copy() if last else marks[default].copy()
            return marks[key].copy()
        start = locate(b["from"],fallback)
        path = [start]
        if action=="enter":
            end = marks[b["to"]] if b["to"] not in ("carry","door","outside") else marks["visitor"]
            path = [marks["outside"], marks["door"], end]
        elif action=="exit":
            if not last and b["from"] in ("door","outside","carry"):
                start = marks["visitor"]
            elif last and b["from"]=="carry":
                start = last["position"]
            path = [start, marks["door"], marks["outside"]]
        elif action in ("walk","walk_away"):
            if action=="walk_away" and b["from"] in ("carry","outside","far"):
                start = marks["door"]
            end = marks[b["to"]] if b["to"]!="carry" else marks["far" if action=="walk_away" else "door"]
            path = [start, end]
        elif seated and b["from"]=="carry" and not last:
            path = [marks["staff"]]
        elif action=="open":
            path = [last["position"],marks["door"]] if last else [marks["door"]]
        lens = [(b-a).length for a,b in zip(path,path[1:])]
        result[name] = {"b":b,"path":path,"lengths":lens,"total":sum(lens),"phase":distance.get(name,0.),
                        "seated":bool(seated),"heading":last["heading"] if last else -math.pi/2}
    # Give coincident standing actors distinct floor space when the planner supplied the same idle mark.
    claimed = []
    for a in result.values():
        if a["total"]==0:
            while any((a["path"][0]-p).length < .44 for p in claimed):
                a["path"][0] = a["path"][0]+Vector((.50,0,0))
            claimed.append(a["path"][0])
    for name,a in result.items():
        face = a["b"]["face"]
        if face in result and face!=name:
            target = result[face]["path"][-1]
        elif (shot["set"],face) in previous and face!=name:
            target = previous[(shot["set"],face)]["position"]
        elif face=="work" and a["b"]["action"]=="lean" and "microphone" in room["props"]:
            target = room["props"]["microphone"]
        elif face in ("door","work"):
            target = marks[face]+Vector((0,.7,0))
        else:
            angle = {"left":math.pi,"right":0.,"front":-math.pi/2}.get(face,a["heading"])
            target = a["path"][-1]+Vector((math.cos(angle),math.sin(angle),0))
        v = target-a["path"][-1]
        if v.length > .01:
            a["heading"] = math.atan2(v.y,v.x)
    return result


def sample(a, frame):
    b, path = a["b"], a["path"]
    p = min(1., max(0., (frame-b["start_frame"])/(b["end_frame"]-b["start_frame"])))
    if not a["total"]:
        return path[0], a["heading"], a["phase"], 0., p
    dist, passed = a["total"]*p, 0.
    for i,n in enumerate(a["lengths"]):
        if n and (dist <= passed+n+1.e-6 or i==len(a["lengths"])-1):
            tangent = path[i+1]-path[i]
            gait = min(1., 1. if b["moving_at_start"] else p/.085, 1. if b["moving_at_end"] else (1.-p)/.085)
            return (path[i].lerp(path[i+1],min(1.,max(0.,(dist-passed)/n))),
                    math.atan2(tangent.y,tangent.x),a["phase"]+dist,gait,p)
        passed += n
    return path[-1],a["heading"],a["phase"]+dist,0.,p


def make_camera(shot, room, actors):
    cam = shot["camera"]
    if "position" in cam and "target" in cam:
        origin = Vector((room["offset"],0,0))
        pos, target = origin+Vector(cam["position"]), origin+Vector(cam["target"])
        lens = cam.get("lens",37.)
    elif cam.get("include_prop") in room["props"] and cam["focus"] in actors:
        subject = actors[cam["focus"]]
        loc = subject["path"][-1]
        prop = room["props"][cam["include_prop"]]
        eye = loc+Vector((0,0,1.59-(.415 if subject["seated"] else 0.)))
        target = .50*(eye+prop)
        sign_x = -1 if prop.x<=loc.x else 1
        pos = target+Vector((1.70*sign_x,.46,.12))
        lens = 42.
    elif cam["focus"] in ("door","work") and cam["view"]=="insert":
        target = room["marks"][cam["focus"]]+Vector((0,.60,1.36 if cam["focus"]=="door" else 1.02))
        pos = target+Vector((-.29*room["sign"],-2.16,.035))
        lens = 57.
    elif cam["view"]=="wide" or cam["focus"] not in actors:
        pos, target = Vector((room["offset"],-6.02,1.57)),Vector((room["offset"],.32,1.06))
        lens = 36.
    else:
        a = actors[cam["focus"]]
        loc,heading,*_ = sample(a,shot["frames"]//2)
        close = cam["view"] in ("close","insert")
        target = loc+Vector((0,0,(1.55 if close else 1.22)-(.415 if a["seated"] else 0)))
        look = Vector((math.cos(heading),math.sin(heading),0))
        side = Vector((look.y,-look.x,0))
        if side.y>.0001 or (abs(side.y)<.0001 and side.x<0):
            side = -side
        dist = 1.60 if close else 2.85
        pos = target+unit(.55*look+.95*side)*dist+Vector((0,0,.05 if close else .14))
        # Keep a reverse camera inside the back wall.
        pos.y = min(pos.y,1.39)
        lens = 56. if close else 44.
    camera = stage.camera(shot["id"]+" / "+cam["view"], pos, target, lens)
    d = (target-pos).length
    return camera, (max(.08,d-1.4),d+2.7)


def bake(plan, dest):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x,scene.render.resolution_y = plan["width"],plan["height"]
    scene.render.resolution_percentage,scene.render.fps = 100,plan["fps"]
    rooms = {k:build_set(k,v,i*25.) for i,(k,v) in enumerate(plan["sets"].items())}
    rigs = {k:build_rig(k,v) for k,v in plan["cast"].items()}
    for index,rig in enumerate(rigs.values(),1):
        for child in rig.children:
            child.pass_index = index
    remap = outputs(scene,dest,1.,9.,len(rigs))
    previous, distance, cameras, door_states = {},{},[],{}
    first = 0
    for shot in plan["shots"]:
        room = rooms[shot["set"]]
        door_id = plan["sets"][shot["set"]].get("door_id",shot["set"])
        initial_door = door_states.get(door_id,0.)
        actors = setup_actors(shot,room,previous,distance)
        camera, depths = make_camera(shot,room,actors)
        cameras.append(camera)
        marker = scene.timeline_markers.new(shot["id"]+" / "+shot["set"],frame=first)
        marker.camera = camera
        for name,val in zip(("From Min","From Max"),depths):
            remap.inputs[name].default_value = val
            remap.inputs[name].keyframe_insert(data_path="default_value",frame=first)
            remap.inputs[name].keyframe_insert(data_path="default_value",frame=first+shot["frames"]-1)
        for t in range(shot["frames"]):
            f, door = first+t, initial_door*max(0.,1.-t/(scene.render.fps*.8))
            for name,rig in rigs.items():
                if name not in actors:
                    if t in (0,shot["frames"]-1):
                        rig.location = (room["offset"]+14,8,-5)
                        rig.keyframe_insert(data_path="location",frame=f,group="Blocking")
                    continue
                a = actors[name]
                point,heading,phase,gait,p = sample(a,t)
                gestures = {}
                for key in a["b"]["poses"]:
                    away = max(0,key["frame"]-t,t-key["frame"]-key.get("hold_frames",0))
                    rate = max(0.,1.-away/min(24.,shot["frames"]*.25))
                    strength = rate*rate*(3.-2.*rate)*key["weight"]
                    gestures[key["pose"]] = max(gestures.get(key["pose"],0.),strength)
                apply_pose(rig,point.copy(),heading,phase,gait,seated=a["seated"],gesture=gestures)
                for attr in ("location","rotation_euler"):
                    rig.keyframe_insert(data_path=attr,frame=f,group="Blocking")
                for pb in rig.pose.bones:
                    pb.keyframe_insert(data_path="rotation_quaternion",frame=f,group=pb.name)
                action = a["b"]["action"]
                if action in ("enter","exit","open") and not room["exterior"]:
                    if action=="enter":
                        opening = min(1.,max(0.,(t+1)/max(1.,.18*shot["frames"])),(1.-p)/.24)
                    else:
                        opening = min(1.,max(0.,(p-.27)/.35))
                    door = max(door,opening)
                if t==shot["frames"]-1:
                    previous[(shot["set"],name)] = {"position":point.copy(),"heading":heading,"seated":a["seated"]}
                    distance[name] = phase
            sign = room["sign"] if room["exterior"] else -room["sign"]
            room["hinge"].rotation_euler.z = sign*math.radians(88)*door
            room["hinge"].keyframe_insert(data_path="rotation_euler",frame=f)
        door_states[door_id] = door
        for name,b in shot["actors"].items():
            for k in b["poses"]:
                scene.timeline_markers.new(f"{name} / {k['pose']}",frame=first+k["frame"])
        first += shot["frames"]
    scene.frame_start, scene.frame_end = 0,first-1
    scene.camera = cameras[0]
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = "LINEAR"
    scene.frame_set(0)
    bpy.context.preferences.filepaths.save_version = 0
    # Keep the exported scene movable. Blender resolves these against the saved .blend.
    scene.render.filepath = "//clay/frame-"
    for node in scene.compositing_node_group.nodes:
        if node.type=="OUTPUT_FILE":
            node.directory = "//"+node["steering_pass"]+"/"
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.overlay.show_overlays = False
    bpy.ops.wm.save_as_mainfile(filepath=str(dest/"stage.blend"),relative_remap=False)
    return scene


def main():
    planfile, destination, mode = sys.argv[sys.argv.index("--")+1:]
    plan,dest = json.loads(Path(planfile).read_text(encoding="utf-8")),Path(destination).resolve()
    scene = bake(plan,dest) if mode=="build" else bpy.context.scene
    if scene.render.engine!="CYCLES" or scene.cycles.device!="CPU" or scene.render.compositor_device!="CPU":
        raise ValueError("The steering draft requires CPU Cycles and CPU compositing")
    cuts = sorted((m for m in scene.timeline_markers if m.camera), key=lambda m:m.frame)
    if len(cuts)!=len(plan["shots"]) or scene.frame_start!=0:
        raise ValueError("The number of bound camera cuts must match the plan and start at frame 0")
    first, timeline = 0,{}
    for cut,s in zip(cuts,plan["shots"]):
        if cut.frame!=first:
            raise ValueError(f"{s['id']}: the plan places the cut on frame {first}, the scene has it on {cut.frame}")
        timeline[s["id"]] = {"start":first,"end":first+s["frames"]-1,"actors":list(s["actors"]),
                             "camera":cut.camera.name,"set":s["set"],"script":s["script"]}
        first += s["frames"]
    if scene.frame_end!=first-1:
        raise ValueError("The scene and plan must cover the same number of frames")
    (dest/"timeline.json").write_text(json.dumps(timeline,indent=2),encoding="utf-8")
    # Also direct renders from a user-edited .blend into this run's own folder.
    scene.render.filepath = str(dest/"clay"/"frame-")
    for node in scene.compositing_node_group.nodes:
        if node.type=="OUTPUT_FILE":
            node.directory = str(dest/node["steering_pass"])
    scenesettings = {"engine":scene.render.engine,"cycles_device":scene.cycles.device,
                     "compositor_device":scene.render.compositor_device,"rigs":[o.name for o in scene.objects if o.type=="ARMATURE"],
                     "frames":scene.frame_end-scene.frame_start+1,"fps":scene.render.fps}
    (dest/"blender-settings.json").write_text(json.dumps(scenesettings,indent=2),encoding="utf-8")
    bpy.ops.render.render(animation=True)


if __name__=="__main__":
    main()
