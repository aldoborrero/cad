# ODrive v4-mono 56 V — local overvoltage layout

This records the OV routing checkpoint. The later
[driver placement checkpoint](v4-mono-56v-driver-layout.md) supersedes the board
counts and staging status below while preserving the six local OV connections.

The reference, comparator input network and local bypass returns are now placed
and routed on the PCB. This advances the earlier
[synchronization checkpoint](v4-mono-56v-pcb-sync.md); the controller is still
unrouted outside this local scope and is not ready for manufacture or operation.

## Placement and routing

C210 and C211 moved from off-board staging to the reference and comparator.
C62, C61, R93, R94 and R95 moved from their inherited remote positions into the
same block. U13 remains at (153, 111.3) mm and U12 at (153, 115) mm. Their supply
bypass and reference output capacitor now sit adjacent to the relevant pins.
U15 moved to (162, 123) mm to make space, with C65 at (165.8, 122) mm.

The layout follows the local-bypass and short-input goals in
[REF35 section 9.4](https://www.ti.com/lit/ds/symlink/ref35.pdf#page=27) and
[TLV3201 section 8.4](https://www.ti.com/lit/ds/symlink/tlv3201.pdf#page=18).
The comparator input/filter/divider connections use F.Cu. The reference branch
to U12 and output feedback to R95 use separate B.Cu paths. The feedback passes
around the input network. Local returns use 0.5 mm GND traces on In1.Cu and
0.6/0.3 mm through vias, pending a continuous ground plane and system return review.
Supply/reference/input/feedback signal traces are 0.25 mm; local front ground
connections are 0.3 mm. These widths do not define power-current capability.

Four old DRV_EN_MCU front-layer segments terminating at U15's former position were
removed. Its incoming via and upstream routing remain; the new U15 location still
requires its input/output logic connections. Sixty-one new track segments and
13 vias implement the local networks. Every other previously retained track/via
was checked against the original archive and is geometrically unchanged.

Initial placement checks found real courtyard extents larger than a body-only
estimate, and retained signal traces crossed two proposed capacitor positions.
The final placement uses the actual courtyards. The first ground routes also
intersected through vias on In1.Cu; they were rerouted with clearance and checked
again. No DRC rules were relaxed.

## Verified connections and remaining boundaries

Native KiCad connectivity, separate from net-name parity, verifies these exact
local connected pad sets:

| Local network | Physically connected pads |
|---|---|
| Reference | C62.1, U13.6, U12.4 |
| Comparator input | C211.1, R93.2, R94.1, R95.2, U12.3 |
| Comparator feedback | U12.1, R95.1 |
| OV local supply | C210.1, U13.3, U13.4, C61.1, U12.5 |
| Enable gate local supply | C65.1, U15.5 |
| Local ground | C210.2, U13.1, U13.2, C62.2, C61.2, U12.2, C211.2, R94.2, C65.2, U15.3 |

These are local islands. The DCBUS feed to R93, VCC distribution, connection to
the system ground, reference feed to U26, and OV output to the brake/interlock
logic are still pending. In particular U26.4 has the same reference net name but
is not physically connected to the reference island; the native check confirms
that distinction. Retained signal routing under the region and the final ground
planes still require coupling/return-path review.

Board SHA-256 at this checkpoint:
`3616412a17e4bfc890ed56c1eb03781fa6085097b46f3c45feb00c546e3e4847`.

| Check | Result |
|---|---|
| Footprints / numbered-pad correspondence | 357 / 1208, zero discrepancies |
| Final schematic synchronization | No-op |
| Tracks / vias / zones | 1265 / 149 / 0 |
| Original retained copper still geometrically unchanged | 1340 items; four obsolete U15 stubs removed |
| Native missing connections | 666, down from 686 |
| DRC missing connections listed | 499, capped by the report |
| Other DRC errors / warnings | 0 / 324 |
| New components still staged outside the outline | 31 |

Warnings comprise 199 footprint/library mismatches, 43 text-height findings,
32 dangling tracks, 25 silkscreen-over-copper findings, 24 silkscreen overlaps
and one dangling via. The latter is the retained incoming DRV_EN_MCU via after
removing its old U15 stubs; it awaits the relocated logic connection.

Evidence is under `.scratch/v4-56v-implementation/pcb-placement/`:
`before-ov.tar.gz`, placement/route plans and progress, `ground-clearance-repair.json`,
`drc-ov-final.json`, `ov-connectivity-audit.json`, `ov-metadata.json`,
`ov-parity.json`, `ov-sync-final.json` and `ov-traces-final.json`.
`audit-ov.py` performs read-only native connectivity and retained geometry checks.
The top render and enlarged native layer plot are under
`kicad/odrive-v4-mono/exports/ov-placement-2026-09-08/`.

The driver buck, arm/reset/brake logic, full power and sensing layout, ground
planes and remaining routing are still open. Physical OV thresholds, startup,
noise, brake latency/energy and thermal behavior remain unqualified. No schematic
or firmware changes, fabrication export, ordering or device programming occurred
in this layout step.
