"""marble-run part — main: build every piece, export each + a combined layout.

Library:   lib.py        (parameters + Part/CSG helpers)
Pieces:    block_*.py, connector_funnel.py, marble.py   (each: NAME + build() -> Shape)
This main: exports exports/<piece>.step + .stl for each, plus a combined
           part.step laying every piece out in a row (for `cad gui`).

Build:  freecadcmd freecad/marble-run/part/part.py     (or: cad export marble-run/part)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import MeshPart  # noqa: E402

import lib  # noqa: E402
import block_blank  # noqa: E402
import block_orange  # noqa: E402
import block_yellow  # noqa: E402
import block_green  # noqa: E402
import block_teal  # noqa: E402
import block_blue  # noqa: E402
import block_wood  # noqa: E402
import block_red  # noqa: E402
import connector_funnel  # noqa: E402

PIECES = [
    block_blank,
    block_orange,
    block_yellow,
    block_green,
    block_teal,
    block_blue,
    block_wood,
    block_red,
    connector_funnel,
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "exports")
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(__file__))[0]

    placed = []
    pitch = lib.SIDE + 15
    for i, mod in enumerate(PIECES):
        shape = mod.build()
        shape.exportStep(os.path.join(out, mod.NAME + ".step"))
        MeshPart.meshFromShape(
            Shape=shape, LinearDeflection=0.1, AngularDeflection=0.5
        ).write(os.path.join(out, mod.NAME + ".stl"))
        preview = shape.copy()
        preview.translate(App.Vector(i * pitch, 0, 0))
        placed.append(preview)
        print("wrote", mod.NAME, "vol(cm3)=", round(shape.Volume / 1000, 2))

    Part.makeCompound(placed).exportStep(os.path.join(out, stem + ".step"))
    print("wrote", stem + ".step", "(", len(PIECES), "pieces )")


main()
