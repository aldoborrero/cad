# ODrive v4-mono 56 V — interlock placement and local brake signals

For the latest board state, see the subsequent
[arm-logic and bus-measurement routing checkpoint](v4-mono-56v-arm-divider-routing.md).
The measurements below describe the preserved placement/brake checkpoint.

All fifteen previously staged parts now have positions inside the board outline.
Seven existing divider/bypass parts moved closer to their associated circuits.
The local brake reset, overcurrent, feedback and command connections are routed.
The arm latch, divider, bypasses and global feeds still require routing; this
checkpoint does not establish a functional brake or motor controller.

This supersedes the placement and board counts in the
[driver power checkpoint](v4-mono-56v-driver-power.md).

## Placement

U56/U57/U59 and their passives sit behind the enable/OV logic. U58 and the brake
pulldowns sit behind U52/U53. R209 remains on the front near U3's ENABLE input;
R210/R213 are on the back near the MCU feedback pins. R211/R70/R71/C70 now form
a smaller divider area near U10. C167–C170 and C212 were reoriented to bring
their supply and return terminals closer to the corresponding ICs; their final
return paths remain to be designed.

Twenty-one components changed from F.Cu to B.Cu. Including the seven driver
passives already there, assembly now includes 28 underside components, four
of them logic ICs. No existing connected component was moved in this step.

The first placement produced 22 DRC errors, including shorts, insufficient
clearance, courtyard overlaps and solder-mask bridges. Nearby placement repairs
removed them. A subsequent continuity audit found C213's ground pad over an
existing same-net via despite a clean DRC; C213 moved to separate pad and drill.
No design rules or existing copper were changed to obtain clearance.

## Physical connections added

| Net / function | Exact connected pads |
|---|---|
| BRK_OK, including U53 feedback | U53.3, U53.4, R214.1, U55.3 |
| BRK_OC_N | U52.1, R212.1, U53.6, U55.6 |
| BRK_RESET_ACTIVE | U58.4, U53.1 |
| BRK_CMD | U54.4, U55.1 |

Added 26 trace segments and three 0.5 mm / 0.2 mm vias. The signal routes use
F.Cu and B.Cu. U53's feedback is a direct 2.275 mm front trace. These four groups
close eight native missing connections. R212/R214's ground ends remain open,
as do the logic supplies and the connections to the wider protection circuit.

## Verification

Saved PCB SHA-256:
`8d3e0eda03df72fb4b31cb55b96b4541f8c350a5ec43027561a1ed7363ab1558`.

| Check | Result |
|---|---|
| Native missing connections | 613, down from 621 |
| Tracks / vias / copper zones | 1482 / 181 / 0 |
| Other DRC errors / warnings | 0 / 374 |
| Native exact connection groups | 30 pass, including all 26 preceding groups |
| Preserved preceding copper items | All 1634, with exact geometry and assignments |
| Components / numbered-pad parity | 357 / 1208; zero discrepancies |
| Live schematic synchronization | No-op |
| New components still staged | 0 |
| Back-side components | 28 |

DRC lists only 499 missing connections because of its report ceiling; the native
connectivity count above is uncapped. Warnings comprise 199 footprint/library
differences, 52 silkscreen-over-copper findings, 47 silkscreen overlaps, 43 text
height findings, 32 dangling tracks and one dangling via. They remain open.
Only the PCB changed among the sixteen protected sources tracked from recovery.

Evidence is in `.scratch/v4-56v-implementation/pcb-interlock-placement/`:
baseline archive, per-call Konnect journals, placement repair proposals,
final placement differences, `drc-brake.json`, `brake-audit.json`,
`brake-metadata.json`, `brake-parity.json` and `sync-final.json`.
Planners and native audits are read-only; all source mutations used Konnect MCP.
KiCad was closed for the flips and reopened for the final moves and routing.

Six native images were visually inspected under
`kicad/odrive-v4-mono/exports/interlock-placement-2026-09-08/`: top and bottom
board views, front/back brake details, underside arm logic and divider details.
The underside copper details are viewed from above, so their text is mirrored.
No component 3D models are associated; the overview renders show board/pads,
not a populated assembly.

## Next work and limits

Route the arm latch, MCU feedback, divider and local supply/return paths. Review
bypass loop geometry while doing so; placement alone does not establish useful
decoupling. Then complete global DCBUS/GND/AGND/VCC feeds, gate/source and Kelvin
paths, remaining signals and copper planes. Package qualification, independent
watchdog/external stop, startup behavior, OV/brake coordination, thermal and
regeneration limits, complete controller firmware, manufacturing and bench
validation remain required by the [implementation plan](v4-mono-56v-implementation.md).
No hardware was programmed or energized.
