"""The radio room. All stage objects and their dimensions are authored here in metres."""
import math
import bpy
from mathutils import Vector

def collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c

def move(obj, col):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)
    return obj

def mat(name, rgb, rough=.62, metal=0., glow=0):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*rgb,1)
    m.use_nodes=True
    p=m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value=(*rgb,1)
    p.inputs["Roughness"].default_value=rough
    p.inputs["Metallic"].default_value=metal
    if glow:
        p.inputs["Emission Color"].default_value=(*rgb,1)
        p.inputs["Emission Strength"].default_value=glow
    return m

def objmesh(name, vs, faces, material, col):
    data=bpy.data.meshes.new(name); data.from_pydata(vs,[],faces);data.update()
    ob=bpy.data.objects.new(name,data);col.objects.link(ob)
    if material: data.materials.append(material)
    return ob

def empty(name, xyz, col, parent=None, display=.08):
    item=bpy.data.objects.new(name,None);col.objects.link(item)
    item.parent=parent;item.location=xyz;item.empty_display_type="PLAIN_AXES";item.empty_display_size=display
    return item

def box(name, xyz, dims, m, col, bevel=.014, parent=None):
    x,y,z=[v/2 for v in dims]
    vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    fs=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    ob=objmesh(name,vs,fs,m,col);ob.parent=parent;ob.location=xyz
    if bevel:
        b=ob.modifiers.new("Rounded edges","BEVEL");b.width=min(bevel,min(dims)*.4);b.segments=2
        b=ob.modifiers.new("Face normals","WEIGHTED_NORMAL")
    return ob

def rod(name,a,b,r,m,col,parent=None,r2=None,segments=14):
    a,b=Vector(a),Vector(b); axis=b-a
    bpy.ops.mesh.primitive_cone_add(vertices=segments,radius1=r,radius2=r if r2 is None else r2,depth=axis.length)
    ob=move(bpy.context.object,col);ob.name=name;ob.parent=parent;ob.location=(a+b)*.5
    ob.rotation_euler=axis.to_track_quat("Z","Y").to_euler();ob.data.materials.append(m)
    for p in ob.data.polygons: p.use_smooth=len(p.vertices)==4
    return ob

def path(name,pts,rad,m,col,parent=None):
    cu=bpy.data.curves.new(name,"CURVE");cu.dimensions="3D";cu.resolution_u=1
    s=cu.splines.new("POLY");s.points.add(len(pts)-1)
    for k,p in zip(s.points,pts):k.co=(*p,1)
    cu.bevel_depth=rad;cu.bevel_resolution=2
    ob=bpy.data.objects.new(name,cu);col.objects.link(ob);ob.parent=parent
    cu.materials.append(m);return ob

def type_on_wall(name,words,location,size,m,col,rot=(math.pi/2,0,0),parent=None):
    d=bpy.data.curves.new(name,"FONT"); d.body=words;d.size=size;d.align_x="CENTER";d.align_y="CENTER"
    d.space_character=1.16;d.extrude=.0007;d.materials.append(m)
    o=bpy.data.objects.new(name,d);col.objects.link(o);o.parent=parent;o.location=location;o.rotation_euler=rot;return o

def light(name,xyz,aim,energy,size,color,col):
    data=bpy.data.lights.new(name,"AREA");data.energy=energy;data.shape="DISK";data.size=size;data.color=color
    o=bpy.data.objects.new(name,data);col.objects.link(o);o.location=xyz
    o.rotation_euler=(Vector(aim)-Vector(xyz)).to_track_quat("-Z","Y").to_euler();return o

HINGE=(2.52,1.69,0)
LEVER_BASE=(-1.005,-.112,1.03)
LEVER_Y=-.097
LEVER_R=.023
MIC=(-1.47,.56,1.20)
BUTTON=(-1.61,.32,.827)

def build():
    c=collection("01  |  Antenna station • architecture")
    props=collection("02  |  Communications desk")
    door=collection("03  |  Airlock • working hardware")
    lx=collection("04  |  Practicals and daylight")
    soft=mat("Wall • sea glass enamel",(.32,.405,.411))
    low=mat("Dado • deep spruce",(.072,.149,.159))
    seam=mat("Joint • blue graphite",(.042,.065,.071))
    frost=mat("Ice light",(.77,.91,1.),.4,0,.9)
    snow=mat("Whiteout exterior",(.87,.94,1),.85,0,1.45)
    nodes=snow.node_tree.nodes;links=snow.node_tree.links
    coords=nodes.new('ShaderNodeTexCoord')
    scale=nodes.new('ShaderNodeVectorMath');scale.operation='MULTIPLY'
    scale.inputs[1].default_value=(1.8,1,9);links.new(coords.outputs['Generated'],scale.inputs[0])
    drift=nodes.new('ShaderNodeVectorMath');drift.operation='ADD';links.new(scale.outputs[0],drift.inputs[0])
    for f,phase in [(1,0),(840,-9)]:
        drift.inputs[1].default_value=(phase,0,-phase*.07);drift.inputs[1].keyframe_insert(data_path='default_value',frame=f)
    noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=2.5;noise.inputs['Detail'].default_value=2.2
    links.new(drift.outputs[0],noise.inputs['Vector'])
    ramp=nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position=.27;ramp.color_ramp.elements[0].color=(.53,.67,.76,1)
    ramp.color_ramp.elements[1].position=.73;ramp.color_ramp.elements[1].color=(1,1,1,1)
    links.new(noise.outputs['Fac'],ramp.inputs[0])
    for input_name in ['Base Color','Emission Color']:
        links.new(ramp.outputs[0],nodes['Principled BSDF'].inputs[input_name])
    bronze=mat("Oxide orange",(.49,.135,.052))
    ivory=mat("Stencilled bone",(.78,.77,.62))
    dark=mat("Bakelite",(.025,.032,.034),.37)
    steel=mat("Gunmetal",(.22,.29,.30),.38,.46)
    silver=mat("Satin aluminum",(.51,.61,.61),.33,.56)
    olive=mat("Receiver • grey green",(.17,.235,.22),.46,.15)
    lamp=mat("Lamp • tungsten",(.98,.65,.25),.34,0,3.0)
    led=mat("Radio • amber phosphor",(.95,.43,.12),.38,0,2.1)
    red=mat("Push-to-talk • red",(.70,.19,.079),.46)
    oak=mat("Desk • sealed birch edge",(.42,.255,.117),.51)
    flooring=mat("Rubber floor",(.095,.132,.142),.76)
    box("Continuous non-slip floor",(0,-.6,-.095),(9.6,7.5,.19),flooring,c,0)
    for x in [-3.55,-2.35,-1.15,.05,1.25,2.45,3.65]:
        box("Floor tile joint",(x,-.52,.0002),(.006,6.7,.001),seam,c,0)
    for y in [-2.54,-1.34,-.14,1.06]:
        box("Floor tile joint",(0,y,.0002),(9,.006,.001),seam,c,0)
    # Leave the entrance aperture physically open. The hinged mesh alone closes it.
    for left,right,z,h in [(-4.4,1.34,1.53,3.06),(2.57,4.5,1.53,3.06),(1.34,2.57,2.65,.82)]:
        box("Pressure bulkhead",((left+right)/2,1.91,z),(right-left,.22,h),soft,c,.008)
        if z<2:
            box("Dark lower wall",((left+right)/2,1.786,.345),(right-left,.032,.69),low,c,.008)
            box("Dado cap",((left+right)/2,1.76,.695),(right-left,.040,.022),silver,c,.005)
    for x in [-4.1,-3.18,-2.19,-1.18,-.16,.85,3.64]:
        box("Folded panel seam",(x,1.789,1.84),(.012,.027,2.28),steel,c,.003)
    for xx in [-4.36,4.43]:
        box("Side bulkhead",(xx,-.45,1.55),(.12,4.80,3.10),soft,c,.005)
        box("Side dado",(xx+(.075 if xx<0 else -.075),-.45,.345),(.035,4.8,.69),low,c,.005)
    # A narrow band of clerestory and cable runs locates the desk from every angle.
    box("Clerestory gasket",(-1.75,1.714,1.93),(2.23,.16,.78),seam,c,.09)
    box("Polar daylight behind glass",(-1.75,1.617,1.93),(2.11,.035,.67),frost,c,.07)
    for xx in [-2.35,-1.22]:
        box("Window mullion",(xx,1.585,1.93),(.035,.046,.68),steel,c,.009)
    for z in [2.67,2.75]:
        path("Exposed galvanized conduit",[(-4.25,1.72,z),(-.55,1.72,z),(-.40,1.72,z+.10),(3.9,1.72,z+.10)],.024,steel,c)
    for x in [-3.4,-1.8,-.12,1.10,3.53]:
        box("Conduit saddle",(x,1.70,2.75),(.04,.09,.20),silver,c,.005)
    box("Radio room station plate",(.42,1.731,1.78),(1.17,.045,.46),low,c,.018)
    type_on_wall("Station lettering","POLAR / 07",(.42,1.702,1.84),.142,ivory,c)
    type_on_wall("Station lettering small","RADIO  STATION",(.42,1.701,1.69),.052,ivory,c)
    box("Bulkhead electrical case",(-.38,1.669,1.05),(.28,.17,.36),olive,c,.027)
    for j in range(3):box("Case cooling slot",(-.38,1.574,1.07+j*.04),(.17,.009,.008),seam,c,.002)
    for xx in (1.307,2.567):box("Hatch jamb",(xx,1.722,1.11),(.093,.22,2.22),steel,door,.023)
    box("Hatch lintel",(1.94,1.722,2.236),(1.35,.22,.105),steel,door,.022)
    box("Threshold",(1.94,1.71,.017),(1.30,.27,.034),silver,door,.006)
    box("Whiteout sky",(2.2,3.78,1.64),(6.1,.045,3.9),snow,door,0)
    box("Exterior landing",(1.95,2.82,-.019),(1.22,2.16,.035),frost,door,.003)
    hinge=empty("AIRLOCK • hinge",HINGE,door)
    box("Door • insulated leaf",(-.575,0,1.105),(1.15,.114,2.18),low,door,.041,hinge)
    box("Door • enamel face",(-.575,-.061,1.115),(1.065,.035,2.07),olive,door,.04,hinge)
    box("Door • lower kick panel",(-.575,-.085,.29),(.91,.017,.405),steel,door,.018,hinge)
    box("Port • black seal",(-.57,-.09,1.64),(.54,.045,.38),dark,door,.11,hinge)
    box("Port • frosted glass",(-.57,-.117,1.64),(.475,.020,.311),frost,door,.08,hinge)
    type_on_wall("Hatch stencil","AIRLOCK",(-.57,-.087,1.33),.079,ivory,door,parent=hinge)
    for zz in (.48,1.70):
        rod("Hinge barrel",(0,-.052,zz-.08),(0,-.052,zz+.08),.032,silver,door,hinge)
    lever=empty("LATCH • depress then pull",LEVER_BASE,door,hinge,.055)
    rod("Latch mounting rose",(0,0,0),(0,-.051,0),.061,silver,door,lever)
    rod("Latch stem",(0,-.04,0),(0,LEVER_Y,0),.022,steel,door,lever)
    grip=rod("LATCH • hand contact surface",(-.014,LEVER_Y,0),(.231,LEVER_Y,0),LEVER_R,bronze,door,lever,segments=32)
    tag=empty("Inspection tag • knock vibration",(-.73,-.10,1.28),door,hinge,.025)
    rod("Tag pin",(0,.01,0),(0,-.013,0),.010,silver,door,tag)
    path("Wire tag hanger",[(0,-.008,-.004),(-.013,-.014,-.043),(0,-.020,-.055)],.003,silver,door,tag)
    box("Brass inspection tag",(0,-.021,-.102),(.078,.007,.099),bronze,door,.006,tag)
    type_on_wall("Tag number","07",(0,-.025,-.101),.036,ivory,door,parent=tag)
    for f,angle in [(1,0),(251,0),(254,8),(258,-5),(259,-3),(262,11),(266,-7),(268,-2),
                    (271,15),(276,-10),(282,6),(289,-3),(297,1),(306,0),(535,0),(554,-3),(573,7),(588,-4),(608,0)]:
        tag.rotation_euler.y=math.radians(angle)
        tag.keyframe_insert(data_path='rotation_euler',frame=f)
    # Instrument bench runs north-south, with Kate seated on its west side.
    box("Radio bench • birch edge",(-1.22,.50,.764),(.92,1.64,.074),oak,props,.032)
    box("Radio bench • writing surface",(-1.22,.50,.805),(.90,1.63,.014),low,props,.009)
    for xx in (-1.55,-.88):
        for yy in (-.17,1.16):
            rod("Bench leg",(xx,yy,.02),(xx,yy,.75),.026,steel,props)
    box("Under-bench service cabinet",(-.96,1.01,.43),(.41,.34,.55),olive,props,.024)
    # Two radios and a speaker face Kate. The forms remain readable in silhouette.
    console=empty("Receiver • face west-southwest",(-1.06,.82,.819),props)
    console.rotation_euler.z=math.radians(-53)
    box("HF receiver chassis",(0,0,.162),(.58,.35,.32),olive,props,.037,console)
    box("HF front panel",(0,-.182,.161),(.526,.026,.265),seam,props,.012,console)
    box("Frequency bezel",(-.06,-.201,.193),(.298,.018,.102),dark,props,.008,console)
    box("Frequency display",(-.06,-.213,.192),(.268,.008,.074),led,props,.005,console)
    type_on_wall("Radio frequency","14.207",(-.060,-.219,.193),.045,dark,props,parent=console)
    for j in range(8):
        box("Receiver speaker slot",(-.192+j*.039,-.202,.076),(.018,.010,.029),steel,props,.002,console)
    for xx,zz,rr in [( .159,.189,.050),(.202,.080,.020),(.126,.082,.017)]:
        rod("Knurled dial",(xx,-.196,zz),(xx,-.24,zz),rr,silver,props,console)
    rod("Mic foot",(-1.45,.60,.815),(-1.45,.60,.84),.081,dark,props)
    path("Gooseneck microphone",[(-1.45,.60,.84),(-1.43,.62,.995),(-1.425,.61,1.115),MIC],.011,steel,props)
    rod("Broadcast microphone capsule",(-1.438,.581,1.178),(-1.522,.532,1.236),.036,dark,props,r2=.041)
    for v in (.15,.32,.49,.66,.83):
        a=Vector((-1.438,.581,1.178));b=Vector((-1.522,.532,1.236))
        v1=a.lerp(b,v);v2=a.lerp(b,v+.045)
        rod("Microphone grille band",v1,v2,.040,steel,props)
    box("Talk switch base",(BUTTON[0],BUTTON[1],.818),(.102,.090,.015),dark,props,.009)
    ptt=box("PTT • key",(BUTTON[0],BUTTON[1],.827),(.078,.057,.019),red,props,.007)
    path("Desk handset cable",[(-1.56,.33,.817),(-1.49,.30,.817),(-1.43,.335,.817),(-1.41,.418,.817),
         (-1.38,.485,.817),(-1.31,.50,.817),(-1.225,.62,.817)],.007,dark,props)
    # Route the paper and mug beyond the actor's reach lane.
    paper=mat("Chart stock",(.77,.73,.57))
    for j in range(3):
        chart=box("Watch log sheet",(-1.29,.00,.814+j*.0018),(.34,.22,.0015),paper,props,0)
        chart.rotation_euler.z=(-.14+j*.06)
    for j in range(6):box("Logbook rule",(-1.28,-.071+j*.021,.820),(.238,.0018,.001),steel,props,0)
    rod("Enamel mug",(-1.03,-.14,.813),(-1.03,-.14,.915),.041,ivory,props)
    rod("Coffee surface",(-1.03,-.14,.915),(-1.03,-.14,.916),.035,dark,props)
    chair=empty("Kate • fixed chair",(-2.03,.49,0),props)
    chair.rotation_euler.z=math.radians(84)
    box("Chair • upholstered seat",(0,.005,.434),(.45,.44,.081),bronze,props,.048,chair)
    box("Chair • upholstered back",(0,.229,.69),(.43,.059,.37),bronze,props,.038,chair)
    for xx in (-.172,.172):
        for yy in (-.152,.159):
            rod("Chair leg",(xx*1.13,yy*1.16,.018),(xx,yy,.415),.017,steel,props,chair)
        rod("Chair back post",(xx,.168,.39),(xx,.235,.82),.013,steel,props,chair)
    box("Task lamp mounting plate",(-1.09,1.20,.821),(.15,.11,.016),dark,props,.007)
    path("Task lamp arm",[(-1.09,1.20,.825),(-1.08,1.18,1.38),(-1.30,1.09,1.58),(-1.42,1.01,1.48)],.014,bronze,props)
    rod("Anglepoise shade",(-1.411,1.02,1.49),(-1.46,.96,1.418),.043,bronze,props,r2=.10)
    rod("Task light diffuser",(-1.46,.96,1.418),(-1.462,.957,1.415),.086,lamp,props)
    light("Softbox • southern practical",(0,-3.25,3.4),(-.4,.7,.85),330,5.0,(.83,.90,1),lx)
    light("Window • cold working light",(-2.25,1.42,2.40),(-1.50,-.20,.75),135,1.8,(.68,.86,1),lx)
    light("Ceiling • fill",(2.4,-.25,2.97),(1.45,1.18,.80),160,2.4,(.94,.83,.67),lx)
    light("Task • copper pool",(-1.46,.94,1.42),(-2.02,.48,.90),22,.35,(1,.68,.38),lx)
    light("Exterior • reflected white",(2.05,2.7,2.48),(1.62,.59,1.0),335,1.7,(.70,.84,1),lx)
    return hinge,lever,grip,ptt
