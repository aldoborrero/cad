# ODrive v4-mono 56 V — PCB synchronization checkpoint

This records the initial synchronized board. The later
[local OV placement/routing checkpoint](v4-mono-56v-ov-layout.md) supersedes its
current-state counts and positions while preserving this evidence.

The saved PCB now implements the repaired schematic's component identities and
pad/net assignments. Electrical placement and routing remain incomplete. This
checkpoint does not qualify the 56 V design for fabrication or operation.

## Changes

The original board had 325 footprints, 2682 tracks, 454 vias and 27 copper zones.
An archived comparison against the repaired schematic detects 410 discrepancies
in reference/library/value/pad-net correspondence, including missing components
and pads. These are comparison findings, not 410 independent electrical faults.

Konnect initially rejected synchronization with 116 conflicts: 27 footprint
library changes, 87 routed pad-net changes and two schematic identity changes.
Its guard considers copper anywhere on either the old or new net. The reviewed
rework therefore removed 1474 tracks, 318 vias and all 27 zones on affected nets,
including 129 locked copper items. This removal was deliberate and is archived;
it is why the missing-connection count increased.

Twenty-nine footprints were replaced and obsolete R96 removed. The subsequent
atomic synchronization added 62 footprints (29 replacements and 33 new parts),
updated 22 existing footprints and reassigned 87 pads. Replacements include the
Infineon MOSFET packages, eight 12.5 mm capacitor bodies, voltage-reference and
protection packages, and the larger bus-measurement resistor.

The replacements retain their previous positions where practical. The capacitor
bank pitch is now 13.5 mm; C6 is 2 mm above the other capacitor origins to clear
D3/C3. R70 moved to (124, 139.5) mm, and U13 to (153, 111.3) mm beside U12. Earlier
U13 positions collided first with SWCLK and then with DRV_EN_MCU; the final move
clears both without changing retained copper. These positions are preliminary
and remain subject to electrical/thermal routing review.

The 33 added components are staged outside the board, on a 10 mm grid starting
at (50, 175) mm. They include the driver buck and the new interlock/reference
support circuits. Their staging positions are not an electrical placement.

## Verified saved state

Board SHA-256:
`278f2d8addb584d4e3a60fb118c6c162bdad9f404189c65601622df94f640d4d`.

| Check | Result |
|---|---|
| Schematic components / PCB footprints | 357 / 357 |
| Numbered physical pads compared | 1208, including repeated numbered pads |
| Schematic net nodes compared | 1086 |
| Reference/library/value/pad-net discrepancies | 0 |
| Final Konnect synchronization | No-op, zero changes/conflicts |
| Retained tracks / vias / copper zones | 1208 / 136 / 0 |
| Native connectivity missing connections | 686 |
| DRC missing connections listed | 499; report ceiling, not total connectivity |
| Other DRC errors | 0 |
| Other DRC warnings | 319 |

The warnings comprise 199 footprint/library mismatches, 43 text-height findings,
32 dangling tracks, 23 silkscreen-over-copper findings and 22 silkscreen overlaps.
Matching library IDs and pad nets does not resolve the footprint-artwork mismatch
warnings; those need individual review. A zero count of other DRC errors also
does not qualify unrouted power distribution or the staged components.

Read-only comparison against the archive verifies all 1344 retained copper items:
UUID, kind, position, endpoints, track width, via diameter on each layer, via drill,
layer span/type, net and lock state. A separate live Konnect query confirms every
retained track's geometry. Of the 16 archived protected CAD/library sources, only
the PCB changed during this synchronization milestone.

`tools/check_pcb_parity.py` compares exported XML with read-only board metadata.
Eight deliberately invalid metadata variants are rejected: wrong driver net,
one incorrect repeated drain pad, missing component, missing exposed pad, wrong
library ID, wrong value, empty board and duplicate reference. KiCad's native
net-name display decoding handles two `{slash}` encodings; board nets were not
renamed. Empty-number MOSFET paste apertures are not electrical pads.

## Evidence and renders

Local evidence is under `.scratch/v4-56v-implementation/pcb-sync/`:

- `before.tar.gz`, `before-sha256.json`: original CAD/library checkpoint.
- `rework-plan.json`, `rework-progress.json`, `applied.json`: selected removals
  and applied synchronization.
- `parity-before-decoded.json`, `parity-after.json`, `negative-parity/validation.json`:
  comparison and rejected faulty metadata.
- `plan-final.json`: live synchronization no-op after saving placement.
- `retained-copper-audit.json`, `traces-final.json`: retained copper verification.
- `after-metadata.json`, `drc-clean-placement.json`: native connectivity and full
  DRC details. Earlier `drc-final.json` predates the two final placement fixes.
- `components-final.json`, `position-plan.json`, `clearance-final-moves.json`:
  current positions and staging history.

KiCad top, bottom and isometric PNGs are generated under
`kicad/odrive-v4-mono/exports/pcb-sync-2026-09-08/`. The prior
`exports/review-2026-09-08/` images show the archived board. These are board/pad
renders: the board lacks component 3D associations, and the renders do not show
the off-board staging as assembled parts. They cannot establish mechanical fit.

## Remaining work toward a functional controller

Place the 33 new components around their electrical owners, review the power
cell and sensing/return paths, then rebuild affected routing and planes. Audit
the retained copper and all footprint mismatch warnings as part of that work.
Close connectivity and DRC, qualify current/thermal/regenerative limits, and
generate a consistent assembly BOM and manufacturing outputs.

Firmware still needs current-control/output and encoder integration beyond the
inhibited diagnostics. Motor, encoder, source behavior and current/cooling inputs
remain unspecified; physical bring-up and fault/thermal tests remain necessary.
