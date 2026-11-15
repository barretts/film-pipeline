r"""Lane B fix run — Blender guide variants, from the Phase 0 .blend.

Usage (on file-cabinet):
  "F:\ue\Blender 5.2\blender.exe" --background --python blender-variants.py -- <variant>
Variants: depth, room-only, silhouette, textured
Each renders 124 frames @24fps 1280x704 to guide/<variant>/frames, assembles
guide/<variant>.mp4 with ffmpeg, prints LANE-B-BLENDER-OK.
"""
import os, subprocess, sys, time
import bpy

ROOT = r"F:\film-pipeline\jobs\phase0-rigid-llm"
BLEND = os.path.join(ROOT, "blender", "p0-b1-blockout.blend")
GUIDE_DIR = os.path.join(ROOT, "guide")
FRAMES = 124
FPS = 24

variant = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "depth"
t0 = time.time()
out_dir = os.path.join(GUIDE_DIR, variant)
frames_dir = os.path.join(out_dir, "frames")
os.makedirs(frames_dir, exist_ok=True)
mp4 = os.path.join(GUIDE_DIR, variant + ".mp4")

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = FRAMES
scene.render.fps = FPS
scene.render.resolution_x = 1280
scene.render.resolution_y = 704
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

CHARACTERS = ["KateBody", "KateHead", "KateFace", "JamesBody", "JamesHead"]

def mat_white():
    m = bpy.data.materials.new("sil_white")
    m.use_nodes = False
    m.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    return m

def mat_black():
    m = bpy.data.materials.new("sil_black")
    m.use_nodes = False
    m.diffuse_color = (0.02, 0.02, 0.02, 1.0)
    return m

if variant == "room-only":
    for name in CHARACTERS:
        o = bpy.data.objects.get(name)
        if o:
            o.hide_render = True
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"

elif variant == "silhouette":
    white, black = mat_white(), mat_black()
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        m = white if o.name in CHARACTERS else black
        o.data.materials.clear()
        o.data.materials.append(m)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "MATERIAL"
    # black background
    world = bpy.data.worlds.new("black")
    world.color = (0, 0, 0)
    scene.world = world

elif variant == "depth":
    scene.render.engine = "BLENDER_EEVEE"
    scene.view_layers["ViewLayer"].use_pass_z = True
    scene.use_nodes = True
    tree = getattr(scene, "compositing_node_group", None)
    if tree is None:
        tree = bpy.data.node_groups.new("LaneBDepth", "CompositorNodeTree")
        scene.compositing_node_group = tree
    tree.nodes.clear()
    rl = tree.nodes.new("CompositorNodeRLayers")
    norm = tree.nodes.new("CompositorNodeMapRange")
    # clamp depth to the room: camera ~7m back, room 5-11m deep; near=white, far=black
    norm.inputs[1].default_value = 5.0
    norm.inputs[2].default_value = 11.0
    norm.inputs[3].default_value = 1.0
    norm.inputs[4].default_value = 0.0
    norm.use_clamp = True
    comp = tree.nodes.new("NodeGroupOutput")
    tree.links.new(rl.outputs["Depth"], norm.inputs[0])
    tree.links.new(norm.outputs[0], comp.inputs[0])

elif variant == "textured":
    scene.render.engine = "BLENDER_EEVEE"
    # principled materials from existing diffuse colours
    for m in list(bpy.data.materials):
        if m.use_nodes:
            continue
        rgb = m.diffuse_color[:3]
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
            bsdf.inputs["Roughness"].default_value = 0.75
    # key + fill lights
    bpy.ops.object.light_add(type="SUN", location=(2, -4, 6))
    sun = bpy.context.active_object
    sun.data.energy = 3.0
    sun.rotation_euler = (0.9, 0.2, 0.5)
    bpy.ops.object.light_add(type="AREA", location=(3.5, 1.0, 2.5))
    area = bpy.context.active_object
    area.data.energy = 250.0
    area.data.shape = "DISK"
    area.data.size = 1.2
    scene.eevee.use_shadows = True
else:
    raise ValueError("unknown variant: " + variant)

scene.render.filepath = os.path.join(frames_dir, "frame_")
bpy.ops.render.render(animation=True)

ff = subprocess.run(
    ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
     "-i", os.path.join(frames_dir, "frame_%04d.png"),
     "-c:v", "libx264", "-pix_fmt", "yuv420p", mp4],
    capture_output=True, text=True)
if ff.returncode != 0:
    raise RuntimeError("ffmpeg failed: " + ff.stderr[-500:])
print("LANE-B-BLENDER-OK variant=%s mp4=%s seconds=%.1f" % (variant, mp4, time.time() - t0))
