# marble-run / part (FreeCAD Part / CSG)

The **Part / CSG** implementation (the reference) — see [`../README.md`](../README.md) for
the shared design, the block table, and measured dimensions.

## Layout (library → pieces → main)

| File | Role |
|------|------|
| `lib.py` | parameters + helpers: `block_base`, and the quadri-plot channel primitives (`ch_top`, `ch_exit`, `ex_vertical`, `ex_side`, `ex_across`, `ex_back`, `ex_bottom`, `carve`) |
| `block_*.py`, `connector_funnel.py` | one piece each: `NAME` + `build() -> Part.Shape` |
| `part.py` | **main**: builds every piece, exports `exports/<piece>.step` + `.stl`, plus a combined `part.step` |

## Build

```sh
cad export marble-run/part          # -> exports/*.step + *.stl (+ part.step)
cad gui    marble-run/part          # build, then open part.step in FreeCAD
```

Every piece's CSG rebuild is watertight (validated with a trimesh mirror). `freecadcmd`
(devshell) runs the real B-rep export — if a Part boolean raises, paste the traceback.

## Print notes

- Material PLA/PETG. Ø20 tunnel vs Ø16 marble ≈ 2 mm/side — fine for FDM.
- Print **stud-down / socket-up**; the top dish bridges cleanly.
- After a test print, tune `STACK_CLEAR` (stud↔socket fit) and `BORE_D` first.
