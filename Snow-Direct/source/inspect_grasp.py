"""Probe finger flexion on a held frame; values are millimetres outside the lever."""
import bpy
from math import radians,hypot
from mathutils import Euler
s=bpy.context.scene
s.frame_set(549)
arm=s.objects['James / skeleton'];mesh=s.objects['James / body and gloves']
lever=next(o for o in s.objects if o.name.startswith('LATCH') and 'depress' in o.name)
dg=bpy.context.evaluated_depsgraph_get()
for finger in ('thumb','ring','pinky'):
    ids=[v.index for v in mesh.data.vertices if v.co.x<-.76 and
         mesh.vertex_groups[max(v.groups,key=lambda g:g.weight).group].name.startswith(finger)]
    results=[]
    for flex in ([-30,-20,-10,0,10,20,30] if finger=='thumb' else [10,16,22,27,31,35,40,45,50]):
        for splay in ([-22,-12,0,12,22] if finger=='thumb' else [0]):
            for i in ('01','02','03'):
                p=arm.pose.bones[finger+'_'+i+'_r'];q=p.bone.matrix_local.to_quaternion()
                p.rotation_quaternion=q.inverted()@Euler((0,radians(-flex),radians(splay if i=='01' else 0))).to_quaternion()@q
            bpy.context.view_layer.update();ev=mesh.evaluated_get(dg);tr=lever.matrix_world.inverted()@ev.matrix_world
            pts=[tr@ev.data.vertices[i].co for i in ids]
            err=min([hypot(v.y+.097,v.z)-.023 for v in pts if -.014<v.x<.231],default=.2)*1000
            results.append((flex,splay,round(err,1)))
    print(finger,results,flush=True)
