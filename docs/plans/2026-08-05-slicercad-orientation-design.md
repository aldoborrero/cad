---
title: Print orientation from the load case
project: slicercad
date: 2026-08-05
status: research updated; pure scoring spike exists, product integration unimplemented
summary: >
  The slicers already choose a print orientation, and they do it well — but only
  for printability: overhang, bed contact, stability. Neither knows what the part
  is for, because neither has the loads. That information exists only in the CAD,
  which makes orientation-from-the-load-case the one thing slicercad can offer
  that the slicer structurally cannot. This records what was verified in
  BambuStudio's, OrcaSlicer's, FreeCAD's and CalculiX's own source, what was
  measured against the installed binaries, and the three implementation tiers
  that follow from it.
verified_against:
  - BambuStudio src @ .scratch/bambustudio
  - OrcaSlicer 2.4.2 src + the installed binary
  - PrusaSlicer src (to establish provenance)
  - FreeCAD 1.1.1 src, and upstream main a61ee58c26 (2026-07-31)
  - CalculiX ccx 2.22 src
open_questions:
  - >
    Volume-lumped nodal CVaR settles on the repeated C3D10 cantilever study while
    the nodal peak diverges. It is now the candidate statistic, but its orientation
    ranking has not been tested across the geometry suite. Integration-point
    output is the fallback when A0 does not stabilise.
  - >
    Allowables have a candidate source (MyTechFun) that measures exactly the two
    specimens needed, but its licence is unread and the complete dataset is behind
    Patreon. Nothing is settled until both are.
  - Bambu Studio's binary was never tested; only OrcaSlicer is installed here.
  - The slicer's cost table is debug output on stdout, not an API.
---

# Print orientation from the load case — design

Date: 2026-08-05
Status: research updated; pure scoring spike exists, product integration unimplemented

## Where this came from

Feedback on slicercad, paraphrased: restricting yourself to the print area is not
high on the priorities when designing a part; what matters far more is print
orientation based on application; and when something is too big, the slicer's cut
tool solves it. The conclusion offered was that the useful thing would be
optimising print orientation from FEA results.

That is right about the weak part. slicercad's fit check is a bounding-box test,
so it is both conservative and approximate, and the slicer already refuses a part
that does not fit and ships a cut tool for the part that genuinely does not. We
were solving a solved problem, worse, one layer upstream.

It is not right that orientation is missing. `bed.placement_from_face` — "rest
this face on the plate" — *is* choosing the print orientation, and the drawn bed
exists to show which one you chose. The mistake was presenting the workbench as a
fit checker. That is a framing fix before it is a code fix.

## What the slicers already do, and it is more than expected

**Auto-orientation exists in both, and it is Bambu's own work.** `libslic3r/Orient.cpp`
is present in BambuStudio and OrcaSlicer and absent from PrusaSlicer, which both
forked from — so it is not inherited. The two have since diverged: Bambu 788
lines against Orca's 544, the difference being a cooling-fan direction term
(`areas_cooling`, `has_cooling_fan`) that Orca does not have.

The cost model is entirely about printability:

```cpp
struct CostItems {
    float overhang, bottom, bottom_hull, contour;
    float area_laf;                      // low-angle faces
    float area_projected;
    float height_to_bottom_hull_ratio;   // "affects stability, the lower the better"
    float unprintability;                // the scalar it minimises
};
```

Candidates are not sampled off a sphere. `area_cumulation_accurate` accumulates
face area per normal over the mesh and over its convex hull (10 and 14 directions
respectively), adds supplements, and deduplicates. That is the same
geometric heuristic anyone would reach for first, already written and already
tuned.

**It runs headless, and it reports everything.** `orient` sits in
`CLITransformConfigDef` next to `arrange` and `cut`. Measured against the
installed OrcaSlicer 2.4.2 rather than read:

```
orca-slicer --orient 1 --export-3mf out.3mf tall.stl
```

A 10 × 10 × 120 tower came back laid flat. The mesh is untouched in its own frame;
the chosen orientation is a 4×4 matrix in `Metadata/model_settings.config`
(a −90° rotation about X), and the build item's `z = 5` — half of 10, not half of
120 — confirms it. On the way it prints its whole cost table to stdout, one line
per candidate:

```
                    overhang, bottom, bothull, contour, A_laf, A_prj, unprintability
orientation: 1.0000 -0.0000 -0.0000, cost:0.0, 1800.0, 1200.0, 169.7, 0.0, 0.0,    0.0
orientation:-0.7071 -0.0000  0.7071, cost:1300.0, 0.0,    0.0,   0.0, 0.0, 0.0, 3430.6
```

So the full ranking is available, not just the winner. **Consulting it beats
reimplementing it** — and reimplementing it would have been the second time we
rebuilt something the slicer already does.

## What no slicer can do

Searching `Orient.cpp` for tensile, anisotropy, interlayer or stress returns
nothing, and that is structural rather than an omission. The scalar is named
`unprintability`. A slicer has no loads, no constraints and no use case; it
receives a mesh. Which orientation *survives service* cannot be computed from
what a slicer is given.

That information exists in the CAD and nowhere else. It is the whole opportunity.

## The property that makes it affordable

The stress field is fixed in the part's own frame. Reorienting for printing
rotates the **layer planes**, not the loads — the loads travel with the part. So
the expensive step, solving, does not have to be repeated per candidate
orientation; only the direction-dependent evaluation does.

## What FreeCAD gives us

The FEM workbench ships with the nixpkgs build, and `calculix-ccx` 2.22 is in
nixpkgs. The result object exposes the full stress tensor per node as
`App::PropertyFloatList`, readable straight from Python:

```
NodeStressXX/YY/ZZ/XY/XZ/YZ    PrincipalMax/Med/Min    vonMises
```

Six components is enough to rotate the tensor into any candidate build frame.

## Orthotropic materials: the gap is one function

This was researched because an anisotropic failure criterion is the point, and it
turned out to be a chain with exactly one link missing.

**CalculiX supports it fully.** `elastics.f` parses all three forms, and
`orientations.f` means `*ORIENTATION` is supported too:

```fortran
'ORTHO'                 -> ityp=9   engineering=.false.
'ENGINEERINGCONSTANTS'  -> ityp=9   engineering=.true.
'ANISO'                 -> ityp=21
```

**FreeCAD already models it.** `Mod/Material/Resources/Models/Mechanical/OrthotropicLinearElastic.yml`
defines exactly the nine engineering constants CalculiX wants: `YoungsModulusX/Y/Z`,
`PoissonRatioXY/XZ/YZ`, `ShearModulusXY/XZ/YZ`.

**Nothing in `Mod/Fem` consumes that model.** Its only consumers are the Material
module's own tests and its UUID registry. The writer emits an isotropic card and
nothing else — `femsolver/calculix/write_femelement_material.py:122`:

```python
f.write("*ELASTIC\n")
f.write(f"{YM_in_MPa:.13G},{PR:.13G}\n")
```

That region is **byte-identical in FreeCAD 1.1.1 and in upstream main**
(`a61ee58c26`, 2026-07-31), so it is not something a version bump fixes.

**A fork bridges it.** [`jwharington/FreeCAD`, branch `fem-orthotropic`](https://github.com/jwharington/FreeCAD/tree/fem-orthotropic)
writes the right card, reading the very property names the stock model defines —
verified in its source, not in its description:

```
*ELASTIC,TYPE=ENGINEERING CONSTANTS
E_X, E_Y, E_Z, ν_XY, ν_XZ, ν_YZ, G_XY, G_XZ
G_YZ, 293.15
```

Its companion [FreeCAD-CompositesWB](https://github.com/jwharington/FreeCAD-CompositesWB)
adds laminates, local coordinate systems and Tsai-Wu/Hashin failure criteria.
Caveats worth stating before anyone depends on it: it **requires the fork**, it is
not in the Addon Manager, no licence was visible, and its activity could not be
established (171 commits, last date not shown). Upstream tracks the topic in
[issue #11642](https://github.com/FreeCAD/FreeCAD/issues/11642) and
[discussion #24843](https://github.com/FreeCAD/FreeCAD/discussions/24843) (Nov 2025),
where maintainers point contributors at this effort.

Note the fork's material module does **not** write `*ORIENTATION`.

## `*ORIENTATION` is the interesting card, for a reason that is not composites

`*ORIENTATION` rotates the *material axes* without moving the part. For laminates
that expresses fibre direction varying across a part. For us it does something
better: **mesh once, keep loads and constraints fixed, and re-solve with a
different orientation card per candidate build direction.** Same mesh, exact
treatment of stress redistribution, and meshing — usually the expensive step —
happens once.

## Where the allowables can come from

[MyTechFun](https://www.mytechfun.com/) — Dr. Igor Gaspar, a mechanical engineer
who publishes filament tests — already measures **exactly the two specimens this
needs**, at the same 4 × 4 mm minimum cross section:

- tensile, printed **horizontally** → the in-plane allowable
- layer adhesion, printed **vertically** → the interlayer allowable

That is the same protocol anyone would design for this from scratch, already run
across a large catalogue of filaments, with spreadsheets published per test.

Two of them were read (kept in `.scratch/mytechfun/`, never an input to a build).
They do not merely supply numbers — **they settle the argument about hardcoding
one**.

**Sixteen PLA brands, one printer** (Prusa MK3S, 210/60 °C), layer adhesion in MPa:

```
PolyPlus 61.5   3DQF 59.2   BQ 58.3   Prusament 57.4   AzureFilm 56.6
Sunlu 52.0   3Dee 48.6   Overture 46.2   Hatchbox 46.1   Geeetech 19.4
```

A factor of three, everything labelled "PLA".

**Ten printers, one filament** ([video 381](https://www.mytechfun.com/video/381),
break force in kg):

```
Sovol SV08 "fixed" 64.2   FLSUN SR 56.7   BambuLab A1 52.8   X1C 52.6
Prusa MK4 42.9   Creality K1 41.9   Ender-3 S1 46.1
Ender-3 S1, large retraction 25.9        Sovol SV08 before the fix 48.3
```

The last two lines are the important ones: **the same printer, one setting
changed**. Retraction costs the Ender 44 % of its layer adhesion; the Sovol gains
33 % from a configuration fix. Neither the machine nor the material moved.

So the interlayer allowable is not a property of "PLA". It is a property of this
machine, this filament and these settings — which is why it stays a configured
value with a cited source, and why a table constant compiled into the addon would
be inventing precision.

What this changes: a user no longer has to run their own tensile tests to get
started. Published figures are a defensible default; measuring your own remains
the way to make them yours.

**Unresolved before any of it is used.** The complete database
(`2025-08-24-all-results-mytechfun.xlsx`) is on Patreon, not in the open, and the
public per-video sheets are partial — the 16-brand sheet carries layer adhesion
only, that video being part 3 of 3, with the tensile half elsewhere. The site's
terms of use were fetched but did not render to readable text, so **the licence is
unread**: citing results is one thing, redistributing a dataset is another, and
this needs settling — probably by asking him — before a number of his ships in
this repository. Some results are reported as kilograms of force rather than MPa;
the 4 × 4 mm section converts them, provided the break really occurs there.

## The nodal statistic does not converge, and that is the open decision

Measured, not feared. A 100 × 10 × 10 cantilever in PLA, one face fully fixed,
50 N spread over the top, meshed by gmsh at five sizes and solved by ccx. The
analytic answers are 15.000 MPa of bending at the root and 2.143 mm of tip
deflection. The first study used FreeCAD's default `ElementOrder = "1st"`; the
generated deck was later inspected and contains `TYPE=C3D4`.

```
   mesh   nodes  deflection      max      p99      p95      p90     mean
    8.0     126       0.841   11.913    6.347    5.037    2.590    0.765
    5.0     199       1.281   12.205    8.668    5.398    3.821    0.923
    3.0     744       1.702   15.030   11.169    7.023    5.148    1.366
    2.0    1760       1.861   17.109   11.464    7.648    5.180    1.367
    1.5    3835       1.982   18.364   11.751    8.127    5.419    1.433
```

The very slow displacement convergence is substantially the known bending
stiffness of linear tetrahedra, not just mesh size. This table confirms the model
and units, but C3D4 was an inadequate family on which to dimension the product's
convergence method. It also used one generated mesh per target size; later
repeated remeshing showed that target size alone does not identify a mesh.

The study was therefore repeated with `ElementOrder = "2nd"` and
`SecondOrderLinear = False`, three independently generated meshes at every size,
and the actual output card checked in every deck: `TYPE=C3D10`. These are the
medians of the three runs:

```
   mesh   nodes  elements  deflection      max      p99      p95      p90     mean
    8.0     646       271       2.128   16.801   14.639   10.177    6.501    1.713
    5.0    1085       502       2.134   17.224   14.266    9.810    6.274    1.667
    3.0    4257      2221       2.141   19.395   13.629    9.066    6.096    1.650
    2.0   11271      6475       2.143   19.517   12.890    8.373    5.468    1.467
    1.5   25541     15458       2.144   22.898   12.640    8.223    5.396    1.451
```

Second-order displacement is within 0.7% at the coarsest level and reaches the
analytic value by size 2.0. That removes the C3D4 stiffness confound.

**The peak does not converge.** The C3D10 median rises 17.3% between the two
finest levels and reaches 22.898 MPa. The 15 MPa beam-theory result is not a
target for this peak: it anchors regular bending away from the restraint, while
the idealised fully fixed three-dimensional boundary is singular. Exceeding 15
MPa is expected; trying to force the peak back to it would be wrong. Within-size
peak spread in this first repeated study is at most 2.4%. A later 21-run A0 study
found isolated peak ranges around 6% at sizes 2.0 and 1.2, further evidence that
the single hottest extrapolated node is erratic. Neither observed spread explains
or arrests the rising sequence. `peak_normal_stress` measures how finely the user
meshed as much as it measures the part.

Two consequences, and the second is worse than the first. The singular peak
cannot be compared with an allowable. And the ranking is only safe while the
peaks of the competing orientations do not all sit in the same artificial
singularity — here upright scored 90 % worse than the alternatives, comfortably
outside any of this, but that is a property of a cantilever whose bending stress
is genuinely axial, not a guarantee.

A high nodal percentile is not a clean answer either. In the C3D10 study p99
moves in the opposite direction, 14.639 → 12.640 MPa, as the nodal population
changes. **It is a percentile over nodes, and gmsh puts nodes where it likes**, so
a refined region carries more of them and drags the percentile with it. A
percentile over nodes is mesh-dependent by a second route.

What would actually be defensible is a volume-weighted statistic: integrate over
elements, so refining the mesh subdivides the same volume rather than adding
votes. `FemMesh` has connectivity and coordinates but no element volumes; those
must be calculated by element type. C3D4 is a cheap first case with constant
Jacobian and one integration point. C3D10 needs isoparametric integration for a
general curved element: FreeCAD's own `meshtools.py` carries a FIXME that its
midnode geometry shortcut is exact only when midside nodes lie on the corner-node
lines.

A provisional route distributes each element's calculated volume among its
nodes and applies a weighted tail statistic to the nodal stresses FreeCAD already
reads. It was measured over seven C3D10 sizes, three remeshes each. All 21 meshes
conserved the 10,000 mm³ solid volume exactly; midside nodes were exact midpoints
for this straight box.

```
   mesh  nodes/element  nodal max  nodal p99  weighted p99  CVaR 1%  CVaR 5%
    8.0          2.379     16.862     14.697        12.546    14.312    11.113
    5.0          2.166     17.603     14.068        12.655    14.050    10.920
    3.0          1.907     19.358     13.575        12.162    13.583    10.085
    2.0          1.741     19.520     12.892        11.580    13.109     9.697
    1.5          1.654     22.890     12.643        11.303    12.811     9.579
    1.2          1.598     24.520     12.442        11.222    12.628     9.519
    1.0          1.551     26.155     12.123        11.108    12.541     9.487
```

That exact volume is a limitation of the fixture, not validation of the general
geometry. `max_midpoint_error = 0` on every row means every quadratic node lay on
the straight line between its corner nodes, so the C3D10 mapping was affine and
the corner determinant was exact by construction. Curved parts still require
isoparametric integration and a fixture with non-zero midpoint deviation.

Nodes per element fall 34.8%, directly measuring the changing representation of
surface nodes. The weighted percentile still drifts, but CVaR settles over the
two finest steps: −1.43%, then −0.69% for the 1% tail; −0.62%, then −0.34% for
the 5% tail. At 1.0 mm the corresponding remeshing spreads are 0.12% and 0.02%.

Treating the last contracting increments as an empirical geometric tail gives
limits near 12.460 MPa and 9.450 MPa; the finest CVaR values are about 0.64% and
0.39% above them. Their final changes are about 6 and 21 times their respective
remeshing spreads. The peak cannot use this estimator because its increments do
not contract consistently. These are not formal Richardson extrapolations: mesh
ratios are unequal and the asymptotic tail is short, so the limits are estimates
to report with their observed ratios, not continuum truths.

The 5% tail is closer to its estimated limit and has the better signal-to-noise
ratio; the 1% tail is more local and therefore closer to a failure-initiation
question. The geometry suite must carry both and decide from ranking stability
and critical-region locality instead of fixing one from this cantilever.

So volume-lumped nodal CVaR is now the candidate first implementation, not just
a disposable shortcut. It still retains extrapolated stresses and has only
passed one geometry; the ranking study must decide whether it is sufficient. The
integration-point route — patch the generated `.inp` with `*EL PRINT`, own a
second CalculiX run and read the `.dat` — becomes a cross-validation or fallback
when A0 fails, rather than a prerequisite assumed in advance.

## Three tiers

1. **One isotropic solve, direction-dependent failure index.** Needs nothing that
   stock FreeCAD lacks; the tensor is already exposed. Cheap. Ignores the stress
   redistribution that anisotropy actually causes — an approximation to declare,
   not to hide.
2. **One mesh, N orthotropic solves via `*ORIENTATION`.** Exact, and affordable
   because the mesh is reused. **This does not require the fork**: the `.inp` is
   text, so FreeCAD can write it, we substitute the `*ELASTIC` block and add
   `*ORIENTATION`, and call `ccx` ourselves. Tens of lines against a documented,
   stable format, versus a dependency on a fork with no visible licence.
3. The fork plus CompositesWB. Heavier, and aimed at laminates rather than at
   deposited parts.

## Division of labour

We answer *which orientations survive the load*. The slicer answers *which of
those prints well*, and it already does that better than we would. Its
`unprintability` becomes the second criterion, not a competitor, and its own
candidate generation can seed ours.

## What is not settled

- **Allowables have a source, but not yet a licence.** See below. Tsai-Wu and
  Hashin still do not rescue the criterion: they are laminate criteria, so not
  even the criterion is inherited.
- **Bambu Studio's binary was never tested.** Only OrcaSlicer is installed here,
  and Bambu is deliberately absent from the devshell (unfree, never substituted).
  Whether `--orient` behaves identically there is assumed, not known.
- **The cost table is `std::cout` debug output**, not a documented interface.
  Parsing it is fragile and could break on any release. The 4×4 matrix in
  `model_settings.config` is the sturdier read.
- **Whether `--orient` accepts a supplied candidate set.** Almost certainly not; it
  computes its own. If we need our candidates scored, we may have to score them.
- **Scope.** slicercad is roughly a thousand lines that export and open a slicer.
  This is a different product with a different failure mode: it returns an answer
  that looks authoritative. Worth building, worth building separately, and worth
  holding to measured numbers.

## Decisions taken

- Do not reimplement orientation search. Consult the slicer.
- Reframe the bed as an orientation tool; the fit check is a detail, not the pitch.
- Prefer patching the `.inp` over depending on the fork, if tier 2 is attempted.
- Do not ship a failure index until there are allowables to put in it.
