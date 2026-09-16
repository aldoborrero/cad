# ODrive v4-mono 56 V — local driver power connections

For the latest board counts and placement, see the subsequent
[interlock placement and brake-signal checkpoint](v4-mono-56v-interlock-layout.md).
The measurements below describe the preserved driver-power checkpoint.

The PCB now connects the driver's local buck supply, ripple injection,
charge pump and bypass returns. Native continuity verifies these connections;
it does **not** establish a working regulator or permission to energize the board.
The local DCBUS and GND islands still need their global feeds, and copper planes,
switching-loop review and physical qualification remain open.

This supersedes the counts and open local connections in the
[initial routing checkpoint](v4-mono-56v-driver-routing.md).

## What changed

VIN and VDRAIN now connect to C202/C203, R203 and the C30 reservoir's DCBUS pad.
VM joins L200/C207, U3.5, C32/C33, R205 and C205. R207/C205/C206 form the physical
ripple-injection network, including its SW, VM and feedback ends. CPL/CPH connect
to C29 and VCP to C30. The remaining local capacitor/divider grounds join U3's
existing ground island. Interface, gate and global reference connections are
outside this completed continuity scope.

The previous front VCC/bootstrap/switch routes enclosed VIN. Moved C203/C204/D200
and the underside C206 to open space for separate VIN and VCC vias. The switching
trunk and diode return were replaced accordingly. Reworked the VGLS escape and
one In1.Cu ground return so VM, VDRAIN and VCP could leave the package without
blocking one another. VM distribution uses In2.Cu around the inductor; ground
returns use In1.Cu and local front/back segments. No zones have been filled.

| Part | Final center, mm | Rotation / side |
|---|---|---|
| C203 | 161.8, 64.8 | 0° / F.Cu |
| C204 | 162.6, 66.8 | 0° / F.Cu |
| D200 | 167.8, 65.1 | 0° / F.Cu |
| C206 | 163.2, 65.8 | −90° / B.Cu |

The seven underside components remain the same. L200 retains the preceding
placement and its 0.5 mm nominal copper-edge margin.

Replaced 25 preceding trace segments; the final board contains 149 new segments
and 23 new vias relative to that baseline, for a net increase of 124 tracks and
23 vias. All other 1462 preceding copper items retain their geometry, net,
width, layer, drill and lock state. New vias are 0.5 mm diameter with 0.2 mm
drills, within the existing KiCad settings; JLCPCB lists 0.2 mm as its preferred
minimum via drill in its [published capabilities](https://jlcpcb.com/capabilities/pcb-capabilities/).
Full fabrication and stackup review remain pending.

Visual review identified an unnecessarily long front return from C207 under the
inductor. Its replacement uses a via 1.125 mm from the ground-pad center and
routes the return on In1.Cu. This improves the local escape; it does not replace
review of the eventual return plane, loop impedance or switching waveforms.

## Verification

Saved PCB SHA-256:
`a568dd9137cb7c3bc1c1163ce55be673629db0c3a027ca0e307bef5819498619`.

| Check | Result |
|---|---|
| Native missing connections | 621, down from 645 |
| Tracks / vias / copper zones | 1456 / 178 / 0 |
| DRC-listed missing connections | 499, report ceiling |
| Other DRC errors / warnings | 0 / 361 |
| Native exact connection groups | 26 pass |
| Components / numbered-pad parity | 357 / 1208; zero discrepancies |
| Live schematic synchronization | No-op |
| New components still staged | 15 |
| Assembly sides | F.Cu and seven B.Cu passives |

The 26 groups include the preceding OV, fuse and snubber groups. Local supply
checks include all six specified DCBUS pads, all seven VM pads, all sixteen
local GND pads, and exact SW, injection, feedback, bias, timing, current-limit,
bootstrap, VGLS, DVDD, AVCC and charge-pump groups. These are native connected
pad sets, not equivalence inferred from matching net labels.

Warnings comprise 199 footprint/library differences, 47 silkscreen-over-copper
findings, 43 text-height findings, 39 silkscreen overlaps, 32 dangling tracks and
one dangling via. No rules were relaxed. Only the PCB changed among the sixteen
protected source files tracked since PCB recovery began.

Evidence is in `.scratch/v4-56v-implementation/pcb-driver-power/`: baseline
archive, reviewed plan, per-call Konnect journals, output-return refinement,
final DRC, native copper/connection audit, placement differences, pad-net parity
and live synchronization reports. The scratch planner only reads/proposes;
all CAD mutations use Konnect MCP.

## Remaining work

Place the fifteen remaining interlock/brake components; connect global DCBUS,
GND and reference consumers; complete gate/source and Kelvin paths, signal
routing and planes. Review the input/diode and output current loops against the
finished stackup, including current density, capacitive coupling and thermal
paths. Connectivity and clearance alone do not qualify these properties.

The acceptance items in [the implementation plan](v4-mono-56v-implementation.md)
remain in force: exact BOM and capacitor bias/ripple validation, supply startup,
overvoltage/brake coordination, complete controller firmware, manufacturing
outputs and bench tests. No hardware was programmed or powered.

Five native images are under
`kicad/odrive-v4-mono/exports/driver-power-2026-09-08/`: top, bottom, F.Cu/B.Cu
details and the two inner copper layers. No component 3D associations are present;
these are board/pad/routing views, not a populated-assembly model. All five
final images were visually inspected.
