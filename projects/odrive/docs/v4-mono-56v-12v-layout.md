# ODrive v4-mono 56 V — local 12 V layout and supply connections

> Superseded PCB counts: the subsequent
> [logic ground checkpoint](v4-mono-56v-logic-ground.md) joins these supplies to
> the lower logic reference plane. It has 395 missing connections, 414 warnings
> and seven zones. The placement and local-supply evidence below remain historical.

The fifteen components of the 12 V buck are now grouped on B.Cu. Its input,
bootstrap, switch, timing, Type-3 ripple, feedback and output connections are
routed. The regulator input connects through R170 to C6's DCBUS pad, and its
output connects to the previously routed 5 V input. The two supplies share
local ground copper. The old PGOOD and R2 bias connections are restored.

All components are now inside the board outline. This does not close global
source routing, the system return, output distribution or physical qualification.
The board is not ready to energize or manufacture.

## Placement

The user confirmed that no underside space restriction is defined. L1 requires
up to 10 mm below the board, plus mechanical clearance. The enclosure, mounting
and cooling design must retain that allowance.

| Reference | Center, mm | Rotation |
|---|---|---:|
| U20 | 85, 84 | 0° |
| L1 | 97.7, 86 | 0° |
| C112 | 79.8, 85.4 | 270° |
| C110 / C111 | 77.4, 85.4 / 77.4, 90.5 | 270° |
| C113 | 90.2, 83.3 | 90° |
| C114 / C115 | 106.8, 83.5 / 106.8, 88.5 | 0° |
| R170 | 77, 79.1 | 0° |
| R118 | 82, 79.3 | 90° |
| R110 / R111 | 87, 77.2 / 87, 79.2 | 180° / 0° |
| R215 | 93.7, 77.5 | 0° |
| C214 | 97.3, 77.5 | 0° |
| C215 | 90.2, 76.5 | 180° |

C112 is adjacent to VIN/GND. The bootstrap connection remains on the component
side, and the output sense connection uses the opposite side. The layout uses
the input-loop, timing, feedback and thermal principles in
[TI's LM5164 guidance, sections 7.4.1–7.4.2](https://www.ti.com/lit/ds/symlink/lm5164.pdf).
The existing PowerPAD footprint and its paste/thermal-via treatment still need
manufacturing qualification; no new land-pattern qualification is claimed here.

[Würth's L1 drawing](https://www.we-online.com/components/products/datasheet/7447709101.pdf)
requires no vias or sensitive traces underneath the component. Its maximum
12.5 × 12.5 mm projected body is now x=91.45–103.95, y=79.75–92.25 mm.
A separate native audit checks all four copper layers and every drilled pad/via
against that region. No prohibited items were found. Power copper and ground
planes are permitted by this audit; it does not establish a measured EMI result.
The exclusion is an audited constraint, not yet a KiCad rule-area object, and
must be preserved during subsequent routing.

## Copper and connectivity

Added three local solid GND pours on B.Cu, In1.Cu and F.Cu, connecting to the
existing 5 V ground island. The new pours use priority 1 and 0.6 mm clearance;
the earlier 5 V pours retain priority 0. KiCad rejected equal-priority overlaps
even though both zones were GND, so the three new zone definitions were replaced
through MCP with distinct priorities. Existing rules were not relaxed.

The +12V feed to the 5 V input uses In2.Cu. Separate small-current routes restore
R2's bias supply and U20 PGOOD to the existing R115 connection. These restorations
matter: moving the source parts alone would have disconnected those functions.
The global GND return and remaining rail loads are still open.

Removed 127 obsolete copper items, retaining the other 2152 exactly. Added
76 trace segments and sixteen vias, including the two restored connections.
No schematic, library, net assignment, part value, design rule or firmware
change was made. All PCB mutations used Konnect MCP; native Python was read-only.

## Verification

Saved PCB SHA-256:
`7e5c95d3066232f08961baaad303beada9cf44ef2dca3254f241bbfaddaa39a8`.

| Check | Result |
|---|---:|
| Components / numbered pads / exported nodes | 360 / 1214 / 1092 |
| Missing connections | 513 → 493 |
| Other DRC errors / warnings | 0 / 414 |
| Tracks / vias / zones | 1961 / 283 / 6 |
| Staged / underside components | 0 / 51 |
| Predicted whole-board physical groups | All 751 match |
| Previous physical pad connections | All preserved or merged into larger groups |
| Saved schematic–PCB pad/net parity | Pass |
| L1 body exclusion, all four layers | Pass |

The predicted groups include the local regulator networks and their deliberate
joins to C6, the 5 V input/ground, R2 and R115. A separate assertion verifies
that every old physical pad group is contained in a resulting group; none of
the previous pad connections was lost. Native DRC independently checks for
cross-net shorts and other geometric errors.

Warnings comprise 199 footprint-library differences, 77 silk/mask conflicts,
63 silk overlaps, 42 text-height issues, 32 dangling tracks and one dangling
via. Source/library hashes remain unchanged except for the PCB itself. The
unchanged saved schematic export remains applicable. The schematic editor was
left open; no new live no-op synchronization result is claimed.

Native top/bottom copper detail views were inspected. Full-board native renders
are exported alongside them; most component bodies lack 3D models, so they
primarily show lands and copper rather than a complete assembled product.

Evidence and journals: `.scratch/v4-56v-implementation/pcb-12v-local/`.
Images: `kicad/odrive-v4-mono/exports/12v-layout-2026-09-08/`.

## Remaining work

Complete the source and system-return paths and distribute 12 V/5 V/3.3 V to
their loads. Qualify capacitor MPNs/effective capacitance, input resistance and
filter behavior, feedback tolerances, hot inductance, startup, transient/fault
response, thermal performance and EMI. The rail calculations remain screens
with explicit assumptions, not powered validation. Power-stage, protection,
firmware, manufacturing and bench milestones also remain incomplete.
