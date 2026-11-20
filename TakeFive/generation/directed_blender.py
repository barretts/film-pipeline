"""Bake a shot from the script's persistent local transforms, attachments and camera."""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector, Euler

source, target, dest, *options = sys.argv[sys.argv.index("--")+1:]
if options not in ([], ["--first-frame"]):
    raise ValueError(f"Unknown render options: {options}")
film = json.loads(Path(source).read_text(encoding="utf-8-sig"))
dest = Path(dest)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.render.use_persistent_data = True
scene.cycles.samples = 2
scene.cycles.use_denoising = True
prefs = bpy.context.preferences.addons["cycles"].preferences
if "OPTIX" in {item[0] for item in prefs.get_device_types(bpy.context)}:
    prefs.compute_device_type = "OPTIX"
    prefs.refresh_devices()
    if any(device.type == "OPTIX" for device in prefs.devices):
        for device in prefs.devices:
            device.use = device.type == "OPTIX"
        scene.cycles.device = "GPU"
        scene.cycles.denoiser = "OPTIX"
scene.world.color = (.4,.4,.4)
scene.render.resolution_x,scene.render.resolution_y = film["size"]
scene.render.resolution_percentage = 50
scene.render.fps = film["fps"]
objects, states, parents = {}, {}, {}
for spec in film["geometry"]:
    name = spec["id"]
    root = bpy.data.objects.new(name,None)
    scene.collection.objects.link(root)
    objects[name] = root
    parents[name] = spec["parent"]
    states[name] = dict(location=Vector(spec["loc"]),rotation_euler=Vector((0,0,0)),scale=Vector((1,1,1)))
    for kind,pos,size,color in spec["parts"]:
        if kind == "box":
            bpy.ops.mesh.primitive_cube_add(size=1)
        elif kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.5,segments=16,ring_count=8)
        else:
            raise ValueError(kind)
        part=bpy.context.object
        part.name=name+"."+kind
        part.parent=root
        part.location=pos
        part.scale=size
        mat=bpy.data.materials.get(color) or bpy.data.materials.new(color)
        mat.diffuse_color=tuple((int(color[i:i+2],16)/255)**2.2 for i in (0,2,4))+(1,)
        mat.use_nodes=True
        shader=mat.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value=mat.diffuse_color
        part.data.materials.append(mat)

def world(name):
    st=states[name]
    local=Matrix.LocRotScale(st["location"],Euler(st["rotation_euler"]).to_quaternion(),st["scale"])
    return world(parents[name]) @ local if parents[name] else local

def step(shot,f):
    for track in shot["tracks"]:
        keys=track["keys"]; n=track["id"]; prop=track["prop"]
        if prop=="attach":
            for at,parent in keys:
                if at==f:
                    loc,rot,scale=(world(parent).inverted() @ world(n)).decompose()
                    parents[n]=parent
                    states[n].update(location=loc,rotation_euler=Vector(rot.to_euler()),scale=scale)
        elif f>=keys[0][0]:
            before=max((k for k in keys if k[0]<=f),key=lambda k:k[0])
            after=next((k for k in keys if k[0]>f),before)
            t=(f-before[0])/max(1,after[0]-before[0])
            states[n][prop]=Vector(before[1]).lerp(Vector(after[1]),t)

for shot in film["shots"]:
    selected=shot["id"]==target
    for f in range(1,shot["frames"]+1):
        step(shot,f)
        if selected:
            for name,ob in objects.items():
                ob.matrix_world=world(name)
                for attr in ("location","rotation_euler","scale"):
                    ob.keyframe_insert(data_path=attr,frame=f)
    if selected:break
else:raise KeyError(target)
scene.frame_end=shot["frames"]
camera=shot["camera"]
bpy.ops.object.camera_add()
cam=bpy.context.object
scene.camera=cam
cam.data.lens=camera["lens"]
if shot["set"]=="black":
    for ob in objects.values():
        for part in ob.children:part.hide_render=True
    scene.world.color=(0,0,0)
else:
    for f,eye,aim in [(1,camera["eye"],camera["aim"]),
                      (scene.frame_end,camera["end_eye"],camera.get("end_aim",camera["aim"]))]:
        cam.location=eye
        cam.rotation_euler=(Vector(aim)-cam.location).to_track_quat("-Z","Y").to_euler()
        for attr in ("location","rotation_euler"):cam.keyframe_insert(data_path=attr,frame=f)
    for light in film["lights"]:
        bpy.ops.object.light_add(type="AREA",location=light["location"])
        ob=bpy.context.object
        ob.rotation_euler=(Vector(light["aim"])-ob.location).to_track_quat("-Z","Y").to_euler()
        ob.data.energy=light["watts"];ob.data.shape="DISK";ob.data.size=light["size"];ob.data.color=light["rgb"]
scene.frame_set(1)
scene.render.filepath="//frames/"
scene.render.image_settings.file_format="PNG"
scene.render.image_settings.compression=5
if options:
    scene.render.filepath=str(dest/"first.png")
    bpy.ops.render.render(write_still=True)
else:
    bpy.ops.wm.save_as_mainfile(filepath=str(dest/"stage.blend"))
    bpy.ops.render.render(animation=True)
