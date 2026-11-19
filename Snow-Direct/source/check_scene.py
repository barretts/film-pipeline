"""Numerical checks on the reopened, evaluated scene and optional native rendering."""
import bpy
import json
import sys
from pathlib import Path
from math import degrees
from math import hypot
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
BASE=Path(__file__).resolve().parent.parent
work=BASE/'work'
work.mkdir(exist_ok=True)
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
s=bpy.context.scene
def find(prefix):return next(o for o in s.objects if o.name.startswith(prefix))
def blocking():
    james=s.objects['James / skeleton'];kate=s.objects['Kate / skeleton']
    holds=[]
    for side,start,end in [('r',418,430),('l',436,445),('r',453,461),('l',468,476),('l',502,533)]:
        pts=[]
        for f in range(start,end+1):
            s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get()
            e=james.evaluated_get(dg)
            pts.append(e.matrix_world@e.pose.bones['foot_'+side].head)
        holds.append(dict(foot=side,frames=[start,end],max_ankle_drift_mm=round(1000*max((p-pts[0]).length for p in pts),3)))
    crosses=[]
    for f in (479,480,481,482):
        s.frame_set(f);crosses.append((f,james.matrix_world.translation.copy()))
    seat=find('Chair • upholstered seat')
    actor=[]
    for f in (1,177,509,645,777,840):
        s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get()
        a=kate.evaluated_get(dg)
        pelvis=a.matrix_world@a.pose.bones['pelvis'].head
        top=seat.matrix_world@Vector((0,0,max(v.co.z for v in seat.data.vertices)))
        actor.append(dict(frame=f,pelvis_above_seat_mm=round(1000*(pelvis.z-top.z),1),
                          cast_root_xyz=[round(v,4) for v in a.matrix_world.translation]))
    return dict(support_intervals=holds,walking_across_cut=[dict(frames=[a[0],b[0]],root_step_mm=round(1000*(a[1]-b[1]).length,3)) for a,b in zip(crosses,crosses[1:])],kate_chair=actor)
def measurement():
    j=s.objects['James / body and gloves'];k=s.objects['Kate / body and gloves']
    jj=j['right contact vertex'];kk=k['right contact vertex']
    grip=find('LATCH • hand contact');button=find('PTT • key')
    hinge=find('AIRLOCK • hinge');lever=find('LATCH • depress')
    hand=[v.index for v in j.data.vertices if v.co.x<-.76 and v.co.z>1.3]
    rows=[]
    frames=sorted(set([1,121,241,361,470,480,481,488,495,600,601,645,721,738,743,747,757,783,817,830])|set(range(500,583)))
    for f in frames:
        s.frame_set(f);dg=bpy.context.evaluated_depsgraph_get()
        je=j.evaluated_get(dg);ke=k.evaluated_get(dg);ge=grip.evaluated_get(dg);be=button.evaluated_get(dg)
        jpos=je.matrix_world@je.data.vertices[jj].co
        kpos=ke.matrix_world@ke.data.vertices[kk].co
        bvh=BVHTree.FromObject(grip,dg)
        togrip=ge.matrix_world.inverted()@je.matrix_world
        def dist(v):return bvh.find_nearest(togrip@je.data.vertices[v].co)[3]
        nearest=min(dist(i) for i in hand)
        tolever=lever.matrix_world.inverted()@je.matrix_world
        inside=[max(0,.023-hypot(v.y+.097,v.z)) for i in hand for v in [tolever@je.data.vertices[i].co] if -.014<v.x<.231]
        switch=BVHTree.FromObject(button,dg)
        button_mm=switch.find_nearest(be.matrix_world.inverted()@kpos)[3]*1000
        jndc=world_to_camera_view(s,s.camera,jpos)
        rows.append(dict(frame=f,tip_to_lever_mm=round(dist(jj)*1000,3),closest_glove_mm=round(nearest*1000,3),
                deepest_glove_vertex_inside_grip_mm=round(1000*max(inside,default=0),3),
                lever_deg=round(degrees(lever.rotation_euler.y),3),door_deg=round(degrees(hinge.rotation_euler.z),3),
                kate_tip_to_switch_mm=round(button_mm,3),switch_height_m=round(be.matrix_world.translation.z,5),
                james_visible=not j.hide_render,kate_visible=not k.hide_render,
                james_tip_world=[round(v,5) for v in jpos],james_tip_in_frame=[round(v,4) for v in jndc[:2]]))
    marks=sorted((m.frame,m.camera.name) for m in s.timeline_markers if m.camera)
    out=dict(unit="Millimetres to the triangulated visible surfaces, measured after skinning and constraints",
       frames=s.frame_end,fps=s.render.fps,cut_cameras=marks,actors=[k.name,j.name],
       right_hand_vertices_tested=len(hand),packed_sound=bool(s.sequence_editor.strips[0].sound.packed_file),
       measurements=rows,blocking=blocking())
    (BASE/'measurements.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    for r in rows:
        if r['frame'] in [500,507,512,522,535,549,560,571,600,601,747,783]:
            print("CHECK",r['frame'],r['tip_to_lever_mm'],r['closest_glove_mm'],r['door_deg'],r['kate_tip_to_switch_mm'],r['james_tip_in_frame'],flush=True)
def frames():
    output=work/'preview';output.mkdir(exist_ok=True)
    for f in [int(x) for x in args[1:]] or [64,178,261,402,475,508,550,578,644,776]:
        s.frame_set(f);s.render.filepath=str(output/f'{f:04}.png')
        bpy.ops.render.render(write_still=True)
        print('PREVIEW',f,flush=True)
if args and args[0]=='review':
    measurement()
    frames()
elif args and args[0]=='preview':frames()
else:measurement()
