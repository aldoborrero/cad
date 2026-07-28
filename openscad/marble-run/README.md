# marble-run (OpenSCAD)

A 3D-printable **Hape Quadrilla-compatible** marble run. The channel geometry is a
faithful port of [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot)
(`blocks.scad` / `bridges.scad`); dimensions were measured on a real set (`SIDE=44`,
`HEIGHT=60`, `BORE_D=20`, `STUD_D=28`, `SOCKET_D=30`). This OpenSCAD version is the
source of truth for the marble run.

## Layout (library → pieces → main)

Pieces are grouped by category; each is one self-contained file that `use`s the shared
library and defines a single `mr_*()` module (it renders itself when opened directly).

```
marble-run/
  lib.scad                 include <BOSL2/std.scad> + parameters + block_base +
                           channel primitives (ch_top, ch_exit, ex_vertical, ex_side,
                           ex_across, ex_back, ex_bottom) + rails + mechanisms + tower
  marble-run.scad          main: includes lib once, uses each piece, lays them out; part= selects one
  blocks/       blank orange yellow green teal blue wood red control
  connectors/   funnel white
  rails/        straight curve60 curve120 s
  mechanisms/   spiral (CylinderLadder)  catcher (MarbleCatcher)  flag_spinner (FlagTower)
                spiral_ramp (Turmdreher: helical ramp that wraps a tower)
  towers/       drop (straight-drop tower, tiers=2|3)
  ramps/        accelerator (red scoop wedge; not in quadri-plot, from the real part)
```

Each piece file `use`s `../lib.scad`. Module names keep a category hint where the bare
name would be ambiguous (`mr_rail_straight`, `mr_drop_tower_3`).

## Render / export

```sh
cad export marble-run                       # whole plate -> exports/marble-run.stl
cad render marble-run iso                   # PNG preview -> exports/
openscad -D 'part="yellow"' -o yellow.stl marble-run/marble-run.scad   # one piece
```

`part` values:
- blocks: `all | blank | orange | yellow | green | teal | blue | wood | red | control`
- connectors: `funnel | white`
- rails: `rail_straight | rail_curve60 | rail_curve120 | rail_s`
- mechanisms: `spiral | catcher | flag | spiral_ramp`
- towers: `drop_tower3 | drop_tower2`
- ramps: `accelerator`

## Print volume note (Bambu Lab P1S, 256³ mm)

Blocks, connectors, towers, `accelerator`, `catcher`, `spiral`, `flag` and
`rail_straight` all fit. The big curved rails do **not** fit axis-aligned: `rail_curve60`
(~250 mm) fits only rotated diagonally; `rail_curve120` (~398 mm) and `rail_s` (~460 mm)
must be printed as 60° segments (split at their nodes).
