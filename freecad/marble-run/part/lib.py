"""marble-run part — shared library: parameters + Part/CSG helpers.

Parameters are reverse-engineered from shuckc/quadri-plot (validated). Fit-critical
rows are flagged MEASURE — confirm on a real set before a full print batch.
Helpers build the block features every piece shares (chamfered body, stud, socket).
"""

import FreeCAD as App
import Part

# ---------------- parameters ----------------
SIDE = 44.0  # cube footprint width (measured with calipers)
HEIGHT = 60.0  # block height (measured: 60 mm; matches quadri-plot)
CHAMFER = 2.0  # vertical-edge bevel
BORE_D = 20.0  # marble tunnel Ø (measured: 20 mm)
STUD_D = 28.0  # bottom registration boss Ø (fits a 30 socket with ~1 mm/side)
STUD_H = 8.0  # stud height -- MEASURE
STACK_CLEAR = 1.0  # radial stud<->socket gap
SOCKET_D = STUD_D + 2 * STACK_CLEAR  # 30 (measured top dish Ø)
SOCKET_DEPTH = STUD_H + 0.5  # 8.5
MINI_H = 12.0  # thin landing connector height (measured, excl. stud)


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


# ---------------- channel geometry (faithful port of quadri-plot) ----------------
# A TopEntry bore drops the marble from the dish to the CENTRE pivot; an ExitPart
# (sphere pivot + bore) then carries it out — straight, tilted, low, or bottom.
CENTER = HEIGHT / 2  # channel pivot (quadri-plot: 30)
LOWEXIT = -STUD_H - 2  # a bore starts just below the stud
LOW = 6  # height of the low across/back crossings

_O = App.Vector(0, 0, 0)
_X = App.Vector(1, 0, 0)
_Y = App.Vector(0, 1, 0)
_Z = App.Vector(0, 0, 1)


def ch_top():
    """TopEntry bore: from the centre pivot up to the top (meets the socket dish)."""
    return z_cyl(BORE_D, CENTER, HEIGHT + 0.05)


def ch_exit():
    """ExitPart: sphere pivot at the centre + bore from below the stud to the centre."""
    sph = Part.makeSphere(BORE_D / 2, App.Vector(0, 0, CENTER))
    return sph.fuse(z_cyl(BORE_D, LOWEXIT, CENTER))


def ex_vertical():
    """Straight vertical exit (orange)."""
    return ch_exit()


def ex_side(theta=60, ang=0):
    """Side exit tilted theta from vertical, azimuth ang (pivot at the centre)."""
    m = ch_exit()
    m.translate(App.Vector(0, 0, -CENTER))
    m.rotate(_O, _X, theta)
    m.rotate(_O, _Z, -90)
    m.translate(App.Vector(0, 0, CENTER))
    if ang:
        m.rotate(_O, _Z, ang)
    return m


def ex_across():
    """Low horizontal through-bore across both faces."""
    c = Part.makeCylinder(BORE_D / 2, SIDE + 8, App.Vector(0, 0, -(SIDE + 8) / 2))
    c.rotate(_O, _X, 90)
    c.rotate(_O, _Y, 90)
    c.translate(App.Vector(0, 0, LOW))
    return c


def ex_back():
    """Low horizontal bore out one side (back)."""
    c = Part.makeCylinder(BORE_D / 2, SIDE / 2 + 4, App.Vector(0, 0, -(SIDE / 2 + 4)))
    c.rotate(_O, _Y, 90)
    c.translate(App.Vector(0, 0, LOW))
    return c


def ex_bottom():
    """Bottom exit: ExitPart lowered so its pivot sits near the bottom."""
    m = ch_exit()
    m.translate(App.Vector(0, 0, LOW - CENTER))
    return m


def carve(height, *cutters):
    """A base block of the given height with the given channel cutters removed."""
    cut = cutters[0]
    for c in cutters[1:]:
        cut = cut.fuse(c)
    return block_base(height).cut(cut).removeSplitter()
