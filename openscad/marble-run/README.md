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
                curve120_split s_split  (optional halves for a small bed)
  mechanisms/   spiral (CylinderLadder)  catcher (MarbleCatcher)  flag_spinner (FlagTower)
                spiral_ramp (Turmdreher: helical ramp that wraps a tower)
  towers/       drop (straight-drop tower, tiers=2|3)
  ramps/        accelerator (the red slope; not in quadri-plot, measured off the real part)
```

Each piece file `use`s `../lib.scad`. Module names keep a category hint where the bare
name would be ambiguous (`mr_rail_straight`, `mr_drop_tower_3`).

**`use` imports modules but not variables**, so a piece file cannot read `SIDE`,
`MINI_H` and friends — anything that needs a parameter has to be a module in
`lib.scad` (this is why `connector_funnel`, `mini_white` and `control_knob` live
there rather than in their piece files).

### The accelerator is swept, not booleaned

Every other piece is a handful of CSG booleans and builds instantly. The accelerator
is built by sweeping a 2D cross-section along its length (`ACC_STEPS` slabs), because
its walls end in a **bullnose** — on the real part the wall does not stop at a sharp
arris, it rolls over from the outer face into the cradle. That rounding is a 2D
`offset` on the finished section outline, which is only expressible per-section.

The bullnose has to taper off towards the tip (`acc_lip`): the wall thins to under a
millimetre there, and rounding a wall shorter than twice the lip radius would erode it
away and cut 2 mm off the end of the ramp.

The cost is build time, and it depends entirely on the CSG backend. On the **Manifold**
backend the sweep is trivial; on the old **CGAL** one it is roughly 1.3 s per step:

| `ACC_STEPS` | step on the surface | Manifold | CGAL |
|-------------|--------------------|----------|------|
| 90 | 0.10 mm — visibly ribbed | ~2 s | ~2 min |
| **200 (default)** | **0.046 mm — under FDM resolution** | **~3 s** | ~4 min |
| 400 | 0.023 mm | ~5 s | unusable |

The sweep leaves the surface faintly stepped, since each slab has a constant section.
The default is set so the step is smaller than a printer can resolve; renders exaggerate
it through shading, so judge it by the number, not the picture. Lower it for previews.

Manifold arrived in OpenSCAD 2023 and is selected with `--backend=Manifold` (it is the
default from 2025 on). If your OpenSCAD is older — nixpkgs' `openscad` is still 2021.01,
which has no Manifold at all — either drop `ACC_STEPS` or switch the devshell to
`openscad-unstable`. Every other part is sub-second on either backend.

Note the underside deliberately differs from the original: the injection-moulded part
has a flat horizontal ceiling, which would be an unsupported overhang in FDM, so here
the shell follows the cradle at constant thickness and prints as an arch instead.

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
- rail halves (optional, for a 256 mm bed): `rail_curve120_a | rail_curve120_b | rail_s_a | rail_s_b`
- mechanisms: `spiral | catcher | flag | spiral_ramp`
- towers: `drop_tower3 | drop_tower2`
- ramps: `accelerator`

## Print volume note (Bambu Lab P1S, 256³ mm)

Sizes below are the smallest bounding box over in-plane rotations — i.e. the part laid
on the bed at its best angle, which is how a slicer will place it.

Everything fits except two rails. `rail_curve60` needs rotating ~75° on the bed (it is
212 × 212 there, but 164 × 250 axis-aligned), and the rest have room to spare: blocks
44 × 44 × 68, `drop_tower3` 44 × 44 × 188, `spiral_ramp` 96 × 96 × 38, `catcher`
108 × 108 × 20, `spiral` 52 × 52 × 114, `flag` 168 × 68 × 80, `rail_straight` 180 × 44.

| Piece | Best bbox | Fits |
|-------|-----------|------|
| `rail_curve120` | 338 × 338 | no — 82 mm over |
| `rail_s` | 374 × 375 | no — 119 mm over |

Both split at an existing **node** into two ~201 × 201 halves, which fit with 55 mm to
spare. Splitting on a node means the node's bore is reassembled from two halves, so the
stud of the block underneath passes through it and pins the joint shut; two sliding
dovetails (one per rail bar, sized to clear the node's Ø30 socket) align the halves and
stop them lifting. Join by lowering one half onto the other — they cannot be pulled
apart along the rail.

This is **opt-in**: the whole pieces are unchanged, and the halves are extra `part`
values. `JOINT_CLEAR` (0.18 mm) is the fit clearance to tune on a test print, and
`JOINT = false` in `lib.scad` gives a plain butt cut instead if you would rather glue.

```sh
openscad -D 'part="rail_curve120_a"' -o a.stl marble-run/marble-run.scad
```
