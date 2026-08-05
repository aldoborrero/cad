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
# This file's own name, not the directory's: under projects/<project>/freecad/ the
# directory is "freecad", while the model is <project>.py — which is the name the export
# should carry. It is the same rule bin/cad resolves a project by.
name = os.path.splitext(os.path.basename(os.path.abspath(__file__)))[0]

shape.exportStep(os.path.join(out, name + ".step"))
MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.1, AngularDeflection=0.5).write(
    os.path.join(out, name + ".stl")
)
print("wrote", name + ".step / .stl")
