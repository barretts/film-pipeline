"""Run with Blender's Python. Rebuilds Snow.blend from documented local inputs."""
from pathlib import Path
import sys
import array
import wave
import bpy
from mathutils import Vector
SRC=Path(__file__).resolve().parent
BASE=SRC.parent
sys.path.insert(0,str(SRC))
from stage_art import build,collection
from cast import Actor
from performance import author

def speech(actor,windows,levels):
    # Move the lower lip and soft chin. Audio gives opening magnitude, not phoneme identity.
    obj=actor.body
    mouth=actor.rest('Head').head_local.z+(.089 if actor.name=='James' else .088)
    obj.shape_key_add(name="Rest");speak=obj.shape_key_add(name="Jaw / dialogue")
    for i,v in enumerate(obj.data.vertices):
        x,y,z=v.co
        if abs(x)>.068 or y>-.052 or z<mouth-.077 or z>mouth+.005:continue
        radial=max(0,1-(abs(x)/.068)**2)
        falloff=min(1,max(0,(mouth+.005-z)/.011),max(0,(z-mouth+.077)/.029),max(0,(-y-.052)/.029))
        speak.data[i].co.z-=.013*falloff*radial
        speak.data[i].co.y+=.003*falloff*radial
    for f in range(1,841):
        value=levels[f-1] if any(a<=f<=b for a,b in windows) else 0
        if value or any(a-1<=f<=b+1 for a,b in windows) or f in (1,840):
            speak.value=value;speak.keyframe_insert(data_path='value',frame=f)

def microphones(path):
    with wave.open(str(path),'rb') as w:
        rate=w.getframerate();data=array.array('h',w.readframes(w.getnframes()))
    levels=[]
    for i in range(840):
        samples=data[i*rate//24:(i+1)*rate//24]
        rms=(sum(x*x for x in samples)/max(1,len(samples)))**.5/32768
        levels.append(min(1,max(0,rms-.012)*7.5))
    return levels

def cameras(scene):
    c=collection("07  |  Camera department")
    cuts=[
     (1,"Reception",[(1,(-.18,-6.70,1.82),(-.18,.68,1.08),43),(120,(-.18,-6.49,1.80),(-.22,.68,1.08),43)]),
     (121,"My voice",[(121,(-.57,-1.13,1.40),(-1.85,.47,1.18),47),(240,(-.65,-1.02,1.39),(-1.88,.48,1.20),49)]),
     (241,"Three knocks",[(241,(1.19,.10,1.29),(1.74,1.58,1.22),49),(360,(1.20,.12,1.29),(1.74,1.58,1.23),50)]),
     (361,"Someone outside",[(361,(.54,-1.86,1.54),(-.22,.35,1.53),51),(405,(.58,-1.91,1.53),(-.18,.34,1.48),50),
                               (438,(.57,-2.66,1.44),(.22,.53,1.13),39),(456,(.60,-3.03,1.30),(.60,.70,.99),35),
                               (480,(.79,-3.13,1.30),(.97,.88,1.00),35)]),
     (481,"His hand on the latch",[(481,(3.18,1.05,1.38),(1.48,1.27,1.18),45),(502,(3.13,1.37,1.27),(1.53,1.32,1.09),50),
                                    (523,(3.13,1.37,1.27),(1.54,1.32,1.09),50),
                                    (556,(3.36,.12,1.35),(1.88,.98,1.12),44),(600,(3.48,-.70,1.54),(2.13,.89,1.25),39)]),
     (601,"An empty threshold",[(601,(-.08,-6.58,1.80),(-.15,.70,1.08),43),(720,(-.13,-6.49,1.79),(-.18,.70,1.08),43)]),
     (721,"Transmit",[(721,(-.58,-1.03,1.38),(-1.77,.47,1.07),44),(758,(-.61,-1.04,1.36),(-1.73,.46,1.065),45),
                       (840,(-.65,-1.04,1.35),(-1.73,.47,1.065),46)])]
    for n,(f,name,keys) in enumerate(cuts,1):
        data=bpy.data.cameras.new(name);data.sensor_width=36;data.clip_start=.025;data.clip_end=80
        obj=bpy.data.objects.new(f"{n:02} / "+name,data);c.objects.link(obj)
        obj.rotation_mode='QUATERNION'
        for frame,pos,target,lens in keys:
            obj.location=pos
            obj.rotation_quaternion=(Vector(target)-Vector(pos)).to_track_quat('-Z','Y')
            data.lens=lens
            obj.keyframe_insert(data_path='location',frame=frame)
            obj.keyframe_insert(data_path='rotation_quaternion',frame=frame)
            data.keyframe_insert(data_path='lens',frame=frame)
        marker=scene.timeline_markers.new(f"{n:02} / "+name,frame=f);marker.camera=obj
        if n==1:scene.camera=obj
    for f,w in [(30,'RX warning'),(162,'Kate speaks'),(252,'Knock 1'),(260,'Knock 2'),(269,'Knock 3'),
                (404,'James speaks'),(500,'One inch / hold'),(522,'First contact'),(535,'Hinge starts'),
                (571,'Grip releases'),(744,'PTT down'),(757,'TX warning')]:
        scene.timeline_markers.new(w,frame=f)

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.name="Snow / Polar station 07"
    scene.frame_start=1;scene.frame_end=840;scene.render.fps=24
    scene.unit_settings.system='METRIC'
    bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
    bpy.context.preferences.filepaths.save_version=0
    scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=4;scene.cycles.use_denoising=True;scene.cycles.max_bounces=2
    scene.cycles.diffuse_bounces=1;scene.cycles.glossy_bounces=1;scene.cycles.transparent_max_bounces=2
    scene.cycles.use_light_tree=True
    scene.render.resolution_x=704;scene.render.resolution_y=396
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.compression=15;scene.render.use_persistent_data=True
    scene.render.filepath="//work/frames/snow-";scene.render.use_file_extension=True
    scene.render.film_transparent=False
    world=bpy.data.worlds.new("Southern fill");world.use_nodes=True
    world.node_tree.nodes["Background"].inputs[0].default_value=(.28,.36,.43,1)
    world.node_tree.nodes["Background"].inputs[1].default_value=.30;scene.world=world
    scene.view_settings.view_transform='AgX'
    stage=build()
    kate=Actor('Kate',BASE/'assets');james=Actor('James',BASE/'assets')
    author(kate,james,stage)
    audio=BASE/'assets/radio-drama.wav';levels=microphones(audio)
    speech(kate,[(161,210),(755,818)],levels);speech(james,[(401,448)],levels)
    strip=scene.sequence_editor_create().strips.new_sound('Snow / radio play',str(audio),1,1)
    bpy.ops.file.pack_all()
    strip.sound.filepath='//assets/radio-drama.wav'
    scene.render.use_sequencer=False
    cameras(scene)
    scene['Screenplay']=(BASE/'screenplay.txt').read_text(encoding='utf-8-sig').strip()
    scene['Stage units']='One Blender unit is one metre. Frame 1 starts the recording.'
    scene['Latch witness']=james.tipi['r'];scene['Desk switch witness']=kate.tipi['r']
    for workspace in bpy.data.screens:
        for area in workspace.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.overlay.show_overlays=False
                area.spaces.active.shading.color_type='MATERIAL'
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active=None
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(BASE/'Snow.blend'),compress=True)
    print("Saved editable scene",flush=True)

if __name__=='__main__':main()
