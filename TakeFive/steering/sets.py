"""Build each named location once. Marks and prop geometry share the same local coordinates."""
import math
from mathutils import Vector
from takefive import stage


def build(name, spec, offset):
    root = stage.empty(name, (offset,0,0))
    sign = -1 if spec["door_side"]=="left" else 1
    outdoor = spec["kind"] in ("street","snow_exterior")
    snowy = spec["kind"] in ("radio_room","snow_exterior")
    door_x, work_x = 1.65*sign, -1.32*sign
    def box(label, pos, size, color, parent=root):
        return stage.box(name+" / "+label, pos, size, color, parent)
    def oval(label, pos, size, color):
        return stage.oval(name+" / "+label, pos, size, color, root)
    def wall_section(left, right, z, height):
        box("Wall", ((left+right)/2,1.74,z), (right-left,.18,height), "83979D" if snowy else "C4BBAA")
    box("Ground", (0,0,-.08), (17,14,.16), "C5D2D6" if spec["kind"]=="snow_exterior" else "858785")
    # A physical gap behind the animated leaf allows a person to cross the threshold.
    wall_section(-6,door_x-.67,1.8,3.6)
    wall_section(door_x+.67,6,1.8,3.6)
    wall_section(door_x-.67,door_x+.67,2.98,1.24)
    for side in (-1,1):
        box("Door casing", (door_x+side*.663,1.61,1.17), (.086,.18,2.34), "46545B")
    box("Door casing", (door_x,1.61,2.34), (1.41,.18,.10), "46545B")
    pivot = stage.empty(name+" / Door hinge",(door_x+sign*.62,1.66,0),root)
    box("Door leaf",(-sign*.62,0,1.14),(1.24,.10,2.28),spec["door_hex"],pivot)
    for y in (-.065,.065):
        box("Door glazing",(-sign*.62,y,1.66),(.50,.045,.49),"BDD3D5",pivot)
        box("Door handle",(-sign*1.07,1.5*y,.99),(.19,.08,.04),"D1BD87",pivot)
    box("Beyond the doorway",(door_x,4.70,1.30),(8,.15,3.20),"CEDBDE" if snowy else "A9B9B7")
    wx = work_x
    box("Window surround",(wx,1.60,1.80),(1.99,.13,1.03),"465961")
    box("Daylight window",(wx,1.49,1.80),(1.84,.055,.88),"C8E0DF")
    box("Mullion",(wx,1.44,1.80),(.055,.06,.91),"64787A")
    if outdoor:
        box("Pavement",(0,-.25,-.010),(13,3.8,.04),"DFE6E7" if snowy else "A4A19A")
        box("Curb",(0,-2.10,-.01),(13,.13,.11),"CCD6D4")
        for x in (-3.4,3.4):
            box("Downpipe",(x,1.55,1.52),(.10,.10,3.04),"586A70")
        if snowy:
            for i in range(7):
                oval("Snowbank",(-3.8+i*1.28,1.33,.04),(.80,.26,.18),"DBE6E5")
    else:
        wall = "899FA5" if snowy else "C6BDAC"
        for side in (-1,1):
            box("Side wall",(side*5.94,-2.52,1.80),(.17,8.7,3.6),wall)
        box("Reverse wall",(0,-6.84,1.80),(12,.17,3.60),wall)
        box("Ceiling",(0,-2.50,3.64),(12,8.85,.13),"C5CAC5")
        box("Reverse wall trim",(0,-6.72,.81),(12,.07,.075),"748687" if snowy else "A69983")
        box("Notice board",(1.2,-6.7,1.58),(1.45,.10,.70),"667575")
        for x,z in ((.78,1.65),(1.13,1.53),(1.52,1.62)):
            box("Notice",(x,-6.63,z),(.23,.015,.31),"D5CDAD")
        color = "576A73" if snowy else "8E694E"
        box("Worktop",(wx,.36,.81),(1.72,.66,.095),color)
        for x in (-.73,.73):
            box("Desk support",(wx+x,.37,.39),(.10,.58,.78),"5B6363")
        box("Desk apron",(wx,.085,.59),(1.59,.075,.35),color)
        box("Seat",(wx,.94,.43),(.43,.44,.07),"49575C")
        box("Seat back",(wx,1.13,.76),(.42,.075,.65),"49575C")
        for x in (-.16,.16):
            for y in (-.15,.15):
                box("Chair leg",(wx+x,.94+y,.21),(.044,.044,.42),"4B5456")
        box("Cabinet",(3.18*-sign,1.25,.81),(.67,.47,1.62),"7E8987")
        if spec["kind"]=="radio_room":
            box("Transceiver",(wx+.24,.37,.98),(.57,.32,.25),"374348")
            box("Radio display",(wx+.24,.197,1.00),(.28,.025,.095),"7DA598")
            stage.bar("Microphone stem",(wx-.37,.33,.85),(wx-.23,.25,1.35),.021,"3F4847",root)
            oval("Microphone",(wx-.22,.24,1.41),(.062,.056,.083),"384546")
        else:
            box("Desk blotter",(wx-.20,.33,.872),(.58,.39,.012),"3E5359")
            box("Documents",(wx+.34,.39,.887),(.31,.24,.035),"E1D8BB")
    marks = {"door":(door_x,1.04,0),"outside":(door_x,2.27,0),"visitor":(wx*.44,-.38,0),
             "staff":(wx,.93,0),"work":(wx,-.21,0),"center":(0,-.23,0),"left":(-2,-.17,0),
             "right":(2,-.17,0),"far":(-sign*2.12,-.48,0)}
    if outdoor:
        marks.update(door=(door_x,.80,0),outside=(door_x,.69,0))
    for key, xyz in marks.items():
        marker = stage.empty(name+" / "+key, xyz, root)
        marker.empty_display_type = "PLAIN_AXES"
    props = {"microphone":Vector((offset+wx-.22,.24,1.41))} if spec["kind"]=="radio_room" else {}
    return {"root":root,"hinge":pivot,"sign":sign,"exterior":outdoor,"props":props,
            "marks":{k:Vector((x+offset,y,z)) for k,(x,y,z) in marks.items()},"offset":offset}
