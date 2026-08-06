# Phase 3 FEM orientation validation

This directory contains the compact result of the repeated-mesh validation for
load-aware print orientation. The raw records are intentionally not committed:
they contain every exact CVaR tail map and are tens of megabytes per fixture.
`summary.json` records their SHA-256 signatures.

## Reproduce

Run the primary C3D10 matrix from the repository root in the devshell:

```bash
freecadcmd --module-path=nix/packages/slicercad/freecad \
  nix/packages/slicercad/tools/validate_phase3.py
```

That command runs six fixtures, four mesh sizes and three seeded remeshes per
size, reusing the same three seeds across refinement levels. Gmsh runs with one
thread so a repeated seed is reproducible. The harness also remeshes the
coarsest case with the same seed and reruns CalculiX on the same input; both the
mesh/ranking and the repeated scores must match. It writes `results.json`,
`results.csv` and one SVG per fixture here. For a quick integration check, pass
each script argument through FreeCAD:

```bash
freecadcmd --module-path=nix/packages/slicercad/freecad \
  nix/packages/slicercad/tools/validate_phase3.py \
  --pass=--smoke --pass=--fixture --pass=cantilever
```

The labelled first-order comparison is a separate four-mesh run:

```bash
freecadcmd --module-path=nix/packages/slicercad/freecad \
  nix/packages/slicercad/tools/validate_phase3.py \
  --pass=--fixture --pass=cantilever \
  --pass=--element-order --pass=1st --pass=--repeats --pass=1 \
  --pass=--output --pass=/tmp/slicercad-phase3-c3d4/results.json
```

`summarize_phase3.py` rebuilds the confidence decisions from raw records. This
separates changes to the convergence contract from expensive FEM execution.

## Result

The recorded run used FreeCAD 1.1.1, gmsh 4.15.0-git and CalculiX 2.22. All 72
primary records contain only an actual `C3D10` card, use
`nodal_volume_lumped`, and have three distinct mesh signatures at each of four
sizes. Six additional fixed-seed remeshes reproduced both mesh signatures and
rankings. Re-running each fixture's same saved input produced bitwise-identical
scores.

Both tails retain a resolution-expanded preferred set on all six fixtures. The
aggregate median movement from the penultimate to finest mesh is:

| Statistic | Movement |
|---|---:|
| Nodal maximum | 5.32% |
| Weighted CVaR 1% | 2.58% |
| Weighted CVaR 5% | 1.73% |

The 5% tail also has lower aggregate remesh spread (0.046% versus 0.144%), so it
is the validation default. The 1% tail remains available as the more
failure-local diagnostic. This choice is empirical and configurable, not a
material allowable.

The direct correlated-gap uncertainty avoids three false `below_resolution`
outcomes that the sum of individual uncertainties would produce. On the tuned
three-axis frame, the `x/y` pair is separated by 2.80% in opening and 1.91% in
shear; both gaps exceed direct uncertainty and both
critical-region overlaps remain below 0.5. It is therefore classified
`physical_distinct_regions` in both channels.

Critical-tail centroids are included in `summary.json`. Some fixtures correctly
remain root-local, especially the cantilever; no arbitrary node exclusion or
Saint-Venant cutoff was applied. The centroid distance reported there is to the
recorded boundary target, not an exact distance to the complete boundary face.

The C3D4 comparison is explicitly separate. Its median last-step movement is
12.35% for the nodal maximum, versus 2.91% for CVaR 1% and 13.54% for CVaR 5%;
it is not used as the production baseline.
