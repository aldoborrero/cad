# marble-run (FreeCAD)

A **Hape Quadrilla-compatible** marble run, parametric for **FDM** printing — implemented
**three ways** for comparison (same numbers, same pieces):

| Folder | Approach | Kernel / paradigm |
|--------|----------|-------------------|
| [`part/`](part/) | **Part / CSG** | primitives + booleans (`makeBox`/`cut`/`fuse`) |
| [`part-design/`](part-design/) | **Part Design** | Sketch → Pad/Pocket, editable feature tree + `.FCStd` |
| [`../../openscad/marble-run/`](../../openscad/marble-run/) | **OpenSCAD** | mesh/CSG with BOSL2 |

Each variant follows the same **library → pieces → main** layout:

```
lib(.py/.scad)     parameters + shared geometry helpers
block_blank        block_straight       block_turn        connector_funnel   ← one file per piece
part / part-design / marble-run   ← the main: builds every piece + a combined layout
```

## Build

```sh
cad export marble-run/part          # Part / CSG        -> exports/*.step + *.stl
cad export marble-run/part-design   # Part Design       -> *.step + *.stl + part-design.FCStd
cad export marble-run               # OpenSCAD (plate)  -> exports/marble-run.stl
cad gui    marble-run/part          # build + open in FreeCAD
```

(`bin/cad` now resolves these nested `name/variant` projects.)

## Pieces (foundation)

`block-blank`, `block-straight` (orange), `block-turn` (yellow), `connector-funnel` (purple).
**More to come** — see the roadmap: red splitter, green/blue/teal exits, control gate,
straight/curved **rails** (will reuse `openscad/lib/common.scad`'s `ring_sector`), and the
special mechanisms (cyclone, seesaw, spiral tower).

## Dimensions

Reverse-engineered from [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot):
`SIDE=44`, `BORE_D=19`, `STUD_D=29` / `SOCKET_D=31`. The fit-critical rows (`HEIGHT`,
stud/socket engagement) are flagged **MEASURE** in `part/lib.py` — confirm on a real set
before a full print batch. See [`part/README.md`](part/README.md) for the full table.
