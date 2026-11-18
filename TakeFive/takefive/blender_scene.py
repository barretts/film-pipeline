"""Build a self-contained animated Blender scene and render selected frame ranges."""
import argparse
import bisect
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import stage

FPS=24
TAU=math.tau
SHAPES={"X":(.051,.003), "A":(.061,.004), "B":(.068,.013), "C":(.059,.029),
        "D":(.055,.043), "E":(.037,.031), "F":(.024,.022), "G":(.058,.011), "H":(.060,.020)}


def clamp(x):
    return max(0.,min(1.,x))


def smooth(x):
    x=clamp(x)
    return x*x*(3-2*x)


def key(o,*props):
    for prop in props:
        o.keyframe_insert(data_path=prop,frame=FRAME,group="Performance")


def cue_at(cues, starts, time):
    idx=bisect.bisect_right(starts,time)-1
    if idx<0 or time>=cues[idx]["end"]:
        return "X"
    return cues[idx]["value"]


def limb(items, a,b,c,r1,r2, hand=False):
    a,b,c=map(Vector,(a,b,c))
    for obj,first,last,r in ((items[0],a,b,r1),(items[1],b,c,r2)):
        stage.between(obj,first,last,r)
        key(obj,'location','rotation_quaternion','scale')
    items[2].location=b
    items[3].location=c+(Vector((0,-.010,-.044)) if hand else Vector((0,-.044,-.006)))
    key(items[2],'location')
    key(items[3],'location')


def pose(ch,role,loc,yaw,walk,phase,time,cue,talking,listening):
    seated=role=="manager"
    ch["root"].location=(*loc,0)
    ch["root"].rotation_euler.z=yaw
    key(ch["root"],'location','rotation_euler')
    z=.56 if seated else .864
    bounce=(1-math.cos(2*phase))*.019*walk
    ch["hips"].location=(0,0,z+bounce)
    key(ch["hips"],'location')
    ch["body"].rotation_euler=(.03*walk+.010*math.sin(time*1.4),.018*walk*math.cos(phase),
                               .040*walk*math.sin(phase)+.014*math.sin(time*1.7))
    key(ch["body"],'rotation_euler')
    ch["head"].rotation_euler=(.028*math.sin(time*(4.1 if talking else 1.7))+.022*listening,
                               .021*math.sin(time*1.4),
                               .06*math.sin(time*1.3)+.035*walk*math.cos(phase))
    key(ch["head"],'rotation_euler')
    bt=(time+(.43 if seated else .85))%3.15
    blink=.10+.90*min(1.,abs(bt-1.12)/.065)
    for eye in ch["eyes"]:
        eye.scale.z=blink
        key(eye,'scale')
    w,h=SHAPES[cue]
    ch["mouth"].scale=(w,1,h)
    key(ch["mouth"],'scale')
    ch["teeth"].scale.x=.001 if cue in ("X","A","F") else .63
    key(ch["teeth"],'scale')
    for i,side in enumerate((-1,1)):
        swing=math.sin(phase+i*math.pi)*walk
        shoulder=Vector((side*.224,0,.402))
        gest=(.5+.5*math.sin(time*3.25+i*.44))*talking
        if seated:
            elbow=(side*.276,-.128,.195+.014*gest)
            wrist=(side*(.217+.022*gest),-.306-.027*gest,.211+.078*gest)
        else:
            elbow=(side*.276,.02+.13*swing,.178+.035*gest)
            wrist=(side*(.249+.04*gest),-.055+.22*swing-.16*gest,-.035+.155*gest)
        limb(ch["arms"][i],shoulder,elbow,wrist,.083,.064,True)
        hip=Vector((side*.115,0,-.021))
        if seated:
            knee=(side*.123,-.35,-.084)
            ankle=(side*.129,-.38,-z+.077)
        else:
            lift=max(0.,math.cos(phase+i*math.pi))*.125*walk
            ankle=Vector((side*.122,-.225*swing,-z-bounce+.077+lift))
            d=ankle-hip
            # Bend the knee forward while keeping the ankle at floor height in stance.
            front=Vector((0,-1,0))
            front=(front-d.normalized()*front.dot(d.normalized())).normalized()
            knee=(hip+ankle)/2 + front*math.sqrt(max(.0004,.410**2-(d.length/2)**2))
        limb(ch["legs"][i],hip,knee,ankle,.093,.072)


def build(d,width):
    global FRAME
    p,t,cues=d["plan"],d["timing"],d["cues"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s=bpy.context.scene
    s.render.engine='BLENDER_WORKBENCH'
    sh=s.display.shading
    sh.light='STUDIO'
    sh.color_type='OBJECT'
    sh.background_type='VIEWPORT'
    sh.background_color=stage.color("A3BFBC")[:3]
    sh.show_shadows=True
    sh.shadow_intensity=.24
    sh.show_specular_highlight=False
    sh.show_cavity=False
    sh.cavity_type='WORLD'
    sh.cavity_ridge_factor=1.05
    sh.cavity_valley_factor=1.22
    s.display.render_aa='5'
    s.display.shading.studiolight_rotate_z=.35
    s.view_settings.view_transform='Standard'
    s.view_settings.exposure=.65
    s.render.resolution_x=width
    s.render.resolution_y=width*9//16
    s.render.resolution_percentage=100
    s.render.fps=FPS
    s.render.image_settings.file_format='JPEG'
    s.render.image_settings.quality=94
    hinge=stage.room(p["door"])
    employee,manager=[stage.character(role,p["cast"][role]) for role in ("employee","manager")]
    cams=[stage.camera("01 / Arrival",(1.50,-4.85,1.83),(-.60,.38,1.13),p["shots"][0]["lens"]),
          stage.camera("02 / Employee",(1.67,.13,1.65),(-.69,-.32,1.48),p["shots"][1]["lens"]),
          stage.camera("03 / Manager",(-.36,-1.25,1.50),(1.09,.82,1.21),p["shots"][2]["lens"]),
          stage.camera("04 / Departure",(1.50,-4.85,1.83),(-.60,.38,1.13),p["shots"][3]["lens"]),
          stage.camera("05 / Street",(-7.19,-3.85,1.55),(-4.00,.80,1.14),p["shots"][4]["lens"])]
    for i,cam in enumerate(cams):
        marker=s.timeline_markers.new(p["shots"][i]["id"],frame=1+t["starts"][i])
        marker.camera=cam
    s.camera=cams[0]
    starts={role:[c["start"] for c in seq] for role,seq in cues.items()}
    s.frame_start=1
    s.frame_end=t["frames"]
    for FRAME in range(1,t["frames"]+1):
        time=(FRAME-1)/FPS
        shot=bisect.bisect_right(t["starts"],FRAME-1)-1
        local=(FRAME-1-t["starts"][shot])/FPS
        duration=t["lengths"][shot]/FPS
        pct=local/duration
        walk=0.
        loc=(-.78,-.22)
        face=math.atan2(1.98,-1.07)
        door=0.
        if shot==0:
            progress=clamp((pct+.045)/.84)
            distance=1-(1-progress)**1.33
            loc=(-4.52+3.74*distance,-.70+.48*distance)
            walk=1-smooth((progress-.84)/.16)
            face=1.70+(face-1.70)*smooth((progress-.66)/.33)
            door=1.38*(1-smooth((pct-.34)/.31))
        elif shot==3:
            cross=p["exit_crossing"]
            progress=clamp((pct-.08)/(cross-.08))
            tail=clamp((pct-cross)/(1-cross))
            loc=(-.78-2.70*progress-.95*tail,-.22-.48*progress+.36*tail)
            walk=smooth((pct-.035)/.14)
            toward_door=math.atan2(-2.70,.48)+TAU
            after_door=math.atan2(-.95,-.36)+TAU
            turn=smooth((pct-cross+.08)/(.08+min(.08,1-cross)))
            face=face+(toward_door-face)*smooth(pct/.17)+(after_door-toward_door)*turn
            door=1.40*smooth((pct-(cross-.27))/.20)
        elif shot==4:
            # Carry the outgoing velocity and walk phase across the camera cut,
            # then turn naturally to follow the sidewalk.
            tail_seconds=t["lengths"][3]/FPS*(1-p["exit_crossing"])
            vx,vy=-.95/tail_seconds,.36/tail_seconds
            turn_rate=1.6
            decay=math.exp(-turn_rate*local)
            arc=(1-decay)/turn_rate
            loc=(-4.43+vx*arc,-.34+.83*local+(vy-.83)*arc)
            face=math.atan2(vx*decay,-(.83+(vy-.83)*decay))+TAU
            walk=1.
            door=1.40*(1-smooth((local-.03)/1.05))
        hinge.rotation_euler.z=door
        key(hinge,'rotation_euler')
        for role,ch in (("employee",employee),("manager",manager)):
            spoken=time-t["speech_samples"][role]/t["rate"]
            mouth=cue_at(cues[role],starts[role],spoken)
            active=float(0<=spoken<cues[role][-1]["end"])
            pose(ch,role,loc if role=="employee" else (1.19,.87),
                 face if role=="employee" else -1.11,walk if role=="employee" else 0.,
                 time*TAU*1.02,time,mouth,active,float(shot in (1,2) and not active))
    s.frame_set(1)
    return s


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("instructions",type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    d=json.loads(args.instructions.read_text(encoding="utf-8"))
    s=build(d,d["width"])
    root=Path(d["target"])
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(root/"scene.blend"))
    shots=d["plan"]["shots"]
    for i in d["render_indices"]:
        folder=root/"frames"/shots[i]["id"]
        folder.mkdir(parents=True,exist_ok=True)
        first=1+d["timing"]["starts"][i]
        last=first+d["timing"]["lengths"][i]-1
        if d.get("board_only"):
            s.frame_set((first+last)//2)
            s.render.filepath=str(folder/"check.jpg")
            bpy.ops.render.render(write_still=True)
        else:
            s.frame_start=first
            s.frame_end=last
            s.frame_set(first)
            s.render.filepath=str(folder/"f")
            bpy.ops.render.render(animation=True)

if __name__=="__main__":
    main()
