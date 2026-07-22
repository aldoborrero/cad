"""<project> — FreeCAD parametric model (Part / OCCT B-rep).

Build headless:  cad export <project>   ->  exports/<project>.step + .stl
Runnable directly with `freecadcmd <project>.py`.
"""

import os
import Part
import MeshPart

# ---------- Parameters ----------
WIDTH = 40
DEPTH = 30
HEIGHT = 10
FILLET = 3

# ---------- Model ----------
shape = Part.makeBox(WIDTH, DEPTH, HEIGHT)
shape = shape.makeFillet(FILLET, shape.Edges)  # real B-rep fillet on every edge

# ---------- Export (STEP B-rep + STL mesh) ----------
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "exports")
os.makedirs(out, exist_ok=True)
name = os.path.basename(here)

Part.export([shape], os.path.join(out, name + ".step"))
MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.1, AngularDeflection=0.5).write(
    os.path.join(out, name + ".stl")
)
print("wrote", name + ".step / .stl")
