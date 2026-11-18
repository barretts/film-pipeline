"""Bake the declarative walk onto an editable Blender armature and render clay and depth together."""
import json
import math
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from takefive import stage


def build_rig(name, colors):
    # +X is the actor's forward axis. Rest coordinates are in metres.
    bones = {"spine": ((0, 0, .91), (0, 0, 1.49), None),
             "head": ((0, 0, 1.49), (0, 0, 1.80), "spine")}
    for side, sign in (("L", 1), ("R", -1)):
        def limb(label, z1, z2, width, parent):
            bones[label+"."+side] = ((0, sign*width, z1), (0, sign*width, z2), parent)
        limb("thigh", .91, .455, .11, "spine")
        limb("shin", .455, .035, .11, "thigh."+side)
        bones["boot."+side] = ((0, sign*.11, .035), (.16, sign*.11, .035), "shin."+side)
        limb("upper_arm", 1.43, 1.138, .235, "spine")
        limb("forearm", 1.138, .872, .235, "upper_arm."+side)
    data = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    rig.show_in_front = True
    bpy.ops.object.mode_set(mode="EDIT")
    for key, (a, b, parent) in bones.items():
        bone = data.edit_bones.new(key)
        bone.head, bone.tail = a, b
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    data.display_type = "STICK"

    def attach(obj, bone):
        # Rigid weights keep the visible proxy and measured skeleton on the same pose.
        obj.data = obj.data.copy()
        group = obj.vertex_groups.new(name=bone)
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        bpy.context.view_layer.update()
        transform = obj.matrix_world.copy()
        obj.data.transform(transform)
        from mathutils import Matrix
        obj.matrix_world = Matrix.Identity(4)
        obj.parent = rig
        mod = obj.modifiers.new("Skeleton", "ARMATURE")
        mod.object = rig
        obj.name = name+" / "+obj.name

    oval = stage.oval
    def part(label, pos, size, color, bone):
        attach(oval(label, pos, size, colors[color]), bone)
    part("Parka", (.012, 0, 1.215), (.162, .246, .325), "coat", "spine")
    part("Parka hem", (0, 0, 1.02), (.161, .217, .15), "coat", "spine")
    part("Collar", (0, 0, 1.47), (.141, .158, .081), "coat", "spine")
    part("Head", (.017, 0, 1.645), (.115, .102, .146), "skin", "head")
    part("Nose", (.126, 0, 1.64), (.034, .026, .031), "skin", "head")
    for s in (-1,1):
        part("Ear", (-.009, s*.102, 1.647), (.026,.018,.039), "skin", "head")
        part("Eye", (.111, s*.049, 1.671), (.010,.013,.009), "boots", "head")
        part("Brow", (.108, s*.049, 1.689), (.009,.021,.005), "boots", "head")
    part("Mouth",(.122,0,1.601),(.007,.024,.004),"boots","head")
    if colors.get("cap"):
        part("Wool cap", (.001, 0, 1.743), (.125, .111, .092), "cap", "head")
    else:
        part("Hair", (-.012, 0, 1.727), (.116, .105, .075), "hair", "head")
    if colors.get("bun"):
        part("Hair bun",(-.112,0,1.72),(.07,.065,.067),"hair","head")
    if colors.get("glasses"):
        for s in (-1,1):
            attach(stage.bar("Glasses temple",(.119,s*.068,1.68),(-.045,s*.100,1.68),.006,colors["boots"]),"head")
            y = s*.052
            for j in range(12):
                alpha,beta = math.tau*j/12,math.tau*(j+1)/12
                attach(stage.bar("Eyeglass frame",(.119,y+.036*math.cos(alpha),1.67+.029*math.sin(alpha)),
                                 (.119,y+.036*math.cos(beta),1.67+.029*math.sin(beta)),.005,colors["boots"]),"head")
    for side, sign in (("L", 1), ("R", -1)):
        for bone, color, radius in (("thigh", "pants", .095), ("shin", "pants", .075),
                                    ("upper_arm", "coat", .081), ("forearm", "coat", .066)):
            key = bone+"."+side
            a, b, _ = bones[key]
            attach(stage.bar(bone, a, b, radius, colors[color]), key)
            part(bone+" joint", a, (radius, radius, radius), color, key)
        part("Glove", (.010, sign*.235, .843), (.051, .047, .075), "boots", "forearm."+side)
        part("Boot", (.055, sign*.11, .012), (.151, .078, .073), "boots", "boot."+side)
    return rig


def pose(rig, start, end, p):
    delta = end-start
    length = math.hypot(delta.x, delta.y)
    gait = min(1., p/.10, (1.-p)/.10)
    apply_pose(rig, start.lerp(end, p), math.atan2(delta.y, delta.x), p*length, gait)


def apply_pose(rig, position, heading, dist, gait, *, seated=False, gesture=None):
    stride, duty = 1.04, .56
    cycle = dist/stride
    bob = .015*math.sin(2*math.pi*cycle)**2*gait
    rig.rotation_euler.z = heading
    rig.location = position
    rig.location.z += bob - (.415 if seated else 0.)
    angles = {"spine": .055*gait, "head": .02*gait}
    for side, phase in (("L", 0.), ("R", .5)):
        q = (cycle+phase) % 1.
        swing = max(0., (q-duty)/(1.-duty))
        # In stance the boot is stationary in world space. Swing uses the same path clock.
        dx = (.5*duty-q+swing*swing*(3.-2.*swing))*stride*gait
        ankle = .067+.13*math.sin(math.pi*swing)**2*gait
        down = .91+bob-ankle
        l1, l2 = .455, .42
        d = min(l1+l2-1.e-5, math.hypot(dx, down))
        def acos(v):
            return math.acos(max(-1., min(1., v)))
        thigh = math.atan2(dx, down)+acos((l1*l1+d*d-l2*l2)/(2*l1*d))
        bend = acos((d*d-l1*l1-l2*l2)/(2*l1*l2))
        angles.update({"thigh."+side: -thigh, "shin."+side: bend-thigh,
                       "boot."+side: -.13*math.sin(2*math.pi*swing)*gait,
                       "upper_arm."+side: .36*math.cos(2*math.pi*q)*gait,
                       "forearm."+side: .36*math.cos(2*math.pi*q)*gait-.32})
        if seated:
            angles.update({"thigh."+side: -1.50, "shin."+side: .09, "boot."+side: 0.,
                           "upper_arm."+side: -.18, "forearm."+side: -.87})
    g = gesture or {}
    angles["spine"] += .61*g.get("lean", 0.)
    angles["head"] += .25*g.get("nod", 0.) + .15*g.get("talk",0.) + .29*g.get("lean",0.) - .36*g.get("look_up",0.)
    angles["upper_arm.R"] -= 1.48*g.get("point", 0.) + 1.68*g.get("raise_hand", 0.) + .58*g.get("talk", 0.)
    angles["forearm.R"] -= 1.30*g.get("point", 0.) + 2.46*g.get("raise_hand", 0.) + 1.02*g.get("talk", 0.)
    rotations = {n: Quaternion((0, 1, 0), a) for n, a in angles.items()}
    rotations["head"] = Quaternion((0, 0, 1), .70*g.get("look", 0.)) @ rotations["head"]
    for pb in rig.pose.bones:
        rest = pb.bone.matrix_local.to_quaternion()
        rotation = rotations[pb.name]
        if pb.parent:
            rotation = rotations[pb.parent.name].inverted() @ rotation
        pb.rotation_quaternion = rest.inverted() @ rotation @ rest


def outputs(scene, destination, near, far, actor_count=0):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.compositor_device = "CPU"
    scene.render.compositor_denoise_device = "CPU"
    bpy.context.preferences.filepaths.file_preview_type = "NONE"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 8
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15
    scene.render.filepath = str(destination/"clay"/"frame-")
    scene.view_layers[0].use_pass_z = True
    scene.view_layers[0].use_pass_object_index = bool(actor_count)
    # Give the clay pass deterministic studio shading in a single CPU sample.
    for mat in stage.MATERIALS.values():
        mat.use_nodes = True
        tree = mat.node_tree
        tree.nodes.clear()
        geo = tree.nodes.new("ShaderNodeNewGeometry")
        dot = tree.nodes.new("ShaderNodeVectorMath")
        dot.operation = "DOT_PRODUCT"
        dot.inputs[1].default_value = (-.24, -.58, .77)
        tree.links.new(geo.outputs["Normal"], dot.inputs[0])
        light = tree.nodes.new("ShaderNodeMath")
        light.operation = "MULTIPLY_ADD"
        light.inputs[1].default_value, light.inputs[2].default_value = .31, .72
        tree.links.new(dot.outputs["Value"], light.inputs[0])
        emission = tree.nodes.new("ShaderNodeEmission")
        emission.inputs[0].default_value = mat.diffuse_color
        tree.links.new(light.outputs[0], emission.inputs[1])
        tree.links.new(emission.outputs[0], tree.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    tree = bpy.data.node_groups.new("Clay and camera depth", "CompositorNodeTree")
    scene.compositing_node_group = tree
    rl = tree.nodes.new("CompositorNodeRLayers")
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    tree.links.new(rl.outputs["Image"], tree.nodes.new("NodeGroupOutput").inputs["Image"])
    remap = tree.nodes.new("ShaderNodeMapRange")
    for key, val in (("From Min", near), ("From Max", far), ("To Min", 1.), ("To Max", 0.)):
        remap.inputs[key].default_value = val
    remap.clamp = True
    tree.links.new(rl.outputs["Depth"], remap.inputs["Value"])
    dest = tree.nodes.new("CompositorNodeOutputFile")
    dest["steering_pass"] = "depth"
    dest.format.media_type = "IMAGE"
    dest.format.file_format = "PNG"
    dest.format.color_mode = "BW"
    dest.format.compression = 15
    dest.directory = str(destination/"depth")
    dest.file_name = ""
    item = dest.file_output_items.new("FLOAT", "frame-")
    item.save_as_render = False
    tree.links.new(remap.outputs["Result"], dest.inputs[item.name])
    if actor_count:
        labels = tree.nodes.new("ShaderNodeMath")
        labels.operation = "DIVIDE"
        labels.inputs[1].default_value = actor_count+1
        tree.links.new(rl.outputs["Object Index"], labels.inputs[0])
        ids = tree.nodes.new("CompositorNodeOutputFile")
        ids["steering_pass"] = "ids"
        ids.format.media_type = "IMAGE"
        ids.format.file_format = "PNG"
        ids.format.color_mode = "BW"
        ids.directory, ids.file_name = str(destination/"ids"), ""
        item = ids.file_output_items.new("FLOAT", "frame-")
        item.save_as_render = False
        tree.links.new(labels.outputs[0], ids.inputs[item.name])
    return remap


def main():
    set_file, shot_file, dest, first_only = sys.argv[sys.argv.index("--")+1:]
    destination = Path(dest).resolve()
    stage_data = json.loads(Path(set_file).read_text(encoding="utf-8"))
    shot = json.loads(Path(shot_file).read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    for name, center, size, shade in stage_data["boxes"]:
        stage.box(name, center, size, shade)
    actor = shot["actor"]
    rig = build_rig(actor, stage_data["cast"][actor])
    cam = stage_data["cameras"][shot["camera"]]
    scene.camera = stage.camera(shot["camera"], cam["position"], cam["target"], cam["lens"])
    scene.frame_start, scene.frame_end, scene.render.fps = 0, 120, 24
    scene.render.resolution_x, scene.render.resolution_y = 640, 384
    scene.render.resolution_percentage = 100
    start, end = (Vector(stage_data["marks"][shot[key]]) for key in ("from_mark", "to_mark"))
    t0, t1 = shot["start_frame"], shot["arrive_frame"]
    for t in sorted({0, *range(t0, t1+1), 120}):
        p = min(1., max(0., (t-t0)/(t1-t0)))
        pose(rig, start, end, p)
        rig.keyframe_insert(data_path="location", frame=t, group="Blocking")
        for pb in rig.pose.bones:
            pb.keyframe_insert(data_path="rotation_quaternion", frame=t, group=pb.name)
    # An idle hold must stay exactly still between the two keys delimiting it.
    action = rig.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = "LINEAR"
    outputs(scene, destination, cam["near_depth"], cam["far_depth"])
    scene.frame_set(0)
    bpy.context.preferences.filepaths.save_version = 0
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.wm.save_as_mainfile(filepath=str(destination/"stage.blend"), relative_remap=True)
    tracks = []
    for t in range(121):
        scene.frame_set(t)
        sites = {}
        for pb in rig.pose.bones:
            point = world_to_camera_view(scene, scene.camera, rig.matrix_world @ pb.head)
            sites[pb.name] = [round(point.x, 6), round(1.-point.y, 6)]
        tracks.append(sites)
    (destination/"joints.json").write_text(json.dumps(tracks), encoding="utf-8")
    if first_only == "smoke":
        scene.frame_start = scene.frame_end = t0
    else:
        scene.frame_start, scene.frame_end = t0, t1
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
