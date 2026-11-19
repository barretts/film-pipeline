"""The seven beats of Snow, authored as continuous stage coordinates at 24 fps."""
from math import sin, pi, radians, cos
from bisect import bisect_right
from mathutils import Vector, Quaternion
from cast import rz
from stage_art import HINGE, LEVER_BASE, LEVER_Y, LEVER_R, BUTTON

def ease(t):return t*t*(3-2*t)
def curve(f,points,smooth=True):
    i=bisect_right([p[0] for p in points],f)-1
    if i<0:return points[0][1:]
    if i>=len(points)-1:return points[-1][1:]
    a,b=points[i:i+2];t=(f-a[0])/(b[0]-a[0])
    if smooth:t=ease(t)
    return tuple(u+(v-u)*t for u,v in zip(a[1:],b[1:]))

def scalar(f,pts):return curve(f,pts)[0]
def weight(f,a,b):return ease(max(0,min(1,(f-a)/(b-a))))
def mix(a,b,t):return Vector(a).lerp(Vector(b),t)

HINGE_KEYS=[(1,0),(535,0),(549,13),(566,44),(580,66),(596,70),(612,68.5),(840,68.5)]
LEVER_KEYS=[(1,0),(523,0),(534,24),(568,24),(578,12),(586,0),(840,0)]
PTT_KEYS=[(1,0),(743,0),(747,.0065),(820,.0065),(826,0),(840,0)]
GAP_KEYS=[(465,.25),(488,.12),(500,.0254),(512,.0254),(522,0),(571,0),(580,.035),(600,.17)]
def latch(f):
    a=scalar(f,HINGE_KEYS);b=scalar(f,LEVER_KEYS)
    q=rz(a);pitch=Quaternion((0,1,0),radians(b))
    wrap=weight(f,522,537)*(1-weight(f,573,584))
    phi=radians(150)*wrap
    contact=Vector(HINGE)+q@(Vector(LEVER_BASE)+pitch@Vector((.134,LEVER_Y-LEVER_R*cos(phi),LEVER_R*sin(phi))))
    normal=q@Vector((0,-1,0))
    return contact,normal,q

def props(f,hinge,lever,button):
    hinge.rotation_euler.z=radians(scalar(f,HINGE_KEYS))
    lever.rotation_euler.y=radians(scalar(f,LEVER_KEYS))
    button.location.z=BUTTON[2]-scalar(f,PTT_KEYS)
    for o,p in [(hinge,'rotation_euler'),(lever,'rotation_euler'),(button,'location')]:
        o.keyframe_insert(data_path=p,frame=f)

# Actor crosses the reverse cut on an existing footfall. Each line in FEET describes one
# particular support change in this room. Unlisted intervals retain the previous footprint.
ROOT=[(1,-.24,.32,-.014),(327,-.24,.32,-.014),(361,-.23,.33,-.011),
      (402,-.21,.34,-.013),(413,-.15,.37,-.023),(438,.25,.53,-.018),
      (460,.64,.68,-.019),(480,1.00,.88,-.022),(495,1.23,1.04,-.027),
      (510,1.36,1.155,-.045),(522,1.38,1.165,-.050),(538,1.40,1.14,-.054),
      (551,1.54,.98,-.058),(565,1.83,.66,-.058),(580,2.17,.49,-.054),
      (588,2.20,.50,-.050),(601,2.11,.60,-.041),(620,1.94,1.03,-.023)]
FACING=[(1,-22),(186,-22),(226,-37),(256,-29),(288,22),(350,34),(380,-34),
        (398,-29),(416,64),(432,109),(476,126),(500,157),(521,165),
        (545,172),(564,182),(581,201),(596,208),(620,197)]
FEET={
 'r':((-.37,.34,-25),[(403,417,.055,.35,65),(431,452,.58,.58,111),
      (462,485,1.14,.82,128),(491,509,1.49,1.13,161),(541,559,1.86,.77,174),
      (560,580,2.37,.49,197),(593,615,2.17,.96,199)]),
 'l':((-.10,.29,-18),[(413,435,.24,.65,104),(446,467,.72,.87,117),
      (477,500,1.20,1.16,150),(535,550,1.30,.97,164),(551,570,1.72,.56,183),
      (575,592,2.00,.46,208),(598,622,1.84,1.16,194)])}
def planted(side,f,ankle_z):
    last,steps=FEET[side]
    for start,end,x,y,yaw in steps:
        if f<start:break
        if f<=end:
            t=(f-start)/(end-start);s=ease(t)
            dest=(x,y,yaw);px,py,h=[m+(n-m)*s for m,n in zip(last,dest)]
            clearance=.078 if end-start>18 else .048
            return (px,py,ankle_z+clearance*sin(pi*t)**1.2),h,9*sin(2*pi*t)
        last=(x,y,yaw)
    return (last[0],last[1],ankle_z),last[2],0

KATE_BEATS=[
 (1,7,-3,14,-12,1),(23,8,-4,15,-14,1),(40,5,-1,6,-8,0),
 (72,3,3,-3,8,-1),(113,3,4,-4,9,-1),(136,2,2,-7,6,-1),
 (157,1,-3,-5,-14,0),(183,4,-6,-1,-19,1),(203,2,-5,-4,-15,0),
 (242,3,-3,2,-4,0),(254,1,0,-8,14,-1),(264,4,3,-2,8,-1),
 (273,0,5,-7,19,-1),(297,2,8,-4,30,0),(351,3,7,-4,22,0),
 (395,4,4,-1,10,0),(476,7,0,7,-9,1),(515,8,0,10,-11,1),
 (545,3,3,-7,10,-1),(583,0,10,-7,29,-1),(615,-2,13,-8,38,-2),
 (647,1,12,-5,36,-1),(683,2,11,-4,30,0),(708,3,3,0,13,0),
 (728,7,-1,8,-8,0),(745,17,-3,6,-5,0),(761,27,-3,-23,-3,0),
 (787,29,-2,-26,-3,0),(816,28,-2,-24,-2,0),(840,21,-2,-18,-2,0)]
JAMES_BEATS=[
 (1,0,0,1,-6,0),(40,1,-4,2,-9,0),(86,2,-6,-2,-17,0),
 (151,1,-6,-2,-18,0),(206,0,-11,-2,-21,0),(245,2,-6,1,-14,0),
 (254,-2,7,-5,19,-2),(274,1,14,-4,33,-1),(315,3,16,-3,42,0),
 (358,2,13,-4,31,0),(375,1,-10,0,-23,0),(399,2,-8,-3,-14,0),
 (420,8,6,1,14,0),(446,5,7,-1,13,2),(475,6,-4,4,4,-1),
 (495,13,2,12,3,2),(504,18,9,12,0,2),(512,18,9,11,-6,2),
 (523,20,11,13,1,2),(541,17,9,13,0,2),(561,12,4,9,6,0),
 (580,9,-3,5,-4,-2),(596,7,-7,-3,-12,0),(620,9,-3,-1,-7,0)]

def kate_pose(k,f):
    k.root((-2.03,.49,-.35),84,f)
    lean,tw,hp,ht,roll=curve(f,KATE_BEATS)
    breath=sin(f*.046)*.45
    k.upper(lean+breath,tw,hp,ht,roll,f)
    for side,sg in [('r',-1),('l',1)]:
        z=k.rest('foot_'+side).head_local.z+.005
        k.ankle(side,(-1.66 if side=='r' else -1.70,.49+sg*.146,z),86+sg*10,0,
                k.local((sg*.19,-.76,.72)),f)
    activation=weight(f,724,744)*(1-weight(f,821,837))
    r=Vector(( -1.57,.239,.826+breath*.002))
    r+=Vector(curve(f,[(1,0,0,0),(125,0,0,0),(155,-.045,-.012,.045),(188,-.070,-.025,.086),(216,-.037,-.009,.042),
                        (253,0,0,.006),(274,-.026,-.010,.057),(321,-.019,0,.025),(365,0,0,0),(725,0,0,0)]))
    top=Vector((BUTTON[0],BUTTON[1],BUTTON[2]+.0095-scalar(f,PTT_KEYS)))
    r=mix(r,top,activation)
    k.hand('r',r,mix((.95,.17,-.28),(.86,.21,-.49),activation),(0,0,1),
           (-1.97,.10,.82),f)
    l=Vector((-1.58,.735,.820))
    l+=Vector(curve(f,[(1,0,0,0),(74,.026,.002,.025),(136,0,0,.006),(180,-.034,.011,.035),
                       (237,0,0,.006),(273,-.044,.014,.042),(330,-.024,.014,.026),(534,0,0,0),
                       (616,-.058,.012,.030),(680,-.067,.014,.035),(750,.005,.003,.001),(840,.019,.008,.001)]))
    k.hand('l',l,(.93,-.12,-.32),(0,0,1),(-2.0,.89,.81),f)
    lift=weight(f,134,165)*(1-weight(f,188,222))
    for side,sg in [('l',1),('r',-1)]:
        for finger,amount in [('index',5),('ring',12),('pinky',17),('thumb',-5)]:
            for seg in ('01','02'):
                k.tilt(finger+'_'+seg+'_'+side,0,sg*(amount+4*lift),0,f)

def james_pose(j,f):
    pos=Vector(curve(f,ROOT,False));yaw=scalar(f,FACING)
    stride=sin((f-410)*pi/15)
    moving=weight(f,401,416)*(1-weight(f,488,505))
    pos.z+=.015*stride**2*moving
    j.root(pos,yaw,f)
    lean,tw,hp,ht,roll=curve(f,JAMES_BEATS)
    j.upper(lean+.6*sin(f*.047),tw,hp,ht,roll+.9*stride*moving,f)
    for side,sg in [('r',-1),('l',1)]:
        ankle,y,p=planted(side,f,j.rest('foot_'+side).head_local.z+.006)
        j.ankle(side,ankle,y,p,j.local((sg*.17,-.85,.73)),f)
    attach=weight(f,463,500)*(1-weight(f,575,598))
    contact,n,q=latch(f)
    target=contact+n*scalar(f,GAP_KEYS)
    wrap=weight(f,522,537)*(1-weight(f,573,584))
    offset=j.fingers('r',.17+.78*wrap,wrap,f)
    for side,sg in [('r',-1),('l',1)]:
        swing=-sg*stride*.17*moving
        location=Vector((sg*.27,-.076+swing,.796+.02*moving))
        if side=='r':
            gesture=weight(f,353,374)*(1-weight(f,396,419))
            location+=Vector((-.045,-.18,.22))*gesture
        point=j.local(location)
        axis=j.rot@Vector((sg*.06,-.16,-.985))
        back=j.rot@Vector((sg*.94,-.28,.04))
        if side=='r':
            point=mix(point,target,attach)
            axis=mix(axis,q@mix((.12,.96,-.29),(.12,.99,.07),wrap),attach)
            back=mix(back,q@Vector((0,.20,.98)),attach)
        pole=j.local((sg*.39,.23,1.03))
        if side=='r':
            pole=mix(pole,j.local((-.41,.26,1.10)),attach)
        j.hand(side,point,axis,back,pole,f,offset if side=='r' else None)

def author(k,j,stage):
    hinge,lever,grip,button=stage
    # The exact beats and contact boundaries are selectable keys, including both sides of cuts.
    frames=set(range(1,841,4))|{840}
    for pts in (ROOT,FACING,KATE_BEATS,JAMES_BEATS,HINGE_KEYS,LEVER_KEYS,PTT_KEYS,GAP_KEYS):
        frames.update(p[0] for p in pts)
    for _,steps in FEET.values():
        for a,b,*_ in steps:frames.update((a,b))
    for start in (121,241,361,481,601,721):frames.update((start-1,start))
    for a,b in ((496,529),(535,582),(740,749)):frames.update(range(a,b+1))
    for f in sorted(frames):
        props(f,hinge,lever,button);kate_pose(k,f);james_pose(j,f)
    import bpy
    bpy.context.scene.frame_set(1)
    k.calibrate();j.calibrate()
    for ob in j.visible:
        for f,hidden in [(1,False),(600,False),(601,True),(840,True)]:
            ob.hide_render=hidden;ob.keyframe_insert(data_path='hide_render',frame=f)
            ob.hide_viewport=hidden;ob.keyframe_insert(data_path='hide_viewport',frame=f)
    bpy.context.scene.frame_set(1)
