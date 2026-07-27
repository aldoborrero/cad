# marble-run / part-design (FreeCAD Part Design)

The **Part Design** implementation — one of three siblings (`../part` = Part/CSG,
`../../../openscad/marble-run` = OpenSCAD). Every piece is a **PartDesign Body** with a
sketch-driven, **editable feature tree** (Pad/Pocket), not a CSG result.

## Layout (library → pieces → main)

| File | Role |
|------|------|
| `lib.py` | parameters + Part Design/Sketcher helpers + `base_block(doc, h)` |
| `block_*.py`, `connector_funnel.py` | one piece each: `NAME` + `build(doc) -> body` |
| `part-design.py` | **main**: builds every piece in one document, exports each, lays them out, and saves the whole editable scene as `part-design.FCStd` (+ `part-design.step`) |

## Feature tree (per block)

```
Body
 ├─ Sketch_body   (chamfered square 44) → Pad  Body_pad
 ├─ Sketch_stud   (circle Ø29)          → Pad  Stud_pad   (down)
 ├─ Sketch_socket (circle Ø31 @ top)    → Pocket Socket
 └─ … channel pockets per piece
```

The chamfer is baked into the body profile (an octagon), avoiding a fragile edge-select
dress-up.

## Build

```sh
cad export marble-run/part-design    # -> exports/<piece>.step + .stl + part-design.FCStd
```

## API / status (FreeCAD 1.1.1)

Uses the 1.1 API: `AttachmentSupport` + `MapMode='FlatFace'`, explicit `BaseFeature`/`Tip`
chaining, `Pocket.Type='ThroughAll'`, `TaperAngle` for the conical bowl.

> **Not executed here** (no `freecadcmd`). Two features are most likely to need a one-line
> tweak on first local run: the **`connector` bowl** taper sign, and the **`turn` side exit**
> `reversed` flag. Run it and paste any traceback.

Parameter table and print notes: see [`../part/README.md`](../part/README.md) (identical dims).
