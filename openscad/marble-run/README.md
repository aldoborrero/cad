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
                spiral_ramp (Turmdreher: helical ramp wrapping a tower, stud + socket hub)
  towers/       drop (straight-drop tower, tiers=2|3)
  ramps/        accelerator (the red slope; not in quadri-plot, measured off the real part)
                skate (the long orange Mega Skatepark ramp; dimensions ESTIMATED)
```

Each piece file `use`s `../lib.scad`. Module names keep a category hint where the bare
name would be ambiguous (`mr_rail_straight`, `mr_drop_tower_3`).

### The rails have guard lips

The 8 mm groove alone is a weak catch. A 16 mm marble sitting in it is held against
sideways load only until it climbs the groove edge, which works out at about **0.44 g** —
in the R = 230 curve that is 0.99 m/s, reached after a free drop of barely **74 mm, a
1.2 block feed**. Past that it leaves the rail. The original has a raised lip either side
for that reason (Hape's spare part is called a *Korrekturschiene*), and so does this.

The lip is a 5 x 5 bar crowned with a shallow arc, copied from that part. It is added
inside `rail_xsec()`, so every piece gets it from its own sweep — linear for the straight,
`rotate_extrude` for the curves, both arcs of the S, and the split halves inherit it.
There is no per-piece lip code.

Its inner face is placed from the marble, not by eye: `lip_y0()` is the marble's half-width
at the top of the lip plus `LIP_GAP`, so a centred marble never touches it, and it takes
hold after 1.2 mm of sideways drift.

At a node the lip has to disappear — a block seats there and covers 44 x 44. `rail_node_cut`
therefore also subtracts a **cone**: it clears everything within `LIP_CLR` (26 mm) of the
node and, by widening as it rises, lets the lip come back to full height over `LIP_RAMP`
rather than as a step the marble would hit. On the 180 mm straight that leaves ~64 mm of
full-height lip per gap, which is about the length of the original spare part.

`LIP = false` in `lib.scad` gives the plain quadri-plot rail back.

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

The bullnose has to taper off towards the tip (`acc_lip`). Rounding a feature by more
than half its thickness erodes it away completely, and towards the tip both the wall and
the floor under the cradle thin to about a millimetre: a fixed radius cut 2 mm off the
end of the ramp and, worse, dissolved the floor so the two walls became separate solids
with a hole between them. `acc_lip` is therefore clamped by whichever of the two is
thinner at that station.

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

The devshell provides `openscad-unstable` for this reason (nixpkgs' `openscad` is still
2021.01, which has no Manifold at all), and `bin/cad` passes `--backend=Manifold` when
the binary supports it. Every other part is sub-second on either backend.

### The skate ramp's dimensions are estimated, not measured

`skate` is the long orange Mega Skatepark ramp: a valley that sags in the **vertical**
plane, unlike the rails, which curve in plan. The marble sits down inside a channel with
raised walls (a cradle like the accelerator's) rather than riding two bars.

It prints as **two parts joined by a snap-in hinge**, so one ramp serves towers of
different heights. The mount is the same 44 x 44 ring as the set's stabiliser pieces and
stacks in a tower like any other block; two ears stand proud of one face, each with a
hole for the ramp's stub axles. A slot runs from the top of each ear down into its hole,
narrower than the axle (`SKATE_SNAP_W` 3.6 against `SKATE_PIN_D` 5), so pressing the ramp
down springs the ears apart and they close behind it. `SKATE_CLR` sets the running
clearance; both want checking on a test print.

Every other piece here is measured off a real part or ported from quadri-plot. This one
is **not** — the part was not to hand. Rather than carry photo guesses, it is pinned to
the system's own grid: `SKATE_SPAN` is six block widths (264 mm) end to end and
`SKATE_RISE` is one block height (60 mm), and the arc is derived from those
(R = 175 mm over 98°). So the tower at each end and the support under the middle all
land on the grid. The retail box is 300 mm long, which the 264 mm chord fits inside.

Underneath the low point is a flat pad with the standard Ø28 stud, so the middle of the
span seats on a ring or a block rather than sliding off — the original rests its middle
on a stack of the set's rings the same way.

The two block counts are the judgement call here; change them and the arc follows.

Note the accelerator's underside deliberately differs from the original: the injection-moulded part
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
- ramps: `accelerator | skate`

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
dovetails (one per rail bar) align the halves and stop them lifting. Join by lowering one
half onto the other — they cannot be pulled apart along the rail.

The dovetails have to fit in the 7 mm band between the node's Ø30 socket and the outer
edge of the rail. With clearance the pocket spans 15.8 to 21.2 mm from the centreline,
leaving ~0.8 mm of wall on each side; reaching further out cut into the rail's chamfer and
left a loose sliver inside half B.

This is **opt-in**: the whole pieces are unchanged, and the halves are extra `part`
values. `JOINT_CLEAR` (0.18 mm) is the fit clearance to tune on a test print, and
`JOINT = false` in `lib.scad` gives a plain butt cut instead if you would rather glue.

```sh
openscad -D 'part="rail_curve120_a"' -o a.stl marble-run/marble-run.scad
```
