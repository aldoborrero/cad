"""connector-funnel (purple) — thin landing connector: conical bowl -> bore + stud."""

import FreeCAD as App
import Part

import lib

NAME = "connector-funnel"


def build():
    body = lib.chamfered_body(lib.SIDE, lib.MINI_H, lib.CHAMFER)
    stud = Part.makeCylinder(lib.STUD_D / 2, lib.STUD_H, App.Vector(0, 0, -lib.STUD_H))
    shape = body.fuse(stud)
    bowl = Part.makeCone(  # concave catch bowl narrowing to the bore
        lib.FUNNEL_TOP_D / 2,
        lib.BORE_D / 2,
        lib.FUNNEL_DEPTH,
        App.Vector(0, 0, lib.MINI_H - lib.FUNNEL_DEPTH),
    )
    bore = lib.z_cyl(lib.BORE_D, -lib.STUD_H, lib.MINI_H - lib.FUNNEL_DEPTH)
    return shape.cut(bowl).cut(bore).removeSplitter()
