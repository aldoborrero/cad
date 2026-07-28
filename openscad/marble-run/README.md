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
  mechanisms/   spiral (CylinderLadder)  flag_spinner (FlagTower)
                spiral_ramp (Turmdreher: helical ramp wrapping a tower, stud + socket hub)
  catchers/     catcher (wedge, the default)  catcher_round  catcher_hape
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
rather than as a step the marble would hit.

The lip is also **not continuous**. On the original each bar carries two short runs, one
near each node, with the middle of the span bare — measured off a real 60° curve: ~37 mm
blank from the node, ~42 mm of lip, ~76 mm bare, then the mirror. `LIP_RUN` (80 mm) is how
far the lip reaches from a node, and `lip_mid_cut` opens the gap with the same cone trick
so the lip ramps down into it. Where the nodes are closer together than `2 * LIP_RUN` there
is no gap to open and the lip simply runs through, which is what the 180 mm straight gets
(its nodes are 136 apart) — matching the original, whose straight spare part is a single
55 mm strip.

`LIP_RUN = 0` gives one continuous lip per span instead, which holds better; the default
follows the original. `LIP = false` gives the plain quadri-plot rail back.

### Every edge on a rail is broken

It is a toy, so no arris is left square. The outer profile already carried `CHAMFER` (2 mm)
on its four long edges, but quadri-plot leaves two places sharp:

- **the groove** — `RAIL_C_IN` (0.8 mm) opens it out at both the top and the bottom face.
  The top pair is the surface the marble actually rides, so this moves the seat: `rail_seat()`
  is the real contact half-width and the seat height and lip placement are derived from it
  rather than from `GROOVE_W` directly.
- **the end faces** — `RAIL_C_END` (1 mm) insets the perimeter where the sweep is cut off.
  `rail_end_chamfer` is a short stack of slabs, each the section eroded by a shrinking
  amount, because a `hull()` between an inset and a full section would fill the groove in.
  Only a **free** end gets it: an arc asked for with no overhang (`before` or `after` = 0)
  ends on a node because it is meant to butt against its neighbour, and chamfering there
  would cut a V-groove around the seam of the S-curve.

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

### The catcher is a wedge, and it is sized by simulation

The bowl is the one piece here whose shape is decided by a measurement rather than by
copying. `sim/` scores it on the only thing it is for — the fraction of marbles it keeps —
and everything below is 30 entries per point, spread across the 20 mm bore and restitution
0.35–0.75, at entry speeds of 1.2 to 2.4 m/s (a block's side exit gives about 1.2).

| | retention | volume |
|---|---|---|
| photo proportions, round, block on a boss beside it, Ø112 × 26 | 71 % | 124 cm³ |
| round, port entry, 2.5 mm wall, shallow depression, Ø96 × 44 | 98 % | 75 cm³ |
| **this — wedge, 70 → 30 over 90** | **100 %** | **67 cm³** |
| wedge, 60 → 26 over 62 | 92 % | 54 cm³ |

**A round bowl is an arena, and that is the problem.** The marble comes in on one line and
crosses the whole diameter, so most of the floor is never used and the far wall has to
survive being hit head-on at full speed — which is where every escape came from. The wedge
puts it into a **V** instead: two converging walls, which cannot be ricocheted off cleanly
the way one flat wall can. It holds every marble up to 3.2 m/s and 97 % at 4.0, where the
round bowl was at about half.

A circle is perimeter-optimal, so no other plan can beat it on wall for the same floor area
— a square costs 13 % more, a hexagon 5 %. The wedge wins by needing **less floor**, which
was half the material, and by not needing a depression carved out of a solid slab: the V
gathers, so the floor is just the minimum printable 3 mm.

There are **three catchers**, and they are a straight trade of fidelity against function:

| part | | retention | volume |
|---|---|---|---|
| `catcher` | wedge, 70 → 30 over 90 | **100 %** | 67 cm³ |
| `catcher_round` | round Ø96 × 44, depression + slots | 98 % | 77 cm³ |
| `catcher_hape` | the original's proportions, Ø112 × 26 | 73 % | 117 cm³ |

`catcher_round` is the round bowl carrying everything the wedge has — port entry, socket
dock, 2.5 mm wall, inward lip — while keeping the original's depression and ring of ten
slots. It is there because the wedge, whatever it measures, looks nothing like the real part.

`catcher_hape` goes further and keeps the original's **proportions**: the wide, shallow
Ø112 × 26 dish. It cannot be made to keep marbles the way the other two do, and the reason
is the shape rather than the finish. A 26 mm rim is too shallow for a port to fit through
the wall — the port's top would sit at 40 — so the block has to stand on a boss as tall as
the rim and the marble falls 35 mm before it lands. A 26 mm wall does not hold that. Across
four builds, varying wall thickness and the lip, retention never moved off 72 %. Thinning
the wall and leaning the top still take 8 cm³ out for free, so it gets those; it is there
for fidelity, not performance.

Where the boss runs into the bowl there is a **fillet**, `CATCH_BLEND` (10 mm). A cylinder
driven into a box leaves two live re-entrant creases; a morphological **closing** in plan —
dilate by the radius, erode back — fills exactly those and leaves every convex corner
untouched, which is what a fillet is. It is swept as one prism through the wall's prismatic
band rather than as slabs: with the same section in every slab, each joint between two of
them came back as a two-triangle shard, 121 of them on the wedge, and the part stopped being
closed. The collar is also trimmed to within `CATCH_BLEND + 1` of the boss, because
otherwise the closing's outline runs along the wall's own face for the whole perimeter and
two solids sharing a face that long come back with a 0.01 mm shard down it.

It is also the one piece written as `include <../lib.scad>` followed by its own parameter
assignments, rather than `use`. That is the only way a piece file can change a library
parameter: the modules the include brings in evaluate against the file's own scope, so the
overrides reach inside them, and `use` from the main file keeps it all local.

### How much does it hold

Dividing the volume by a marble gives 67, and that is the wrong answer. Marbles arriving at
one end pile in a **heap**, not level, so the peak reaches the rim long before the box is
full. Fed one every 0.2 s at 1.2 m/s:

| | marbles |
|---|---|
| heap first touches the rim | ~35 |
| still in when fed past that | ~47 |
| levelled off by hand | ~67 |

So **about 35 before it wants emptying**, and it will go on taking them to roughly 47 as the
heap spreads.

**The block plugs in.** One side carries the system's Ø30 socket, so a block seats on it by
its stud and the run stacks up from there like any tower — the catcher is the base.
`CATCH_DOCK_H` picks the topology and is the number that matters:

- **as tall as the rim** — the boss puts the block's face on the bowl's inner wall so it
  overhangs and drops the marble straight in. Simple, but the marble falls the full height
  of the boss and arrives with it.
- **low (the default)** — the pad is only as deep as the socket needs, the block stands
  outside the wall, and the marble comes in through a **port pierced through the wall** at
  exit height. The wall stays whole above and below, the drop is 19 mm instead of 35, and
  the pad costs a third of the material. Worth 25 points of retention.

The port is sized by the **trajectory**, not by the marble: it arrives descending 30°, so
crossing the wall it drops another 2.3 mm. Sized for the marble alone it clips the bottom
lip on the way in — tried at 20 mm high, that alone cost 17 points.

The top of the wall leans inwards 8 mm at 45°. Both surfaces lean together so the wall keeps
its thickness, which means it *removes* material rather than adding it, it is self-supporting
to print, and a marble running up the wall meets a face pointing back into the bowl.

Two things that were tried and lost, left in the source at 0 so they stay reproducible.
**`CATCH_TAPER`**, flaring the wall outwards as it rises so the wall does the gathering:
24–60 % retention, because a flaring wall leans *away* from a marble coming up it and
launches rather than returns. And **`CATCH_VANE_H`**, the deflector lip the original has in
its mouth: standing 17 mm it reached above the marble's centre and *turned* it rather than
braking it, and a turned marble hits the far wall glancing, keeps its speed, and circulates
until it gets over the rim.

The floor is left **solid**; the place to hollow it out is the slicer's infill. The
moulded-in branding on the original is deliberately not reproduced.

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
- mechanisms: `spiral | flag | spiral_ramp`
- catchers: `catcher` (wedge) `| catcher_round | catcher_hape`
- towers: `drop_tower3 | drop_tower2`
- ramps: `accelerator | skate`

## Print volume note (Bambu Lab P1S, 256³ mm)

Sizes below are the smallest bounding box over in-plane rotations — i.e. the part laid
on the bed at its best angle, which is how a slicer will place it.

Everything fits except two rails. `rail_curve60` needs rotating ~75° on the bed (it is
212 × 212 there, but 164 × 250 axis-aligned), and the rest have room to spare: blocks
44 × 44 × 68, `drop_tower3` 44 × 44 × 188, `spiral_ramp` 96 × 96 × 38, `catcher`
185 × 70 × 44, `spiral` 52 × 52 × 114, `flag` 168 × 68 × 80, `rail_straight` 180 × 44.

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

The S-curve's halves needed two more things the 120° pair got for free. Its arcs stop dead
on the shared node but `rail_stud` does not — it is a whole Ø28 cylinder centred there, so
half of it hangs past the arc's end face, and both halves were carrying the same stud. And
because the second half is placed by a 180° rotation, its pocket has to reach the *opposite*
way from the tenon it receives. Both are fixed; the check is that the two halves intersect
in zero volume and assemble to the one-piece S minus the clearance gap.

This is **opt-in**: the whole pieces are unchanged, and the halves are extra `part`
values. `JOINT_CLEAR` (0.18 mm) is the fit clearance to tune on a test print, and
`JOINT = false` in `lib.scad` gives a plain butt cut instead if you would rather glue.

```sh
openscad -D 'part="rail_curve120_a"' -o a.stl marble-run/marble-run.scad
```
