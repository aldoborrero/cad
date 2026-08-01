# marble-run / ramps / accelerator (FreeCAD / Python)

The marble run's red slope, built as OCCT B-rep. A second construction of a piece that also
exists in OpenSCAD — `openscad/marble-run/ramps/accelerator.scad` — and the paths mirror
each other deliberately.

```sh
cad export marble-run/ramps/accelerator     # -> exports/accelerator.step + .stl
```

## Why this one piece

The other 33 parts of the set are boxes, cylinders and revolutions combined with booleans,
which is what OpenSCAD is for. This one is not:

- **It is a loft.** Its section changes shape along the length — the plan tapers, the top
  and the cradle drop at 12.5°, the bullnose shrinks, the foot starts and stops — and
  `linear_extrude` only scales a single profile. OpenSCAD's answer is 200 stacked prisms.
- **Its bullnose is a fillet**, and OpenSCAD has no edges to fillet. There it is faked as a
  2D morphological opening applied section by section.

In B-rep both are primitives, and the piece stops being a sweep at all. The cradle turns out
to be an **oblique cylinder** — a circle in the YZ plane swept along the tilted axis, which
is not the same as a tilted cylinder, since that one cuts as an ellipse. The top and the
base are planes. Before rounding, the whole part is 21 faces.

| | OpenSCAD, 200 prisms | here |
|---|---|---|
| facets | 178 590 | 16 926 |
| bounding box | 41.260 × 22.795 × 20.677 | **41.250 × 22.830 × 20.700** |
| bodies | 1 solid + 9 zero-area shards | **1 solid, watertight** |

The bounding box is the tell: the B-rep gives `ACC_L`, `ACC_W0` and `ACC_ZTOP` exactly,
while the prism stack overshoots the length and undershoots the height. Read it with
`optimalBoundingBox(False)` — plain `BoundBox` uses the shape's triangulation if one exists
and the control poles if not, so it is exact after meshing and 0.6 mm over before it, and
`optimalBoundingBox()` with its default `useTriangulation=True` reads 0.14 mm over. And the facet count
here is an **export setting**, not a property of the model — `LinearDeflection` chooses it.

## What is verified, and what is not

The honest comparison is against the piece with the bullnose switched off, since that
isolates the construction from the rounding:

```sh
openscad -D 'part="accelerator"' -D 'ACC_LIP=0' -o sharp.stl ../../../../openscad/marble-run/marble-run.scad
```

That reads **4.2466 cm³ against this model's 4.2488 — 0.052 %**, inside the project's own
tolerance.

The finished parts differ by **+2.0 %**, and that is a difference of definition rather than
an error. OpenSCAD's bullnose is an *opening*, which rounds every convex corner of every
section — the base, the foot, all of them. This rounds the eight edges it is asked to.
Closing the gap is a matter of naming more edges.

## The numbers are not copied

They are read out of `lib.scad` through OpenSCAD's own `echo`, the same way `sim/` does it,
because a copied CAD dimension goes stale in silence. The cost is that this build needs
`openscad` on PATH as well as FreeCAD; the devshell has both.

## Two things worth knowing before editing

- **Edges are picked by geometric predicate**, not by index — *"the edges lying in the top
  plane"*, *"the edges lying on the cradle"*. Index-based selection is what breaks when OCCT
  renumbers a rebuilt shape, which is the topological naming problem FreeCAD ships a
  dedicated test for. Describing what an edge *is* survives it.
- **`Part::Fillet`, the document object.** `shape.makeFillet()` does have a variable-radius
  overload — `makeFillet(r1, r2, edgeList)` — but it applies one pair to the whole list, so a
  radius per edge needs one call per edge, and chaining those fails on the first:
  `StdFail_NotDone`. `Part::Fillet` takes all eight with their own radii in one operation,
  which is where OCCT resolves the corners between adjacent filleted edges together.
  `PartDesign::Fillet` is out either way — its `Radius` is a single value. On the wall's top
  face there is a limit `lib.scad` never had to state, because a 2D opening cannot
  over-round: the strip is only 1.87 mm wide at the entry and carries a fillet on *both*
  sides, so two radii of 0.9 would consume it and drop the top face by 0.2 mm.

Also: `freecadcmd` passes the script's own path as `sys.argv[1]`. Do not use it as an output
path — it will overwrite the source.

## Not in `check.py`

`openscad/marble-run/tools/check.py` builds its 34 parts with `openscad -D part=`, so this
one is outside the regression harness. Teaching it to drive FreeCAD as well is the work this
port still owes.
