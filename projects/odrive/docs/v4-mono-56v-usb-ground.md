# ODrive v4-mono 56 V — USB connector ground escape

J6's coincident A12/B1 ground lands now connect to the interior logic GND
plane. Previously these two pads formed an isolated physical group, while
the opposite A1/B12 lands already belonged to the main logic return.
USB data routing and complete interface qualification remain open.

## Applied change

The adjacent VBUS via blocked a direct ground escape. Moved it from
(110.4131, 151.1718) to (109.4, 151.08), using a 0.5 mm pad / 0.2 mm drill.
Replaced its two F.Cu approach segments and one B.Cu segment with a short
F.Cu approach and three B.Cu segments around the new GND via. VBUS routing
remains 0.2 mm wide; this change does not establish its current rating.

Added a 1.07 mm long, 0.3 mm wide F.Cu connection from A12/B1 at
(110.2, 152.32) to a 0.5/0.2 mm through-via at (110.2, 151.25). Refilling
the seven existing GND zones joins it to the interior logic plane.
CC2, shield routing, footprints, schematic, libraries and rules are unchanged.

All PCB mutations used Konnect MCP against the live PCB editor. The schematic
editor's pending save/close dependency does not affect this PCB-only change.

## Verification

- Native whole-board connectivity preserves every previous physical pad
  connection. The only group change is the intended merge of A12/B1 with
  the main GND group: 647 → 646 numbered-pad groups, GND 10 → 9 groups.
- 2451 retained tracks/vias have identical native geometry, net and layer
  data. Three segments and one via were replaced; five segments and two
  vias were added. All 1214 numbered pads retain position and assignment.
- Saved schematic parity passes for 360 components and 1092 net nodes.
  All 20 non-PCB protected source files retain their hashes.
- Native DRC: **388 unconnected, 414 warnings, zero other errors**.
  Warnings remain 199 footprint mismatches, 77 silk over copper, 63 silk
  overlaps, 42 text-height, 32 dangling-track and one dangling-via warning.
- Board totals: 2081 tracks, 377 vias, seven GND zones and 57 components
  on B.Cu. No components were moved or added. New copper lies below y=149 mm,
  outside the L1 body exclusion.
- Native F.Cu, B.Cu and In1.Cu detail exports were visually inspected.

Saved PCB SHA-256:
`c120e93c612254e73946070022709e03bd2994276d5cb5e7a06c8da278ece852`.
Evidence is under `.scratch/v4-56v-implementation/pcb-usb-ground/`, including
the pre-change snapshot, route plan, MCP journal, DRC, native audit and parity.
The annotated native detail is in
`kicad/odrive-v4-mono/exports/usb-ground-2026-09-08/retorno-masa-usb.png`.

This closes one physical ground connection. It does not complete USB D+/D−,
CC1, the board's power/analog returns, or physical EMI and interface testing.
