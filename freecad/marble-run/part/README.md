# marble-run / part (FreeCAD Part / CSG)

The **Part / CSG** implementation — one of three siblings (`../part-design` = Part Design,
`../../../openscad/marble-run` = OpenSCAD). A **Hape Quadrilla-compatible** marble run,
parametric for **FDM** printing.

## Layout (library → pieces → main)

| File | Role |
|------|------|
| `lib.py` | parameters + Part/CSG helpers (`chamfered_body`, `z_cyl`, `block_base`) |
| `block_blank.py` / `block_straight.py` / `block_turn.py` / `connector_funnel.py` | one piece each: `NAME` + `build() -> Part.Shape` |
| `part.py` | **main**: builds every piece, exports `exports/<piece>.step` + `.stl`, plus a combined `part.step` |

## Pieces

| Export | Quadrilla | What it does |
|--------|-----------|--------------|
| `block-blank` | plain block | body + stud + top socket, no path |
| `block-straight` | orange | marble drops straight through (dish → bore → hollow stud) |
| `block-turn` | yellow | enters top, turns 90° and exits the +X side face |
| `connector-funnel` | purple | thin landing connector: conical catch bowl → bore + stud |

## Key parameters (`lib.py`)

| Name | Meaning | Default | Confidence |
|------|---------|---------|------------|
| `SIDE` | cube footprint | 44 mm | high (compatibility) |
| `HEIGHT` | block height | 44 mm | **measure** (quadri-plot=60) |
| `BORE_D` | marble channel Ø | 19 mm | high |
| `STUD_D` / `SOCKET_D` | stack peg / socket Ø | 29 / 31 mm | **measure** |
| `STUD_H` / `SOCKET_DEPTH` | stack engagement | 8 / 8.5 mm | **measure** |
| `CHAMFER` | vertical-edge bevel | 2 mm | medium |

Defaults reverse-engineered from [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot).

## Build

```sh
cad export marble-run/part          # -> exports/*.step + *.stl (+ part.step)
cad gui    marble-run/part          # build, then open part.step in FreeCAD
```

> The CSG rebuild of every piece is watertight (validated). `freecadcmd` (devshell) runs the
> real B-rep export — if a Part boolean raises, paste the traceback.

## Print notes

- Material: PLA/PETG. Ø19 bore vs Ø16 marble ≈ 1.5 mm/side — fine for FDM.
- Orientation: print **stud-down / socket-up**; the top dish bridges cleanly.
- After a test print, tune `STACK_CLEAR` (stud↔socket fit) and `BORE_D` (marble roll) first.
