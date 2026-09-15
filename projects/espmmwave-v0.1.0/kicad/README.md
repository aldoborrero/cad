# espmmwave-v0.1.0 (KiCad)

The board and schematic for the ESPHome LD2450 presence sensor. **The project manual —
bill of materials, datasheets, differences from the original and credits — is one level up
in [`../README.md`](../README.md).** This file covers only what is specific to the KiCad
half.

The usual trio, all sharing the project's name: `espmmwave-v0.1.0.kicad_pro`,
`.kicad_sch` and `.kicad_pcb`, plus this project's own libraries — `espmmwave.kicad_sym`
and `espmmwave.pretty/` — which hold the XIAO ESP32S3 symbol and footprint that KiCad does
not ship.

## Both files are source; the geometry can still be rebuilt

**`.kicad_pcb` is edited.** It can be *rebuilt* from the measured geometry in
`../tools/board.py`, which parses it out of the original's gerbers — something KiCad has no
way to do — but that is a bootstrap, not the daily path.

```sh
board --regenerate   # -> .kicad_pcb, from the measured geometry and the schematic's netlist
```

**Both files are edited and kept**, in eeschema and pcbnew or through the Konnect MCP
server. They began life generated, which is why they agree, but that is now a property to be
*checked* rather than one the tooling can guarantee:

```sh
check        # the everyday command: do the board and the sheet still agree?
```

`board` refuses to write without `--regenerate`: it rebuilds the whole file and every run
mints fresh UUIDs, so there is nothing to merge — what it writes replaces everything. There
is no schematic generator any more; eeschema and Konnect both write schematics perfectly
well, and one description of the circuit is enough.

## Checking it

`check` runs three checks, and they fail for different reasons:

| Check | Catches |
|---|---|
| connectivity | the board's pad-to-net assignment, against the netlist KiCad exports from the sheet |
| annotation | every symbol's instance reference and root-sheet path |
| ERC | KiCad's own electrical rules |

The middle one is not redundant. **`kicad-cli sch erc` resolves a symbol's reference from its
`Reference` property, while eeschema resolves it from the `instances` block** — so a file can
report 0 violations and still open full of duplicate, unannotated `#PWR?` symbols. That is a
defect this project actually shipped; the repo's `CLAUDE.md` records the trap. Run ERC in the
GUI too.

The board keeps its own:

```sh
kicad-cli pcb drc --severity-all -o /tmp/drc.rpt espmmwave-v0.1.0.kicad_pcb
```

## Handoff to the mechanical side

```sh
cad export espmmwave-v0.1.0     # -> exports/espmmwave-v0.1.0.step
cad render espmmwave-v0.1.0 iso # -> exports/espmmwave-v0.1.0-iso.png
```

The STEP is what FreeCAD opens to check the board against the Hammond 1551V3GY case and the
LD2450 bracket. Importing the `.kicad_pcb` directly with the **KiCadStepUp** workbench works
too, and resolves each footprint's 3D model against the library the devshell's `kicad`
ships.
