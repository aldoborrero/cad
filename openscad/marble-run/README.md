# marble-run (OpenSCAD)

The **OpenSCAD** sibling of the FreeCAD implementations
([`freecad/marble-run/part`](../../freecad/marble-run/part/) = Part/CSG,
[`part-design`](../../freecad/marble-run/part-design/) = Part Design). Same numbers, same
pieces, built with **BOSL2**.

A **Hape Quadrilla-compatible** marble run, parametric for **FDM** printing:
`block-blank`, `block-straight` (orange), `block-turn` (yellow), `connector-funnel`
(purple), and a reference `marble`.

## Render / export

`part` selects a piece; the default `all` lays every piece out on a plate.

```sh
# whole plate (what a plain build produces):
openscad -o exports/marble-run.stl marble-run.scad

# a single piece:
openscad -D 'part="straight"' -o exports/straight.stl marble-run.scad
openscad -D 'part="turn"'     -o exports/turn.stl     marble-run.scad
```

Valid `part` values: `all | blank | straight | turn | connector | marble`.

## Parameters

Mirror `../../freecad/marble-run/part/params.py`: `SIDE=44`, `HEIGHT=44` (**measure**),
`BORE_D=19`, `STUD_D=29` / `SOCKET_D=31`, `MARBLE_D=16`, `CHAMFER=2`. Reverse-engineered
from [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot).

## Notes

- Uses BOSL2 (`include <BOSL2/std.scad>`, on `OPENSCADPATH` via the flake): `cuboid` with
  `chamfer`/`edges="Z"`, `cyl`/`xcyl` with anchors, conical `cyl(d1, d2)` for the bowl.
- `.scad` has no reliable CLI formatter — kept to a light 2-space style, lint with `sca2d`.
