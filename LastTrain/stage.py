import bpy,math,json
from pathlib import Path
from mathutils import Vector
D=Path(__file__).resolve().parent
s=bpy.context.scene
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
s.frame_end=840;s.render.fps=24
story=json.loads((D/'story.json').read_text())
s['Screenplay']=' '.join(story)
def mesh(name,loc,size,color,ball=False,parent=None):
 if ball:bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8)
 else:bpy.ops.mesh.primitive_cube_add(size=2)
 o=bpy.context.object;o.name=name;o.parent=parent;o.location=loc;o.scale=size
 m=bpy.data.materials.get(color) or bpy.data.materials.new(color);m.diffuse_color=tuple(int(color[i:i+2],16)/255 for i in (0,2,4))+(1,);o.data.materials.append(m);return o
def root(name):
 o=bpy.data.objects.new(name,None);s.collection.objects.link(o);return o
def key(o,f,pos):
 o.location=pos;o.keyframe_insert(data_path='location',frame=f)
def actor(name,skin,coat,hair):
 p=root(name)
 for label,pos,scale,col in [('coat',(0,0,1.07),(.25,.16,.39),coat),('face',(0,0,1.64),(.145,.14,.19),skin),('hair',(0,.015,1.78),(.153,.14,.095),hair)]:
  mesh(name+label,pos,scale,col,True,p)
 for sign in [-1,1]:
  mesh(name+' leg',(sign*.115,0,.44),(.092,.10,.44),'26282C',True,p)
  mesh(name+' sleeve',(sign*.235,-.04,1.09),(.08,.09,.25),coat,True,p)
 return p
nell=actor('Nell','683B27','CC9023','211A17');ken=actor('Ken','BB8463','182943','B6B3AF')
mesh('black shoulder bag',(-.23,-.10,.87),(.12,.08,.16),'181716',False,nell)
mesh('platform', (0,0,-.12),(12,8,.12),'BDB6A4');mesh('station end wall',(3,1.75,1.55),(3,.09,1.55),'45654E');mesh('left doorpost',(-4,1.75,1.5),(.1,.12,1.5),'395745')
mesh('wooden counter',(.66,.15,.50),(.68,.37,.50),'805437')
train=root('Departing carriage')
mesh('carriage sill',(0,0,.6),(4,.12,.56),'335873',False,train);mesh('roof',(0,0,2.31),(4,.15,.13),'BBB6A5',False,train)
for x in [-4,-2,0,2,4]:mesh('window post',(x,0,1.69),(.045,.12,.55),'475E66',False,train)
mesh('far carriage wall',(0,1.2,1.3),(4,.08,1.05),'B1AA97',False,train)
for f,x in [(1,-9),(121,-8),(240,-2),(780,-2),(840,-4)]:key(train,f,(x,2.61,0))
for f,x,y,z in [(1,-.45,-.16,0),(190,-.45,-.16,0),(240,-.63,-.16,0),(360,-2.55,1,0),(480,-2.55,1,0),(575,-1.9,1,0),(620,-1.9,1,0),(720,-2.9,3.0,.04),(721,-2.9,3.0,-.06),(780,-2.9,3.0,-.06),(840,-4.9,3.0,-.06)]:key(nell,f,(x,y,z))
for f,x,y in [(1,.65,.67),(400,.65,.67),(480,-.65,.78),(560,-1.32,1),(840,-1.32,1)]:key(ken,f,(x,y,0))
scarf=mesh('Single crimson scarf', (0,0,0),(.28,.085,.07),'A50E27',True)
for f,pos in [(1,(-.43,-.36,1.27)),(90,(.13,-.14,1.07)),(395,(.13,-.14,1.07)),(432,(.38,.38,1.73)),(480,(-.95,.57,1.74)),(560,(-1.6,.82,1.3)),(600,(-1.88,.81,1.25)),(635,(-1.9,.91,1.46)),(720,(-2.9,2.91,1.5)),(721,(-2.9,2.91,1.4)),(780,(-2.9,2.91,1.4)),(840,(-4.9,2.91,1.4))]:key(scarf,f,pos)
ticket=mesh('paper ticket',(.2,-.2,1.2),(.07,.012,.035),'FAE9C1',False,nell)
ticket.hide_render=True;ticket.keyframe_insert(data_path='hide_render',frame=1);ticket.hide_render=False;ticket.keyframe_insert(data_path='hide_render',frame=175)
views=[((-.5,-4,1.65),(.05,.1,1.12),39),((-.75,-2.6,1.55),(-.30,-.05,1.22),46),((-.7,-5,1.75),(-.85,.65,1.13),35),((-.65,-4.4,1.60),(-.75,.7,1.25),38),((-1.6,-2.9,1.55),(-1.64,.95,1.28),45),((-2.5,-3.9,1.85),(-2.4,2.2,1.28),38),((-3.9,.65,1.65),(-3.9,3.1,1.39),37)]
for i,(pos,aim,lens) in enumerate(views):
 data=bpy.data.cameras.new('Lens');cam=bpy.data.objects.new('Shot '+str(i+1),data);s.collection.objects.link(cam);cam.location=pos;cam.rotation_euler=(Vector(aim)-Vector(pos)).to_track_quat('-Z','Y').to_euler();data.lens=lens;s.timeline_markers.new(story[i][:50],frame=i*120+1).camera=cam
 if i==0:s.camera=cam
s.render.engine='CYCLES';s.cycles.samples=2;s.world=bpy.data.worlds.new('Day');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.8,.85,.9,1)
s.render.resolution_x=704;s.render.resolution_y=396;s.render.resolution_percentage=100
s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(D/'LastTrain.blend'))
for i in range(7):
 for f in (i*120+1,(i+1)*120):
  s.frame_set(f);s.render.filepath=str(D/'guides'/f'{f:04}.png');bpy.ops.render.render(write_still=True)

