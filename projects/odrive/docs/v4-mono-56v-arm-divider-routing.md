# ODrive v4-mono 56 V — local arm logic and bus-measurement routing

For the latest board state, see the subsequent
[interlock distribution checkpoint](v4-mono-56v-interlock-distribution.md).
The measurements below describe the preserved arm/divider checkpoint.

The local U56/U57/U59 arm logic, its supply/bypass connections, and the bus
divider/buffer/filter signal path now have PCB connections. MCU feedback pads
and the driver's ENABLE pad also have their local resistor connections.
Global interlock inputs, enable/request trunks, power and reference feeds are
still missing. This is a routing checkpoint, not a working measurement or arm
circuit. It supersedes the counts in the
[interlock-placement checkpoint](v4-mono-56v-interlock-layout.md).

## Placement corrections

D10, the divider-input clamp, was at (173, 129.5), approximately 77 mm from U10.
R72 was at (141.5, 137), far from both its buffer and ADC filter. Moved D10 near
the divider and R72/C71 near MCU PA6. All three now use B.Cu. Moved C63 from
(113.5, 123.5) to provide local AVCC bypass at U10. None of these four parts had
copper connections before moving. C208/C209/C213 were also reoriented and moved
after preliminary routing exposed unnecessary supply/return detours.

| Component | Final center, mm | Rotation / side |
|---|---|---|
| D10 | 95.1, 119.8 | 90° / B.Cu |
| R72 | 62.3, 126.7 | 180° / B.Cu |
| C71 | 58.2, 127.0 | −90° / B.Cu |
| C63 | 98.5, 111.3 | 180° / F.Cu |
| C208 | 161.5, 128.7 | 180° / B.Cu |
| C209 | 161.5, 115.0 | 180° / B.Cu |
| C213 | 155.9, 125.2 | 180° / B.Cu |

The first D10/R72/C71 placement caused twelve additional DRC errors. Nearby
translations cleared existing copper and courtyards; rules were not relaxed.
The final board has 31 underside components and no staged components.

## Connections made

- U56 CLK joins R208 and U15's request input; Q joins U15's armed input.
  U57's clear output joins U56 CLR, U59's ready output joins U57, and U14's
  inverted OV output joins U57. U56 D/PRE/VCC and all three local bypass supplies
  join U15/C65 VCC. Their ground returns join the existing local OV/enable island.
- R211/R70's midpoint is connected. R70/R71/C70/D10 and U10's input share the
  divided-voltage node. U10's first amplifier has feedback and connects to R72;
  R72/C71 connect to PA6, U2.22. C71's return reaches U2.12 (AGND).
- D10/C63 and U10's supply pin form a local AVCC island. Their local AGND
  connections join R71/C70 and U10's ground/unused-amplifier input. U10's existing
  second-amplifier output-to-inverting-input connection is preserved.
- R210's MCU end reaches PC6/U2.37, and R213's MCU end reaches PC7/U2.38.
  R209's signal end reaches U3.33. These are local ends; the corresponding source
  trunks and R209's ground end are still open.

Added 169 segments and 35 vias for 41 endpoint joins. New tracks are 0.2 mm;
new vias are 0.5 mm diameter / 0.2 mm drill. Ground crossings use In1.Cu and
signal/supply crossings use In2.Cu, with local front/back routing. The buffered
U10-to-R72 route is approximately 37.6 mm. No copper zones are present, so
continuous reference-plane and analog-noise qualification remain open.

## Verification

Saved PCB SHA-256:
`54a2ead89e715855553876f47c985dd23a82c586315d58ce788d3060f57a6f1b`.

| Check | Result |
|---|---|
| Native missing connections | 572, down from 613 |
| Tracks / vias / copper zones | 1651 / 216 / 0 |
| Other DRC errors / warnings | 0 / 390 |
| Components / numbered-pad parity | 357 / 1208; zero discrepancies |
| Whole-board native pad connectivity | All 829 predicted groups match exactly |
| Preserved prior copper | All 1663 items, including geometry and assignments |
| Live schematic synchronization | No-op |
| Staged / underside components | 0 / 31 |

The connectivity prediction starts from all 1208 numbered copper pads and their
native pre-routing groups, then unions only the 41 planned endpoint pairs. The
saved board's entire partition matches that prediction: no prior group is split
and no additional pad group is merged. This checks more than shared net names or
selected local continuity samples; it does not model component behavior.

DRC lists only 499 unconnected items because of its report ceiling. The native
count above is uncapped. Warnings comprise 199 footprint/library differences,
63 silkscreen-over-copper findings, 52 silkscreen overlaps, 43 text-height
findings, 32 dangling tracks and one dangling via. Only the PCB changed among
the sixteen protected source files tracked since recovery began.

Evidence lives in `.scratch/v4-56v-implementation/pcb-arm-divider/`: baseline
archive, seven final placement differences, Konnect mutation journals,
`local-plan.json`, `expected-connectivity.json`, `local-audit.json`,
`local-metadata.json`, `local-parity.json`, `drc-local.json` and `sync-final.json`.
All source changes used Konnect MCP. Native geometry/planning/audits are read-only.

Nine final native images were visually inspected in
`kicad/odrive-v4-mono/exports/arm-divider-2026-09-08/`: top/bottom board views,
front/back arm, divider and ADC details, plus an inner-copper overview. Back
detail views look through from above and have mirrored text. No component 3D
models are associated; board renders do not depict a populated assembly.

## Remaining work

Connect the MCU request trunk, actual-enable distribution and feedback source,
BRK_OK distribution and feedback source, NRST and RAILS_OK inputs, R209 ground,
and the remaining brake supply/return paths. Connect R211's DCBUS feed and the
global AVCC/AGND/VCC/GND distribution. In particular, the U10 and MCU analog
ground islands are still separate; the ADC path cannot yet be credited with a
common reference. Local arm VCC/GND also still need their global feeds.

Then complete gate/source and Kelvin paths, power distribution, other signals,
reference planes and thermal review. Exact BOM/package qualification, supply
startup, OV/brake coordination, independent watchdog/external stop, complete
controller firmware, fabrication outputs and physical validation remain in the
[implementation plan](v4-mono-56v-implementation.md). No hardware was programmed
or energized.
