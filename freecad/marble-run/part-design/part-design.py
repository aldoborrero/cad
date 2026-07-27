"""marble-run part-design — main: build every piece and place them in one scene.

Library:   lib.py        (parameters + Part Design / Sketcher helpers)
Pieces:    block_*.py, connector_funnel.py, marble.py  (each: NAME + build(doc) -> obj)
This main: builds every piece as a Body in a single document, exports
           exports/<piece>.step + .stl for each, lays them out, and saves the whole
           editable scene as part-design.FCStd (+ a combined part-design.step).

Build:  freecadcmd freecad/marble-run/part-design/part-design.py
        (or, once bin/cad supports nesting: cad export marble-run/part-design)

NOTE: not executed in the authoring env (no freecadcmd). The `turn` side exit and the
`connector` tapered bowl are the features most likely to need a one-line local tweak.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import MeshPart  # noqa: E402

import lib  # noqa: E402
import block_blank  # noqa: E402
import block_straight  # noqa: E402
import block_turn  # noqa: E402
import connector_funnel  # noqa: E402

PIECES = [block_blank, block_straight, block_turn, connector_funnel]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "exports")
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(__file__))[0]

    doc = App.newDocument("marble-run")
    pitch = lib.SIDE + 15
    placed = []
    for i, mod in enumerate(PIECES):
        obj = mod.build(doc)
        doc.recompute()

        # per-piece export (local coords, at the origin)
        shape = obj.Shape
        shape.exportStep(os.path.join(out, mod.NAME + ".step"))
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.1).write(
            os.path.join(out, mod.NAME + ".stl")
        )

        # lay it out in the combined scene
        obj.Placement = App.Placement(App.Vector(i * pitch, 0, 0), App.Rotation())
        s = obj.Shape.copy()
        s.Placement = obj.Placement
        placed.append(s)
        print("wrote", mod.NAME, "(.step/.stl)")

    doc.recompute()
    doc.saveAs(os.path.join(out, stem + ".FCStd"))  # editable scene, all pieces
    Part.makeCompound(placed).exportStep(os.path.join(out, stem + ".step"))
    print("wrote", stem + ".FCStd + .step  (", len(PIECES), "pieces )")


main()
