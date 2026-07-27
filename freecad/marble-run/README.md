# marble-run (FreeCAD)

A **Hape Quadrilla-compatible** marble run, parametric for **FDM** printing — implemented
**three ways** for comparison (same numbers, same pieces):

| Folder | Approach | Kernel / paradigm |
|--------|----------|-------------------|
| [`part/`](part/) | **Part / CSG** | primitives + booleans (`makeBox`/`cut`/`fuse`) |
| [`part-design/`](part-design/) | **Part Design** | Sketch → Pad/Pocket, editable feature tree + `.FCStd` |
| [`../../openscad/marble-run/`](../../openscad/marble-run/) | **OpenSCAD** | mesh/CSG with BOSL2 |

All three build the same foundation pieces: `block-blank`, `block-straight` (orange),
`block-turn` (yellow), `connector-funnel` (purple), and a reference `marble`.

## Which to use?

- **`part/`** is the reference: for this geometry (cubes + cylinders + cones + boolean
  channels) CSG is the most direct and was validated (watertight rebuild of every piece).
- **`part-design/`** if you want to edit features in the FreeCAD GUI (drag a sketch, change
  a length) rather than editing code.
- **`openscad/`** if you prefer the OpenSCAD toolchain.

## Build

These live one level deeper than a normal `cad` project, so run the scripts directly:

```sh
freecadcmd freecad/marble-run/part/marble-run.py          # Part / CSG
freecadcmd freecad/marble-run/part-design/marble-run.py   # Part Design (+ .FCStd)
openscad   -o /tmp/marble-run.stl openscad/marble-run/marble-run.scad   # OpenSCAD (all pieces)
```

> The `cad` helper expects a flat `freecad/<name>/<name>.py`; it does not yet traverse these
> nested variant folders. Extending `bin/cad` to handle `name/variant` is a small follow-up.

## Dimensions

Defaults are reverse-engineered from [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot):
`SIDE=44`, `BORE_D=19`, `STUD_D=29` / `SOCKET_D=31`, `MARBLE_D=16`. The fit-critical rows
(`HEIGHT`, stud/socket engagement, marble Ø) are flagged in `part/params.py` to **measure**
on a real set before a full print batch — every value is parametric.

See [`part/README.md`](part/README.md) for the full parameter table and print notes.
