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
  mechanisms/   spiral (CylinderLadder)  catcher (the moulded bowl)  flag_spinner (FlagTower)
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

### The catcher is sized by simulation, not by the photograph

The bowl is the one piece here whose shape is decided by a measurement rather than by
copying. `sim/` scores it on the only thing it is for — the fraction of marbles it keeps —
and the defaults are the best of a sweep over topology, diameter, rim height and depression
depth. Retention is over 1.2 to 2.4 m/s, 30 entries per point (spread across the 20 mm bore
and restitution 0.35–0.75, so about ±18 on any one figure):

| | retention | volume |
|---|---|---|
| photo proportions, block on a boss beside it, Ø112 × 26 | 71 % | 124 cm³ |
| port topology, Ø96 × 44, 4 mm wall, 8 mm depression | 98 % | 105 cm³ |
| **this** — 2.5 mm wall, 4 mm depression, inward lip | **98 %** | **75 cm³** |
| flat floor as well | 88 % | 62 cm³ |

A **tapered bowl** was the one structural alternative left and the simulator rejected it.
Letting the wall flare outwards as it rises should have let the wall do the gathering and
the floor go thin — 55 cm³ against 75. But a wall that flares leans *away* from a marble
coming up it, so it launches rather than returns: 24–60 % retention against 98 %. Retention
wants the opposite, the wall leaning back over the bowl, which is what `CATCH_LIP` does.
`CATCH_TAPER` is left in at 0 so the dead end stays reproducible.

Most of the material was the **floor**: a solid 11 mm disc under a depression that only
needed to be 4 deep, plus a 4 mm wall 41 tall. Halving the depression, thinning the wall to
2.5 and trimming the pad took **29 % out with no retention cost**. Going further does cost —
a flat floor saves another 13 cm³ and gives back 10 points, so the depression is earning its
keep. The top of the wall also leans inwards 8 mm at 45°: both surfaces lean together so the
wall keeps its thickness, which means it *removes* material, it is self-supporting to print,
and a marble running up the wall meets a face pointing back into the bowl.

`-D CATCH_D=112 -D CATCH_H=26 -D CATCH_DISH=5 -D CATCH_DISH_R=46 -D CATCH_SLOT_R=34
-D CATCH_DOCK_H=26` puts the shallow photo-shaped bowl back.

**The block plugs in.** On one side the bowl grows a pad carrying the system's Ø30 socket,
so a block seats on it by its stud and the run stacks up from there like any tower — the
catcher is the base. `CATCH_DOCK_H` picks the whole topology and is the number that matters:

- **as tall as the rim** — the boss puts the block's face on the bowl's inner wall, so it
  overhangs and drops the marble straight in. Simple, but the marble then falls the full
  height of the boss, and that fall is what it leaves with.
- **low (the default)** — the pad only has to be deep enough for the socket, the block
  stands outside the wall, and the marble comes in through a **port pierced through the
  wall** at exit height. The wall stays whole above and below it, the drop is 19 mm instead
  of 35, and the pad costs a third of the material. This is worth 25 points of retention.

The port is sized by the **trajectory**, not by the marble: it arrives descending 30°, so
crossing 4 mm of wall it drops another 2.3. Sized for the marble alone it clips the bottom
lip on the way in — tried at 20 mm high, that alone cost 17 points.

**The floor gathers.** It falls away to a central depression so the marbles roll to the
middle and stay in a heap instead of scattering. The profile is an arc revolved, tangent to
the flat ledge at `CATCH_DISH_R`, so there is no step to trip a marble. A ring of ten radial
slots sits around it, as the original has. Deeper is not better — at `CATCH_DISH=14` the
ledge rises past the port and the marble lands on it, which halves retention.

There is no deflector. The original has a lip in the mouth and the first version copied it,
but the mouth is gone with the port, and measured against a marble the lip only ever cost:
standing 17 mm it reached above the marble's centre and **turned** it rather than braking
it, and a turned marble hits the far wall glancing instead of head-on, keeps its speed and
circulates until it gets over the rim. `CATCH_VANE_H` still builds it if you want it.

The floor is left **solid**. Shelling it would want either a 15° unsupported ceiling or a
pocket far too shallow to self-support, so the place to hollow this out is the slicer's
infill, not the model. The moulded-in branding on the original is deliberately not
reproduced.

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
141 × 96 × 44, `spiral` 52 × 52 × 114, `flag` 168 × 68 × 80, `rail_straight` 180 × 44.

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
