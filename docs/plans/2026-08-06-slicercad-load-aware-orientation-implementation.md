---
title: Load-aware print orientation implementation plan
project: slicercad
date: 2026-08-06
status: ready for implementation, with a validation gate before product integration
follows: 2026-08-05-slicercad-orientation-design.md
baseline:
  - feature/orientation @ dfd2611
  - docs/fea-orientation @ a71b3da
---

# Load-aware print orientation — implementation plan

## Outcome

Given a solved FreeCAD FEM load case, slicercad will answer:

> Which printable orientations expose the interlayer bonds to less damaging
> stress, and how confident are we that the order is independent of the mesh?

The result is a recommendation, not a load rating. The first useful release must
be able to say that orientation B is mechanically preferable to A, show why, and
say when the evidence is too close or too mesh-dependent to choose.

The slicer remains responsible for overhangs, support, bed contact and stability.
slicercad contributes the information that the slicer cannot have: loads,
constraints and the resulting stress field.

## Reviewer requirement: diagnose the ranking

Samuel, whose original remark led to load-aware orientation, stated the product
need directly:

> the interesting thing would be able to see a ranking — because if there are two
> orientations that score similarly it may be that the part is just badly designed
> for the application, or rather if two orientations are competing
>
> as an example would be a shape with multiple load paths but it's not possible to
> orient the part so that doesn't have one of the load paths oriented normal to the
> print bed and so that would be a risk of delamination

The implementation must therefore preserve the shape of the ranking: margins,
whether a tie is numerical or physical, whether tied candidates fail in the same
region, and how much orientation can reduce layer-normal tension at all. These
are additions to the existing mechanics and A0 sampling decisions, not changes
to either.

## Product boundary

In scope for the first release:

- rank candidate layer planes from one isotropic linear-elastic solve;
- account for both opening and shear traction across the layers;
- use a volume-weighted tail statistic rather than a nodal maximum;
- check whether the ranking is stable under mesh refinement;
- preserve mechanical and printability scores as separate dimensions;
- show per-channel margins, classified ties and the regions responsible;
- report an allowable-free orientation-sensitivity ratio;
- apply the selected orientation to the existing bed/export workflow.

Explicitly out of scope:

- claiming that a part is safe or will carry a stated load;
- embedding generic PLA/PETG allowables;
- certification or factors of safety;
- nonlinear fracture, fatigue, creep, temperature and impact;
- automatic remeshing of arbitrary user models in the first UI release;
- replacing the slicer's orientation search or support calculation;
- orthotropic re-solves until the isotropic ranking has passed validation.

## Starting point

`feature/orientation` already contains the pure module and its tests:

```
nix/packages/slicercad/freecad/slicercad/orient.py
nix/packages/slicercad/tests/test_orient.py
```

It currently provides:

- conversion of FreeCAD's six nodal stress-component lists into tensors;
- `n^T sigma n` for a candidate build direction;
- a maximum tensile normal-stress score;
- candidates derived from planar face normals, with opposite signs collapsed;
- deterministic candidate grouping and ordering.

That is a sound mathematical spike, but `peak_normal_stress` must not become the
product score. A fixed-face singularity makes its value grow with refinement,
and it ignores shear acting along the layer interface.

### Reference-element correction

The original five-mesh cantilever study used FreeCAD/gmsh's default first-order
setting. The generated CalculiX deck contains `TYPE=C3D4`, not `C3D10`. That
explains the very slow displacement convergence: linear tetrahedra are overly
stiff in bending. The original table is still evidence about that exact model,
but it must not define the validation method for a second-order production
workflow.

The same study was repeated on 2026-08-06 with `ElementOrder = "2nd"`,
`SecondOrderLinear = False`, and three independent remeshes per requested size.
The generated deck was checked and contains `TYPE=C3D10` in all 15 runs. Medians:

| Size | Nodes | Elements | Deflection | Nodal max | Nodal p99 | Nodal p95 |
|---:|---:|---:|---:|---:|---:|---:|
| 8.0 | 646 | 271 | 2.1278 | 16.8006 | 14.6389 | 10.1774 |
| 5.0 | 1,085 | 502 | 2.1345 | 17.2235 | 14.2659 | 9.8100 |
| 3.0 | 4,257 | 2,221 | 2.1413 | 19.3954 | 13.6291 | 9.0665 |
| 2.0 | 11,271 | 6,475 | 2.1430 | 19.5165 | 12.8897 | 8.3729 |
| 1.5 | 25,541 | 15,458 | 2.1444 | 22.8980 | 12.6403 | 8.2230 |

The analytic deflection is 2.1429 mm and the beam-theory root stress is
15.0000 MPa. Second order removes the stiffness problem almost immediately, but
does not rescue the nodal peak: it rises 17.3% between the two finest levels and
ends at 22.898 MPa. The 15 MPa beam-theory value is not a convergence target for
this peak: it describes regular bending away from the fully fixed boundary,
whereas the three-dimensional idealised restraint is singular. Do not tune any
statistic to make the peak return 15 MPa. The nodal p99 moves in the opposite
direction, falling as the nodal population changes. This strengthens the case
against both a nodal maximum and an unweighted nodal percentile.

The A0 volume-lumped experiment was then run over the same five levels plus 1.2
and 1.0 mm, again with three independent remeshes. Every C3D10 in this straight
box had its midside nodes exactly at edge midpoints, the corner determinant was
therefore valid for this fixture, and both element and lumped nodal volumes
summed to 10,000 mm³ in all 21 runs. Medians:

| Size | Nodes/element | Nodal max | Nodal p99 | Weighted p99 | CVaR 1% | CVaR 5% |
|---:|---:|---:|---:|---:|---:|---:|
| 8.0 | 2.379 | 16.862 | 14.697 | 12.546 | 14.312 | 11.113 |
| 5.0 | 2.166 | 17.603 | 14.068 | 12.655 | 14.050 | 10.920 |
| 3.0 | 1.907 | 19.358 | 13.575 | 12.162 | 13.583 | 10.085 |
| 2.0 | 1.741 | 19.520 | 12.892 | 11.580 | 13.109 | 9.697 |
| 1.5 | 1.654 | 22.890 | 12.643 | 11.303 | 12.811 | 9.579 |
| 1.2 | 1.598 | 24.520 | 12.442 | 11.222 | 12.628 | 9.519 |
| 1.0 | 1.551 | 26.155 | 12.123 | 11.108 | 12.541 | 9.487 |

`volume_error = 0` and `max_midpoint_error = 0` do **not** validate curved C3D10
volume integration. They prove that this planar box produced affine tetrahedra,
for which the corner determinant happens to be exact. A curved fixture with at
least one midside node off its corner-node line is required before the geometry
implementation can claim general C3D10 support.

Nodes per element fall 34.8% across the study, directly measuring the changing
vote given to surface nodes by an unweighted statistic. The weighted percentile
still moves, but CVaR settles: over the two finest steps CVaR 1% changes -1.43%
then -0.69%, and CVaR 5% changes -0.62% then -0.34%. At 1.0 mm their remeshing
spreads are only 0.12% and 0.02% respectively.

An empirical geometric-tail extrapolation of the last contracting increments
estimates limits near 12.460 MPa for CVaR 1% and 9.450 MPa for CVaR 5%; the
finest results are about 0.64% and 0.39% above those estimates. The final signal
is roughly 6 times the remeshing spread for CVaR 1% and 21 times for CVaR 5%.
The observed tail contraction ratios are approximately 0.63, 0.61 and 0.48 for
CVaR 1%, and 0.30, 0.51 and 0.54 for CVaR 5%. The maximum does not meet the
estimator's premise because its increments do not contract consistently.

These are empirical sequence limits, not formal Richardson extrapolations: the
mesh-size ratios are unequal and only a short asymptotic tail is available. Store
the observed increments, contraction ratios and estimator with the result; do
not present either extrapolated value as an exact continuum answer.

This is enough to promote `nodal_volume_lumped` CVaR from a disposable spike to
the candidate first implementation. It passes the cantilever magnitude test; it
still has to preserve orientation rankings across the Phase 3 geometry suite.
Integration-point output is now a cross-validation and upgrade path, not an
automatic prerequisite for the first product gate.

## Environment prerequisites

The repository devshell does not currently provide the two programs required by
the validation chain. Before implementing the FEM adapters, add `gmsh` and
`calculix-ccx` to `nix/devshell.nix` and verify their actual executable names and
versions inside `nix develop`.

All validation commands must resolve the executables from `PATH`, record their
versions and fail early with a useful message when either is absent. Do not put
Nix store paths in the addon. A clean checkout entering the devshell must be able
to run the end-to-end validation command without separately installed software.

## Mechanical model

For a stress tensor `sigma` and unit build direction `n`, the traction acting on
a layer plane is:

```
t       = sigma n
sigma_n = n . t
tau     = ||t - sigma_n n||
```

The two quantities used by the product are:

```
opening = max(sigma_n, 0)
shear   = tau
```

Compression is excluded from the opening channel, but not from shear. Keep both
channels in MPa and do not silently combine them under an assumption that the
interlayer tensile and shear strengths are equal.

If the user later supplies calibrated interlayer allowables `Z_t` and `S`, an
optional mixed-mode index may be added:

```
index = sqrt((opening / Z_t)^2 + (shear / S)^2)
```

This is still a configured engineering model, not a universal FDM failure law.
The UI and stored result must identify the formula and its inputs. Until both
allowables exist, compare opening and shear independently and use Pareto
dominance: one orientation is mechanically better only when it is no worse in
either channel and better in at least one. A trade-off is reported as such, not
collapsed into an invented winner.

## Sampling and statistic

### What FreeCAD provides, and what it does not

Stock FreeCAD writes `*EL FILE` with `S, E`; CalculiX puts those results in the
`.frd` after extrapolating them to nodes. FreeCAD deliberately leaves `*EL PRINT`
commented out in `write_step_output.py` because its CalculiX result reader does
not support integration-point output. It therefore cannot be enabled by a solver
preference or consumed through `ccxtools.FemToolsCcx` unchanged.

`FemMesh` provides node coordinates, element connectivity and element counts. It
does not provide element volumes. Both the provisional nodal weighting and the
target integration-point weighting therefore need geometry integration by
element type.

For a curved quadratic tetrahedron such as the ten-node tetrahedra generated by
gmsh, the volume is not generally the corner-node `tet4` volume. Implement the
isoparametric mapping for each supported element type and evaluate:

```
sample_volume_i = abs(det(J(xi_i))) * quadrature_weight_i
element_volume  = sum(sample_volume_i)
```

This is also an upstream-known limitation, not a hypothetical edge case:
FreeCAD's `src/Mod/Fem/femmesh/meshtools.py:1192` has a FIXME stating that its
midnode area calculation is exact only when midside nodes lie on the lines
between corner nodes. The same geometric assumption must not enter the volume
weights.

The quadrature point coordinates, order and weights must match the element's
CalculiX formulation. The parser must map CalculiX integration-point numbers to
that same order. Start with the exact solid types produced by the validation
models and reject every unsupported type explicitly.

Implement `C3D4` first: it has straight sides, a constant Jacobian, direct
determinant volume and one CalculiX integration point, so it is the smallest
end-to-end parser/weighting fixture. Then implement `C3D10` before evaluating
curved production geometry. For second-order elements, do not reuse the C3D4
corner determinant except as a test case where every midside node is known to be
linear.

### A0 data path: volume-lumped nodal stresses

Build the complete scoring and validation pipeline first with data FreeCAD
already reads:

1. Read the six extrapolated nodal stress lists from the result object.
2. Calculate every supported element's physical volume with the element geometry
   code above.
3. Distribute each element volume equally among its participating nodes and sum
   contributions at shared nodes.
4. Pair each nodal tensor with its accumulated nodal volume and calculate the
   weighted statistics.
5. Verify that the nodal weights sum to the integrated mesh volume.

Equal distribution is deliberately a positive lumping rule, not an exact
quadrature rule. It removes the known defect where locally dense mesh regions get
more votes merely because they contain more nodes, but it still uses stresses
extrapolated into a singular region. Name and persist this source as
`nodal_volume_lumped`; never present it as integration-point data.

This path is Hito A0: it unblocks the mechanics API, candidate pipeline and the
whole repeated-mesh validation harness while the CalculiX runner/parser is being
built. The cantilever experiment above shows that volume-lumped CVaR can settle
even while the nodal peak diverges. A0 may close the first product gate if it also
stabilises the orientation ranking across the complete Phase 3 suite; it is no
longer disqualified solely because its stresses were extrapolated to nodes.

### Cross-validation path: CalculiX integration points

The adapter owns a second CalculiX execution:

1. Ask FreeCAD's writer to generate the ordinary `.inp` for the solved analysis.
2. Copy it into a slicercad-owned run directory; do not mutate the user's solver
   artefact in place.
3. Patch the copied input to add `*EL PRINT` stress output for the required
   element set, preserving the existing steps and output requests.
4. Run `ccx` as a cancellable subprocess and retain stdout, stderr, exit status,
   version and patched input for diagnosis.
5. Parse element id, integration-point id and six stress components from the
   resulting `.dat`.
6. Join every record to the matching geometry quadrature point and its physical
   sample volume.
7. Verify that sample volumes sum to the integrated mesh and CAD solid volumes
   within documented tolerances.

Reusing FreeCAD's input writer avoids recreating materials, loads and boundary
conditions. Patching, process ownership and `.dat` parsing belong to slicercad
because FreeCAD intentionally has no reader for this output. Build this path when
an A0 validation model remains unstable, when curved-element weighting requires
an independent check, or after Milestone B to measure the approximation directly.
Do not block an otherwise passing A0 gate merely because this parser is absent.

The pure layer should receive data shaped like:

```python
WeightedStress(stress=(xx, yy, zz, xy, xz, yz), volume=volume)
```

The CalculiX/FreeCAD adapters own solver orchestration, parsing and coordinate
conversion. Element geometry and `orient.py` remain pure and importable without
FreeCAD.

### Tail score

For every candidate and for each channel, calculate volume-weighted CVaR over
both the worst 1% and worst 5% of material throughout Phase 3. Do not designate
one as primary before the geometry suite is measured. The 1% tail stays closer
to local failure initiation; the 5% tail was more reproducible and closer to its
empirical limit in the cantilever. This is a fidelity-versus-stability decision,
not a reason to select the smoother number automatically.

Weighted upper-tail CVaR is the mean of the largest values whose accumulated
weight equals the requested fraction of total volume. The boundary sample must
be split proportionally rather than included whole, otherwise coarse elements
make the result jump.

Return at least:

```python
OrientationScore(
    build=...,
    opening_cvar_1=...,
    opening_cvar_5=...,
    shear_cvar_1=...,
    shear_cvar_5=...,
    total_volume=...,
    critical_samples=...,
)
```

`critical_samples` is keyed by `(channel, tail_fraction)` and contains enough
node/element provenance and contributions to highlight and compare the
responsible region later. Each retained contribution needs a stable sample id
within the mesh, position, tail volume actually consumed by the exact CVaR
calculation, and source node/element provenance. Do not retain every transformed
sample inside the result object if that materially increases memory use.

Candidate-independent diagnostics belong one level above `OrientationScore`:

```python
RankingResult(
    scores=...,
    pareto_front=...,
    margins=...,
    tie_diagnostics=...,
    principal_tension_cvar=...,
    orientation_sensitivity=...,
)
```

CVaR is the initial statistic, not a fact to freeze forever. The validation gate
below compares it with volume-weighted p95/p99 and a high-order `L^p` norm. Keep
the aggregation function replaceable and record its name and parameters in each
result.

### Margins and the Pareto order

Return the signed and absolute gap between adjacent displayed candidates for
every mechanical channel and tail fraction, in MPa. Also retain all pairwise gaps
inside the Pareto front so the top set can be diagnosed without depending on an
arbitrary display order.

Opening and shear may order a pair differently. Do not collapse their margins
into one scalar. An adjacent display position is not a claim of Pareto dominance;
the UI must label a cross-channel trade-off as such.

### Tie classification

Classify a candidate pair separately per channel and tail fraction. Start with a
5% relative tie band:

```
g_r(h)       = score_b,r(h) - score_a,r(h)              # MPa, signed
g_bar(h)     = median_r(g_r(h))
s_x_bar(h)   = median_r(score_x,r(h))                    # x is a or b
gap          = abs(g_bar(h_finest))
relative_gap = 0 if both finest score medians are 0
               else gap / max(s_a_bar(h_finest), s_b_bar(h_finest))
u_gap        = max(spread_r(g_r(h_finest)),
                   abs(g_bar(h_finest) - g_bar(h_previous)))
u_x          = max(spread_r(score_x,r(h_finest)),
                   abs(s_x_bar(h_finest) - s_x_bar(h_previous)))
u_sum        = u_a + u_b                                # diagnostic only
```

Use one stable candidate-pair ordering so the sign does not change with display
rank. Pair A and B scores only when they come from the same mesh hash and repeat;
never form gaps from unrelated remeshes. Calculate spread from the signed gaps,
not their absolute values, so an order reversal remains visible. Initially,
`spread_r(x) = max_r(x) - min_r(x)`; store this versioned choice with the result
and change it only from Phase 3 evidence.

`u_gap` is the resolution estimate because evaluating both candidates on the
same field creates correlated errors. `u_sum` discards that covariance and takes
the worst-case sum of the individual errors; retain it in Phase 3 to measure how
many distinctions that conservative assumption would suppress, but never use it
for classification when paired gaps are available. On the measured cantilever
CVaR sequence, the contraction ratio of about 0.48 makes the last score change
about 1.1 times the extrapolated residual. That supports the last-step
estimator's conservative direction for that sequence only; the pairwise gaps
still need their own Phase 3 measurements and this is not a universal error
bound.

The 5% band is an initial, versioned diagnostic parameter for Phase 3 to test,
not a hidden truth. Store it with the result. Use these outcomes:

| Outcome | Rule | Meaning |
|---|---|---|
| `below_resolution` | `gap <= u_gap` | The measurement cannot separate the candidates. |
| `physical_shared_region` | `gap > u_gap`, `relative_gap <= tie_band`, same critical region | One weak region dominates both. |
| `physical_distinct_regions` | `gap > u_gap`, `relative_gap <= tie_band`, distinct critical regions | Competing load paths. |

Pairs outside the tie band are resolved, not a fourth tie type. Without repeated
matched mesh data, do not substitute `u_sum` or guess `u_gap`: leave the
diagnostic `not_checked` and assign no physical tie label. Apply the relative tie
band only after `gap > u_gap`; it decides whether a resolved pair is an
interesting near-tie, not whether the pair is numerically distinguishable.

Compare critical regions with weighted Jaccard overlap of their CVaR tail-volume
maps:

```
overlap = sum_i min(tail_volume_a[i], tail_volume_b[i])
          ------------------------------------------------
          sum_i max(tail_volume_a[i], tail_volume_b[i])
```

Start with `same_region_overlap = 0.5`. Since equal tail fractions contain equal
total volume, this requires at least two thirds of the tail volume to be shared.
Record the overlap, threshold, channel, tail fraction and mesh identity in the
classification. The threshold must have named tests around both sides and may be
changed only with Phase 3 evidence.

The idealised geometry explains why `physical_distinct_regions` is possible: one
uniaxial load path leaves a plane of build directions perpendicular to it; two
non-parallel paths leave the axis parallel to their cross product; three
independent paths leave no direction perpendicular to all three. This motivates
the competing-path fixture but is not a classifier for a real stress field.

### Allowable-free orientation sensitivity

For each tail fraction, calculate a first-class dimensionless diagnostic:

```
principal_tension_i = max(largest_eigenvalue(stress_i), 0)
denominator         = weighted_cvar(principal_tension, alpha)
numerator           = min(candidate.opening_cvar(alpha))
sensitivity         = numerator / denominator
```

Numerator and denominator must use the same sample weights, aggregation and tail
fraction. CVaR divided by a nodal peak or by a differently sized tail is invalid.
Return `not_applicable` when the denominator is zero within numerical tolerance.
Otherwise the ratio must lie in `[0, 1]` up to that tolerance, which is a testable
property of `n^T sigma n <= lambda_max`.

Near zero means orientation is a strong lever; near one means none of the
**analysed candidates** keeps principal tension out of the layer bonds. Always
report candidate-set provenance beside the ratio: a finite face-normal set cannot
prove that no unexamined direction would work. This diagnostic uses no material
allowable and is therefore deliverable before material calibration.

## Phase 1 — complete the pure mechanics

Extend `orient.py` without FreeCAD imports:

- add a typed weighted-stress sample;
- calculate traction, tensile opening and interface shear;
- implement weighted quantile and weighted upper-tail CVaR;
- return exact per-sample tail-volume contributions from CVaR;
- score both channels for one build direction;
- rank by Pareto dominance, retaining deterministic display order for ties;
- calculate per-channel pairwise/adjacent margins without a combined scalar;
- calculate positive principal-tension CVaR and orientation sensitivity;
- compare critical-region maps and classify ties from explicit uncertainty,
  tie-band and overlap inputs;
- reject empty fields, non-positive/non-finite volumes and non-finite stresses;
- make `field_from_lists` keyword-only if it remains as a compatibility helper;
- make `rank` accept `Candidate` objects or provide one unambiguous adapter from
  `Candidate` to the scoring API;
- preserve candidate area as metadata, not as mechanical evidence.

Keep `peak_normal_stress` as an explicitly labelled, mesh-dependent diagnostic
until the validation study has compared every replacement against the original
measure. Mark that limitation in its docstring and keep it out of product ranking
and UI paths. Removing it later is a separate compatibility decision; retaining
it must not make it a supported engineering score.

Required unit cases:

- pure tension normal to the layers: opening non-zero, shear zero;
- pure compression normal to the layers: opening zero, shear zero;
- pure interface shear: opening zero, shear non-zero;
- combined loading with a hand-calculated result;
- invariance under simultaneous rotation of tensor and build direction;
- stress-tensor eigenvectors recover the principal normal stresses;
- weighted CVaR is unchanged when one sample is subdivided into equal-valued
  samples whose weights sum to the original;
- exact handling of a sample split at the CVaR tail boundary;
- invalid and empty input rejection;
- two candidates that trade opening against shear remain incomparable;
- exact margins for both a widely separated and a close candidate pair;
- paired-gap uncertainty cancels a perfectly correlated score drift while
  retaining independent or opposite drift;
- signed-gap uncertainty detects an order reversal across remeshes or refinement
  levels;
- a pair resolved by direct gap uncertainty is not falsely classified as
  `below_resolution` merely because `u_a + u_b` is larger;
- identical, threshold-boundary and disjoint critical maps for weighted Jaccard;
- all three tie outcomes and `not_checked` without convergence inputs;
- a pure uniaxial field gives sensitivity 0 when a perpendicular candidate exists
  and 1 when only the parallel candidate is analysed;
- sensitivity is invariant under positive load scaling and rejects a zero
  denominator as `not_applicable`;
- numerator and denominator cannot be constructed with different aggregations or
  tail fractions.

Acceptance: the pure API expresses no safety verdict, all quantities have stated
units, and no production ranking path calls `peak_normal_stress`.

## Phase 2 — build A0 and preserve the integration-point route

Keep solver-specific concerns out of `orient.py`. A tentative split is:

```
nix/packages/slicercad/freecad/slicercad/fem_result.py
nix/packages/slicercad/freecad/slicercad/element_geometry.py
nix/packages/slicercad/freecad/slicercad/calculix_runner.py
```

Responsibilities:

- identify the selected FreeCAD FEM result and its analysis/solver objects;
- expose the A0 volume-lumped nodal path from the existing result object;
- calculate element geometry and quadrature weights by supported type;
- transform stresses into the same part coordinate frame used by face normals;
- return plain `WeightedStress` values to the pure layer;
- report unsupported element types, missing files and stale results clearly.

Additional responsibilities when the integration-point route is triggered:

- generate, copy and patch the CalculiX input;
- execute and cancel the owned `ccx` process without blocking FreeCAD's GUI;
- parse integration-point stress output from `.dat`;
- map element and integration-point ids to connectivity, position and volume.

The module names are not a required abstraction boundary, but three concerns
must remain independently testable: FreeCAD object access, pure element geometry
and CalculiX process/file handling.

Coordinate frames are a release blocker. Add one asymmetric fixture whose body
has both translation and rotation. The score must be identical whether the same
physical model is represented by transformed geometry or by transformed tensor
and build vectors. A test containing only boxes at the origin is insufficient.

Acceptance for A0 and the product gate:

- A0 nodal weights sum to the independently measured CAD solid/FEM mesh volume;
- curved ten-node tetrahedra are integrated from all geometry nodes, not reduced
  to their four corner nodes;
- a deliberately curved C3D10 unit fixture has non-zero midpoint deviation and
  matches an independent high-accuracy reference volume;
- a curved CAD solid's integrated mesh volume approaches the CAD volume under
  systematic refinement rather than being asserted equal on one mesh;
- a real gmsh + CalculiX solve produces finite weighted samples end to end;
- moving/rotating the body does not change the physical ranking;
- unsupported models fail with a diagnostic instead of falling back to nodal
  maxima.

Additional acceptance when the integration-point route is implemented:

- C3D4 passes a constant-Jacobian, one-integration-point end-to-end fixture;
- target weights sum to the independently measured CAD solid/FEM mesh volume;
- integration-point values, not `NodeStressXX` and companions, feed that route;
- the patched run preserves the original analysis input and reports solver
  failure with retained diagnostic artefacts.

## Phase 3 — validate convergence of the ranking

This phase is a gate. Do not start the product UI or claim a recommended
orientation until it passes.

Create reproducible validation models for at least:

| Model | Dominant loading | Purpose |
|---|---|---|
| Cantilever | bending | known analytic trend and fixed-face singularity |
| L-bracket | bending plus local concentration | realistic fixture/root |
| Hook or curved beam | curved stress path | face-normal candidates are less obvious |
| Clamp | opening plus contact-like load | local concentration under clamping |
| Shaft or tab | torsion/combined load | exercises interface shear |
| Three-axis fork/frame, or constrained Y-fork | three independent paths, or two paths whose common safe axis is explicitly unavailable | must produce a stable close pair whose candidates have distinct critical regions |

Prefer three non-coplanar load paths for the mechanical-only fixture, because no
build direction can avoid all three. A two-arm Y-fork is valid only when the
single common safe axis `t1 x t2` is explicitly absent from the candidate set or
rejected by the printability side; otherwise it does not guarantee a conflict.
Tune the loads so no path trivially dominates. The purpose is not to manufacture
exact equality; it is to make changing orientation move the critical CVaR tail
between converged load paths. Without this fixture the strongest design
diagnosis, `physical_distinct_regions`, has no end-to-end validation.

Use second-order `C3D10` as the primary tetrahedral family. Set `ElementOrder` and
`SecondOrderLinear` explicitly and assert the actual `TYPE=` card written to the
`.inp`; a UI property is not evidence of the solver element. Run the cantilever
with `C3D4` as a documented comparison, not as the production convergence
baseline.

Use at least four target mesh sizes per model and at least three independently
generated meshes at each size. Keep geometry, loads, constraints, actual element
card and candidate set fixed within a refinement series. Record the actual mesh
produced; a requested gmsh size is an input, not an identity.

First run the same saved mesh through CalculiX repeatedly. Those scores must be
identical within numerical tolerance; otherwise solver execution or parsing is
introducing a third source of variation.

For remeshing, set and record gmsh's random seed when the installed version
supports a verified seed option. Use one fixed-seed sequence for the primary
refinement trend, but still run multiple seeds or independent generations at
each size to measure sensitivity to topology. A deterministic seed alone makes a
study reproducible; it does not show whether a different valid mesh changes the
ranking.

For each mesh and candidate, store a machine-readable record containing:

- requested mesh size, gmsh seed, mesh hash, configured order, actual CalculiX
  element card, node count, element count and total volume;
- data source (`nodal_volume_lumped` or `integration_point`);
- opening and shear CVaR at 1% and 5%;
- comparison statistics under evaluation;
- Pareto front and deterministic display order;
- absolute and relative score margins per channel/tail fraction;
- exact critical tail-volume maps and their pairwise overlaps;
- signed matched gaps, direct gap uncertainty, summed individual uncertainty as
  a diagnostic, tie band, overlap threshold and resulting tie classification;
- principal-tension CVaR, orientation sensitivity and candidate-set provenance;
- solve and parser versions.

Evaluate ranking convergence with:

- top-set consistency across repeats at one size and between successive sizes;
- Kendall rank correlation for candidates comparable in both channels;
- within-size score/rank spread caused by remeshing;
- movement of each size's median score and signed pairwise gap under refinement;
- direct pairwise gap uncertainty versus summed individual uncertainty, including
  how often the latter would create a false `below_resolution` result;
- stability of critical-region overlap and tie class under refinement;
- convergence of the orientation-sensitivity ratio;
- whether the critical region remains physically located or collapses onto a
  constraint/load artefact.

A candidate is confidently preferred only when its paired advantage in both
relevant channels exceeds `u_gap` calculated from matched runs. Otherwise return
`indeterminate` or a tied top set. Use the repeated runs to report distributions
or ranges, not a single trajectory through one arbitrary mesh per size. Compare
`u_gap` with `u_a + u_b` to quantify the conservatism avoided by preserving
correlation. The exact uncertainty rule may be revised from the measurements,
but it must be written down and tested before the gate closes.

The validation suite establishes that the chosen statistic behaves acceptably
over the reference problem class. It does not prove convergence for an arbitrary
user model. Per-model confidence requires multiple results for the same geometry,
loads, constraints, element family and candidate set. Use these states:

| State | Meaning |
|---|---|
| `not_checked` | Only one mesh is available; scores are comparative but model-specific convergence is unknown. |
| `stable_at_tested_meshes` | At least three refinement levels, with repeated remeshing at each, retain the preferred set and satisfy the documented margin rule. |
| `indeterminate` | The preferred set changes, or its paired margin is no larger than the observed direct-gap uncertainty. |
| `invalid` | Inputs cannot be compared, are incomplete, or contain unsupported/non-finite data. |

Never infer `stable_at_tested_meshes` merely because the model resembles one in
the validation suite.

Tie diagnosis is downstream of these states. `not_checked` carries no tie label;
an unresolved close pair becomes `below_resolution`; only a
`stable_at_tested_meshes` close pair may be labelled
`physical_shared_region` or `physical_distinct_regions`. Element ids need only
match between candidates on one mesh. Across refinements, require the overlap
value and classification to stabilise; do not compare raw ids from different
meshes.

Gate to continue:

- the preferred set stabilises on all validation models, or unstable cases are
  detected and reported as indeterminate;
- remeshing variance at fixed target size is measured separately from the
  refinement trend;
- the primary conclusions hold with explicitly verified C3D10 elements; C3D4
  results are labelled as a first-order comparison;
- the statistic is substantially less mesh-sensitive than the nodal maximum;
- pure-shear validation changes the ranking in the physically expected way;
- CVaR 1% and 5% are compared by ranking stability, critical-region locality,
  remeshing spread and estimated residual; the selected default and trade-off are
  recorded rather than inherited from the cantilever alone;
- the competing-load-path fixture converges to a close pair with distinct
  critical regions, while unit fixtures cover below-resolution and shared-region
  outcomes;
- margins and orientation sensitivity converge or are explicitly reported as
  indeterminate alongside the score;
- every result records `nodal_volume_lumped` as its stress source; if any model's
  A0 ranking remains unstable, implement the integration-point route and rerun
  that model before proceeding;
- results and plots can be regenerated with one documented command;
- any constraint exclusion or Saint-Venant distance rule is explicit and is
  applied by physical distance, never by dropping an arbitrary number of nodes.

If no tested statistic meets the gate, stop. Improve the physical boundary
conditions or the statistic before building product integration.

## Phase 4 — candidate orientations

Keep face-normal candidates as the initial geometric seed, with these changes:

- represent a mechanical layer plane as an unoriented axis, because `n` and
  `-n` give the same opening and shear magnitudes;
- expand each axis into both bed-facing signs when evaluating printability;
- deduplicate near-parallel candidates deterministically;
- retain supporting face area as a printability hint only;
- allow the user to include or exclude candidates;
- leave room for candidates supplied by the slicer or by a later, explicitly
  defined stress-direction heuristic.

Do not begin with continuous spherical optimisation. The finite set is easier to
explain, inspect and validate. Record candidate provenance (`face`, `slicer`,
`user`) so the UI can explain where each came from. Principal-stress directions
vary over the body, so a future `principal` source must not be added until there
is a tested rule for aggregating them into a bounded global candidate set.

Acceptance: asymmetric parts retain distinct `+n` and `-n` placements for the
slicer while sharing one mechanical score for the layer plane.

## Phase 5 — slicer collaboration

Mechanical quality and printability remain separate columns. Do not publish one
opaque weighted sum.

Target result:

| Orientation | Opening | Opening gap | Shear | Shear gap | Supports | Confidence |
|---|---:|---:|---:|---:|---:|---|
| A | low | — | low | — | high | stable |
| B | low | +0.2 MPa | medium | +1.1 MPa | low | stable |
| C | high | +4.5 MPa | low | −0.3 MPa | medium | indeterminate |

The signs are per-channel differences from the preceding displayed candidate,
not a combined ranking distance. A detail view for the selected top pair shows
its relative gaps, tie classification, critical-region overlap and allowable-free
orientation sensitivity.

Implementation sequence:

1. Verify Bambu Studio's actual `--orient` behaviour against the version shipped
   to users; OrcaSlicer alone is not sufficient evidence.
2. Determine whether a candidate placement can be scored without allowing the
   slicer to replace it with its own orientation.
3. Prefer a documented output or the resulting 3MF metadata over parsing the
   current stdout debug table.
4. If arbitrary candidate scoring is unavailable, ship mechanical ranking first
   and let the user inspect the finalists in the slicer. Do not reimplement all
   of `Orient.cpp` merely to fill the table.

Parsing slicer stdout is an adapter behind a version check, never part of the
mechanical core. Save the slicer name/version and the source of every
printability score.

## Phase 6 — FreeCAD workflow

Add one command, `Analyze print orientations`, enabled when an active document
contains a solved FEM result and printable solids.

The workflow:

1. Select the FEM result/load case.
2. Optionally associate a family of results from successively refined and
   repeatedly generated meshes of the same case for a per-model convergence
   check.
3. Collect or edit candidate orientations.
4. Load the weighted field once, performing the owned CalculiX run when target
   data is not already cached, then run the cheap pure scoring pass for every
   candidate. Never re-solve per candidate in this isotropic tier.
5. Show the Pareto front first, dominated candidates below it and per-channel
   margins between displayed neighbours.
6. For a selected candidate, highlight the volume contributing to opening and
   shear tail scores in different colours or modes.
7. For a selected pair, compare critical regions and show overlap only when both
   use the same mesh, channel and tail fraction.
8. Show the confidence state and tie diagnosis; never label a tie physical
   without convergence data.
9. Show orientation sensitivity with its tail fraction and candidate-set scope.
10. Apply the chosen placement to the existing bed mechanism.
11. Export and open the slicer through the existing send path.

Minimum useful UI fields:

- orientation preview and source;
- opening and shear tail scores in MPa;
- per-channel absolute margins in MPa and relative margins as diagnostics;
- relative comparison with the current orientation;
- convergence/confidence status;
- tie class, critical-region overlap and the thresholds used;
- orientation sensitivity, denominator and analysed candidate-set provenance;
- printability values when available;
- explicit warning that the result is comparative and based on one isotropic
  linear solve.

Do not display a factor of safety or “will survive”. The useful statement is:

> Of the analysed orientations, B transfers less opening and shear traction
> through the layer bonds than A; B and C cannot be distinguished at the current
> mesh resolution.

## Persistence and reproducibility

Store enough metadata to reproduce and audit a result:

```text
analysis/result object ids
mesh identity and element counts
mesh generator seed and content hash
solver and slicer versions
candidate vectors in the part frame
aggregation name and tail fractions
stress data source: nodal_volume_lumped or integration_point
opening/shear scores and units
pairwise signed and absolute margins by channel and tail fraction
critical tail contributions or their versioned comparable representation
matched run identities, direct gap uncertainty and summed individual uncertainty
tie band, region overlap, overlap threshold and classification
principal-tension CVaR and orientation-sensitivity ratio
candidate-set provenance and coverage
configured allowables, if any, with source
convergence status and meshes compared
coordinate transform used
```

Prefer a versioned plain-data structure serialisable to JSON. Do not store a
Python object graph or make the pure layer depend on FreeCAD property classes.

Invalidate a cached analysis when the FEM result, mesh, body placement,
candidate set or scoring configuration changes.

## Test layers

Keep four distinct test suites:

1. **Pure unit tests:** tensor projection, shear, weighted statistics,
   candidates, Pareto ordering, margins, critical-region overlap, tie
   classification, orientation sensitivity and invalid input.
2. **Adapter tests:** element weights, coordinate frames and malformed/stale
   results. Include straight and curved supported elements and sample-volume
   conservation. Add `.inp` patch placement and `.dat` fixtures when the
   integration-point route is implemented.
3. **End-to-end tests:** FreeCAD → gmsh → CalculiX → weighted ranking on small
   deterministic fixtures, covering A0 and, when present, the integration-point
   path. The competing-load-path fixture must exercise distinct-region diagnosis.
4. **Validation studies:** slower mesh-refinement experiments that produce
   tables/plots, repeat each target size and guard the engineering assumptions
   rather than every commit.

The first three belong in automated test commands. Validation studies may be a
separate documented command, but their generated summary must be reviewed before
changing the score definition.

## Delivery milestones

### Milestone A0 — weighted nodal pipeline

Phase 1, pure element volumes and the `nodal_volume_lumped` adapter are complete.
The full repeated-mesh validation harness runs against data FreeCAD already
exposes. This milestone can compare candidate rankings and develop the method,
and it is eligible for the product gate because the extended cantilever study
shows CVaR settling despite extrapolated nodal stresses. C3D4 may bring up the
pipeline, but A0 is not complete until the nodal volume calculation and study
also run on the explicitly verified C3D10 reference family.

### Milestone A — integration-point cross-validation

When triggered by an unstable A0 model or scheduled as a later cross-check,
slicercad can generate and patch a FreeCAD CalculiX input, own the second `ccx`
execution, parse the `.dat`, and produce opening/shear CVaR from correctly
weighted integration-point stresses. Estimate this as a solver lifecycle, parser
and finite-element geometry work package, not as a thin result-object adapter.
It is not a prerequisite for Milestone B when A0 passes the complete gate.

### Milestone B — validated recommendation

Phase 3 passes with A0 across the geometry suite, plus integration-point data for
any case that A0 cannot stabilise. The system measures fixed-size remeshing
variance separately from refinement, can identify a stable preferred set or
explicitly decline to choose, classifies converged close pairs by critical
region, reports margins and allowable-free orientation sensitivity, and records
whether a user's own model was convergence-checked. This is the go/no-go point
for the product.

### Milestone C — usable CAD tool

Phases 4 and 6 complete. A user can inspect, select and apply a mechanically
ranked orientation in FreeCAD, then send it to the slicer.

### Milestone D — combined decision support

Phase 5 complete where the slicer's supported interfaces permit it. Mechanical
and printability trade-offs appear together without losing their provenance.

### Later — calibrated prediction

Only after the ranking product works:

- accept measured interlayer tensile and shear allowables;
- validate a mixed-mode criterion experimentally;
- patch CalculiX input for orthotropic material axes and run one solve per
  candidate using the same mesh;
- compare isotropic ranking against orthotropic re-solves;
- add safety language only if model, process parameters and validation support
  it.

## Definition of done for the first release

The first release is done when a user can start from a solved FEM case, compare a
bounded set of orientations, inspect per-channel margins, understand whether a
close pair is unresolved or reflects shared/competing critical regions, see how
much orientation can reduce principal tension in the layer bonds, understand the
opening/shear trade-off, see whether the recommendation is convergence-checked,
apply one orientation and reach the slicer without slicercad claiming a load
capacity.

It is not done merely because one orientation has the lowest floating-point
score. The deliverable is a recommendation with provenance and an honest
uncertainty state.
