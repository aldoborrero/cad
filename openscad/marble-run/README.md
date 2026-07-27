# marble-run (OpenSCAD)

The **OpenSCAD** sibling of the FreeCAD implementations
([`part`](../../freecad/marble-run/part/) = Part/CSG,
[`part-design`](../../freecad/marble-run/part-design/) = Part Design). Same numbers, same
pieces, built with **BOSL2**.

## Layout (library → pieces → main)

| File | Role |
|------|------|
| `lib.scad` | `include <BOSL2/std.scad>` + parameters + helper modules (`block_base`, cutters) |
| `block_*.scad`, `connector_funnel.scad` | one piece each: `use <lib.scad>` + `module mr_*()` (renders itself when opened directly) |
| `marble-run.scad` | **main**: `include`s lib once, `use`s each piece, lays them all out; `part=` selects one |

`use` (not `include`) for the pieces keeps BOSL2/lib included exactly once — no duplicate
definitions.

## Render / export

```sh
cad export marble-run                       # whole plate -> exports/marble-run.stl
cad render marble-run iso                   # PNG preview -> exports/
openscad -D 'part="turn"' -o turn.stl marble-run/marble-run.scad   # a single piece
```

Valid `part` values: `all | blank | straight | turn | connector`.

## Notes

- Uses **BOSL2** (`cuboid` with `chamfer`/`edges="Z"`, `cyl`/`xcyl` with anchors, conical
  `cyl(d1, d2)`), on `OPENSCADPATH` via the flake.
- The repo's shared `openscad/lib/common.scad` isn't needed for these blocks, but its
  **`ring_sector`** will be reused for the upcoming **curved rails**.
- `.scad` has no reliable CLI formatter — light 2-space style, lint with `sca2d`.

Parameters mirror `../../freecad/marble-run/part/lib.py`.
