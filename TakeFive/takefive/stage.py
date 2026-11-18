"""The dispatch set and cast. Executed by Blender's embedded Python."""
import math
import bpy
from mathutils import Vector

PALETTE = {"rust": "C65C37", "teal": "287978", "navy": "334860", "olive": "7B8051",
           "ochre": "C89B4B", "plum": "87536F", "blue": "3376A0", "cream": "DFCFAB"}
PAPER, INK, WOOD, BRASS = "F0DFBA", "243C40", "9E6444", "D0A762"
MESHES = {}
MATERIALS = {}


def color(code):
    v = [int(code[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in v)+(1,)


def paint(obj, code):
    if code not in MATERIALS:
        m = bpy.data.materials.new(code)
        m.diffuse_color = color(code)
        MATERIALS[code] = m
    obj.color = color(code)
    if obj.type in ("MESH", "FONT", "CURVE"):
        if not obj.data.materials:
            obj.data.materials.append(MATERIALS[code])
        obj.material_slots[0].link = 'OBJECT'
        obj.material_slots[0].material = MATERIALS[code]


def mount(o, name, pos, parent=None):
    o.name = name
    if parent is not None:
        o.parent = parent
    o.location = pos
    return o


def empty(name, pos=(0,0,0), parent=None):
    o = bpy.data.objects.new(name,None)
    bpy.context.collection.objects.link(o)
    o.empty_display_size = .08
    return mount(o,name,pos,parent)


def primitive(kind, name, pos, scale, shade, parent=None):
    if kind not in MESHES:
        if kind == "box":
            bpy.ops.mesh.primitive_cube_add(size=2)
        elif kind == "oval":
            bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12)
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=1, depth=2)
        o = bpy.context.object
        MESHES[kind] = o.data
        if kind == "oval":
            for p in o.data.polygons:
                p.use_smooth = True
    else:
        o = bpy.data.objects.new(name,MESHES[kind])
        bpy.context.collection.objects.link(o)
    mount(o,name,pos,parent)
    o.scale = scale
    paint(o,shade)
    return o


def box(name, pos, size, shade, p=None):
    return primitive("box",name,pos,tuple(x/2 for x in size),shade,p)


def oval(name, pos, radii, shade, p=None):
    return primitive("oval",name,pos,radii,shade,p)


def cyl(name, pos, radius, height, shade, p=None):
    return primitive("tube",name,pos,(radius,radius,height/2),shade,p)


def between(o, a, b, radius, flat=None):
    av,bv = Vector(a), Vector(b)
    delta = bv-av
    o.location = (av+bv)/2
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = delta.to_track_quat('Z','Y')
    o.scale = (radius, flat or radius, delta.length/2)


def bar(name, a, b, r, shade, p=None):
    o = cyl(name,(0,0,0),r,1,shade,p)
    between(o,a,b,r)
    return o


def mesh(name, verts, faces, shade, p=None):
    data=bpy.data.meshes.new(name)
    data.from_pydata(verts,[],faces)
    data.update()
    obj=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    mount(obj,name,(0,0,0),p)
    paint(obj,shade)
    return obj


def rings(name, rows, shade, p, segments=24):
    vs=[(a*math.cos(i*math.tau/segments),b*math.sin(i*math.tau/segments),z)
        for z,a,b in rows for i in range(segments)]
    fs=[(j*segments+i,j*segments+(i+1)%segments,(j+1)*segments+(i+1)%segments,(j+1)*segments+i)
        for j in range(len(rows)-1) for i in range(segments)]
    fs += [tuple(range(segments-1,-1,-1)),tuple(range((len(rows)-1)*segments,len(rows)*segments))]
    o=mesh(name,vs,fs,shade,p)
    for poly in o.data.polygons[:-2]:
        poly.use_smooth=True
    return o


def inscription(text, pos, height, shade, p=None, yaw=0):
    data=bpy.data.curves.new(text,'FONT')
    data.body=text
    data.align_x='CENTER'
    data.align_y='CENTER'
    data.size=height
    obj=bpy.data.objects.new(text,data)
    bpy.context.collection.objects.link(obj)
    mount(obj,text,pos,p)
    obj.rotation_euler=(math.pi/2,0,yaw)
    paint(obj,shade)
    return obj


def room(door_color):
    box("Freight yard ground",(0,0,-.34),(80,80,.18),"9AA69C")
    box("Terrazzo floor",(0,.05,-.09),(7.1,6.3,.18),"BEAE91")
    for i in range(-3,4):
        box("Terrazzo joint",(i,0,.002),(.009,6,.004),"A09480")
    for i in range(-3,4):
        box("Terrazzo joint",(0,i,.002),(7,.009,.004),"A09480")
    box("North plaster wall",(0,2.9,1.8),(7.15,.16,3.6),"E9DABD")
    box("East plaster wall",(3.58,.0,1.8),(.16,5.9,3.6),"E4D5B7")
    box("East wainscot",(3.48,.0,.46),(.07,5.9,.92),"59918A")
    box("East picture rail",(3.43,.0,.94),(.08,5.9,.075),"345F61")
    box("North wainscot",(0,2.79,.46),(7.1,.07,.92),"59918A")
    box("North rail",(0,2.74,.94),(7.1,.09,.075),"345F61")
    for i in range(-13,14):
        box("Wainscot bead",(i*.26,2.748,.48),(.012,.018,.83),"447C77")
    box("Skirting",(0,2.737,.075),(7.1,.09,.14),INK)
    # The two sides of the threshold belong to the same wall.
    for centre,width in ((-2.405,1.59),(1.57,2.66)):
        box("Street wall",(-3.48,centre,1.7),(.18,width,3.4),"D5C7A9")
        box("Street wainscot",(-3.37,centre,.47),(.06,width,.94),"59918A")
        box("Street rail",(-3.34,centre,.94),(.065,width,.07),"345F61")
        box("Exterior plinth",(-3.60,centre,.29),(.12,width,.58),"528282")
    # Door spans y=-1.61 to .24. Opening rotates inward from its north jamb.
    box("Lintel",(-3.48,-.685,3.02),(.2,1.86,.84),"D5C7A9")
    for y in (-1.61,.24):
        box("Door casing",(-3.47,y,1.30),(.31,.12,2.60),"E4D4AD")
    box("Door casing",(-3.47,-.685,2.59),(.31,1.97,.14),"E4D4AD")
    hinge=empty("Blue street door • hinge",(-3.47,.19,0))
    shade=PALETTE[door_color]
    box("Door bottom",(0,-.86,.535),(.105,1.72,1.07),shade,hinge)
    for y in (-.10,-1.63):
        box("Door stile",(0,y,1.72),(.105,.19,1.30),shade,hinge)
    box("Door top",(0,-.86,2.43),(.105,1.72,.20),shade,hinge)
    box("Glass",(0,-.86,1.73),(.024,1.35,1.23),"9DBBB5",hinge)
    box("Glass rail",(0,-.86,1.70),(.112,1.46,.035),shade,hinge)
    box("Glass mullion",(0,-.86,1.72),(.112,.035,1.35),shade,hinge)
    for x in (-.10,.10):
        box("Brass push plate",(x,-1.52,.99),(.028,.12,.26),BRASS,hinge)
        bar("Door grip",(x*1.45,-1.55,.99),(x*1.45,-1.32,.99),.025,INK,hinge)
    # Feature wall, practical office furniture and recognizable landmarks.
    box("Dispatch enamel sign",(-.98,2.765,2.09),(2.52,.065,.64),"284C50")
    box("Sign accent",(-2.14,2.722,2.09),(.035,.025,.52),BRASS)
    inscription("D I S P A T C H",(-.95,2.722,2.17),.224,PAPER)
    inscription("F R E I G H T   O F F I C E",(-.95,2.719,1.985),.085,"D7AD73")
    box("Window trim",(1.38,2.747,1.98),(1.95,.11,1.48),WOOD)
    box("North light",(1.38,2.672,1.98),(1.78,.055,1.30),"B4D1C4")
    for j in range(9):
        box("Venetian blind",(1.38,2.615,1.46+j*.13),(1.84,.095,.045),"E4D2AC")
    box("Window sash",(1.38,2.60,1.99),(.055,.08,1.35),"A68762")
    # The clock is recognizable from both interior angles.
    clock=empty("Wall clock",(2.80,2.74,2.28))
    clock.rotation_euler.x=math.pi/2
    cyl("Clock rim",(0,0,0),.235,.07,INK,clock)
    cyl("Clock dial",(0,0,.05),.211,.03,PAPER,clock)
    for j in range(12):
        ang=j*math.tau/12
        bar("Clock tick",(.172*math.sin(ang),.172*math.cos(ang),.075),(.191*math.sin(ang),.191*math.cos(ang),.075),.007,INK,clock)
    bar("Hand",(0,0,.087),(.11,.075,.087),.010,INK,clock)
    bar("Hand",(0,0,.09),(-.105,.127,.09),.007,"A54C32",clock)
    deskx,desky=1.22,.15
    box("Desk top",(deskx,desky,.745),(1.83,.75,.10),"A76F49")
    box("Desk inlay",(deskx,desky,.80),(1.76,.70,.018),"B88153")
    for x in (.45,1.98):
        for y in (-.13,.43):
            box("Desk foot",(x,y,.35),(.09,.09,.72),INK)
    box("Desk modesty panel",(1.22,-.12,.47),(1.52,.085,.45),"46746E")
    for j in range(3):
        box("Drawer front",(1.82,-.225,.64-j*.15),(.35,.09,.13),"B07E54")
        box("Drawer pull",(1.82,-.281,.64-j*.15),(.13,.028,.022),BRASS)
    for j in range(3):
        o=box("Dispatch log",(.97,-.01,.832+j*.014),(.32,.23,.012),("C4B59A","DED0AD","EEE1C3")[j])
        o.rotation_euler.z=-.13
    box("Log binding",(.835,-.01,.871),(.025,.23,.013),"476961")
    cyl("Lamp foot",(1.92,.29,.836),.11,.05,INK)
    bar("Lamp arm",(1.92,.29,.85),(1.92,.29,1.21),.022,BRASS)
    oval("Lamp green enamel",(1.86,.29,1.23),(.19,.115,.086),"396D62")
    box("Telephone",(.58,.18,.855),(.23,.17,.105),INK)
    oval("Receiver",(.58,.19,.931),(.15,.053,.044),"293B3B")
    box("Chair",(1.18,.87,.49),(.54,.50,.09),"775240")
    box("Chair back",(1.26,1.10,.83),(.50,.10,.61),"805841")
    for x in (.99,1.41):
        for y in (.69,1.02):
            bar("Chair foot",(x,y,.02),(x,y,.49),.03,INK)
    for x in (2.68,):
        box("Cabinet",(x,2.21,.61),(.67,.67,1.22),"71918A")
        for j in range(3):
            z=.25+j*.36
            box("File drawer",(x,1.865,z),(.615,.03,.31),"809E94")
            box("Card label",(x,1.84,z+.045),(.14,.015,.04),PAPER)
            box("Pull",(x,1.82,z-.035),(.18,.035,.025),INK)
    # On the street the same blue door opens onto a paving strip and freight yard.
    box("Pavement",(-7.1,0,-.105),(7.1,32,.20),"C4BBA3")
    box("Kerb",(-5.66,0,-.028),(.14,32,.14),"B3AB97")
    box("Service road",(-9.72,0,-.122),(7.95,32,.15),"778383")
    for i in range(-8,9):
        box("Concrete joints",(-4.58,i*1.38,.001),(2.02,.014,.004),"9C9E8B")
    for y in (-2.55,1.71):
        box("Street window",(-3.592,y,1.58),(.09,.92,1.42),"385E60")
        box("Street window glass",(-3.653,y,1.59),(.042,.78,1.24),"8DACA7")
        for j in range(4):
            box("Street window louver",(-3.692,y,1.18+j*.23),(.035,.76,.035),PAPER)
    box("Door canopy",(-3.83,-.685,2.77),(.76,2.25,.145),INK)
    box("Depot sign",(-3.59,.99,2.44),(.06,1.26,.34),INK)
    inscription("DEPOT  04",(-3.637,.99,2.44),.153,PAPER,yaw=-math.pi/2)
    for y in (-1.83,.52):
        cyl("Bollard",(-3.97,y,.22),.085,.46,"CE9F51")
        cyl("Bollard stripe",(-3.97,y,.32),.088,.06,INK)
    # A row of distant service buildings also closes the view through the threshold.
    for i in range(8):
        x=-7+i*2
        box("Freight buildings",(x,7.9,2.1),(1.96,1.8,4.2+i%3*.42),("8CA4A1","95A49A","A0ADA4")[i%3])
        box("Roof coping",(x,6.96,4.15+i%3*.21),(1.98,.13,.13),"597576")
        box("Warehouse shutter",(x,6.972,1.27),(1.38,.065,2.54),"637F7D")
        for j in range(7):
            box("Shutter rib",(x,6.92,.28+j*.32),(1.35,.04,.028),"84978A")
        for side in (-1,1):
            box("Clerestory glass",(x+side*.39,6.95,3.28),(.64,.06,.48),"B7CBC0")
    return hinge


def character(role, actor):
    manager=role=="manager"
    skin="995F48" if manager else "D79C73"
    skin_light="AF7357" if manager else "E3AF83"
    hair="302B2B" if manager else "46352F"
    coat=PALETTE[actor["coat"]]
    root=empty(role+" • "+actor["name"])
    hips=empty("Hips",parent=root)
    body=empty("Upper body",parent=hips)
    oval("Trousers",(0,0,-.005),(.209,.14,.14),"30474D" if manager else "455261",hips)
    rings("Work jacket",[(-.018,.204,.142),(.05,.225,.147),(.32,.244,.156),(.44,.265,.136),(.485,.170,.117)],coat,body)
    mesh("Shirt front",[(-.121,-.134,.456),(.119,-.134,.456),(0,-.16,.19)],[(0,1,2)],PAPER,body)
    for side in (-1,1):
        mesh("Jacket lapel",[(side*.124,-.136,.471),(side*.183,-.128,.402),
                             (side*.084,-.160,.323),(0,-.163,.205)],[(0,1,2,3)],coat,body)
    bar("Front seam",(0,-.151,.015),(0,-.161,.21),.008,BRASS,body)
    box("Pocket",(-.142,-.132,.253),(.094,.018,.07),coat,body)
    box("Pocket piping",(-.142,-.147,.28),(.093,.014,.013),PAPER,body)
    cyl("Neck",(0,0,.50),.092,.17,skin,body)
    head=empty("Head",(0,-.010,.718),body)
    oval("Face",(0,0,0),(.201,.172,.248),skin,head)
    for side in (-1,1):
        oval("Ear",(side*.196,.003,-.005),(.039,.036,.061),skin_light,head)
        if manager:
            oval("Earring",(side*.208,-.014,-.060),(.019,.013,.022),BRASS,head)
    oval("Nose",(0,-.156,-.005),(.041,.047,.058),skin_light,head)
    haircap=rings("Hair",[(-.016,.198,.174),(.046,.208,.185),(.138,.188,.167),(.202,.139,.131),(.239,.055,.065)],hair,head)
    haircap.location=(0,.027,.041)
    for i in range(7):
        x=(i-3)*.048
        o=oval("Swept fringe",(x,-.100+.030*abs(i-3),.174-.011*abs(i-4)),
               (.074,.072,.059 if manager else .066),hair,head)
        o.rotation_euler.y=-.23
    if manager:
        oval("Bun",(0,.187,.11),(.137,.105,.133),hair,head)
    else:
        for side in (-1,1):
            oval("Sideburn",(side*.181,-.03,.057),(.027,.048,.074),hair,head)
    eyes=[]
    for side in (-1,1):
        e=empty("Eye",(side*.080,-.152,.045),head)
        e.rotation_euler.z=side*.26
        eyes.append(e)
        oval("Sclera",(0,-.006,0),(.050,.020,.026),"F4EBD7",e)
        oval("Iris",(0,-.024,-.001),(.022,.007,.022),"4F5142",e)
        oval("Pupil",(0,-.030,-.001),(.011,.004,.016),"262D2D",e)
        oval("Catchlight",(-.006,-.034,.008),(.004,.002,.004),"FFF4D7",e)
        brow=oval("Brow",(side*.081,-.152,.103),(.055,.019,.013),hair,head)
        brow.rotation_euler.y=side*.09
        if manager:
            pts=[(side*.083+.062*math.cos(j*math.tau/16),-.181+side*.014*math.cos(j*math.tau/16),
                  .043+.051*math.sin(j*math.tau/16)) for j in range(16)]
            for j in range(16):
                bar("Spectacles",pts[j],pts[(j+1)%16],.0050,BRASS,head)
            bar("Glasses temple",(side*.143,-.166,.05),(side*.201,.005,.053),.005,BRASS,head)
    if manager:
        bar("Glasses bridge",(-.023,-.198,.052),(.023,-.198,.052),.005,BRASS,head)
    mouth=empty("Mouth",(0,-.156,-.104),head)
    oval("Lips",(0,-.006,0),(1,.013,1),"AC6857" if not manager else "8E4A43",mouth)
    oval("Oral cavity",(0,-.015,.025),(.89,.008,.78),"543635",mouth)
    teeth=oval("Upper teeth",(0,-.022,.41),(.63,.005,.135),"E9D8BC",mouth)
    if not manager:
        for side in (-1,1):
            o=oval("Moustache",(side*.027,-.175,-.061),(.035,.012,.010),hair,head)
            o.rotation_euler.y=side*.11
    arms,legs=[],[]
    for side in (-1,1):
        a=[cyl("Upper sleeve",(0,0,0),1,1,coat,body),cyl("Lower sleeve",(0,0,0),1,1,coat,body),
           oval("Elbow",(0,0,0),(.072,.070,.071),coat,body),
           oval("Hand",(0,0,0),(.052,.050,.074),skin_light,body)]
        arms.append(a)
        l=[cyl("Thigh",(0,0,0),1,1,"354951" if manager else "475663",hips),
           cyl("Shin",(0,0,0),1,1,"354951" if manager else "475663",hips),
           oval("Knee",(0,0,0),(.082,.08,.08),"354951" if manager else "475663",hips),
           oval("Boot",(0,0,0),(.092,.158,.067),"463936",hips)]
        legs.append(l)
    return dict(root=root,hips=hips,body=body,head=head,eyes=eyes,mouth=mouth,teeth=teeth,arms=arms,legs=legs)


def camera(name, pos, target, lens):
    cam=bpy.data.cameras.new(name)
    o=bpy.data.objects.new(name,cam)
    bpy.context.collection.objects.link(o)
    o.location=pos
    o.rotation_euler=(Vector(target)-Vector(pos)).to_track_quat('-Z','Y').to_euler()
    cam.lens=lens
    cam.clip_start=.04
    return o
