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
                spiral_ramp (Turmdreher: BROKEN, see below -- neither end connects)
                seesaw (Wippe: a tipping cup on a balance arm; two parts)
  catchers/     catcher (wedge, the default)  catcher_round  catcher_hape
  towers/       drop (straight-drop tower, tiers=2|3)
  ramps/        accelerator (the red slope; not in quadri-plot, measured off the real part)
                skate (the long orange Mega Skatepark ramp; dimensions ESTIMATED)
  tools/        fitcheck (the tolerance comb — print this before anything else)
                check.py (builds every part and asserts its mesh; parts.json is the baseline)
  sim/          core.py (the marble, the world, the sweep) params.py (reads lib.scad's own
                numbers) blockexit.py catcher.py retention.py seesaw.py
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
0.35–0.75.

**Read the table below as headroom, not as a ranking.** It was measured at entry speeds of
1.2 to 2.4 m/s, on the strength of a hand figure saying a block's side exit gives about 1.2.
It does not: `sim/blockexit.py` measures 0.54 m/s from a single block and 1.28 from a 600 mm
tower, and 2.4 is unreachable in this system (see below). Re-run across the band that
actually occurs, at 30 entries per cell:

| | 0.54 | 0.68 | 0.79 | 0.96 | 1.13 | 1.28 | mean | volume |
|---|---|---|---|---|---|---|---|---|
| `catcher` — wedge | 100 | 100 | 100 | 100 | 100 | 100 | **100 %** | 73 cm³ |
| `catcher_round` — round Ø96 | 100 | 100 | 100 | 100 | 100 | 100 | 100 % | 83 cm³ |
| wedge + the 17 mm deflector | 100 | 100 | 100 | 100 | 100 | 97 | 99 % | 74 cm³ |
| wedge, rim raised to 56 | 100 | 100 | 100 | 100 | 100 | 100 | 100 % | 82 cm³ |
| `catcher_hape` — the original's proportions | 100 | 100 | 100 | 97 | 93 | 80 | 95 % | 113 cm³ |

Two different conclusions, and it matters not to blur them.

Among the **redesigned** bowls — wedge, round Ø96, taller rim — retention saturates: all
100 %, and the test stops telling them apart. Between those three the wedge is chosen on
**material and footprint**, not on retention, and the older table's spread says only that it
carries the most headroom above a regime it will never meet. The deflector's single 97 is
29/30 against 30/30, which is p = 1.0 — noise.

But it is *not* true that any bowl will do. `catcher_hape`, which keeps the original's wide
shallow proportions, holds at the slow end and then gives way exactly where the band gets
fast: 97 %, 93 %, 80 % at 0.96, 1.13 and 1.28 m/s. Against the wedge that is 171/180 versus
180/180, p = 0.0035. And 1.28 m/s is not a corner case — it is what a 600 mm tower delivers,
which is an ordinary thing to build. **So the redesign bought real function after all**, just
against the original rather than against its own variants.

| | retention | volume |
|---|---|---|
| photo proportions, round, block on a boss beside it, Ø112 × 26 | 71 % | 124 cm³ |
| round, port entry, 2.5 mm wall, shallow depression, Ø96 × 44 | 98 % | 75 cm³ |
| **this — wedge, 70 → 30 over 90** | **100 %** | **73 cm³** |
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
| `catcher` | wedge, 70 → 30 over 90 | **100 %** | 73 cm³ |
| `catcher_round` | round Ø96 × 46, depression + slots | 98 % | 83 cm³ |
| `catcher_hape` | the original's proportions, Ø112 × 24 | 75 % | 113 cm³ |

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

The boss is **a whole `MINI_H`** — 12 mm, exactly a white spacer, and 24 on `catcher_hape`.
It has to be: the boss is what decides the height a tower standing on it starts from, and
heights in this set are sums of 60 and 12. At the 10 mm it used to be (socket depth plus a
little) a run ending in the catcher could not be levelled against anything else on the
table. Nothing else about the part needs to be on the grid — the rim can be whatever holds
marbles, and at 12 mm, `white`'s height, it would not even reach over one.

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

That last verdict needs qualifying, and the qualification is the same one as above. The
deflector's 95 % was measured at 1.2–2.4 m/s. At the speeds a block's exit actually
delivers it keeps 100 %, exactly like the bare wedge. The mechanism described is real
physics, but it only bites above the speed this system can produce. It stays out for a
duller reason than "it is harmful": it does nothing, and costs 1.1 cm³ and an overhang.

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
clearance; both are gauged by the tolerance comb.

Writing that comb meant reading the hinge closely, and it did not survive the reading —
three faults, none of which the whole-part render showed:

- **Only one stub axle existed.** `cylinder()` always grows in +z, so the stub mirrored to
  −z grew back *into* the knuckle instead of out of it.
- **The ear pair sat 2 mm off centre.** Each ear was grown in +y from its mid-plane rather
  than about it, which happens to leave the right gap between them but puts that gap in the
  wrong place — the ramp fouled the −y ear by 1.65 mm.
- **The snap slot was beside the axle, not over it**, grown in +x from the bore rather than
  centred on it. And the ear was short enough that the bore broke out of its end face
  anyway, so there was no throat to speak of: the ear now reaches `SKATE_EAR_END` (8 mm)
  past the axis.

Fixed and measured on the mesh: the ears now sit at ±13.35…±17.35 against a 26 mm ramp, a
symmetric 0.35 mm per side; both stubs reach ±17; the throat is 3.6 mm centred on the bore.

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
- mechanisms: `spiral | flag | spiral_ramp | seesaw` (both parts) `| seesaw_arm | seesaw_mount`
- catchers: `catcher` (wedge) `| catcher_round | catcher_hape`
- towers: `drop_tower3 | drop_tower2`
- ramps: `accelerator | skate`
- tools: `fitcheck`

### The seesaw is a tipping cup, because a seesaw cannot work

A plain seesaw — a trough pivoted at its middle that the marble runs along — cannot work,
and it is worth writing down why, because it is the obvious thing to build. Whichever end
is up at rest, the marble has to travel *outward along that end* to tip it, and that is
uphill. Whichever end is down, the marble reaches it without changing any moment. Under
gravity alone the marble can never get from a non-tipping position to a tipping one.

What does work is a **tipping cup**: the marble drops into a tray at the end of the raised
arm, a counterweight one grid pitch the other side holds that end up, the loaded arm swings
down, and past level the tray's floor tips the marble out of its open outer end. The empty
arm then rides back up. Two printed parts, joined by the **same snap hinge as the skate
ramp** — same axle, same throat — so the tolerance comb gauges this piece too.

The design rule is that the arm must be **balanced about its pivot except for the
counterweight**. The marble is glass and weighs 5.36 g; the arm is PLA and weighs 16 g. If
the arm's own imbalance were fighting the marble the thing would never move, but with the
arm balanced, its mass only adds inertia and the marble has to beat the counterweight alone.

The counterweight was sized by measurement, not by guessing. The tray alone is ~2.6 cm³
sitting a full 40 mm out from the pivot, and balancing that against a counterweight tucked
in close needed 13 g of PLA — a brick, doubling the arm's mass. Out at one grid pitch the
same job takes 4 g, and the piece then reads as the balance it actually is. Sweeping the
counterweight's height against the arm's centre of mass, measured off the exported STL:

| counterweight | arm | restoring moment | margin, marble at the inner wall |
|-----|-----|-----|-----|
| 20 × 22 × 6 | 15.7 g | 89 g·mm | 2.29× |
| **20 × 22 × 7** | **16.0 g** | **103 g·mm** | **1.97×** |
| 20 × 22 × 8 | 16.3 g | 117 g·mm | 1.73× |
| 20 × 22 × 9 | 16.6 g | 132 g·mm | 1.55× |

7 mm is the pick: about 2× to tip, and still ~8× what the axle's friction can resist on the
way back.

#### What the simulation settled

`sim/seesaw.py` runs the arm as a real hinged body — a revolute joint with the mass, centre
of mass and inertia tensor read off the exported STL, and the gate's two stops expressed as
joint limits. Three things came out of it that the CAD alone would not have told us.

**The outer end must stay open.** The obvious worry is that the marble rolls out too easily,
so the obvious fix is a lip across the open end. Measured, a lip buys *nothing*: at every
height from 2 to 5 mm, and at bottom-stop angles from 10° to 22°, the lip either changed
nothing or trapped the marble in the cup for good. Rolling the tray's 20 mm of floor at a
10° tilt only buys the marble 3.5 mm of height, so any lip tall enough to hold it is also
tall enough to keep it.

**It needs a vertical feed.** A marble arriving with more than ~0.1 m/s of sideways speed
overshoots the tray or bounces along it and out — and that is not a retention failure a lip
can fix, it is the marble never landing inside. So the seesaw is fed by a drop: a block's
vertical exit or the funnel connector, in the column one grid pitch out. That is why the
piece is laid out the way it is.

**The tray sits 4 mm inboard of the feed.** The feed position is fixed by the grid, so it
is the tray that gets positioned to catch it. Simulation put the reliable landing band in
the tray's outer half, so the tray was moved inboard until the grid's 44 mm lands mid-band.
With that, every drop height from 8 to 60 mm works, across restitution 0.25–0.55 and
friction 0.25–0.45. The cycle — drop, tip, release, reset — takes 0.28 to 0.44 s.

#### Two faults the clearance check caught

Intersecting the mount with the arm at a series of angles, and watching where the
interference rises, is what verifies the stops. It found both of these:

- **The cup-down stop was not there.** The gate is cut by subtracting the beam swept through
  its range, which puts a pad below and a bridge above with no arithmetic. But the gate
  block was capped at 56 mm and the swept void reached 55.5, so the "bridge" was 0.5 mm of
  material. The arm swung straight past its limit.
- **The swept fan ran the wrong way round.** `rotate([90,0,0])` puts the profile in the
  world XZ plane, where a positive 2D rotation tilts the cup *up*, while the arm's own
  `rotate([0,a,0])` tilts it *down*. Sweeping the fan the intuitive way cut the mirror image
  of the range: cup-up stopped at 10° instead of 12°, and cup-down never stopped at all.

The mount is 65 cm³, most of it solid base. Hollowing it is a job for the slicer's infill.

### Print the tolerance comb first

Four numbers in this project are guesses marked "tune on a test print", and three of them
gate parts that cost 70 cm³ or more. `part="fitcheck"` settles all four for **51 cm³**:

| Row | Gauges | Sweep |
|-----|--------|-------|
| sockets | `STACK_CLEAR` — the Ø28 stud in the Ø30 socket | Ø30.0 → Ø28.4, 0.4 steps |
| dovetails | `JOINT_CLEAR` — the sliding joint that rejoins a split rail | −0.12 → +0.48, 0.15 steps |
| snap hinge | `SKATE_SNAP_W` and `SKATE_CLR` — the skate ramp's axle | 3.30 → 3.90, 0.15 steps |

Count the pips in front of a feature: 1 is always the tightest, 5 the loosest. On the
dovetail and the hinge the nominal sits in the middle at 3. On the socket it is at **5**,
because `STACK_CLEAR` is currently a whole millimetre of air per side and stepping either
side of that would have gauged five fits all far too loose to tell apart — so that row
starts at nominal and only tightens, down to a 0.2 mm slip fit.

Read it by feel, not by eye: the one you want is the tightest that still goes together
without forcing, and comes apart again.

Two things it deliberately does **not** do. It does not sink the features into a backing
plate — a Ø30 hole in a 2.5 mm plate gauges the diameter but not the friction, and friction
over the socket's full 8.5 mm is what actually decides whether a stud goes in without
forcing, so a plate-mounted comb would read far too loose. Instead every feature stands on
the bed at its real engagement depth, tied to its neighbours by a 3 mm rib: same test, a
fifth of the plastic. And it does not engrave numbers, so it needs no font.

It prints as six pieces — three combs, and three loose gauges (a stud, a tenon, an axle)
to try in them — on a 211 × 152 mm footprint.

## Checking the geometry

`python3 tools/check.py` builds every `part` and asserts its mesh against
`tools/parts.json`. It is a regression test, not a simulator, and it exists because the
question it answers kept going unasked — the skate ramp shipped with only one of its two
stub axles, the tolerance comb's first build came out in 25 pieces with the ears floating
free, and none of that shows up in a render.

The part list is read out of `marble-run.scad` itself, so a new part cannot be forgotten:
it turns up as "not in the baseline" until someone records it with `--update`.

**Testing the test mattered more than writing it.** The first version checked volume, body
count, watertightness and bed fit — and passed all five deliberate regressions thrown at
it. Reverting the skate's stub-axle fix changed the volume by *nothing*, because the
mirrored stub grew back inside the knuckle and the union swallowed it. So there is a second
layer: ray probes, each firing a ray through a built part and asserting where it crosses
the surface. They are the hand measurements that caught the real faults, written down
instead of retyped — one ray down each row of the tolerance comb pins all five of its
gauges at once. With those in place, and the volume tolerance at 0.1% and the probe
tolerance at 0.02 mm:

| deliberate regression | caught by |
|---|---|
| skate loses a stub axle (volume change: zero) | probe: crossings `[-17, 13]`, wanted `[-17, 17]` |
| seesaw tray detached from the beam | 2 solid bodies not 1, +3.9% volume, and the probe |
| snap throat drifts 1 mm off-centre | probe |
| tolerance comb's step 0.15 → 0.20 | probe (it passed at a 0.15 mm probe tolerance) |
| catcher wall 2.5 → 2.8 | volume +5.4% |

Two parts are declared known exceptions rather than left to fail every run: `rail_curve120`
and `rail_s` are oversize by design, which is why the split halves exist.

## The simulations

`sim/` drops marbles through the mechanisms under pybullet. `core.py` holds the marble, the
world and the sweep runner; `params.py` reads lib.scad's own parameters through OpenSCAD's
`echo` export, so a simulation never carries a copied CAD number.

That last part is not tidiness. Consolidating found that **both catcher scripts had stopped
measuring the catcher**: their stand-in block was still pinned to a Ø112 pedestal with a
26 mm dock, from a generation of the part that no longer ships. Run against the shipped
wedge, the marble was released outside the bowl and every case read "escapes" — the part
looked broken when it was fine. A second constant of the same family, an escape radius of
`bowl_r + 26`, was a round-bowl assumption that falls *inside* a 149 mm wedge. Both are now
derived, one from lib.scad and one from the mesh's own bounds.

Porting the seesaw turned up a third: `part="seesaw_arm"` is exported **laid on its side for
printing**, so its inertia tensor arrives with y and z swapped relative to the arm's own
frame, and a hinge about y silently picks up Izz instead of Iyy — 1.2% out, every swing time
wrong by about 2%. `mass_properties(..., rotate_x=-90)` puts it back.

Each port was checked against the numbers it produced beforehand. The seesaw's tip times and
swing angles come back identical to the microsecond; release and reset land within 0.5%,
which is a freshly exported mesh differing in the last bits and a chaotic bounce amplifying
it. The catcher's shipped wedge scores 100% over 180 runs, as published.

### The spiral ramp does not connect at either end

**`spiral_ramp` is broken. Do not print it.** It was found by eye, not by any of the
checking here, and that is the point.

Seat a block on the ramp's hub — the only way the piece stacks — drop a marble in, and it
jams inside the block at radius 17 and stays there for the whole run. It never reaches the
block's face, because **the block's 60° side exit discharges straight into the ramp's solid
inner wall**: the exit puts the marble's centre at z=27, radius 22, and the channel wants it
at z=36, radius 36.5. Out by 9 mm in height and 14.5 in radius. At the far end the helix
simply stops at radius 36.5, z=18.5 — 14.5 mm past the neighbouring column's block face, in
mid-air.

Re-basing the helix to meet the block is the obvious repair and it does not work. Follow the
marble: it leaves the block falling at 30°, so reaching the helix radius costs it 8.4 mm of
height, and it arrives needing a floor at 10.6. The helix still has 17.5 mm to descend, so
it would end at floor −6.9 — **18.9 mm below the hub's own top face**, with the last quarter
turn passing through the hub and the tower beneath it. There is no room. A block on this
piece's own hub cannot feed it at all.

And half the supports hold nothing. The webs run radially from x=21 to x=26 at every angle,
but the hub is a **square**: at the corners it reaches 31.1 while the ramp's inner edge
retreats to 34.5. So the three corner webs are buried inside the hub and never touch the
ramp, and a fourth at 22.5° stops 2 mm short. Only the four at the face angles bridge
anything — and the source comment says the count went from four to eight precisely because
the long spans were unsupported. The four that were added are inert.

So it needs a design decision, not a repair: the feed has to come from somewhere else, and
the exit has to be brought onto a grid position. The measured helix itself is fine — 202 mm
of path descending 17.5 mm, a 4.96° slope — and is kept as the starting point.

**What this says about the checking.** `tools/check.py` verifies every piece *in isolation*:
watertight, one body, right volume, features where they belong. `spiral_ramp` passes all of
it, because nothing about the piece alone is wrong. The defect only exists in **assembly**,
and nothing here looks at assemblies. That is the same blind spot that let the catcher's
simulation drift onto a part that no longer shipped, and it is the strongest argument yet
for checking hand-offs: for each piece, where does the marble arrive, where does it leave,
and does either land on the grid.

### The block's bend is a speed limiter

Every catcher number rested on one unchecked line in `retention.py`: *"a marble that fell
one block height inside that block leaves at about 1.2 m/s"*. `sim/blockexit.py` measures it
instead — drop a marble into `yellow` (top entry, one 60° side exit, nothing else) and read
the speed where it crosses the block's face, with a tower of `orange` above it.

| tower | arrives at the block | leaves the side exit | kept |
|-------|------|------|------|
| 60 mm (the block alone) | — | **0.54** | — |
| 120 mm | 1.05 | 0.68 | 65% |
| 180 mm | 1.50 | 0.79 | 52% |
| 300 mm | 2.14 | 0.96 | 45% |
| 420 mm | 2.61 | 1.13 | 43% |
| 600 mm | 3.19 | 1.28 | 40% |

The marble never falls a block height inside a block: it enters the top bore, drops to the
pivot at mid-height, and the **bend there destroys most of its speed** — it arrives moving
straight down and has to leave at 30° below horizontal, and the vertical component simply
goes. Below the bend there is only 12.7 mm of height left to re-accelerate in.

Worse, the bend keeps a *smaller* share the faster the marble arrives: 65% of 1.05 m/s but
only 40% of 3.19. So the exit speed saturates. **1.2 m/s needs about 500 mm of tower**, and
2.4 m/s — the top of the sweep this used to run — would need an arrival speed of 6 m/s even
if the ratio stopped falling at 40%, which is 1.8 m of free fall, and the ratio has not
stopped falling. Call it two metres, and it cannot happen in this system. The old sweep was
measuring a regime that does not exist; the realistic band for anything a child builds is
0.5 to 1.0 m/s.

That the catcher survived anyway is luck, not method: it was being over-tested, and had it
scored marginally the decision would have been made on the wrong numbers.

Two smaller things fell out of the same measurement. The exit *dip* is 30–34°, which is what
was assumed. The exit *height* was not: `catch_exit_z()` is where the bore's axis crosses
the face, but a 16 mm ball rides on the floor of a 20 mm bore, so its centre passes 2 mm
lower — measured at 15.0 against an axis at 17.3. Right for cutting the port, wrong for
placing the marble, and the simulation now subtracts it.

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
