# marble-run / part-design (FreeCAD Part Design)

The **Part Design** implementation of the marble run — one of three siblings
(`../part` = Part/CSG, `../../../openscad/marble-run` = OpenSCAD).

Every piece is a **PartDesign Body** with a sketch-driven, **editable feature tree**
(Pad/Pocket), not a CSG result. Building it also saves an editable `.FCStd` per piece you
can open and tweak by clicking features.

Modeled as code in `marble-run.py` (per-piece builders + orchestrator) + `pdlib.py`
(sketch/feature helpers) + `params.py` (same numbers as `../part/params.py`).

## Feature tree (per block)

```
Body
 ├─ Sketch_body   (chamfered square 44) → Pad  Body_pad   (up HEIGHT)
 ├─ Sketch_stud   (circle Ø29)          → Pad  Stud_pad   (down 8)
 ├─ Sketch_socket (circle Ø31 @ top)    → Pocket Socket   (down 8.5)
 └─ … channel pockets per piece (straight: through bore; turn: vertical + side; …)
```

The chamfer is baked into the body profile (an octagon), avoiding a fragile edge-select
dress-up.

## Build

```sh
freecadcmd freecad/marble-run/part-design/marble-run.py
# -> exports/<piece>.step + .stl + .FCStd (editable tree)
```

## API / status (FreeCAD 1.1.1)

Uses the 1.1 API: `AttachmentSupport` + `MapMode='FlatFace'` for sketch attachment,
explicit `BaseFeature`/`Tip` chaining of solid features, `Pocket.Type='ThroughAll'`,
`TaperAngle` for the conical bowl.

> **Not executed here** (no `freecadcmd` in the authoring env). Two features are the most
> likely to need a one-line tweak on first local run:
> - **`connector` bowl** — a tapered pocket; if the taper widens instead of narrowing, flip
>   the sign of `taper` in `build_connector`.
> - **`turn` side exit** — a pocket on the YZ plane; if it exits the wrong face, flip
>   `reversed` on `Hbore_pocket`.
>
> Run it and paste any traceback — these are quick fixes.

See `../part/README.md` for the parameter table and print notes (identical dimensions).
