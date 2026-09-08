# ODrive v4-mono 56 V — motor shunt space and RC routing

The three motor RC snubbers now occupy the underside beside their low-side
MOSFETs. Their outer ends are connected, and their old series connections are
restored. This clears checked positions for the larger Bourns motor shunts.
The replacement shunts are still library candidates, not installed devices.
See [part selection and thermal limits](v4-mono-56v-shunt-review.md).

## Applied placement and routing

All six components are on B.Cu at rotation 0; dimensions below are millimetres.
Values remain 1 Ω for R31–R33 and 1 nF for C35–C37.

| Reference | X | Y |
|---|---:|---:|
| R31 | 142.5 | 79 |
| C35 | 146 | 79 |
| R32 | 166 | 95.5 |
| C36 | 169.5 | 95.5 |
| R33 | 181.5 | 79 |
| C37 | 185 | 79 |

Each series resistor-to-capacitor connection is 1.9 mm long and 0.25 mm wide
on B.Cu. Outer connections use 0.4 mm traces and one 0.5/0.2 mm through-via each:

| Connection | Routed length (mm) |
|---|---:|
| R31.1 → Q12.5, phase A | 5.075 |
| C35.2 → Q13.3, source A | 4.067 |
| R32.1 → Q17.5, phase B | 5.168 |
| C36.2 → Q17.3, source B | 7.398 |
| R33.1 → Q20.5, phase C | 5.158 |
| C37.2 → Q21.3, source C | 4.896 |

These connect selected members of each parallel MOSFET pair. The high-current
connections between pair members, current loops and power pours remain open.
Snubber pulse/voltage ratings, ringing, values and thermal behavior require
qualification; connectivity does not establish an effective tuned snubber.

## Candidate shunt placement, not applied

Read-only native geometry preflight against the final saved board passes for
R22 at (141.5, 83.5), R23 at (166, 101.5) and R24 at (183, 84), all F.Cu,
rotation 0, using the prepared Bourns footprint. New routing explicitly avoids
the old and proposed shunt lands. This proves geometric clearance only; Kelvin
routing, power-current paths and thermal performance remain to be designed.
R164 and the brake cluster still require a combined placement review.

Konnect refused a schematic synchronization preflight because the hierarchy
is open: “save and close the hierarchy before syncing”. The user was asked to
save and close eeschema; no unobserved edits were discarded. PCB-only work was
completed independently. Schematic, library, rule, value and firmware files
were unchanged in this checkpoint.

## Brake review finding

The saved schematic exports R160 as `50R/150R`, without an exact MPN, using
`Resistor_SMD:R_2512_6332Metric`. The legacy design instead specifies a
TO-263 Bourns PWR263S-35-class default populated brake resistor, 150 Ω for
56 V, with an external resistor in parallel. The present footprint therefore
does not implement that package intent. At continuous conduction, 150 Ω would
dissipate 20.91 W at 56 V and 24 W at 60 V. Exact selection, mounting, duty,
energy and cooling must be resolved together with R164 and the brake layout;
no default brake function has been removed or qualified by this change.

## Verification and saved state

- 360 footprints, 1214 numbered pads and 1092 schematic net nodes match.
- 389 unconnected items, down from 395; 414 warnings and zero other DRC errors.
- 2079 tracks, 376 vias, seven GND zones and 57 underside components.
- Retained 2422 prior copper items exactly; replaced six old RC series tracks
  with 27 segments and six vias, preserving every prior physical pad connection.
- All 647 predicted whole-board physical pad groups match.
- Warnings: 199 library-footprint mismatches, 77 silk-over-copper, 63 silk
  overlaps, 42 text heights, 32 dangling tracks and one dangling via.
- L1's body exclusion is untouched: all new routes and moved parts lie outside it.

Saved PCB SHA-256:
`58fd7d42d3c0b32232d271e7f4de450a1b6a58e17c8facad88c9ed790b5c94e2`.

Scratch evidence: `.scratch/v4-56v-implementation/pcb-motor-shunt-space/`,
including `native-audit.json`, `parity.json`, `drc.json`, `routes-plan.json`
and `future-position-audit.json`. Placement and routing mutation scripts have
already run; do not replay them.

Native copper views and bare-board renders are under
`kicad/odrive-v4-mono/exports/motor-shunt-space-2026-09-08/`. There are no
attached component 3D models, so renders cannot verify assembled height.
The board remains unfinished and is not ready for fabrication or energizing.
