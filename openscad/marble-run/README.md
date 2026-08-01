# marble-run (OpenSCAD)

A 3D-printable **Hape Quadrilla-compatible** marble run. The channel geometry is a faithful
port of [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot) (`blocks.scad` /
`bridges.scad`); dimensions were measured on a real set — `SIDE=44`, `HEIGHT=60`,
`BORE_D=20`, `STUD_D=28`, `SOCKET_D=30`, and a Ø16 glass marble. Everything else derives
from those.

**Print `part="fitcheck"` first.** Four clearances in this project are guesses; the comb
settles all four for 51 cm³, and three of them gate parts that cost 70 cm³ or more.

## Layout

Each piece is one self-contained file that `use`s the shared library and defines a single
`mr_*()` module, so it renders itself when opened directly.

```
marble-run/
  lib.scad          parameters, block_base, the channel primitives (ch_top, ch_exit,
                    ex_vertical, ex_side, ex_across, ex_back, ex_bottom), rails, mechanisms
  marble-run.scad   main: uses each piece and lays them out; part= selects one
  blocks/           blank orange yellow green teal blue wood red control
  connectors/       funnel white
  rails/            straight curve60 curve120 s + curve120_split s_split
  mechanisms/       spiral (CylinderLadder)  flag_spinner (FlagTower)
                    spiral_ramp (Turmdreher)  seesaw (Wippe)
  catchers/         catcher (wedge, the default)  catcher_hape
  towers/           drop (straight-drop tower, tiers=2|3)
  ramps/            accelerator (the red slope)  skate (Mega Skatepark; dimensions ESTIMATED)
  tools/            fitcheck (the tolerance comb)  check.py (+ parts.json baseline)
  sim/              core.py params.py assembly.py run.py view.py blockexit.py catcher.py
                    retention.py seesaw.py spiralramp.py
```

**`use` imports modules but not variables.** A piece file cannot read `SIDE` or `MINI_H`, so
anything that needs a parameter has to be a module in `lib.scad` — which is why
`connector_funnel`, `mini_white` and `control_knob` live there rather than in their own files.

## Building a part

```sh
cad export marble-run                       # whole plate -> exports/marble-run.stl
cad render marble-run iso                   # PNG preview
openscad -D 'part="yellow"' -o yellow.stl marble-run/marble-run.scad
```

`part="all"` is the plate `cad export` builds: the eight channelled blocks and the funnel on
the 44 grid, 252 mm square, which fits a 256 mm bed. `part="catalogue"` is the other kind of
whole plan — every distinct piece side by side, 745 × 1041 mm, for looking at rather than
printing. Its offsets are not a grid: each piece carries its own origin, so they are packed
from the recorded bounding boxes. Both go through one `piece(name)` dispatch, which is also
the list `check.py` reads to find out what parts exist.

| | `part=` |
|---|---|
| blocks | `all` `blank` `orange` `yellow` `green` `teal` `blue` `wood` `red` `control` |
| connectors | `funnel` `white` |
| rails | `rail_straight` `rail_curve60` `rail_curve120` `rail_s` |
| rail halves | `rail_curve120_a` `rail_curve120_b` `rail_s_a` `rail_s_b` |
| descents | `spiral` `spiral_ramp` `drop_tower2` `drop_tower3` |
| ramps | `accelerator` `skate` |
| catchers | `catcher` `catcher_hape` |
| mechanisms | `flag` `seesaw` (both halves) `seesaw_arm` `seesaw_mount` |
| tools | `fitcheck` |
| whole plans | `all` (the printable plate) `catalogue` (every piece, to look at) |

---

# The pieces

## Rails

### Guard lips

The 8 mm groove alone is a weak catch. A 16 mm marble sitting in it resists sideways load
only until it climbs the groove edge — about **0.44 g**, which in the R = 230 curve is
0.99 m/s, reached after a free drop of **74 mm**. Past that it leaves the rail. The original
has a raised lip either side for the same reason (Hape's spare part is the
*Korrekturschiene*).

The lip is a 5 × 5 bar crowned with a shallow arc, added inside `rail_xsec()` so every piece
gets it from its own sweep — linear for the straight, `rotate_extrude` for the curves, both
arcs of the S, and the split halves inherit it. There is no per-piece lip code.

Its inner face is placed from the marble rather than by eye: `lip_y0()` is the marble's
half-width at the top of the lip plus `LIP_GAP`, so a centred marble never touches it and it
takes hold after 1.2 mm of drift.

At a node the lip has to disappear, because a block seats there and covers 44 × 44.
`rail_node_cut` subtracts a **cone**: it clears everything within `LIP_CLR` (26 mm) of the
node and, by widening as it rises, lets the lip return to full height over `LIP_RAMP` rather
than as a step.

The lip is **not continuous**. On the original each bar carries two short runs, one near each
node, with the middle bare — measured off a real 60° curve: ~37 mm blank from the node,
~42 mm of lip, ~76 mm bare, then the mirror. `LIP_RUN` (80 mm) is how far the lip reaches
from a node and `lip_mid_cut` opens the gap with the same cone. Where nodes are closer than
`2 * LIP_RUN` there is no gap to open, which is what the 180 mm straight gets (its nodes are
136 apart) — matching the original, whose straight spare part is a single 55 mm strip.

`LIP_RUN = 0` gives one continuous lip per span, which holds better. `LIP = false` gives the
plain quadri-plot rail back.

### Broken edges

It is a toy, so no arris is left square. The outer profile already carried `CHAMFER` (2 mm)
on its four long edges; quadri-plot leaves two places sharp.

- **The groove.** `RAIL_C_IN` (0.8 mm) opens it out at the top and bottom face. The top pair
  is the surface the marble rides, so this moves the seat: `rail_seat()` is the real contact
  half-width, and seat height and lip placement derive from it rather than from `GROOVE_W`.
- **The end faces.** `RAIL_C_END` (1 mm) insets the perimeter where the sweep is cut off.
  `rail_end_chamfer` is a stack of slabs, each the section eroded by a shrinking amount,
  because a `hull()` between an inset and a full section would fill the groove in — the
  groove is what makes the section non-convex, and a hull spans it. `RAIL_C_STEPS` was 4,
  which is a **0.25 mm step: above a print layer**, and so the coarsest surface in the set —
  worse than the accelerator's 0.046 mm, on all six rail parts. At 16 it is 0.062, under
  half a layer, for 1536 facets and 0.027 % of volume.
  Only a **free** end gets it: an arc with no overhang ends on a node, meant to butt against
  its neighbour, and chamfering there would cut a V-groove around the seam of the S.

## Blocks

Every block is the same 44 × 44 × 60 cube; what differs is where the channel comes out.
`ch_top` bores from the centre pivot to the top dish; the exits are `ex_vertical`,
`ex_side(60, ang)`, `ex_across`, `ex_back` and `ex_bottom`.

All twelve arrises are broken, not just the four vertical ones quadri-plot chamfers. The
break has to be cut from the *chamfered* outline: narrow a plain square and it lands on the
four flat faces only, mitring into itself over each corner cut and leaving that arris as
sharp as it started. Volume cannot see the difference — 0.007 % of a block — so `check.py`
fires a ray up the corner diagonal, which moves 2 mm.
`CHAMFER_TOP` matches `CHAMFER` at 2 mm; `CHAMFER_BOT` is only 0.8 because the base is the
face that *seats* on the piece below, and at the full 2 mm every joint in a stack would open
a 4 mm V. `SOCKET_CH` breaks the socket mouth as a lead-in for the stud above, and the same break is
taken off the **bore's** mouth in the socket floor, where the hole steps from Ø30 down to
Ø20 — the one arris a marble actually crosses when it is dropped in by hand at the top of a
tower. That break belongs to the bore, not to the socket: `blank` has a socket and no bore,
and cutting it in `block_base` would leave a conical groove in the middle of a flat floor. The two are
named for where they sit on the **model** — these have to print socket-down, since base-first
the 44 × 44 would overhang the Ø28 stud by 8 mm all round, so it is `CHAMFER_TOP` that lands
on the bed and takes the elephant foot with it. Cost: 0.41 cm³ a block, whatever its height,
since the breaks are on the two rings only.

### `LOW`, and the trap in the stud

`LOW`, the height of the low across/back crossings, is upstream quadri-plot's 6. The bore's
floor lands **4 mm below the block's own base**, so the channel has no floor of its own — the
piece below is the floor — and the same cut slices a channel through the Ø28 registration
stud. That is the real part: on a real block the straight low path runs below the base and
across the stud's circle, which is why the tunnel is open when you look at one from
underneath.

Raising it so the bore cleared the base gave the channel a floor and kept the stud whole, and
it was wrong twice over. It is not the part, and it drove the crossing into the pivot and the
60° side exit — see **[the crossing that ate the side exit](#the-crossing-that-ate-the-side-exit)**.

**There is a live defect here.** Fed straight into `teal`'s low bore with a `blank`
underneath, a marble drops 4 mm into the stud's channel and *stops*:

| entry speed | outcome |
|---|---|
| 0.3 m/s | stops, 4.0 mm below where it entered |
| 0.5 m/s | stops |
| 0.8 m/s | stops |
| 1.2 m/s | crosses, in 0.09 s |

A block's own side exit delivers **0.54 m/s** (measured, see the table further down), so in
normal use a marble arriving from a neighbour never reaches the speed that clears it. Either
`STUD_H`/`SOCKET_DEPTH` are wrong here, or the real stud is not the solid Ø28 × 8 boss this
models — it needs a real block to measure. Unresolved.

Every one of these blocks passes `check.py`: watertight, one body, right volume, features
where they belong. The defect only exists where two pieces meet, and a per-part check cannot
see a hand-off.

## The accelerator

Every other piece is a handful of CSG booleans and builds instantly. The accelerator is swept
— a 2D cross-section along its length, `ACC_STEPS` slabs — because its walls end in a
**bullnose**: on the real part the wall rolls over from the outer face into the cradle rather
than stopping at an arris. That rounding is a 2D `offset` on the finished section outline,
which is only expressible per-section.

The bullnose has to taper off towards the tip (`acc_lip`). Rounding a feature by more than
half its thickness erodes it away completely, and towards the tip both the wall and the floor
under the cradle thin to about a millimetre: a fixed radius cut 2 mm off the end of the ramp
and dissolved the floor, so the two walls became separate solids with a hole between them.
`acc_lip` is clamped by whichever of the two is thinner at that station.

The cost is build time, and it depends entirely on the CSG backend:

| `ACC_STEPS` | step on the surface | Manifold | CGAL |
|---|---|---|---|
| 90 | 0.10 mm — visibly ribbed | ~2 s | ~2 min |
| **200 (default)** | **0.046 mm — under FDM resolution** | **~3 s** | ~4 min |
| 400 | 0.023 mm | ~5 s | unusable |

The default is set so the step is smaller than a printer can resolve; renders exaggerate it
through shading, so judge it by the number rather than the picture. This is why the devshell
provides `openscad-unstable` — nixpkgs' `openscad` is 2021.01 and has no Manifold at all.

The underside deliberately differs from the original: the injection-moulded part has a flat
horizontal ceiling, which would be an unsupported overhang in FDM, so here the shell follows
the cradle at constant thickness and prints as an arch.

This is the one piece of the set that fights the tool, and it also exists as B-rep at
`freecad/marble-run/ramps/accelerator/`: a loft and a variable-radius fillet are primitives
in OCCT, so the sweep disappears — the cradle is an oblique cylinder and the part is 21 faces
before rounding. Same dimensions, read from this `lib.scad` rather than copied. 16 926
facets against 178 590, and the bounding box comes out exactly `ACC_L` x `ACC_W0` x
`ACC_ZTOP`. The printed part is unchanged: 0.046 mm is a quarter of a layer.

## The skate ramp

A valley that sags in the **vertical** plane, unlike the rails, which curve in plan. The
marble sits down inside a channel with raised walls rather than riding two bars.

It prints as **two parts joined by a snap-in hinge**, so one ramp serves towers of different
heights. The mount is the same 44 × 44 ring as the set's stabiliser pieces; two ears stand
proud of one face, each with a hole for the ramp's stub axles, and a slot runs from the top
of each ear down into its hole, narrower than the axle (`SKATE_SNAP_W` 3.6 against
`SKATE_PIN_D` 5), so pressing the ramp down springs the ears apart and they close behind it.
`SKATE_CLR` sets the running clearance; both are gauged by the tolerance comb.

Writing that comb meant reading the hinge closely, and it did not survive the reading. Three
faults, none of which the whole-part render showed:

- **Only one stub axle existed.** `cylinder()` always grows in +z, so the stub mirrored to −z
  grew back *into* the knuckle instead of out of it.
- **The ear pair sat 2 mm off centre.** Each ear was grown in +y from its mid-plane rather
  than about it, which leaves the right gap in the wrong place — the ramp fouled the −y ear
  by 1.65 mm.
- **The snap slot was beside the axle, not over it**, grown in +x from the bore rather than
  centred on it. The ear was also short enough that the bore broke out of its end face, so
  there was no throat at all; it now reaches `SKATE_EAR_END` (8 mm) past the axis.

Measured on the mesh after the fix: ears at ±13.35…±17.35 against a 26 mm ramp, a symmetric
0.35 mm per side; both stubs reach ±17; the throat is 3.6 mm centred on the bore.

**Its dimensions are estimated, not measured** — the part was not to hand. Rather than carry
photo guesses it is pinned to the system's own grid: `SKATE_SPAN` is six block widths
(264 mm) end to end and `SKATE_RISE` is one block height (60 mm), and the arc follows
(R = 175 mm over 98°), so the tower at each end and the support under the middle all land on
the grid. The retail box is 300 mm long, which the 264 mm chord fits inside. Those two block
counts are the judgement call; change them and the arc follows.

Underneath the low point is a flat pad with the standard Ø28 stud, so the middle of the span
seats on a ring or a block rather than sliding off — the original rests its middle the same
way.

## The catcher

The one piece whose shape is decided by measurement rather than by copying. `sim/` scores it
on the only thing it is for: the fraction of marbles it keeps, 30 entries per point spread
across the 20 mm bore and restitution 0.35–0.75, at the entry speeds a block's side exit
actually delivers (see [what a block's exit delivers](#what-a-blocks-exit-delivers)).

| | 0.54 | 0.68 | 0.79 | 0.96 | 1.13 | 1.28 | mean | volume |
|---|---|---|---|---|---|---|---|---|
| `catcher` — wedge, 70 → 30 over 90 | 100 | 100 | 100 | 100 | 100 | 100 | **100 %** | 73 cm³ |
| round Ø96 × 46 (`-D CATCH_SHAPE="round"`) | 100 | 100 | 100 | 100 | 100 | 100 | 100 % | 83 cm³ |
| `catcher_hape` — the original's Ø112 × 24 | 100 | 100 | 100 | 97 | 93 | 80 | 95 % | 113 cm³ |
| wedge + a 17 mm deflector | 100 | 100 | 100 | 100 | 100 | 97 | 99 % | 74 cm³ |
| wedge, rim raised to 56 | 100 | 100 | 100 | 100 | 100 | 100 | 100 % | 82 cm³ |

Two separate conclusions, and blurring them would be easy.

Among the **redesigned** bowls retention saturates — all 100 %, and the test stops telling
them apart. The wedge is chosen among those on material and footprint, not on retention. The
deflector's single 97 is 29/30 against 30/30, p = 1.0: noise.

But it is not true that any bowl will do. `catcher_hape` keeps the original's wide shallow
proportions and gives way exactly where the band gets fast — 171/180 against 180/180,
p = 0.0035. And 1.28 m/s is what a 600 mm tower delivers, which is an ordinary thing to
build.

**A round bowl is an arena.** The marble comes in on one line and crosses the whole diameter,
so most of the floor is never used and the far wall has to survive being hit head-on at full
speed, which is where every escape came from. The wedge puts it into a **V**: two converging
walls cannot be ricocheted off cleanly the way one flat wall can. A circle is
perimeter-optimal, so no plan can beat it on wall for the same floor area — a square costs
13 % more, a hexagon 5 % — but the wedge wins by needing **less floor**, which was half the
material, and by not needing a depression carved out of a slab: the V gathers, so the floor
is the minimum printable 3 mm.

The round bowl is a **shape, not a part**: `-D CATCH_SHAPE="round"` builds it, carrying
everything the wedge has — port entry, socket dock, 2.5 mm wall, inward lip — plus the
original's depression and ring of ten slots. It had its own `part=` value once; the shape
stayed and the part did not, and `retention.py` still measures it through the override, which
is where the row above comes from. `catcher_hape` goes
further and keeps the **proportions**, and cannot be made to keep marbles the way the other
two do: a 26 mm rim is too shallow for a port through the wall, so the block has to stand on
a boss as tall as the rim and the marble falls 35 mm before it lands. Across four builds,
varying wall thickness and the lip, retention did not move at all. It is there for fidelity.

The dock-height and port-height comparisons above were measured before `blockexit.py`
corrected the entry-speed band, so their *margins* are quoted from a regime that does not
occur. The direction of each is unaffected — a 35 mm drop into a 26 mm rim is worse than a
19 mm drop into a 46 mm one at any speed — but do not read absolute points off them.

### Capacity

Dividing the volume by a marble gives 67, and that is the wrong answer: marbles arriving at
one end pile in a **heap**, so the peak reaches the rim long before the box is full. Fed one
every 0.2 s at 1.2 m/s — **about 35 before it wants emptying**, going on to roughly 47 as the
heap spreads, 67 only if levelled by hand.

### How the block plugs in

One side carries the system's Ø30 socket, so a block seats on it by its stud and the run
stacks from there — the catcher is the base. `CATCH_DOCK_H` picks the topology:

- **as tall as the rim** — the boss puts the block's face over the bowl's inner wall so it
  drops the marble straight in. Simple, but the marble falls the full height of the boss.
- **low (the default)** — the pad is only as deep as the socket needs, the block stands
  outside the wall, and the marble comes in through a **port pierced through the wall** at
  exit height. The wall stays whole above and below, the drop is 19 mm instead of 35, and the
  pad costs a third of the material.

The boss is a whole `MINI_H` — 12 mm, exactly a white spacer, and 24 on `catcher_hape`. It
has to be: the boss decides the height a tower standing on it starts from, and heights in
this set are sums of 60 and 12. At the 10 mm it used to be, a run ending in the catcher could
not be levelled against anything else on the table.

The port is sized by the **trajectory**, not by the marble: it arrives descending 30°, so
crossing the wall it drops another 2.3 mm. Sized for the marble alone, at 20 mm high, it
clips the bottom lip on the way in.

The top of the wall leans inwards 8 mm at 45°. Both surfaces lean together so the wall keeps
its thickness, which means it removes material rather than adding it, it is self-supporting,
and a marble running up the wall meets a face pointing back into the bowl.

Where the boss runs into the bowl there is a **fillet**, `CATCH_BLEND` (10 mm). A cylinder
driven into a box leaves two live re-entrant creases; a morphological **closing** in plan —
dilate by the radius, erode back — fills exactly those and leaves every convex corner
untouched, which is what a fillet is. It is swept as one prism rather than as slabs: with the
same section in every slab, each joint came back as a two-triangle shard, 121 of them on the
wedge, and the part stopped being closed. The collar is trimmed to within `CATCH_BLEND + 1`
of the boss, or the closing's outline runs along the wall's own face for the whole perimeter
and two solids sharing a face that long come back with a 0.01 mm shard down it.

Two things were tried and lost. **A tapered wall**, flaring outwards as it rises so the wall
does the gathering: 24–60 % retention, because a flaring wall leans *away* from a marble
coming up it and launches rather than returns. Retention wants the opposite, which is what
`CATCH_LIP` does. That one is gone from the source — it was a `CATCH_TAPER` fixed at 0 sitting
inside three live expressions, including a `catch_r_at(z)` whose name promised a radius that
varied with height and returned a constant.

The other, **`CATCH_VANE_H`**, is the deflector the original has in its mouth: at 17 mm it
reaches above the marble's centre and turns it rather than braking it, and a turned marble
hits the far wall glancing, keeps its speed and circulates until it gets over the rim. That
mechanism is real but only bites above the speed this system can produce; at the speeds that
occur it keeps 100 %, exactly like the bare wedge. It stays in the source at 0, in modules of
its own where it costs nothing to leave, because unlike the taper it is a feature of the real
part that someone may want to reproduce.

`catcher_hape` is the one piece written as `include <../lib.scad>` followed by its own
parameter assignments rather than `use`. That is the only way a piece file can change a
library parameter: the modules the include brings in evaluate against the file's own scope.

## The seesaw

A plain seesaw — a trough pivoted at its middle — **cannot work**, and it is the obvious
thing to build. Whichever end is up at rest, the marble has to travel outward along that end
to tip it, and that is uphill. Whichever end is down, the marble reaches it without changing
any moment. Under gravity alone it can never get from a non-tipping position to a tipping
one.

What works is a **tipping cup**: the marble drops into a tray at the end of the raised arm, a
counterweight one grid pitch the other side holds that end up, the loaded arm swings down,
and past level the tray's floor tips the marble out of its open outer end. Two printed parts,
joined by the **same snap hinge as the skate ramp**, so the tolerance comb gauges this piece
too.

The arm must be **balanced about its pivot except for the counterweight**. The marble is
5.36 g of glass, the arm 16 g of PLA; with the arm balanced, its mass only adds inertia and
the marble has to beat the counterweight alone. The counterweight was sized off the exported
mesh: the tray alone is ~2.6 cm³ a full 40 mm out from the pivot, and balancing that against
a counterweight tucked in close needed 13 g — a brick that doubled the arm's mass. At one
grid pitch out the same job takes 4 g.

| counterweight | arm | restoring moment | margin, marble at the inner wall |
|---|---|---|---|
| 20 × 22 × 6 | 15.7 g | 89 g·mm | 2.29× |
| **20 × 22 × 7** | **16.0 g** | **103 g·mm** | **1.97×** |
| 20 × 22 × 8 | 16.3 g | 117 g·mm | 1.73× |
| 20 × 22 × 9 | 16.6 g | 132 g·mm | 1.55× |

7 mm gives about 2× to tip and ~8× what the axle's friction can resist on the way back.

`sim/seesaw.py` runs the arm as a real hinged body — a revolute joint with the mass, centre
of mass and inertia tensor read off the exported STL, the stops expressed as joint limits.
Three things came out of it that the CAD would not have told us.

**The outer end must stay open.** A lip buys nothing: at every height from 2 to 5 mm and
every bottom-stop angle from 10° to 22°, it either changed nothing or trapped the marble for
good. Rolling the tray's 20 mm of floor at a 10° tilt only buys 3.5 mm of height, so any lip
tall enough to hold the marble is tall enough to keep it.

**It needs a vertical feed.** A marble arriving with more than ~0.1 m/s of sideways speed
overshoots the tray or bounces out — not a retention failure a lip can fix, but the marble
never landing inside. So it is fed by a drop: a block's vertical exit or the funnel
connector, in the column one grid pitch out.

**The tray sits 4 mm inboard of the feed.** The feed is fixed by the grid, so the tray gets
positioned to catch it; simulation put the reliable landing band in the tray's outer half.
With that, every drop height from 8 to 60 mm works across restitution 0.25–0.55 and friction
0.25–0.45, and the cycle — drop, tip, release, reset — takes 0.28 to 0.44 s.

Intersecting the mount with the arm at a series of angles, and watching where the
interference rises, is what verifies the stops. It found two faults:

- **The cup-down stop was not there.** The gate is cut by subtracting the beam swept through
  its range, which puts a pad below and a bridge above with no arithmetic — but the gate
  block was capped at 56 mm and the swept void reached 55.5, so the bridge was 0.5 mm of
  material and the arm swung straight past its limit.
- **The swept fan ran the wrong way round.** `rotate([90,0,0])` puts the profile in the world
  XZ plane, where a positive 2D rotation tilts the cup *up*, while the arm's own
  `rotate([0,a,0])` tilts it *down*. Sweeping the fan the intuitive way cut the mirror image:
  cup-up stopped at 10° instead of 12°, and cup-down never stopped at all.

## The spiral ramp (Turmdreher)

A detour round **one** block: out of its 60° side exit, round the outside, and back in
through the low straight bore on the **next** face. Teal carries straight on out the far
side; green and blue drop out of the bottom instead (`-D TURM_DROP=true` opens the tray).
Blue cannot be used — its low bore is on the face *opposite* the 60° exit, and this loop
always lands on the adjacent one.

| block | tray floor | delivered, n=24 |
|---|---|---|
| teal, straight through | closed | **100 %** |
| green, out the bottom | `TURM_DROP=true` | **100 %** |
| blue | either | 0 % — wrong face, by construction |

Every earlier version wrapped the block on a path chosen for clearance and let a lead-in bend
the marble onto it. That cannot work, and it looks like a tuning problem. **The marble leaves
the face radially**, and a channel that wraps the block presents its outer wall square across
that line: the marble hit it at radius 33.6 and lost **86 % of its energy in a single step**,
then crawled the rest of the way at 0.15 m/s and stopped. No slope, bank or lead-in recovers
that, because the loss happens before any of them apply.

Two conditions then fix the shape completely:

* the marble leaves heading straight **out** of the +x face, and
* it must arrive heading straight **in** through the −y face.

A circle tangent to +x at `(SIDE/2, 0)` has its centre on `x = SIDE/2`; one tangent to +y at
`(0, -SIDE/2)` has its centre on `y = -SIDE/2`. There is exactly one circle: centred on the
block's own **corner**, travelled the long way round — 270°. That is the oval on the real
part, and with it the marble holds 0.33–0.39 m/s all the way round.

The radius is the only dial left. `SIDE/2` is the smallest that works geometrically and it is
too small — at 22 mm the marble pulls 7.3 m/s² sideways and grinds away enough speed to stop
halfway along the bore. 26 costs 18 mm of footprint and gets it out the far side.

**The tray is a landing connector**, exactly `MINI_H` thick, socket on top and its own stud
underneath. It began as a 50.8 mm collar the block dropped into, which is not a part of this
system: it overhangs the 44 grid, has no stud, and nothing can be stacked under it. It also
needed gates cut through it on all four faces to stop it walling off the block's own bores —
four holes to undo a wall that should not have existed.

Three more things each stopped the marble dead on its own:

- The socket for the block's stud must **not** be a through-hole, or a marble crossing a
  straight low bore drops into it halfway along.
- Both doorways are **flat-bottomed** rather than round: a round groove lifts a marble that
  is not dead-centre by 1.1 mm, onto the top edge of the bore.
- The doorways are straight and the channel arrives curving, so the two cuts drift apart
  along the corridor and what survives between them is a wall that tapers to nothing — a
  fragile fin in the marble's path. Widening the corridor swallows the fin but takes the
  channel's side walls with it: at 24 mm over the full 18 mm reach, delivery fell to 72 %.
  **The length is what mattered, not the width** — start the corridor 4 mm past the tangent
  point instead of 11.5 and every width from 20 to 24 reads 100 %, because the arc has barely
  diverged by then. It is cut wider than the bar, so no rind of it can remain.

Edges are broken like the rest of the set: the block's square carries the same `CHAMFER` on
its vertical edges, the bottom edge gets 0.8 mm where it meets the bed, and the channel wall
tops 0.5 mm — smaller because what remains of the bar above the groove is a 1.5 mm rim. There
is no chamfered `linear_extrude` and the plan is a C, so `hull()` is out; the bottom is a
short stack of inset slices, each overlapping the next. Built as a separate band and unioned
on, it came out non-manifold at 23 bodies — the band's top face and the prism's bottom face
were the same plane, and coincident faces are what Manifold cannot resolve.

---

# Verification

## Print the tolerance comb first

Four numbers are guesses marked "tune on a test print". `part="fitcheck"` settles all four
for **51 cm³**.

| Row | Gauges | Sweep |
|---|---|---|
| sockets | `STACK_CLEAR` — the Ø28 stud in the Ø30 socket | Ø30.0 → Ø28.4, 0.4 steps |
| dovetails | `JOINT_CLEAR` — the sliding joint that rejoins a split rail | −0.12 → +0.48, 0.15 steps |
| snap hinge | `SKATE_SNAP_W` and `SKATE_CLR` — the skate ramp's axle | 3.30 → 3.90, 0.15 steps |

Count the pips in front of a feature: 1 is always the tightest, 5 the loosest. On the
dovetail and the hinge the nominal sits in the middle at 3. On the socket it is at **5**,
because `STACK_CLEAR` is currently a whole millimetre of air per side and stepping either
side of that would have gauged five fits all far too loose to tell apart — so that row starts
at nominal and only tightens, down to a 0.2 mm slip fit.

Read it by feel: the one you want is the tightest that still goes together without forcing,
and comes apart again.

Two things it deliberately does not do. It does not sink the features into a backing plate —
a Ø30 hole in a 2.5 mm plate gauges the diameter but not the friction, and friction over the
socket's full 8.5 mm is what decides whether a stud goes in without forcing. Every feature
stands on the bed at its real engagement depth, tied to its neighbours by a 3 mm rib: same
test, a fifth of the plastic. And it engraves no numbers, so it needs no font.

Six pieces — three combs and three loose gauges — on a 211 × 152 mm footprint.

## tools/check.py

Builds every `part` and asserts its mesh against `tools/parts.json`. A regression test, not a
simulator. The part list is read out of `marble-run.scad` itself, so a new part cannot be
forgotten: it turns up as "not in the baseline" until someone records it with `--update`.

**Testing the test mattered more than writing it.** The first version checked volume, body
count, watertightness and bed fit — and passed all five deliberate regressions thrown at it.
Reverting the skate's stub-axle fix changed the volume by *nothing*, because the mirrored
stub grew back inside the knuckle and the union swallowed it. So there is a second layer: ray
probes, each firing a ray through a built part and asserting where it crosses the surface —
the hand measurements that caught the real faults, written down instead of retyped. One ray
down each row of the tolerance comb pins all five of its gauges at once.

With probes in place, the volume tolerance at 0.1 % and the probe tolerance at 0.02 mm:

| deliberate regression | caught by |
|---|---|
| skate loses a stub axle (volume change: zero) | probe: crossings `[-17, 13]`, wanted `[-17, 17]` |
| seesaw tray detached from the beam | 2 solid bodies not 1, +3.9 % volume, and the probe |
| snap throat drifts 1 mm off-centre | probe |
| tolerance comb's step 0.15 → 0.20 | probe (it passed at a 0.15 mm probe tolerance) |
| catcher wall 2.5 → 2.8 | volume +5.4 % |

`rail_curve120` and `rail_s` are declared known exceptions rather than left to fail every
run: they are oversize by design, which is why the split halves exist.

One recorded number is **not** a property of the model: the accelerator's `degenerate`
count. Those are zero-area two-triangle shards the triangulator leaves at the joints of the
200-slab sweep, and how many survive is the CSG backend's business, not the geometry's — an
OpenSCAD bump moved it 6 → 9 with the volume unchanged in the fourth decimal (4.1293 cm³)
and the solid still one watertight body. It is worth keeping, because a count that *grows
with an edit* means the sweep has started leaving real slivers; it is not worth chasing when
only the toolchain moved. Re-record it with `--update` and check the diff touches nothing
else, which is the whole test.

### Ports

Each piece declares, in `lib.scad` next to the geometry that decides it, where a marble
crosses its boundary: `["in"|"out", position, direction]`, the position being the marble's
**centre** as it crosses. `params.py` reads them straight out through OpenSCAD's `echo`.

This exists because that fact was previously restated in four places — `catch_exit_z`'s
hardcoded 17.3, `turm_zin`'s hardcoded 15, and the axis-to-ride-height correction written
separately in `catcher.py` and `retention.py` — and it was wrong in two of them at once. It
is now one pair of functions, `side_axis_z()` and `ride_z()`, and everything else derives.
Unifying them moved the ramp's channel entry up 0.57 mm, which it turns out it had been
approximating; it still delivers 36/36.

`check.py` then asserts that a Ø `MARBLE_D` sphere fits at every declared port and keeps
fitting a little way inward: `yellow`, which has no low bore, fails `teal`'s low-bore ports
outright. The probe stops at 6 mm because it is straight and the tightest channel in the set
is not — at 8 mm the spiral ramp's curved entry already reads 7.59 against the 8.0 needed.

**What no per-part check can see is a floor.** Clearance is measured on one mesh, and a bore
cut so low that it runs out of the bottom of the block reads as *more* room, not less: fed
its own ports, `LOW = 6` scores 8.93 mm where the correct value scores 7.99. The marble's
floor is provided by the piece underneath — an assembly property.

**But a floor that has fallen *into another channel* is a per-part property**, and
`check_floors` is the check for it. It walks each channel inward from its port and asks how
far down the first surface is, which is the opposite question to `check_ports`: room is
exactly what a channel gains when it merges into its neighbour, so the clearance probe waves
the merge through while this one fires.

It is the check that found **[the crossing that ate the side exit](#the-crossing-that-ate-the-side-exit)**,
below, and it now passes all 34 parts.

## The crossing that ate the side exit

`LOW` was wrong, and it was wrong because of a fix made here.

Upstream quadri-plot puts the low crossing at **z = 6** with a Ø19 bore, which leaves its
floor 3.5 mm *below* the block's base: the crossing has no floor of its own, and the piece
underneath is the floor. Raising it to `BORE_D/2 + 1 = 11` gave it one and kept the Ø28 stud
whole, and looked like a strict improvement. It was not:

| | `LOW` | `BORE_D` | material between crossing and side exit |
|---|---|---|---|
| upstream quadri-plot | 6 | 19 | +2.06 mm |
| here, before | 11 | 20 | **−4.09 mm** |
| here, now | 10 | 20 | +0.92 mm |

Negative means one void. Measured on the built mesh of `teal`: from the pivot down into the
crossing there was no material at all, and for the first 9 mm out of the pivot the 60° side
exit **had no floor** — the marble dropped 17 mm to the crossing's floor and climbed out from
there. It still left by the right port 18/18, which is why `run.py` never complained. It got
there by falling into the tunnel and rolling up the far side, and that detour is visible as a
curve in the viewer.

`assembly.py` could not see it either, for a stated reason: it excludes descending ports from
the floor check, because *a 60° side exit is a launch, it is meant to land on something*. The
hole was exactly inside that exclusion.

**The fix is upstream's height**, `LOW = 6`, and it took two wrong turns to get there. Both
were attempts to keep the crossing's floor inside the piece, and both were driven by not
having looked at a real block.

The first kept `LOW` at `BORE_D/2` so the crossing sat exactly on the base plane, and slotted
the stud through to open the tunnel out of the bottom. That measures *worse*: the stud is what
fills the socket of the block below, so cutting it exposes that socket and the marble drops
8.5 mm into it. The second left the stud whole and reserved a divider under the side exit by
subtracting it built fat. That measured fine — 0.92 mm of divider, a floor flat end to end —
and it was still wrong, because it is not the part. On a real block the straight low path runs
**below the base and across the stud's circle**, which is why the tunnel is open when you look
at one from underneath.

So the crossing has no floor of its own, and two things follow. `port_across` now states the
ride height as `MARBLE_D/2` — one radius above the base, where the piece below puts the marble
— not `ride_z(LOW)`, which is where the bore's own floor would put it and is 4 mm lower. And
`assembly.py`'s negative case changes with it: "teal on nothing at all" used to pass correctly,
because a lifted crossing needs nothing underneath. At the real height it is the failure the
check is for, and it reads *"out port at [0.0, -22.0, 8.0] has nothing under it"*.

The crossing does dip where it crosses the stud — 4 mm, measured on `teal` stacked on a
`blank`. That is the cut through the stud's circle and it is in the real part too, so
`check_floors` ignores anything below z = 0: what the marble rests on down there is the
assembly's business, not the piece's.

**Not finished.** `spiral_ramp` is a part of this project's own invention and its hand-off was
calibrated against the wrong `LOW`, so it now delivers 4 mm below the bore it aims at. The
giveaway is in `run.py`'s own output — the deliberately-broken case, the block seated 4 mm
proud, is the one that passes 2/2, because it cancels the error exactly. `turm_zout()` has
been re-derived from `MARBLE_D/2`, which fixes the declared port and satisfies `assembly.py`,
but the physics still reads 0/18: the marble leaves the ramp and does not cross. The channel
needs re-aiming, not just the port.

## sim/assembly.py

Pieces placed on the grid, ports resolved into world coordinates, and three assertions that
only mean anything once there is more than one piece. No physics: it is geometry, it runs in
seconds, and it covers the failures that cost this project the most.

**Support.** A level port's floor must be exactly one marble radius below it, checked in
*both* directions — and measured under the marble's **footprint**, not under the port. A
single ray asks the wrong question the moment a port sits on a broken edge: `CHAMFER_TOP`
takes 2 mm off the block's top face at exactly `y = ±SIDE/2`, which is where the low
crossing's ports are, so a point sample reads the chamfer and calls the floor 2 mm too low.
The marble does not fall into it — the gap between two stacked blocks is 4 mm wide, and a
16 mm ball bridges it, dipping 0.25 mm, which is one print layer. So a disc of rays is fired
instead and each hit is lifted onto the sphere, `z + √(R² − d²)`, taking the highest. A floor
that is genuinely absent is absent under the whole footprint, so nothing is lost; what is
gained is that a support more than a radius below now reads as *nothing under it* rather than
as a floor, because a marble is not sitting on it, it is falling past it. Too low and the marble drops out of the channel it was handed to. Too high
and the port's declared ride height is a fiction — the marble sits where the floor puts it,
and every clearance measured from that port is taken at the wrong height. `LOW = 6` is the
second kind, and it reads as *"floor at 60.0 puts the marble at 68.0, +4.0 from where the port
says"*.

**Exits.** An "out" port must have somewhere to go once everything else is placed. `check.py`
already says the channel is open inside the piece; this is the other half, and it is the
collar the tower twister used to carry — a wall standing across the bore it was delivering
into, which the ramp alone and the block alone were both perfectly happy with.

**Handover.** Where an "out" port mates an "in" port, a marble must fit the whole way between.

Half the cases in `main()` are assemblies **broken on purpose**, each declaring the phrase its
failure must contain, because a harness only ever fed working assemblies is a demo. One of
them is "teal on nothing at all", and it has been both a wrong test and a right one without
its text changing. While the crossing was lifted clear of the base it *passed*, correctly —
the bore had a floor of its own and needed nothing underneath. At the height a real block
uses, the piece below is the floor and its absence is exactly the failure to test for.

Three tolerances differ, and the reasons are not interchangeable. `SUPPORT_TOL` is tight
(0.6 mm) because a floor is either at one radius or it is not. `AHEAD_TOL` is looser (0.5 mm
on top of a value that should be exact) because a marble running a channel is *touching* its
floor, so the room around it is one radius by construction and mesh facets take tenths off
that; the signal there is a wall, which reads at or below zero. And a descending exit is
excluded from both — it is a launch, and it is meant to land on something.

**Beyond hand-offs**, the other defect class is features below the resolution of a render.
A thin-feature check finds those: slice the solid at 1 mm intervals and keep whatever
survives a morphological opening, since anything thinner than the probe is by definition
what is left.

## sim/run.py

Drop a marble into an assembly and follow it. `assembly.py` answers the geometry — is there a
floor, is the way open, do the ports mate — and this answers what only physics can: whether
the marble actually gets there, and out of which hole.

Doing it over an assembly rather than a piece means **the outcome classifies itself**. Every
earlier script wrote its own success condition by hand — "did it reach y > SIDE/2", "is it
still inside the bowl", "did it get back near the axis" — and each was a chance to measure the
wrong thing; one of them scored a marble parked 30 mm in the air as a perfect hit because it
compared only x and y. The ports already say where a marble may leave, so the result is a
**route**:

```
the tower twister carrying teal   n=18
    left by teal +y             18  100%
      route  teal +x -> spiral_ramp +y -> teal +y            18
```

Out of the block's 60° side exit, round the loop, back in and out the far face — the mechanism
this README describes in prose, produced by the runner rather than asserted.

Stopping at the first "out" port crossed is the obvious implementation and it is wrong: a
marble leaving the 60° exit really has left by that port, and it then goes round the twister
and back into the same block. The first port is not the answer; the last one is.

One of the cases is broken on purpose — the block seated 4 mm proud of the tray, which
`assembly.py` already flags as a bad hand-off — and its route is the clearest failure
signature this produces:

```
      route  teal +x -> (spiral_ramp +y -> teal -y) x28
```

The marble stops going anywhere and starts going back and forth in the doorway. Repeating
cycles are folded, or a stuck run prints a screenful.

## sim/view.py

The same run, watchable. `drop(..., path_every=N)` keeps every Nth position, and `view.py`
writes the assembly and that trajectory out as one self-contained HTML page: the placed
pieces, the path as a polyline, and the marble running along it, with orbit, scrub and a
clock.

Everything is **baked in** — the geometry, the trajectory, the route. Nothing is fetched and
no physics runs in the browser, which is the point: a second engine with different tuning
would produce different numbers from the ones quoted here, and an animation that merely looks
like evidence is worse than none. Playback is a quarter speed, off the wall clock rather than
one sample per frame, so it does not run at whatever rate the display happens to refresh at.

Meshes are decimated to fit, and the decimation is **verified on volume and on the bounding
box**. Volume alone is not enough, and the failure is instructive: 6000 faces takes 3.1 mm off
the spiral ramp's stud — a third of it — for 0.05 % of the volume, a stud being nearly all
surface and nearly no solid. Checking only the volume passes a part that can no longer be
plugged into anything. 12000 faces is exact on both, so that is what ships.

## The simulations

`sim/` drops marbles through the mechanisms under pybullet. `core.py` holds the marble, the
world and the sweep runner; `params.py` reads lib.scad's own parameters through OpenSCAD's
`echo` export, so a simulation never carries a copied CAD number.

That is not tidiness. Consolidating found that **both catcher scripts had stopped measuring
the catcher**: their stand-in block was still pinned to a Ø112 pedestal with a 26 mm dock,
from a generation of the part that no longer ships. Run against the shipped wedge, the marble
was released outside the bowl and every case read "escapes" — the part looked broken when it
was fine. A second constant of the same family, an escape radius of `bowl_r + 26`, was a
round-bowl assumption that falls *inside* a 149 mm wedge.

Porting the seesaw turned up a third: `part="seesaw_arm"` is exported **laid on its side for
printing**, so its inertia tensor arrives with y and z swapped, and a hinge about y silently
picks up Izz instead of Iyy — 1.2 % out, every swing time wrong by about 2 %.
`mass_properties(..., rotate_x=-90)` puts it back.

Bouncing is chaotic, so a single trajectory is not evidence: every figure quoted here is a
tally over a grid of entry conditions, and `sweep()` is the only runner offered.

### What a block's exit delivers

Every catcher number rested on one unchecked line: *"a marble that fell one block height
inside that block leaves at about 1.2 m/s"*. `sim/blockexit.py` measures it — drop a marble
into `yellow` and read the speed where it crosses the block's face, with a tower of `orange`
above.

| tower | arrives at the block | leaves the side exit | kept |
|---|---|---|---|
| 60 mm (the block alone) | — | **0.54** | — |
| 120 mm | 1.05 | 0.68 | 65 % |
| 180 mm | 1.50 | 0.79 | 52 % |
| 300 mm | 2.14 | 0.96 | 45 % |
| 420 mm | 2.61 | 1.13 | 43 % |
| 600 mm | 3.19 | 1.28 | 40 % |

The marble never falls a block height inside a block: it enters the top bore, drops to the
pivot at mid-height, and **the bend there destroys most of its speed** — it arrives moving
straight down and has to leave at 30° below horizontal, and the vertical component simply
goes. Below the bend there is only 12.7 mm to re-accelerate in.

Worse, the bend keeps a *smaller* share the faster the marble arrives, so the exit speed
saturates. **1.2 m/s needs about 500 mm of tower**, and 2.4 m/s — the top of the sweep the
catcher used to be tested at — would need an arrival speed of 6 m/s even if the ratio stopped
falling at 40 %, which is 1.8 m of free fall. Call it two metres: it cannot happen in this
system. The realistic band is 0.5 to 1.0 m/s. That the catcher survived being tested outside
it is luck; had it scored marginally, the decision would have been made on the wrong numbers.

Two smaller things fell out of the same measurement. The exit *dip* is 30–34°, as assumed.
The exit *height* was not: `catch_exit_z()` is where the bore's axis crosses the face, but a
16 mm ball rides on the floor of a 20 mm bore, so its centre passes 2 mm lower — 15.0 against
an axis at 17.3. Right for cutting the port, wrong for placing the marble.

---

# Printing (Bambu Lab P1S, 256³ mm)

Sizes are the smallest bounding box over in-plane rotations — the part laid on the bed at its
best angle, which is how a slicer will place it.

Everything fits except two rails. The tightest that do are `skate` at 221 × 221 × 144 and
`rail_curve60` at 212 × 212; the rest have room to spare — blocks 44 × 44 × 68,
`drop_tower3` 44 × 44 × 188, `spiral` 52 × 52 × 114, `spiral_ramp` 89 × 88 × 43, `seesaw`
104 × 92 × 70, `flag` 138 × 138 × 80, `catcher` 149 × 149 × 46, `rail_straight` 157 × 157,
`fitcheck` 192 × 192.

| Piece | Best bbox | Fits |
|---|---|---|
| `rail_curve120` | 338 × 338 | no — 82 mm over |
| `rail_s` | 374 × 374 | no — 118 mm over |

These are `tools/parts.json`'s own `footprint` field, so `check.py` and this table cannot
drift apart.

Both split at an existing **node** into two ~206 × 206 halves, which fit with 50 mm to spare.
Splitting on a node means the node's bore is reassembled from two halves, so the stud of the
block underneath passes through it and pins the joint shut; two sliding dovetails (one per
rail bar) align the halves and stop them lifting. Join by lowering one half onto the other —
they cannot be pulled apart along the rail.

The dovetails have to fit in the 7 mm band between the node's Ø30 socket and the outer edge
of the rail. With clearance the pocket spans 15.8 to 21.2 mm from the centreline, leaving
~0.8 mm of wall each side; reaching further out cut into the rail's chamfer and left a loose
sliver inside half B.

The S-curve's halves needed two things the 120° pair got for free. Its arcs stop dead on the
shared node but `rail_stud` does not — it is a whole Ø28 cylinder centred there, so half of it
hangs past the arc's end face and both halves were carrying the same stud. And because the
second half is placed by a 180° rotation, its pocket has to reach the *opposite* way from the
tenon it receives. The check is that the two halves intersect in zero volume and assemble to
the one-piece S minus the clearance gap.

This is **opt-in**: the whole pieces are unchanged and the halves are extra `part` values.
`JOINT_CLEAR` (0.18 mm) is the fit clearance to tune on a test print, and `JOINT = false` in
`lib.scad` gives a plain butt cut instead if you would rather glue.

```sh
openscad -D 'part="rail_curve120_a"' -o a.stl marble-run/marble-run.scad
```
