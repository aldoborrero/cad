# marble-run (FreeCAD)

A **Hape Quadrilla-compatible** marble run, parametric for **FDM** printing. The channel
geometry is a **faithful port of [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot)**
(`blocks.scad`): a TopEntry bore drops the marble from the top dish to the block's centre
pivot, then an ExitPart (a sphere pivot + a bore) carries it out — straight, or tilted 60°.

Implemented in two tools (same numbers, same pieces):

| Folder | Approach |
|--------|----------|
| [`part/`](part/) | **Part / CSG** — primitives + booleans (the reference) |
| [`../../openscad/marble-run/`](../../openscad/marble-run/) | **OpenSCAD / BOSL2** |

> `part-design/` (Part Design feature tree) is **frozen** at the foundation set — Part
> Design's sketch/pad model doesn't express the tilted 60° channels cleanly in a headless
> script, so the faithful set lives in `part/` (CSG) and `openscad/`.

## Blocks (the 8 Quadrilla types + connector)

| Piece | Quadrilla | Channel |
|-------|-----------|---------|
| `block-blank` | plain | dish + stud, no channel |
| `block-orange` | Vertical | straight through |
| `block-yellow` | One side lateral | 60° sloped side exit |
| `block-green` | Sideways, bottom | 60° side + bottom + low crossing |
| `block-teal` | Sideways, bottom | 60° side + low crossing |
| `block-blue` | Sideways, bottom | 60° side + bottom + back |
| `block-wood` | bottom crossing | vertical + low crossing |
| `block-red` | Built-in toggle | two 60° side exits at 90° |
| `connector-funnel` | purple | thin dish → bore → stud |

## Measured dimensions (real set, calipers)

`SIDE=44`, `HEIGHT=60`, `BORE_D=20` (tunnel), `SOCKET_D=30` (top dish), `MINI_H=12`
(connector, excl. stud), `CHAMFER=2`. `STUD_D=28` (fits a 30 socket with ~1 mm/side);
`STUD_H` still to confirm. All parametric in `part/lib.py`.

## Build

```sh
cad export marble-run/part          # -> exports/*.step + *.stl (+ part.step)
cad export marble-run               # OpenSCAD plate
```

## Still to come

Rails (straight, curved, S, spirals — will reuse `openscad/lib/common.scad`'s `ring_sector`),
the red wedge accelerator, and the drop tube — see *The Challenger* (E6016) parts sheet.
