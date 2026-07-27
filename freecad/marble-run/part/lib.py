"""marble-run part — shared library: parameters + Part/CSG helpers.

Parameters are reverse-engineered from shuckc/quadri-plot (validated). Fit-critical
rows are flagged MEASURE — confirm on a real set before a full print batch.
Helpers build the block features every piece shares (chamfered body, stud, socket).
"""

import FreeCAD as App
import Part

# ---------------- parameters ----------------
SIDE = 44.0  # cube footprint (quadri-plot side=44)
HEIGHT = 44.0  # block height -- MEASURE (quadri-plot uses 60)
CHAMFER = 2.0  # vertical-edge bevel
BORE_D = 19.0  # marble channel Ø
STUD_D = 29.0  # bottom registration boss Ø
STUD_H = 8.0  # stud height -- MEASURE
STACK_CLEAR = 1.0  # radial stud<->socket gap
SOCKET_D = STUD_D + 2 * STACK_CLEAR  # 31
SOCKET_DEPTH = STUD_H + 0.5  # 8.5
MINI_H = 12.0  # thin landing connector height
FUNNEL_TOP_D = 34.0  # connector catch-bowl mouth Ø
FUNNEL_DEPTH = 8.0


# ---------------- helpers ----------------
def chamfered_body(side, height, chamfer):
    """Square prism centred on X/Y, base at z=0, with its 4 vertical edges chamfered."""
    b = Part.makeBox(side, side, height, App.Vector(-side / 2, -side / 2, 0))
    if chamfer > 0:
        vedges = [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6]
        b = b.makeChamfer(chamfer, vedges)
    return b


def z_cyl(d, z0, z1, x=0.0, y=0.0):
    """Vertical cylinder of diameter d spanning z0..z1 (axis +Z)."""
    return Part.makeCylinder(d / 2, z1 - z0, App.Vector(x, y, z0))


def block_base(height):
    """Common block body: chamfered prism + bottom stud + top socket/dish (no channel)."""
    body = chamfered_body(SIDE, height, CHAMFER)
    stud = Part.makeCylinder(STUD_D / 2, STUD_H, App.Vector(0, 0, -STUD_H))
    shape = body.fuse(stud)
    socket = Part.makeCylinder(
        SOCKET_D / 2, SOCKET_DEPTH, App.Vector(0, 0, height - SOCKET_DEPTH)
    )
    return shape.cut(socket)
