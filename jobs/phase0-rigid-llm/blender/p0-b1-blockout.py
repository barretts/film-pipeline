"""Phase 0 Lane B blockout: James crosses the radio room to Kate.

Blender 5.2.2, headless. Builds a capsule/box blockout of shot P0-B1,
renders a 124-frame Workbench guide video (1280x704 @24 fps) plus a
frame-1 validation still, and saves the .blend.

Run: "F:\\ue\\Blender 5.2\\blender.exe" --background --python <this file>
No GUI, no interaction. Prints PHASE0-BLENDER-OK with timings on success.
"""
import math
import os
import time

import bpy

ROOT = r"F:\film-pipeline\jobs\phase0-rigid-llm"
GUIDE_DIR = os.path.join(ROOT, "guide")
BLEND_PATH = os.path.join(ROOT, "blender", "p0-b1-blockout.blend")
GUIDE_MP4 = os.path.join(GUIDE_DIR, "p0-b1-guide.mp4")
FRAME1_PNG = os.path.join(GUIDE_DIR, "p0-b1-frame-001.png")
FRAMES = 124
FPS = 24

t0 = time.time()


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = False
    m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    return m


def box(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    return o


def ball(name, loc, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    o.data.materials.append(material)
    return o


def key(obj, frame, loc=None, rot=None, linear=True):
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert(data_path="location", frame=frame)
    if rot is not None:
        obj.rotation_euler = rot
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    if linear:
        # Blender 5.x layered actions: fcurves live in layer strips' channelbags,
        # one channelbag per action slot: strip.channelbag(slot).fcurves.
        action = obj.animation_data.action
        fcurves = []
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    try:
                        cb = strip.channelbag(slot)
                    except Exception:
                        continue
                    fcurves.extend(cb.fcurves)
        for fc in fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


# --- clean scene -------------------------------------------------------------
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras):
    pass

grey = mat("wall_grey", (0.45, 0.45, 0.48))
dark = mat("floor_dark", (0.22, 0.22, 0.25))
wood = mat("desk_wood", (0.45, 0.30, 0.16))
brass = mat("radio_brass", (0.75, 0.60, 0.25))
yellow = mat("lamp_warm", (1.0, 0.80, 0.35))
orange = mat("james_orange", (1.0, 0.35, 0.05))
navy = mat("kate_navy", (0.10, 0.15, 0.40))
skin = mat("skin", (0.85, 0.65, 0.50))
cream = mat("kate_cream", (0.90, 0.85, 0.70))

# Room: floor 10 x 7, back wall at y=+3, side walls at x=+-5.
box("Floor", (0, 0, -0.05), (5.0, 3.5, 0.05), dark)
box("BackWall", (0, 3.0, 1.5), (5.0, 0.1, 1.5), grey)
box("LeftWall", (-5.0, 0, 1.5), (0.1, 3.5, 1.5), grey)
box("RightWall", (5.0, 0, 1.5), (0.1, 3.5, 1.5), grey)

# Door frame, left wall (x=-4.2, back wall). Door panel ajar.
box("DoorFrameL", (-4.55, 2.9, 1.1), (0.12, 0.12, 1.1), wood)
box("DoorFrameR", (-3.85, 2.9, 1.1), (0.12, 0.12, 1.1), wood)
box("DoorFrameT", (-4.2, 2.9, 2.15), (0.5, 0.12, 0.12), wood)
door = box("DoorPanel", (-3.95, 2.55, 1.0), (0.35, 0.06, 1.0), wood)
door.rotation_euler = (0, 0, math.radians(35))

# Radio desk, right side, against back wall. Radio box + lamp on top.
box("Desk", (3.2, 2.3, 0.38), (0.85, 0.35, 0.38), wood)
box("Radio", (3.0, 2.3, 0.88), (0.28, 0.2, 0.14), brass)
ball("Lamp", (3.6, 2.3, 1.05), (0.12, 0.12, 0.12), yellow)

# Kate (C01): seated at desk, facing the camera (-Y). Body blob + head + face plate.
kate_body = ball("KateBody", (3.2, 1.55, 0.62), (0.42, 0.36, 0.62), navy)
kate_head = ball("KateHead", (3.2, 1.55, 1.32), (0.21, 0.21, 0.21), skin)
face = box("KateFace", (3.2, 1.32, 1.32), (0.13, 0.03, 0.15), cream)
# Head turn, marked by the face plate orbiting the head: front (facing camera, -Y)
# at frame 90, west side (facing James, -X) at frame 124. No parenting: the head
# and body spheres are scaled objects, and parenting a child to a scaled object
# distorts the child's offset (that bug left James's head floating at the ceiling).
key(kate_head, 1, rot=(0, 0, 0))
key(kate_head, 90, rot=(0, 0, 0))
key(kate_head, 124, rot=(0, 0, math.radians(-80)))
key(face, 1, loc=(3.2, 1.32, 1.32))
key(face, 90, loc=(3.2, 1.32, 1.32))
key(face, 124, loc=(2.97, 1.55, 1.32))

# James (C02): walks door (x=-3.6) to desk (x=+2.0) along y=0, frames 1-100.
# Head is keyframed with the same walk, not parented (see note above).
james_body = ball("JamesBody", (-3.6, 0, 0.88), (0.34, 0.34, 0.88), orange)
james_head = ball("JamesHead", (-3.6, 0, 1.82), (0.23, 0.23, 0.23), skin)
key(james_body, 1, loc=(-3.6, 0, 0.88))
key(james_body, 100, loc=(2.0, 0, 0.88))
key(james_body, 124, loc=(2.0, 0, 0.88))
key(james_head, 1, loc=(-3.6, 0, 1.82))
key(james_head, 100, loc=(2.0, 0, 1.82))
key(james_head, 124, loc=(2.0, 0, 1.82))

# Camera: dolly right, tracking James via TRACK_TO.
bpy.ops.object.camera_add(location=(-0.5, -7.0, 1.6))
cam = bpy.context.active_object
cam.name = "Camera"
cam.data.lens = 35
con = cam.constraints.new("TRACK_TO")
con.target = james_body
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"
key(cam, 1, loc=(-0.5, -7.0, 1.6))
key(cam, 124, loc=(2.0, -7.0, 1.6))
bpy.context.scene.camera = cam

# --- render settings ---------------------------------------------------------
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = FRAMES
scene.render.fps = FPS
scene.render.resolution_x = 1280
scene.render.resolution_y = 704
scene.render.resolution_percentage = 100
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_shadows = False
scene.display.shading.show_cavity = False
# Note: Blender 5.2 removed FFMPEG from image_settings.file_format; the guide is
# rendered as a PNG sequence and assembled to mp4 with ffmpeg below.

os.makedirs(GUIDE_DIR, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

# Single-frame validation still first (plan gate: check framing before full render).
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = FRAME1_PNG
scene.frame_set(1)
bpy.ops.render.render(write_still=True)

# Full guide as a PNG image sequence (Blender 5.2 no longer accepts FFMPEG as an
# image_settings file_format), then assemble to mp4 with ffmpeg.
frames_dir = os.path.join(GUIDE_DIR, "frames")
os.makedirs(frames_dir, exist_ok=True)
scene.render.filepath = os.path.join(frames_dir, "frame_")
bpy.ops.render.render(animation=True)

import subprocess

ffmpeg = subprocess.run(
    ["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
     "-i", os.path.join(frames_dir, "frame_%04d.png"),
     "-c:v", "libx264", "-pix_fmt", "yuv420p", GUIDE_MP4],
    capture_output=True, text=True)
if ffmpeg.returncode != 0:
    raise RuntimeError("ffmpeg guide assembly failed: " + ffmpeg.stderr[-500:])

print("PHASE0-BLENDER-OK blend=%s guide=%s frame1=%s seconds=%.1f"
      % (BLEND_PATH, GUIDE_MP4, FRAME1_PNG, time.time() - t0))
