"""iotorero-mount — FreeCAD (Part / OCCT B-rep) port of the OpenSCAD design.

Schuko outlet cradle for the round Athom / IoTorero IR remote: rests on the
rectangular USB charger, puck hangs in a cradle of tabs over the lower semicircle
(45 deg self-supporting lips), with a snap-in cable clip.

Build:  cad export iotorero-mount   ->  exports/iotorero-mount.step + .stl
"""

import os
import FreeCAD as App
import Part
import MeshPart

# ---------- Puck (measured) ----------
DEVICE_DIA = 65  # base diameter (measured 64.33)
DEVICE_STRAIGHT = 25  # straight wall height (edge)
DEVICE_H = 29  # total height at the dome centre  (unused here; for reference)

# ---------- Charger brick (RECTANGULAR Schuko — TODO: measure) ----------
BRICK_W = 45
BRICK_H = 50
BRICK_R = 5
BRICK_FIT = 0.6

# ---------- Plate ----------
PLATE_T = 4
RIM = 6
LEDGE = 6
CH_GAP = 16

# ---------- Retaining tabs (lower semicircle; mouth open at top) ----------
RING_H = DEVICE_STRAIGHT
LIP = 2
LIP_H = 2.5
FIT = 0.5
RING_WALL = 3
TAB_ANGLES = [150, 190, 230, 270, 310, 350]
TAB_HALF = 11

# ---------- Cable clip ----------
CABLE_DIA = 4
CLIP_WALL = 2

WELD = 0.6

# ---------- Derived ----------
a = DEVICE_DIA / 2
apW = BRICK_W + 2 * BRICK_FIT
apH = BRICK_H + 2 * BRICK_FIT
ch_y = a + RIM + CH_GAP + apH / 2
holeR = a - LEDGE
ro = a + FIT + RING_WALL


def rounded_box(w, h, t, r, cx=0.0, cy=0.0):
    """Box centred at (cx, cy), base at z=0, with its 4 vertical edges filleted."""
    b = Part.makeBox(w, h, t, App.Vector(cx - w / 2, cy - h / 2, 0))
    if r > 0:
        vedges = [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6]
        b = b.makeFillet(r, vedges)
    return b


def sector(radius, center_deg, half_deg, z0, z1):
    """Pie-slice solid centred on center_deg, half-width half_deg, spanning z0..z1."""
    c = Part.makeCylinder(
        radius, z1 - z0, App.Vector(0, 0, z0), App.Vector(0, 0, 1), 2 * half_deg
    )
    c.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), center_deg - half_deg)
    return c


# ---------- Plate (disc + trapezoid neck + rounded brick frame, minus holes) ----------
disc = Part.makeCylinder(a + RIM, PLATE_T)
y_top = ch_y - apH / 2
neck_pts = [
    App.Vector(-(a + RIM) * 0.9, 0, 0),
    App.Vector((a + RIM) * 0.9, 0, 0),
    App.Vector(apW / 2 + RIM, y_top, 0),
    App.Vector(-(apW / 2 + RIM), y_top, 0),
]
neck = Part.Face(Part.makePolygon(neck_pts + [neck_pts[0]])).extrude(
    App.Vector(0, 0, PLATE_T)
)
frame = rounded_box(apW + 2 * RIM, apH + 2 * RIM, PLATE_T, BRICK_R + RIM, 0, ch_y)

plate = disc.fuse(neck).fuse(frame)

dev_hole = Part.makeCylinder(holeR, PLATE_T + 2, App.Vector(0, 0, -1))
brick_ap = rounded_box(apW, apH, PLATE_T + 2, BRICK_R, 0, ch_y)
brick_ap.translate(App.Vector(0, 0, -1))
plate = plate.cut(dev_hole).cut(brick_ap)

# ---------- Tabs: ring + chamfered lip, kept only at the tab angles ----------
ring = Part.makeCylinder(ro, RING_H)
bore = Part.makeCylinder(a + FIT, RING_H - LIP_H + 1, App.Vector(0, 0, -1))
cone = Part.makeCone(a + FIT, a - LIP, LIP_H + 0.1, App.Vector(0, 0, RING_H - LIP_H))
ring_shell = ring.cut(bore).cut(cone)

wedges = None
for ang in TAB_ANGLES:
    s = sector(ro + 3, ang, TAB_HALF, -1, RING_H + 3)
    wedges = s if wedges is None else wedges.fuse(s)
tabs = ring_shell.common(wedges)
tabs.translate(App.Vector(0, 0, PLATE_T - WELD))

# ---------- Cable clip ----------
cr = CABLE_DIA / 2
clip = Part.makeCylinder(cr + CLIP_WALL, CABLE_DIA + CLIP_WALL)
clip = clip.cut(Part.makeCylinder(cr, CABLE_DIA + CLIP_WALL + 2, App.Vector(0, 0, -1)))
clip = clip.cut(
    Part.makeBox(
        cr + CLIP_WALL + 2,
        cr * 1.6,
        CABLE_DIA + CLIP_WALL + 2,
        App.Vector(0, -cr * 0.8, -1),
    )
)
clip.translate(App.Vector(a - CABLE_DIA - 2, (a + y_top) / 2, PLATE_T - WELD))

# ---------- Assemble + export ----------
part = plate.fuse(tabs).fuse(clip).removeSplitter()

here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "exports")
os.makedirs(out, exist_ok=True)
name = os.path.basename(here)

Part.export([part], os.path.join(out, name + ".step"))
MeshPart.meshFromShape(Shape=part, LinearDeflection=0.1, AngularDeflection=0.5).write(
    os.path.join(out, name + ".stl")
)
print("wrote", name + ".step / .stl  volume(cm3)=", round(part.Volume / 1000, 2))
