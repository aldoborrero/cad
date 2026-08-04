# bambucad — the bed as a placement, not a height

Date: 2026-08-04
Status: designed, not implemented
Follows: 2026-08-04-bambucad-design.md

Phase 1 draws the bed at Z = 0 around the model origin. That breaks on any model
not built on the origin plane: FreeCAD's own `PartDesignExample` spans **Z −100 to
0**, so an opaque plate 0.03 mm under its top face hides the whole body and its
faces cannot even be clicked.

The fix is not a "floor height" setting. Asking *which face rests on the bed* is
asking for an orientation, and a picked face is rarely horizontal. So the bed
gains a **Placement**, and print orientation is expressed by moving the bed —
never the model. That is the same rule that kept the layout out of the document
for X and Y, taken to its conclusion.

## What already exists, and where

Nothing below needs inventing. Sources are `.scratch/freecad-1.1.1` and
`.scratch/bambustudio`.

| Need | Existing implementation |
|---|---|
| A face → a placement (centre of gravity, u/v, normal) | `src/Mod/Draft/draftgeoutils/geometry.py:672` `placement_from_face(face, vec_z, rotated, tol)` |
| How that is used, including the planarity guard | `src/Mod/Draft/WorkingPlane.py:246` `align_to_face`, which returns False unless `face.Surface.isPlanar()` |
| Measuring a shape in another frame | `TopoShape.transformShape(matrix, copy, checkScale)` |
| Inverting and serialising a placement | `Base::Placement::inverse()`, `Placement.toMatrix()` |
| Drawing a rotated node | `coin.SoTransform()`, as Draft's own trackers use |
| What "place on face" means | `src/slic3r/GUI/Selection.cpp:1530` `flattening_rotate`: rotate so the picked face "faces downwards"; asserts the normal is unit length |
| Whether a rotation survives the 3MF | `_apply_transform` sets the instance transformation from the item matrix whole, and `ensure_on_bed` only ever calls `translate_instances(z_offset * UnitZ)` |
| A trap in that path | `_apply_transform` returns early, silently dropping the item, when `!t.get_scaling_factor().all()` — the exported matrix must be a proper rotation |

The last two are what make this feasible rather than clever: Bambu keeps the
orientation we write and normalises only the height.

## The shape of it

`fit.offset` becomes the bed's placement. Today it is a translation of half the
plate; it generalises to a full `Placement`, and the three consumers stay the
same three:

- **Drawing** hangs an `SoTransform` in front of the existing geometry. The
  vertex arithmetic in `bed.py` does not change.
- **The fit check** transforms a copy of each shape into bed coordinates with
  `transformShape` and takes the axis-aligned bounding box it already takes. The
  29 pure tests keep working untouched, because they were always about numbers
  rather than about FreeCAD.
- **The export** multiplies the item matrix instead of adding to its last three
  numbers. `shift_transform` becomes a matrix multiply — a change in the pure
  layer, so it goes test-first like the rest.

## Where the bed goes

Default: under the lowest point of the visible parts, so a model opens resting on
the plate whatever Z it was built at. This is what Bambu will do anyway.

`Set the bed from the selection` takes the selected face and calls
`placement_from_face`, refusing anything non-planar the way `align_to_face` does.
Running it with nothing selected goes back to automatic. There is no numeric
field: in a CAD you know which face rests, not the coordinate it sits at.

## Decisions still open

- **Whether to import from Draft.** `placement_from_face` is exactly right, but
  it lives inside Draft — a heavy import, and the workbench that segfaulted until
  the expat fix. Its essence is a rotation from a normal plus a centre of
  gravity, which is a handful of lines against `Part` alone. Reuse buys edge-case
  handling for degenerate faces; copying buys independence for phase 2.
- **A tilted bed and the plate rectangle.** A part resting on a tilted bed can
  poke outside the 256 mm rectangle in ways the current check cannot see until
  the shape is transformed. That is exactly what `transformShape` solves, but the
  order of operations wants writing down before coding.

## Unverified

`Mesh.export` is known to pass `mesh.getTransform()` into the item matrix, but
this has only been exercised with identity placements. Before building on it,
export a deliberately rotated object and read the twelve numbers back.
