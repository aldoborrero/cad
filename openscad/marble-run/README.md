# marble-run (OpenSCAD)

The **OpenSCAD** sibling of [`../../freecad/marble-run/part`](../../freecad/marble-run/part/)
(Part/CSG). Same numbers, same pieces — the channel geometry is a faithful port of
[`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot) (`blocks.scad`). See
[`../../freecad/marble-run/README.md`](../../freecad/marble-run/README.md) for the block
table and measured dimensions.

## Layout (library → pieces → main)

| File | Role |
|------|------|
| `lib.scad` | `include <BOSL2/std.scad>` + parameters + `block_base` + channel primitives (`ch_top`, `ch_exit`, `ex_vertical`, `ex_side`, `ex_across`, `ex_back`, `ex_bottom`) |
| `block_*.scad`, `connector_funnel.scad` | one piece each: `use <lib.scad>` + `module mr_*()` (renders itself when opened directly) |
| `marble-run.scad` | **main**: `include`s lib once, `use`s each piece, lays them all out; `part=` selects one |

## Render / export

```sh
cad export marble-run                       # whole plate -> exports/marble-run.stl
cad render marble-run iso                   # PNG preview -> exports/
openscad -D 'part="yellow"' -o yellow.stl marble-run/marble-run.scad   # one piece
```

`part` values: `all | blank | orange | yellow | green | teal | blue | wood | red | connector`.

The repo's shared `openscad/lib/common.scad` isn't needed for the blocks, but its
**`ring_sector`** will be reused for the upcoming curved rails.
