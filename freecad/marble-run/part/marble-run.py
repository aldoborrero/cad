"""marble-run — Hape Quadrilla-compatible marble run (FreeCAD Part / OCCT B-rep).

A parametric family of pieces, not a single part: this orchestrator builds every
piece and exports one STEP + STL each into exports/, plus a combined
`marble-run.step` layout so `cad gui marble-run` has something to open.

Build:  cad export marble-run    ->  exports/<piece>.step + .stl  (+ marble-run.step)
Runs headless under `freecadcmd marble-run.py`.

Piece coverage so far (foundation): marble, blank block, straight (orange),
90 deg turn (yellow), landing connector (purple). The rest of the catalogue
(red splitter, green/blue/teal, control gate, rails, cyclone, seesaw, spiral)
comes next once the base fit is confirmed on a print.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import MeshPart  # noqa: E402

import params as P  # noqa: E402
import parts  # noqa: E402

# name -> builder. Order controls the assembly layout.
PIECES = {
    "marble": parts.marble,
    "block-blank": parts.block_blank,
    "block-straight": parts.block_straight,
    "block-turn": parts.block_turn,
    "connector-funnel": parts.connector_funnel,
}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "exports")
    os.makedirs(out, exist_ok=True)

    placed = []
    pitch = P.SIDE + 15
    for i, (name, build) in enumerate(PIECES.items()):
        shape = build()
        shape.exportStep(os.path.join(out, name + ".step"))
        MeshPart.meshFromShape(
            Shape=shape, LinearDeflection=0.1, AngularDeflection=0.5
        ).write(os.path.join(out, name + ".stl"))

        preview = shape.copy()
        preview.translate(App.Vector(i * pitch, 0, 0))
        placed.append(preview)
        print("wrote", name + ".step / .stl  vol(cm3)=", round(shape.Volume / 1000, 2))

    Part.makeCompound(placed).exportStep(os.path.join(out, "marble-run.step"))
    print("wrote marble-run.step  (", len(PIECES), "pieces )")


main()
