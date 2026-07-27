"""marble-run part-design — shared library: parameters + Part Design helpers.

Same numbers as ../part/lib.py. Helpers wrap FreeCAD 1.1's PartDesign/Sketcher API
(AttachmentSupport + FlatFace, explicit BaseFeature/Tip chaining, Pad/Pocket) and
build the block features every piece shares (base_block = body + stud + socket).
"""

import FreeCAD as App
import Part
import Sketcher

# ---------------- parameters ----------------
SIDE = 44.0
HEIGHT = 44.0  # MEASURE (quadri-plot uses 60)
CHAMFER = 2.0
BORE_D = 19.0
STUD_D = 29.0
STUD_H = 8.0  # MEASURE
STACK_CLEAR = 1.0
SOCKET_D = STUD_D + 2 * STACK_CLEAR  # 31
SOCKET_DEPTH = STUD_H + 0.5  # 8.5
MINI_H = 12.0
FUNNEL_TOP_D = 34.0
FUNNEL_DEPTH = 8.0

_PLANE_INDEX = {"XY": 3, "XZ": 4, "YZ": 5}


# ---------------- sketch / feature helpers ----------------
def origin_plane(body, key):
    """The body's local datum plane 'XY' | 'XZ' | 'YZ' (robust to name/order)."""
    for f in body.Origin.OriginFeatures:
        if key in getattr(f, "Label", "") or key in getattr(f, "Name", ""):
            return f
    return body.Origin.OriginFeatures[_PLANE_INDEX[key]]


def _chain(body, feat):
    """Chain a solid feature onto the body tip (BaseFeature) and advance the tip."""
    if getattr(body, "Tip", None) is not None:
        feat.BaseFeature = body.Tip
    body.Tip = feat
    return feat


def new_sketch(body, name, support, offset_z=0.0):
    sk = body.newObject("Sketcher::SketchObject", name)
    sk.AttachmentSupport = [(support, "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = App.Placement(App.Vector(0, 0, offset_z), App.Rotation())
    return sk


def sk_circle(sk, r):
    sk.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), r), False)
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    sk.addConstraint(Sketcher.Constraint("Radius", 0, r))


def sk_circle_at(sk, u, v, r):
    sk.addGeometry(Part.Circle(App.Vector(u, v, 0), App.Vector(0, 0, 1), r), False)
    sk.addConstraint(Sketcher.Constraint("Radius", 0, r))


def sk_polygon(sk, pts):
    n = len(pts)
    for i in range(n):
        a = App.Vector(pts[i][0], pts[i][1], 0)
        b = App.Vector(pts[(i + 1) % n][0], pts[(i + 1) % n][1], 0)
        sk.addGeometry(Part.LineSegment(a, b), False)
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % n, 1))


def chamfered_square_pts(side, ch):
    """Octagon = square with its 4 corners cut by `ch` (chamfered vertical edges)."""
    h = side / 2.0
    return [
        (-h + ch, -h),
        (h - ch, -h),
        (h, -h + ch),
        (h, h - ch),
        (h - ch, h),
        (-h + ch, h),
        (-h, h - ch),
        (-h, -h + ch),
    ]


def pad(body, name, sketch, length, reversed=False, midplane=False):
    p = body.newObject("PartDesign::Pad", name)
    p.Profile = sketch
    p.Length = length
    p.Reversed = reversed
    p.Midplane = midplane
    return _chain(body, p)


def pocket(
    body,
    name,
    sketch,
    length=0.0,
    through=False,
    reversed=False,
    midplane=False,
    taper=0.0,
):
    p = body.newObject("PartDesign::Pocket", name)
    p.Profile = sketch
    if through:
        p.Type = "ThroughAll"
    else:
        p.Length = length
    p.Reversed = reversed
    p.Midplane = midplane
    if taper:
        p.TaperAngle = taper
    return _chain(body, p)


# ---------------- shared block body ----------------
def base_block(doc, height, name="Body"):
    """A new Body with chamfered-square pad + bottom stud + top socket (no channel)."""
    body = doc.addObject("PartDesign::Body", name)
    doc.recompute()
    xy = origin_plane(body, "XY")

    sb = new_sketch(body, "Sketch_body", xy)
    sk_polygon(sb, chamfered_square_pts(SIDE, CHAMFER))
    pad(body, "Body_pad", sb, height)
    doc.recompute()

    ss = new_sketch(body, "Sketch_stud", xy)
    sk_circle(ss, STUD_D / 2)
    pad(body, "Stud_pad", ss, STUD_H, reversed=True)
    doc.recompute()

    sk = new_sketch(body, "Sketch_socket", xy, offset_z=height)
    sk_circle(sk, SOCKET_D / 2)
    pocket(body, "Socket_pocket", sk, SOCKET_DEPTH)
    doc.recompute()
    return body
