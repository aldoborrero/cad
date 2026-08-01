"""accelerator — the marble-run's red slope, as OCCT B-rep instead of stacked prisms.

A second construction of a piece that already exists in OpenSCAD
(`openscad/marble-run/ramps/accelerator.scad`), kept side by side the way `iotorero-mount`
is. It is here because this one piece is the only part of the set that fights OpenSCAD:

  - It is a LOFT. Its section changes shape along the length -- the plan tapers, the top and
    the cradle drop at 12.5 deg, the bullnose shrinks, the foot starts and stops -- and
    `linear_extrude` only scales one profile. OpenSCAD's answer is 200 stacked prisms, which
    leaves a 0.046 mm staircase and 178590 facets on a 4 cm3 part.
  - Its bullnose is a FILLET, and OpenSCAD has no edges to fillet. There it is faked as a 2D
    morphological opening applied section by section.

In B-rep both are primitives, and the piece stops being a sweep altogether: the cradle turns
out to be an oblique cylinder, the top and base are planes, and the bullnose is a real
variable-radius fillet. 21 faces before rounding.

The numbers are NOT copied. They are read out of lib.scad through OpenSCAD's own echo, the
same way sim/ does it -- a copied CAD dimension goes stale silently. The cost is that this
build needs openscad on PATH as well as FreeCAD; both are in the devshell.

Build:  cad export marble-run/ramps/accelerator
          ->  exports/accelerator.step + .stl
"""

import math
import os
import pathlib
import sys

import Part
from FreeCAD import Vector
import FreeCAD as App

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "openscad" / "marble-run" / "sim"))
from params import params  # noqa: E402

# ---------- the dimensions, read from lib.scad rather than copied ----------
P = params(
    L="ACC_L",
    w0="ACC_W0",
    w1="ACC_W1",
    ztop="ACC_ZTOP",
    zc="ACC_ZC",
    r="ACC_R",
    tilt="ACC_TILT",
    base="ACC_BASE",
    shell="ACC_SHELL",
    wall="ACC_WALL",
    foot_w="ACC_FOOT_W",
    foot_s="ACC_FOOT_S",
    foot_x0="ACC_FOOT_X0",
    foot_x1="ACC_FOOT_X1",
    lip="ACC_LIP",
)
L, W0, W1 = P["L"], P["w0"], P["w1"]
ZTOP, ZC, R = P["ztop"], P["zc"], P["r"]
TILT, BASE, SHELL, WALL = P["tilt"], P["base"], P["shell"], P["wall"]
FOOT_W, FOOT_S, FOOT_X0, FOOT_X1 = P["foot_w"], P["foot_s"], P["foot_x0"], P["foot_x1"]
LIP = P["lip"]

T = math.tan(math.radians(TILT))
R1, Y0 = W1 / 2, W0 / 2
CX = L - R1
BIG = 400.0
EPS = 1e-6

# Half-width of the cradle where it crosses the top plane. Constant, because the cradle axis
# and the top drop at the same rate: it is what makes the wall's top face a strip of varying
# width rather than a wedge, and what the entry-end fillet radius has to be clamped against.
WCR = math.sqrt(R * R - (ZC - ZTOP) ** 2)


def half_w(x):
    """lib.scad's acc_w(): a straight taper, then a round nose."""
    if x <= CX:
        return Y0 + (R1 - Y0) * x / CX
    return math.sqrt(max(0.0, R1 * R1 - (x - CX) ** 2))


def plan_face(inset=0.0):
    """The plan with its half-width reduced by `inset`.

    That is what lib.scad does: it subtracts from acc_w(), a shift in y, not a normal
    offset. So the inset nose is no longer a circle and has to be interpolated. The wire is
    built in order -- entry face, top edge out to where the two sides meet, mirror back.
    """
    xend = L if inset == 0 else CX + math.sqrt(max(0.0, R1 * R1 - inset * inset))
    n = 64
    nose = []
    for i in range(n + 1):
        x = CX + (xend - CX) * i / n
        nose.append(Vector(x, max(0.0, half_w(x) - inset), 0))
    nose[-1] = Vector(xend, 0, 0)  # the two sides meet exactly here
    a, a_m = Vector(0, Y0 - inset, 0), Vector(0, -(Y0 - inset), 0)

    top, bot = Part.BSplineCurve(), Part.BSplineCurve()
    top.interpolate(nose)
    bot.interpolate([Vector(v.x, -v.y, 0) for v in reversed(nose)])
    return Part.Face(
        Part.Wire(
            [
                Part.LineSegment(a, nose[0]).toShape(),
                top.toShape(),
                bot.toShape(),
                Part.LineSegment(Vector(nose[0].x, -nose[0].y, 0), a_m).toShape(),
                Part.LineSegment(a_m, a).toShape(),
            ]
        )
    )


def below_plane(z_at_0):
    """Everything under the plane z = z_at_0 - tan(TILT) * x."""
    p = [
        Vector(-BIG, -BIG, z_at_0 + T * BIG),
        Vector(BIG, -BIG, z_at_0 - T * BIG),
        Vector(BIG, -BIG, -BIG),
        Vector(-BIG, -BIG, -BIG),
    ]
    return Part.Face(Part.makePolygon(p + [p[0]])).extrude(Vector(0, 2 * BIG, 0))


def oblique_cylinder(r):
    """A circle in the YZ plane swept along the tilted axis.

    Every section at constant x is then a circle of radius r, which a plain tilted cylinder
    would NOT give -- that one cuts as an ellipse. lib.scad draws a circle per station, so
    this is the faithful surface and the reason the sweep disappears.
    """
    c = Part.Circle(Vector(-5, 0, ZC + T * 5), Vector(1, 0, 0), r)
    return Part.Face(Part.Wire([c.toShape()])).extrude(Vector(L + 10, 0, -T * (L + 10)))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def sharp():
    """The solid with every arris square -- lib.scad at ACC_LIP = 0."""
    outer = plan_face().extrude(Vector(0, 0, BIG))
    outer = outer.common(below_plane(ZTOP)).cut(box(-BIG, BIG, -BIG, BIG, -BIG, BASE))

    inner = plan_face(WALL).extrude(Vector(0, 0, BIG)).translate(Vector(0, 0, -BIG / 2))
    hollow = inner.common(below_plane(ZC)).cut(oblique_cylinder(R + SHELL))

    foot = box(FOOT_X0, FOOT_X1, -FOOT_W / 2, FOOT_W / 2, 0, BIG).common(
        below_plane(ZC)
    )

    s = outer.cut(hollow).fuse(foot)
    s = s.cut(oblique_cylinder(R))
    s = s.cut(box(FOOT_X0 - 1, FOOT_X1 + 1, -FOOT_S / 2, FOOT_S / 2, -1, BASE))
    return s.removeSplitter()


# ---------- the bullnose radius, clamped exactly as lib.scad's acc_lip() is ----------
def _wall_h(x):
    w, zc = half_w(x), ZC - T * x
    top = (zc - math.sqrt(max(0.0, R * R - w * w))) if w < R else (ZTOP - T * x)
    return top - BASE


def _floor_t(x):
    return (ZC - T * x) - R - BASE


def lip_at(x):
    """lib.scad's acc_lip(): rounding a feature by more than half its thickness erodes it
    away, so the radius is clamped by whichever of the wall and the floor is thinner."""
    return max(0.0, min(LIP, (_wall_h(x) - 0.4) / 2, (_floor_t(x) - 0.4) / 2))


def lip_top(x):
    """On the wall's top face there is a third limit lib.scad never had to state, because a
    2D opening cannot over-round: the strip is only half_w(x) - WCR wide, and it carries a
    fillet on BOTH sides. At the entry that is 1.87 mm, so two radii of 0.9 would consume
    it and drop the top face by 0.2 mm."""
    return max(0.02, min(lip_at(x), 0.45 * max(0.05, half_w(x) - WCR)))


def _on_top(p):
    return abs(p.z - (ZTOP - T * p.x)) < 1e-4


def _on_cradle(p):
    return abs(math.hypot(p.y, p.z - (ZC - T * p.x)) - R) < 1e-4


def build():
    """The finished piece: the sharp solid with its arrises rounded.

    Edges are picked by GEOMETRIC PREDICATE, not by index -- "the edges lying in the top
    plane", "the edges lying on the cradle". Index-based selection is what breaks when OCCT
    renumbers a rebuilt shape, which is the topological naming problem FreeCAD carries a
    dedicated test for; describing what an edge *is* survives it.
    """
    s = sharp()
    doc = App.newDocument("accelerator")
    feat = doc.addObject("Part::Feature", "sharp")
    feat.Shape = s
    doc.recompute()

    spec = []
    for i, e in enumerate(feat.Shape.Edges):
        n = 6
        ps = [
            e.valueAt(e.FirstParameter + (e.LastParameter - e.FirstParameter) * k / n)
            for k in range(n + 1)
        ]
        if all(abs(p.x) < EPS for p in ps):
            continue  # the entry face: lib.scad's 2D opening works inside a section, so it
            # can never round an arris that runs across one. Neither does this.
        if all(_on_top(p) for p in ps):
            spec.append((i + 1, lip_top(ps[0].x), lip_top(ps[-1].x)))
        elif all(_on_cradle(p) for p in ps) and max(p.x for p in ps) > 12:
            spec.append(
                (i + 1, max(0.02, lip_at(ps[0].x)), max(0.02, lip_at(ps[-1].x)))
            )

    # Part::Fillet, the document object, rather than shape.makeFillet(). makeFillet does
    # have a variable-radius overload -- makeFillet(r1, r2, edgeList) -- but it applies ONE
    # pair to the whole list, so a radius per edge means one call per edge, and chaining
    # those fails here on the very first one: StdFail_NotDone. Part::Fillet takes all eight
    # with their own radii in a single operation, where OCCT resolves the corners between
    # adjacent filleted edges together, and that succeeds. (PartDesign::Fillet is not an
    # option either way: its Radius is a single value.)
    fil = doc.addObject("Part::Fillet", "bullnose")
    fil.Base = feat
    fil.Edges = spec
    doc.recompute()
    return fil.Shape, len(spec)


shape, n_edges = build()
if not shape.isValid() or len(shape.Solids) != 1:
    raise SystemExit(
        f"accelerator: {len(shape.Solids)} solid(s), valid={shape.isValid()} -- "
        f"a fillet that half-succeeds still returns a shape, so this is checked, not printed."
    )
out = HERE / "exports"
out.mkdir(exist_ok=True)
shape.exportStep(str(out / "accelerator.step"))

import MeshPart  # noqa: E402

mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.2)
mesh.write(str(out / "accelerator.stl"))

# optimalBoundingBox(False). Plain BoundBox is BRepBndLib::Add, which uses the shape's
# triangulation IF one exists and falls back to the control poles otherwise -- so it is
# exact after meshing and reads 41.85 x 25.01 x 22.38 before it, against the true
# 41.25 x 22.83 x 20.70. Depending on whether something happened to tessellate first is not
# a property to rely on. The False turns OFF useTriangulation: with it on (the default) the
# answer comes from whatever tessellation is lying about and reads 41.39.
b = shape.optimalBoundingBox(False)
print(
    "accelerator: %d solid(s), %.4f cm3, bbox %.3f x %.3f x %.3f, %d faces, "
    "%d edges filleted, %d facets, valid=%s"
    % (
        len(shape.Solids),
        shape.Volume / 1000.0,
        b.XLength,
        b.YLength,
        b.ZLength,
        len(shape.Faces),
        n_edges,
        mesh.CountFacets,
        shape.isValid(),
    )
)
print("wrote accelerator.step / .stl")
