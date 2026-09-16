# ODrive v4-mono 56 V — initial driver routing

This initial checkpoint is superseded by
[local driver power connections](v4-mono-56v-driver-power.md), which records the
current routing and four further placement changes.

The driver has local ground, bypass and buck control connections on the PCB.
This supersedes the routing counts in the [placement checkpoint](v4-mono-56v-driver-layout.md).
The regulator is **not yet electrically complete**: its input feeds, full output
distribution, ripple injection and remaining returns are open.

## Physical changes

Added 65 tracks and six through vias relative to the placement checkpoint.
All 1416 preceding copper items retain their exact geometry, layers, widths,
drills, net assignments and lock state. No copper zones have been added.

The switching trunk connects U3.42, D200.1 and L200.1; C204.2 now lands on that
trunk. L200.2 connects to C207.1. U3's three ground pins connect to its exposed
pad, with local D200/C200/C31/C34 returns through In1.Cu. VGLS, DVDD and the local
AVCC bypass connection are routed. These returns form a local island, not a
completed system ground plane or a qualified switching-current return path.

The feedback group joins U3.48, R205.2, R206.1 and C206.2, using one via to the
underside. Separate routes connect RT to R203, RCL to R204, BST to C204 and
internal buck VCC to C201. Neither the feedback divider's supply/ground ends nor
the opposite ends of R203/R204 are connected yet.

Routing exposed a placement problem: the earlier C203/C204 arrangement required
a bootstrap detour longer than 6 mm and obstructed fine-pitch fanout. C203 moved
from (161.3, 67.2) to (161.3, 65.1) mm; C204 moved from (158.9, 68.1) to
(162.6, 67.65) mm. The new BST trace is about 2.1 mm long. D200 moved 0.3 mm up
and L200 0.1 mm up to clear their courtyards while preserving connections.
L200's closest pad is now 0.5 mm from the nominal upper board edge, matching
the current copper-edge rule; enclosure and manufacturing review remain open.
No additional parts changed side. Assembly still includes seven B.Cu passives.

Short bypass and switching connections follow the priorities in
[TI's DRV8353 layout guidance, section 11.1](https://www.ti.com/lit/ds/symlink/drv8353.pdf#page=78).
This is an intermediate layout; passing clearance checks does not qualify
regulator stability, noise coupling, switching loops or temperature rise.

## Verification

Saved board SHA-256:
`0683080a9b0e01179300bbefd2b1f87a1818cb0e42a3fcd56f8a38d821d720a5`.

| Check | Result |
|---|---|
| Components / numbered pads | 357 / 1208; zero parity discrepancies |
| Live schematic synchronization | No-op |
| Tracks / vias / copper zones | 1332 / 155 / 0 |
| Native missing connections | 645, down from 666 at placement |
| DRC-listed missing connections | 499, report ceiling |
| Other DRC errors / warnings | 0 / 357 |
| New components still staged | 15 |
| Exact native connection groups | 21 passing, including all ten preceding groups |
| Changed component placements | C203, C204, D200, L200 |

Warnings comprise 199 library/footprint differences, 44 silkscreen-over-copper
findings, 43 text-height findings, 38 silkscreen overlaps, 32 dangling tracks and
one dangling via. No design rules were relaxed. The saved schematic, libraries
and tables remain unchanged since PCB synchronization began.

Evidence is in `.scratch/v4-56v-implementation/pcb-driver-routing/`: the baseline
archive, mutation journals, final DRC, native geometry/connection audit, pad-net
parity report, placement differences and final live synchronization report.
The scratch clearance planner reads native geometry and proposes routes; all
source mutations use Konnect MCP. Its conservative geometry checks supplement,
and do not replace, KiCad DRC and physical review.

## Remaining driver work

- Connect DCBUS to VIN/VDRAIN, C202/C203, R203 and the charge-pump reservoir.
- Complete VM distribution to U3/C32/C33, R205 and the ripple network.
- Route R207/C205/C206 injection and the charge-pump capacitor/reservoir.
- Connect C201/C202/C203/C207 and R204/R206 returns; design and review the
  input-diode and output return loops together with the future planes.
- Complete interface/enable/fault and gate/Kelvin routing, full-board supplies,
  placement of the remaining 15 parts, and the rest of the acceptance plan.

Exact capacitor MPNs, bias-adjusted capacitance, startup, thermal/ripple budgets,
overvoltage coordination, complete firmware and physical tests remain open.

Top/bottom renders and native F.Cu/B.Cu details are in
`kicad/odrive-v4-mono/exports/driver-routing-2026-09-08/`. All four PNGs were
visually inspected. The render lacks component 3D associations, so it shows the
board, pads and markings rather than a populated assembly. Back-layer details
use board coordinates viewed from above; the bottom render shows the underside.
