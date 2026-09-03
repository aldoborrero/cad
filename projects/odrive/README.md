# odrive (KiCad)

ODrive brushless motor controller: a faithful KiCad 10 recreation of the v3.5
schematic, and a v4 redesign derived from it.

Upstream: [madcowswe/ODriveHardware](https://github.com/madcowswe/ODriveHardware)
(Altium sources; we work from a local fork clone). Firmware is open source (MIT) at
odriverobotics/ODrive up to v0.5.6, which supports every v3.x board.

## Layout

```
docs/
  v3.5-weaknesses.md    # audited weak points of the v3.5 design (workflow phase: Audit)
  v4-design.md          # v4 design decisions with rationale (workflow phase: Design)
kicad/
  odrive-v3.5/          # faithful v3.5 schematic (no PCB) — the audited baseline
  odrive-v4/            # the v4: schematic + 4-layer board
workflow/
  e2e.js                # oracle-gated end-to-end Workflow script (see below)
```

Reference material lives in `.scratch/odrive/` at the repo root (gitignored, per repo
convention): `schematic_v3.5.pdf` (the 24V variant), `CHANGELOG.md`, board photos, and
`netlist-ref/` (netlist ground truth extracted from the PDF by the workflow). Refresh
from `/mnt/c/Users/aldob/dev/ODriveHardware/v3/` if missing.

## Scope decisions (2026-09-03)

- **Architecture: modernized.** Keep STM32F405RGT6 (firmware nearly intact); replace
  the NRND DRV8301 with DRV8353RS (100 V, SPI, integrated buck + 3 CSAs); modern FETs;
  USB-C; better CAN; add the protections v3.5 lacks.
- **Bus voltage: both variants.** One design, two BOMs — 24 V and 56 V.
- **v3.5 conversion: faithful schematic only.** Clean ERC, netlist checked against the
  PDF (which embeds the Altium netlist as text). No v3 PCB recreation.
- **Form factor: free.** Connectors and dimensions optimized, not v3.5-compatible.

## The end-to-end workflow

`workflow/e2e.js` drives the whole flow with oracle gates: every phase's output is
verified by adversarial/judge agents before the next phase consumes it. Phases:

| Phase | Needs | Output |
|-------|-------|--------|
| Gate | — | Konnect MCP + KiCad IPC availability |
| Audit | PDF only | `docs/v3.5-weaknesses.md` (findings, adversarially verified) |
| Design | Audit | `docs/v4-design.md` (judge panel: electrical / firmware / manufacturability) |
| Extract | PDF only | `.scratch/odrive/netlist-ref/*.json` (ground truth per sheet) |
| Rebuild | Konnect | v3.5 schematic in KiCad; oracle diffs exported netlist vs ground truth |
| V4Schematic | Konnect | v4 schematic; ERC + design-review oracle loop |
| Layout | Konnect + KiCad IPC | v4 4-layer board; DRC oracle loop |
| Fab | Layout done | gerbers, 24V/56V BOMs, pick-and-place in `kicad/odrive-v4/exports/` |

Phases that need tools this session lacks are skipped with a `blocked` status and
instructions; re-running the workflow resumes where it left off (completed outputs are
detected on disk).

**Konnect requirement:** the Konnect MCP server is registered in this repo's
`.mcp.json`, so the Claude session must be started *inside this worktree* (direnv puts
`konnect` on PATH). For the Layout phase, KiCad's IPC API must be live: start KiCad
(GUI, or `xvfb-run kicad` headless) with the API server enabled
(socket `ipc:///tmp/kicad/api.sock`).

## Build

```sh
cad render odrive/kicad/odrive-v4 [iso|top|bottom|...]   # raytraced PNG -> exports/
cad export odrive/kicad/odrive-v4                        # STEP -> exports/
cad gui    odrive/kicad/odrive-v4                        # open in KiCad
```
