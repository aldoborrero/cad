"""block-turn (yellow) — marble enters top, turns 90 deg, exits the +X side face."""

import FreeCAD as App
import Part

import lib

NAME = "block-turn"


def build():
    s = lib.block_base(lib.HEIGHT)
    zmid = lib.HEIGHT * 0.45  # side-exit centre-line
    z1 = lib.HEIGHT - lib.SOCKET_DEPTH
    vbore = lib.z_cyl(lib.BORE_D, zmid, z1)  # vertical drop from the dish
    hbore = Part.makeCylinder(  # horizontal run out to the +X face
        lib.BORE_D / 2,
        lib.SIDE / 2 + lib.CHAMFER + 1,
        App.Vector(0, 0, zmid),
        App.Vector(1, 0, 0),
    )
    return s.cut(vbore.fuse(hbore)).removeSplitter()
