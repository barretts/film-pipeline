"""Blank skinned actors, made-to-measure expedition clothing, and editable IK handles."""
from math import cos, sin, pi, radians
import bpy
from mathutils import Vector, Matrix, Quaternion, Euler
from stage_art import collection, move, objmesh, mat, empty

Z=Vector((0,0,1))
def rz(degrees):
    return Quaternion(Z,radians(degrees))

def frame_basis(axis, dorsal):
    a=Vector(axis).normalized()
    d=(Vector(dorsal)-a*a.dot(Vector(dorsal))).normalized()
    return Matrix((a,d.cross(a),d)).transposed().to_quaternion()

def import_blank(path):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path),bone_heuristic='TEMPERANCE')
    new=set(bpy.data.objects)-before
    return next(o for o in new if o.type=='ARMATURE'), [o for o in new if o.type=='MESH']

def skin(obj,arm,levels):
    obj.parent=arm
    groups={name:obj.vertex_groups.new(name=name) for z,name in levels}
    for v in obj.data.vertices:
        h=v.co.z
        if h<=levels[0][0]:
            groups[levels[0][1]].add([v.index],1,'REPLACE')
            continue
        for (lo,a),(hi,b) in zip(levels,levels[1:]):
            if h<=hi:
                t=(h-lo)/(hi-lo)
                groups[a].add([v.index],1-t,'REPLACE')
                groups[b].add([v.index],t,'REPLACE')
                break
        else:groups[levels[-1][1]].add([v.index],1,'REPLACE')
    mod=obj.modifiers.new("Expedition wear • body weights","ARMATURE");mod.object=arm
    for p in obj.data.polygons:p.use_smooth=True

class Actor:
    def __init__(self,name,assets):
        self.name=name
        self.col=collection(name+"  |  Cast and wardrobe")
        self.ctrl=collection(name+"  |  World-space animation controls")
        self.arm,self.visible=import_blank(assets/(name+"-body.glb"))
        self.body=max(self.visible,key=lambda o:len(o.data.vertices))
        self.arm.name=name+" / skeleton"
        for ob in [self.arm]+self.visible:move(ob,self.col)
        for ob in self.visible:ob.name=name+" / "+ob.name
        self.body.name=name+" / body and gloves"
        self.arm.data.display_type='STICK'
        self.arm.show_in_front=False
        self.arm.rotation_mode='XYZ'
        hair_pigment=mat(name+" / hair pigment",(.062,.031,.018) if name=='Kate' else (.135,.090,.057),.76)
        for obj in self.visible:
            if 'eyebrow' in obj.name.lower():
                obj.data.materials.clear();obj.data.materials.append(hair_pigment)
        scalp,meshes=import_blank(assets/(name+"-hair.glb"))
        correction=self.arm.data.bones['Head'].head_local-scalp.data.bones['Head'].head_local
        for obj in meshes:
            for v in obj.data.vertices:v.co+=correction
            obj.parent=self.arm
            for mod in obj.modifiers:
                if mod.type=='ARMATURE':mod.object=self.arm
            obj.name=name+" / hair"
            obj.data.materials.clear();obj.data.materials.append(hair_pigment)
            move(obj,self.col);self.visible.append(obj)
        bpy.data.objects.remove(scalp,do_unlink=True)
        self.dress()
        self.limbs={}
        self.tip={}
        self.tipi={}
        for side,sign in [('r',-1),('l',1)]:
            vertex=max(self.body.data.vertices,key=lambda v:sign*v.co.x)
            self.tipi[side]=vertex.index
            self.tip[side]=vertex.co-self.rest('hand_'+side).head_local
            for part,bone,tip in [('arm','lowerarm','hand'),('leg','calf','foot')]:
                goal=empty(name+' / '+part+' '+side+' • goal',(0,0,0),self.ctrl,display=.065)
                pole=empty(name+' / '+part+' '+side+' • bend',(0,0,0),self.ctrl,display=.045)
                goal.rotation_mode='QUATERNION'
                pb=self.arm.pose.bones[bone+'_'+side]
                ik=pb.constraints.new('IK');ik.name="Editable two-bone reach"
                ik.target=goal;ik.pole_target=pole;ik.chain_count=2;ik.use_stretch=False
                end=self.arm.pose.bones[tip+'_'+side]
                orient=end.constraints.new('COPY_ROTATION');orient.name="World orientation"
                orient.target=goal;orient.target_space='WORLD';orient.owner_space='WORLD'
                self.limbs[part+side]=(goal,pole,ik)
        self.body['right contact vertex']=self.tipi['r']
        self.body['left contact vertex']=self.tipi['l']

    def rest(self,n):return self.arm.data.bones[n]

    def dress(self):
        kate=self.name=='Kate'
        shell=mat(self.name+" / canvas",(.47,.132,.051) if kate else (.048,.173,.206),.89)
        yoke=mat(self.name+" / reinforced yoke",(.255,.071,.042) if kate else (.032,.091,.130),.91)
        cuff=mat(self.name+" / knit",(.080,.081,.067) if kate else (.046,.061,.063),.95)
        pants=mat(self.name+" / trousers",(.095,.107,.108) if kate else (.074,.089,.106),.98)
        boot=mat(self.name+" / boot leather",(.070,.052,.042),.60)
        glove=mat(self.name+" / glove",(.205,.133,.073) if not kate else (.26,.17,.092),.83)
        tape=mat(self.name+" / safety tape",(.69,.62,.40),.64)
        ms=self.body.data.materials
        for m in [shell,yoke,cuff,pants,boot,glove,tape]:ms.append(m)
        wrist=abs(self.rest('hand_r').head_local.x); shoulder=abs(self.rest('upperarm_r').head_local.x)
        height=self.rest('Head').head_local.z
        for p in self.body.data.polygons:
            x,y,z=p.center; a=abs(x)
            if z<.235: p.material_index=5
            elif z<.90: p.material_index=4
            elif a>wrist+.012 and z>1.23:p.material_index=0 if kate else 6
            elif a>wrist-.011 and z>1.23:p.material_index=3
            elif z<height-.07 or (a>shoulder*.75 and z<height-.035):p.material_index=1
        # Shaped padded jacket and a contrasting shoulder yoke, independent of the skin texture.
        s=.91 if kate else 1.0
        lift=-.031 if kate else 0
        rings=[(.810,.192,.151),(.835,.207,.160),(.925,.215,.173),(1.05,.209,.171),
               (1.20,.230,.186),(1.33,.253,.188),(1.403,.252,.172),(1.466,.203,.137),
               (1.500,.091,.089),(1.529,.084,.084)]
        rings=[(z+lift,x*s,y*s) for z,x,y in rings]
        # Bring the hidden torso inside the lining. This preserves original vertex indices
        # and weights while preventing the skin and jacket crossing under a spine bend.
        for v in self.body.data.vertices:
            x,y,z=v.co
            if .844+lift<z<1.47+lift and abs(x)<(.157 if kate else .181):
                v.co.y=.030+(y-.030)*.72
        count=40
        def pt(r,t):
            z,x,y=r
            return (x*sin(t),.030-y*cos(t),z)
        vs=[pt(r,2*pi*j/count) for r in rings for j in range(count)]
        fs=[(i*count+j,i*count+(j+1)%count,(i+1)*count+(j+1)%count,(i+1)*count+j) for i in range(len(rings)-1) for j in range(count)]
        fs.extend([tuple(reversed(range(count))),tuple((len(rings)-1)*count+j for j in range(count))])
        coat=objmesh(self.name+" / field jacket",vs,fs,shell,self.col)
        for m in (yoke,cuff,tape):coat.data.materials.append(m)
        for p in coat.data.polygons:
            ring=p.index//count
            if ring==0 or ring==8:p.material_index=2
            elif ring in (6,7):p.material_index=1
        levels=[(.85+lift,'pelvis'),(1.01+lift,'spine_01'),(1.21+lift,'spine_02'),(1.396+lift,'spine_03'),(1.58+lift,'neck_01')]
        skin(coat,self.arm,levels);self.visible.append(coat)
        def trim(name,rows,material):
            vs=[];fs=[]
            for z,x,depth,hw in rows:
                i=len(vs);vs.extend([(x-hw,depth,z),(x+hw,depth,z)])
                if i:fs.append((i-2,i-1,i+1,i))
            ob=objmesh(self.name+' / '+name,vs,fs,material,self.col);skin(ob,self.arm,levels);self.visible.append(ob)
        trim('zip',[(z,0,.027-y,.007) for z,x,y in rings],cuff)
        for side in (-1,1):
            trim('yoke piping',[(z,side*.11*s,.024-y*(1-(.11*s/x)**2)**.5,.021) for z,x,y in rings[4:7]],tape)
        for side,sg in [('r',-1),('l',1)]:
            bone=self.rest('hand_'+side)
            ax,cy,cz=bone.head_local
            cut=[(-.100,.053),(-.092,.053),(-.072,.050),(-.036,.046),(-.009,.040),(.008,.035),(.010,.024)]
            scale=.94 if kate else 1
            vs=[(ax+sg*u,cy+rad*scale*cos(j*2*pi/24),cz+rad*scale*.94*sin(j*2*pi/24))
                for u,rad in cut for j in range(24)]
            faces=[(r*24+j,r*24+(j+1)%24,(r+1)*24+(j+1)%24,(r+1)*24+j) for r in range(len(cut)-1) for j in range(24)]
            band=objmesh(self.name+' / sleeve cuff '+side,vs,faces,cuff,self.col)
            band.data.materials.append(tape);band.data.materials.append(shell)
            for p in band.data.polygons:
                p.use_smooth=True
                p.material_index=1 if p.index//24 in (1,2) else (2 if p.index//24==0 else 0)
            group=band.vertex_groups.new(name='lowerarm_'+side);group.add(list(range(len(vs))),1,'REPLACE')
            hand=band.vertex_groups.new(name='hand_'+side)
            for i,share in [(4,.12),(5,.30),(6,.34)]:
                ring=list(range(i*24,(i+1)*24));group.add(ring,1-share,'REPLACE');hand.add(ring,share,'REPLACE')
            band.parent=self.arm;mod=band.modifiers.new("Wrist weights","ARMATURE");mod.object=self.arm
            self.visible.append(band)
        for p in self.body.data.polygons:p.use_smooth=True

    def root(self,xyz,yaw,f):
        self.orig=Vector(xyz);self.yaw=yaw;self.rot=rz(yaw)
        self.arm.location=xyz;self.arm.rotation_euler=(0,0,radians(yaw))
        for prop in ('location','rotation_euler'):self.arm.keyframe_insert(data_path=prop,frame=f,group="Staging")

    def local(self,xyz):return self.orig+self.rot@Vector(xyz)

    def tilt(self,bone,lean,side,turn,f):
        p=self.arm.pose.bones[bone];rest=self.rest(bone).matrix_local.to_quaternion()
        rotation=Euler(tuple(map(radians,(lean,side,turn)))).to_quaternion()
        p.rotation_quaternion=rest.inverted()@rotation@rest
        p.keyframe_insert(data_path='rotation_quaternion',frame=f,group=bone)

    def upper(self,lean,twist,headpitch,headturn,roll,f):
        for b,w in [('spine_01',.30),('spine_02',.36),('spine_03',.34)]:self.tilt(b,lean*w,roll*w,twist*w,f)
        self.tilt('neck_01',headpitch*.30,0,headturn*.38,f)
        self.tilt('Head',headpitch*.70,0,headturn*.62,f)

    def goal(self,part,side,world,quat,pole,f):
        goal,bend,_=self.limbs[part+side]
        goal.location=world
        quat.make_compatible(goal.rotation_quaternion)
        goal.rotation_quaternion=quat;bend.location=pole
        goal.keyframe_insert(data_path='location',frame=f,group="Position")
        goal.keyframe_insert(data_path='rotation_quaternion',frame=f,group="Orientation")
        bend.keyframe_insert(data_path='location',frame=f)

    def hand(self,side,tip,axis,back,pole,f,offset=None):
        sign=-1 if side=='r' else 1
        delta=frame_basis(axis,back)@frame_basis((sign,0,0),(0,0,1)).inverted()
        wrist=Vector(tip)-delta@(self.tip[side] if offset is None else offset)
        q=delta@self.rest('hand_'+side).matrix_local.to_quaternion()
        self.goal('arm',side,wrist,q,pole,f)

    def ankle(self,side,where,yaw,pitch,pole,f):
        q=rz(yaw)@Quaternion((1,0,0),radians(pitch))@self.rest('foot_'+side).matrix_local.to_quaternion()
        self.goal('leg',side,where,q,pole,f)

    def fingers(self,side,load,wrap,f):
        s=-1 if side=='r' else 1
        # Every phalanx is keyed. The middle fingertip follows the surface from near to
        # far as the phalanges curl. Its posed offset also sets the position of the wrist.
        for finger,amount in [('index',27),('ring',31),('pinky',36),('thumb',-10)]:
            for segment in ('01','02','03'):
                bone= finger+'_'+segment+'_'+side
                splay=-22*wrap if finger=='thumb' and segment=='01' else 0
                if self.arm.pose.bones.get(bone):self.tilt(bone,0,s*amount*load,splay,f)
        sol=Matrix.Identity(4)
        for seg,angle in [('01',24),('02',35),('03',40)]:
            name='middle_'+seg+'_'+side
            p=self.rest(name).head_local
            deg=s*angle*wrap
            self.tilt(name,0,deg,0,f)
            sol=sol@Matrix.Translation(p)@Matrix.Rotation(radians(deg),4,'Y')@Matrix.Translation(-p)
        tip=self.body.data.vertices[self.tipi[side]].co
        return sol@tip-self.rest('hand_'+side).head_local

    def calibrate(self):
        dg=bpy.context.evaluated_depsgraph_get()
        for key,(goal,pole,ik) in self.limbs.items():
            part=key[:-1];side=key[-1]
            upper=('upperarm' if part=='arm' else 'thigh')+'_'+side
            lower=('lowerarm' if part=='arm' else 'calf')+'_'+side
            def direction():
                a=self.arm.evaluated_get(dg)
                start=a.matrix_world@a.pose.bones[upper].head
                joint=a.matrix_world@a.pose.bones[lower].head
                axis=(goal.location-start).normalized()
                e=joint-start;d=pole.location-start
                return (e-axis*axis.dot(e)).normalized().dot((d-axis*axis.dot(d)).normalized())
            best=(-2,0)
            for deg in range(-180,180,15):
                ik.pole_angle=radians(deg);bpy.context.view_layer.update()
                best=max(best,(direction(),deg))
            ik.pole_angle=radians(best[1]);bpy.context.view_layer.update()
