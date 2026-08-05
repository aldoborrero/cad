# <project> (KiCad)

One-line description of the board.

The project is the usual KiCad trio, all sharing the directory's name: `<project>.kicad_pro`
(the project), `<project>.kicad_sch` (the schematic) and `<project>.kicad_pcb` (the board).
The scaffold starts from a blank schematic and a 50 × 30 mm rectangle on `Edge.Cuts`, so
`cad export` and `cad render` produce something on the first run.

## Board

| Name | Meaning | Default |
|------|---------|---------|
| Outline | `Edge.Cuts` rectangle | 50 × 30 mm |
| Thickness | board stackup | 1.6 mm |
| Layers | copper | 2 (F.Cu / B.Cu) |

## Build

```sh
cad render <project> [iso|top|bottom|front|back|left|right]   # raytraced PNG -> exports/
cad export <project>    # kicad-cli pcb export step -> exports/<project>.step
cad gui    <project>    # open the project in KiCad
```

The STEP is the handoff to the mechanical side: open it in FreeCAD, or import the
`.kicad_pcb` directly with the **KiCadStepUp** workbench, which resolves each footprint's
3D model against the library the devshell's `kicad` ships and keeps the two in sync.

## Notes

- Fab house / stackup / finish: …
