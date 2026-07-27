"""marble-run — shared parameters (single source of truth).

A Hape Quadrilla-compatible marble run, parametric for FDM printing.

Provenance of the defaults:
  - Reverse-engineered geometry from the OpenSCAD project `shuckc/quadri-plot`
    (validated by the repo owner as correct for the real Quadrilla system).
  - "target marble" 16 mm (5/8") is the standard Quadrilla marble size.

MEASURE THESE ON YOUR SET before printing a full batch (they drive fit):
  - HEIGHT       : quadri-plot models 60 mm; the schematics look cubic (44). Measure.
  - STUD_D / SOCKET_D / STUD_H / SOCKET_DEPTH : the stack peg-and-socket engagement.
  - MARBLE_D     : 14 vs 16 mm changes the whole system.
Everything is parametric, so a measured value is a one-line change here.
"""

# ---------- Marble ----------
MARBLE_D = 16.0  # glass "target" marble diameter (quadri-plot sphere r=8.25 -> 16.5)

# ---------- Block module (the cube) ----------
SIDE = 44.0  # footprint X = Y  (quadri-plot: side=44) -- key compatibility dim
HEIGHT = 44.0  # full block height -- MEASURE (quadri-plot uses 60; schematic ~cube)
CHAMFER = 2.0  # bevel on the 4 vertical edges (quadri-plot: chamfer=2)

# ---------- Marble channel ----------
BORE_D = 19.0  # internal marble path diameter (marble + rolling clearance)

# ---------- Stacking: registration peg (bottom) + socket/dish (top) ----------
STUD_D = 29.0  # bottom boss diameter (quadri-plot BaseStud d=29)
STUD_H = 8.0  # bottom boss height
STACK_CLEAR = 1.0  # radial gap stud<->socket (29 -> 31 in quadri-plot = 1 mm/side)
SOCKET_D = STUD_D + 2 * STACK_CLEAR  # top recess that receives the stud (= 31)
SOCKET_DEPTH = STUD_H + 0.5  # a hair deeper than the stud so it seats fully

# ---------- Thin "landing" connector (the purple pieces) ----------
MINI_H = 12.0  # connector height (quadri-plot MiniBlock height=11.5; vgrid ~12)
FUNNEL_TOP_D = 34.0  # mouth diameter of the connector's catch bowl
FUNNEL_DEPTH = 8.0  # depth of the conical catch bowl

# ---------- FDM tolerances (spare, for future snap/press fits) ----------
FIT = 0.25  # radial clearance for press-fit features on an FDM printer
