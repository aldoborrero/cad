# ODrive v4-mono 56 V — logic ground reference and returns

The logic section now shares an In1.Cu GND reference with the local 12 V and
5 V supplies. Added 97 short trace segments and 87 through-vias, retaining all
2244 preceding tracks/vias exactly. Missing connections fall from 493 to 395.
The complete controller, rail distribution and power returns remain unfinished.

## Ground domains and layout

The new `Logic GND reference` zone has vertices, in millimetres:
`(51,89), (73,89), (73,110), (189,110), (189,161), (51,161)`.
It uses In1.Cu, priority 2, 0.6 mm clearance, 0.2 mm minimum fill width and
thermal pad connections. The left corridor joins the existing regulator ground
zones. Their definitions remain; all seven zones are refilled through live MCP.

Short F.Cu stubs and 0.5/0.2 mm through-vias connect MCU VSS, digital regulator
returns, bypass capacitors, logic, interface protection and connector grounds
to that plane. Existing long ground routes were retained. Their parallel plane
connection does not by itself qualify return impedance or EMC performance.

| Domain | Physical pad groups before | After |
|---|---:|---:|
| GND | 108 | 10 |
| AGND | 32 | 32 |
| PGND | 33 | 33 |

All lower-section GND pad groups join the regulator ground group except the
coincident J6 A12/B1 USB grounds. Existing VBUS/CC2 tracks and connector holes
block the checked escape there; local USB routing must be revised. J6 A1/B12
already joins the plane. The other remaining GND groups are the upper driver
island, R25–R30 pulldowns and H4. These are explicit open work, not isolated
grounds intended for operation.

NT1's GND side joins the plane; its AGND connectivity is unchanged. NT2's GND
side now joins it too, but its PGND side is still unrouted. NT2 is currently
about 53 mm from the DRV8353 center. The historical description of a tie
"near the driver" is therefore not satisfied. Its position and the driver/power
return structure must be reviewed together before routing the power ground.
Brake power parts also extend into the nominal logic half; a y-coordinate split
alone cannot determine their high-current return path.

The layout review uses the local bypass and switching-loop guidance in
[TI's LM5164 datasheet, section 7.4](https://www.ti.com/lit/ds/symlink/lm5164.pdf)
and the separate gate/source sensing and high-current path guidance in
[TI's DRV8353 datasheet, section 11.1](https://www.ti.com/lit/ds/symlink/drv8353.pdf).
Those principles still require a complete power-cell and analog-return review.
This checkpoint establishes physical connectivity, not transient, thermal or
motor-current qualification. The legacy external HV-clearance claims also need
reconciliation with the actual board rules; the new zone's clearance is not a
claim of compliance with those legacy claims.

## Verification

Saved PCB SHA-256:
`cb64af571792b5c460257118e71034e89313ddb07069969dcc49452e908b402b`.

| Check | Result |
|---|---:|
| Footprints / numbered pads / exported schematic nodes | 360 / 1214 / 1092 |
| Missing connections | 493 → 395 |
| Other native DRC errors / warnings | 0 / 414 |
| Tracks / vias / zones | 2058 / 370 / 7 |
| Predicted whole-board physical pad groups | All 653 match |
| Old tracks/vias retained without change | 2244 |
| Previous physical pad connections | All preserved |
| All non-GND physical groups | Unchanged |
| Saved schematic–PCB parity | Pass |

The first native DRC found a new NT2 via too close to the net-tie's copper
graphic, which the scratch geometry planner did not model. Replaced only that
new via and stub through MCP; final hole-clearance DRC passes. No rule was relaxed.
Whole-board pad groups are compared by UUID, including repeated thermal lands.
The parity export decodes KiCad's escaped net names; literal `{slash}` storage
otherwise produces false differences for two unconnected SWD pins.

Warnings remain 199 footprint-library differences, 77 silk/mask conflicts,
63 silk overlaps, 42 text-height issues, 32 dangling tracks and one dangling via.
No schematic, library, footprint placement, rule or firmware changes were made.
L1's exclusion is preserved: all old copper/pads remain and every new copper
item is below y=110 mm, away from its body ending at y=92.25 mm. The user's
absence of an underside height restriction remains recorded in the 12 V layout.

Evidence: `.scratch/v4-56v-implementation/pcb-logic-ground/` contains before/after
audits, intended joins, MCP journals, DRC and parity reports. Native top/bottom
board renders and exported copper views are in
`kicad/odrive-v4-mono/exports/logic-ground-2026-09-08/`.
All four views were visually inspected. The PCB has no attached component 3D
models, so these renders show the bare board and footprints; they do not
establish assembled height or mechanical fit.
