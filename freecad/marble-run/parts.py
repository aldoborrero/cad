"""marble-run — piece builders (FreeCAD Part / OCCT B-rep).

Each public builder returns a single `Part.Shape`. The orchestrator
(`marble-run.py`) calls them, then exports one STEP + STL per piece.

Coordinate convention (per block):
  - Body occupies z in [0, height]; X = Y = SIDE footprint, centred on origin.
  - Bottom registration stud protrudes DOWN, z in [-STUD_H, 0].
  - Top recess (socket / catch dish) is cut into the top face.
  - Marble travels along Ø BORE_D channels cut through the body.
"""

import FreeCAD as App
import Part

import params as P


# ---------- low-level helpers ----------
def _chamfered_body(side, height, chamfer):
    """A square prism centred on X/Y, base at z=0, with its 4 vertical edges chamfered."""
    b = Part.makeBox(side, side, height, App.Vector(-side / 2, -side / 2, 0))
    if chamfer > 0:
        vedges = [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6]
        b = b.makeChamfer(chamfer, vedges)
    return b


def _z_cyl(d, z0, z1, x=0.0, y=0.0):
    """Vertical cylinder of diameter d spanning z0..z1 (axis +Z)."""
    return Part.makeCylinder(d / 2, z1 - z0, App.Vector(x, y, z0))


def _block_base(height):
    """Common block body: chamfered prism + bottom stud + top socket/dish.

    No marble channel yet — the specific pieces cut their own.
    """
    body = _chamfered_body(P.SIDE, height, P.CHAMFER)
    stud = Part.makeCylinder(P.STUD_D / 2, P.STUD_H, App.Vector(0, 0, -P.STUD_H))
    shape = body.fuse(stud)
    socket = Part.makeCylinder(
        P.SOCKET_D / 2, P.SOCKET_DEPTH, App.Vector(0, 0, height - P.SOCKET_DEPTH)
    )
    return shape.cut(socket)


# ---------- pieces ----------
def marble():
    """Reference marble (for fit checks / assembly previews)."""
    return Part.makeSphere(P.MARBLE_D / 2)


def block_blank():
    """Plain building block: body + stud + socket, no marble path (spacer/tower)."""
    return _block_base(P.HEIGHT).removeSplitter()


def block_straight():
    """Orange: marble enters the top dish and drops straight through the bottom stud."""
    s = _block_base(P.HEIGHT)
    z1 = P.HEIGHT - P.SOCKET_DEPTH  # floor of the top socket
    bore = _z_cyl(P.BORE_D, -P.STUD_H, z1)  # through the stud, up to the socket
    return s.cut(bore).removeSplitter()


def block_turn():
    """Yellow: marble enters the top and turns 90 deg to exit the +X side face."""
    s = _block_base(P.HEIGHT)
    zmid = P.HEIGHT * 0.45  # centre-line of the side exit
    z1 = P.HEIGHT - P.SOCKET_DEPTH
    vbore = _z_cyl(P.BORE_D, zmid, z1)  # vertical drop from the dish
    hbore = Part.makeCylinder(  # horizontal run out to the +X face
        P.BORE_D / 2,
        P.SIDE / 2 + P.CHAMFER + 1,
        App.Vector(0, 0, zmid),
        App.Vector(1, 0, 0),
    )
    return s.cut(vbore.fuse(hbore)).removeSplitter()


def connector_funnel():
    """Purple: thin landing connector — conical catch bowl on top, through to a stud."""
    body = _chamfered_body(P.SIDE, P.MINI_H, P.CHAMFER)
    stud = Part.makeCylinder(P.STUD_D / 2, P.STUD_H, App.Vector(0, 0, -P.STUD_H))
    shape = body.fuse(stud)
    bowl = Part.makeCone(  # concave catch bowl narrowing to the bore
        P.FUNNEL_TOP_D / 2,
        P.BORE_D / 2,
        P.FUNNEL_DEPTH,
        App.Vector(0, 0, P.MINI_H - P.FUNNEL_DEPTH),
    )
    bore = _z_cyl(P.BORE_D, -P.STUD_H, P.MINI_H - P.FUNNEL_DEPTH)
    return shape.cut(bowl).cut(bore).removeSplitter()
