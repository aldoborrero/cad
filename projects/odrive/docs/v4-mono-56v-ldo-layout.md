# ODrive v4-mono 56 V — local 3.3 V regulator layout

U22's digital 3.3 V regulator and U23's analog 3.3 V regulator now have their
local input, enable, output-capacitor and return connections. The 5 V source
feeds, connections to their consumers and continuous reference planes remain
open. This checkpoint does not establish regulated operation.

## Placement and routing

Moved C122/C123 beside U22. The crowded front-side area around U23 could not
accommodate its capacitors with the retained copper and component courtyards.
Moved U23, C124, C125, FB1 and NT1 to B.Cu and grouped them locally. U23 keeps its
original center. The board now has 36 underside components.

| Part | Center, mm | Rotation | Side |
|---|---|---|---|
| U22, unchanged | 183.5, 115 | 0° | F.Cu |
| C122 | 183.5, 112 | 0° | F.Cu |
| C123 | 186.6, 112 | 180° | F.Cu |
| U23 | 80, 129.5 | 0° | B.Cu |
| C124 | 74.8, 129.6 | 90° | B.Cu |
| C125 | 80, 132.6 | 180° | B.Cu |
| FB1 | 74.8, 125.8 | −90° | B.Cu |
| NT1 | 80, 126.7 | 0° | B.Cu |

Replaced six previous AVCC_IN segments associated with U23's IN/EN connection
and the remote FB1/C124 connection. Retained all other 2197 copper items with
their exact geometry, net, layer, width, drill and lock state. Added 50 segments
and four vias for twelve endpoint joins; two joins restore those previous
connections. All new segments are 0.4 mm wide; vias are 0.5/0.2 mm.

The output-pin-to-capacitor paths are approximately 3.59 mm for U22 and 2.30 mm
for U23, without layer changes. Their capacitor returns also remain on the
component side. U23's input-capacitor feed crosses existing routing using two
vias; its GND return uses two more. NT1 preserves the schematic's GND/AGND tie:
C124 returns to GND, while U23 and C125 return to AGND. Native connectivity
maintains these distinct net groups; the footprint's copper bridge provides
the intentional tie.

Both TI layout guides call for capacitors close to the regulator and suitable
copper for heat spreading: [TLV755P, layout section](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)
and [TPS7A20, layout section](https://www.ti.com/lit/ds/symlink/tps7a20.pdf).
The TPS7A20 specifies at least 0.47 µF effective output capacitance, with 1 µF
nominal recommended. These existing nominal capacitor values are not yet an
exact-part/DC-bias/temperature qualification. Rail load budgets, thermal design,
startup and transient measurements remain necessary.

## Verification

Saved PCB SHA-256:
`16c3a440e12c26e720b58cf11b27336f83083b11de3cfed7db21cf15dde52e0c`.

| Check | Result |
|---|---|
| Native missing connections | 519, down from 529 |
| Tracks / vias / zones | 1979 / 272 / 0 |
| Other DRC errors / warnings | 0 / 398 |
| Component / numbered-pad parity | 357 / 1208; zero discrepancies |
| Whole-board native pad groups | All 776 predicted groups match exactly |
| Preserved preceding copper | 2197 items; six deliberately replaced |
| Live schematic synchronization | No-op |
| Staged / underside components | 0 / 36 |

The connectivity prediction starts with the archived pre-change board, including
the two groups temporarily broken during relocation, and unions only the twelve
planned pairs. Thus it checks restored connections as well as new ones, across
all numbered pad UUIDs. Selected local groups are recorded in the audit report.

The first routing DRC found one hole-clearance violation between a new GND via
and NT1's copper polygon. The planner's pad/track model did not include that
footprint graphic. Moved the via 0.3 mm away and replaced its two adjacent
segments with three. Final native DRC passes apart from missing connections;
no rules were relaxed. This footprint-graphic limitation must be accounted for
in future planning near net ties. Warnings comprise 199 footprint/library
differences, 67 silkscreen-over-copper, 56 silkscreen overlaps, 43 text-height
findings, 32 dangling tracks and one dangling via.

All mutations used Konnect MCP. Only the PCB differs among the sixteen protected
source hashes recorded at recovery. Firmware was unchanged and no hardware was
programmed or energized. Four native images were visually inspected under
`kicad/odrive-v4-mono/exports/ldo-local-2026-09-08/`: top, bottom and details of
both regulators. No component 3D models are associated with the board; the back
detail looks through from above, so its text is mirrored.

Evidence: `.scratch/v4-56v-implementation/pcb-ldo-local/`, including the baseline
archive, placement/flip/deletion journals, final route plan, via repair,
whole-board connectivity prediction and audit, parity, DRC and live sync.

## Next work

Review and compact the 12 V and 5 V buck circuits before connecting the global
feeds. U20 SW and U21 SW are still disconnected from the remote inductor
islands; retained copper on an inductor does not establish a working switching
loop. Their bootstrap, input/output capacitors and feedback placement require
review. Then distribute 5 V, VCC, AVCC and references, including the MCU and
supervisor bypasses and power-good paths. Power-stage routing, planes, thermal
review, protection coordination, complete firmware, manufacturing and bench
acceptance remain open in the [implementation plan](v4-mono-56v-implementation.md).
