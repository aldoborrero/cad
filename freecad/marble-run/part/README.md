# marble-run / part (FreeCAD Part / CSG)

The **Part / CSG** implementation of the marble run — one of three siblings
(`../part-design` = Part Design feature tree, `../../../openscad/marble-run` = OpenSCAD).

A **Hape Quadrilla-compatible** marble run, parametric for **FDM** printing. This is a
*family* of pieces: the entry script builds them all and exports one STEP + STL per piece.

Modeled as code in `marble-run.py` (orchestrator) + `parts.py` (piece builders) +
`params.py` (all dimensions), using FreeCAD's `Part` (OCCT B-rep) primitives + booleans —
no GUI needed.

## Pieces (foundation)

| Export | Quadrilla equivalent | What it does |
|--------|----------------------|--------------|
| `block-blank` | plain wooden block | body + stud + top socket, no path (spacer / tower) |
| `block-straight` | orange | marble drops straight through (top dish → bore → hollow stud) |
| `block-turn` | yellow | marble enters top, turns 90° and exits the +X side face |
| `connector-funnel` | purple | thin landing connector: conical catch bowl → through-bore + stud |
| `marble` | glass marble | Ø16 reference sphere for fit checks |

Still to come (see `../../` catalogue): red splitter, green/blue/teal exits, control gate,
straight/curved rails, and the special mechanisms (cyclone, seesaw, spiral tower).

## Key parameters (`params.py`)

| Name | Meaning | Default | Confidence |
|------|---------|---------|------------|
| `SIDE` | cube footprint | 44 mm | high (compatibility) |
| `HEIGHT` | block height | 44 mm | **measure** (quadri-plot=60) |
| `BORE_D` | marble channel Ø | 19 mm | high |
| `MARBLE_D` | marble Ø | 16 mm | high (14 on some sets) |
| `STUD_D` / `SOCKET_D` | stack peg / socket Ø | 29 / 31 mm | **measure** |
| `STUD_H` / `SOCKET_DEPTH` | stack engagement | 8 / 8.5 mm | **measure** |
| `CHAMFER` | vertical-edge bevel | 2 mm | medium |

Geometry defaults are reverse-engineered from [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot)
(validated as correct). **Measure the flagged rows on your own set** before a full batch —
they drive whether stacked pieces seat and stay put.

## Build

Nested under `marble-run/`, so run the script path directly (the `cad` helper expects a
flat `freecad/<name>/<name>.py`):

```sh
freecadcmd freecad/marble-run/part/marble-run.py   # -> exports/*.step + *.stl (+ marble-run.step)
```

> `freecadcmd` is provided by the devshell (`nix develop`). The script was authored
> without a local FreeCAD to execute it — if a Part boolean raises, report the traceback.

## Print notes

- Material: PLA/PETG. The Ø19 bore vs Ø16 marble leaves ~1.5 mm/side — fine for FDM.
- Orientation: print blocks **stud-down** or **socket-up**; the top dish bridges cleanly.
  The hollow stud on through-pieces may want a brim rather than supports.
- After a test print, tune `STACK_CLEAR` (stud↔socket fit) and `BORE_D` (marble roll) first.
