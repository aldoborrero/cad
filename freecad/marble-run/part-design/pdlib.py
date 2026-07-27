"""marble-run part-design — Part Design helpers (FreeCAD 1.1 API).

Thin wrappers over FreeCAD 1.1's PartDesign/Sketcher Python API so the piece
builders read cleanly. Every piece is a PartDesign Body whose features
(Pad/Pocket) are driven by attached sketches — an editable tree, not a CSG result.

API notes (FreeCAD 1.1.1):
  - Sketch attachment uses `AttachmentSupport` (renamed from `Support` in 1.0)
    + `MapMode = 'FlatFace'` + `AttachmentOffset`.
  - Origin datum planes: body.Origin.OriginFeatures — order is
    [X_Axis, Y_Axis, Z_Axis, XY_Plane, XZ_Plane, YZ_Plane, Origin].
  - Solid features must be chained: feature.BaseFeature = previous tip, and
    body.Tip = feature. `newObject` alone does not always do this in script.
"""

import FreeCAD as App
import Part
import Sketcher

_PLANE_INDEX = {"XY": 3, "XZ": 4, "YZ": 5}


def origin_plane(body, key):
    """The body's local datum plane 'XY' | 'XZ' | 'YZ' (robust to name/order)."""
    for f in body.Origin.OriginFeatures:
        if key in getattr(f, "Label", "") or key in getattr(f, "Name", ""):
            return f
    return body.Origin.OriginFeatures[_PLANE_INDEX[key]]  # fallback: conventional order


def _chain(body, feat):
    """Chain a solid feature onto the body tip (BaseFeature) and advance the tip."""
    if getattr(body, "Tip", None) is not None:
        feat.BaseFeature = body.Tip
    body.Tip = feat
    return feat


def new_sketch(body, name, support, offset_z=0.0):
    """A sketch flat-attached to `support`, optionally offset along its normal."""
    sk = body.newObject("Sketcher::SketchObject", name)
    sk.AttachmentSupport = [(support, "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = App.Placement(App.Vector(0, 0, offset_z), App.Rotation())
    return sk


def sk_circle(sk, r):
    """Circle centred on the sketch origin, radius-constrained."""
    sk.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), r), False)
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    sk.addConstraint(Sketcher.Constraint("Radius", 0, r))


def sk_circle_at(sk, u, v, r):
    """Circle at sketch-local (u, v), radius-constrained (position left free)."""
    sk.addGeometry(Part.Circle(App.Vector(u, v, 0), App.Vector(0, 0, 1), r), False)
    sk.addConstraint(Sketcher.Constraint("Radius", 0, r))


def sk_polygon(sk, pts):
    """Closed polygon from (x, y) list; endpoints coincident-constrained."""
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
