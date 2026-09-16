# ODrive v4-mono 56 V — interlock distribution and brake bypasses

The PCB now connects the MCU request, actual driver enable, brake permission,
rail-good combination and reset across their intended consumers. Local brake
bypasses, pulldown returns and links to the arm/analog supply islands are also
routed. These islands still need regulator feeds and reference planes. This
checkpoint does not establish powered operation or qualified fault handling.
It supersedes the counts in the [arm/divider checkpoint](v4-mono-56v-arm-divider-routing.md).

## Changes

Moved C64 next to U14 instead of leaving its bypass across the board. Moved
R100/C92 from the lower component rows to the MCU/supervisor reset area. All
three had no copper connections before moving and remain on F.Cu.

| Part | Final center, mm | Rotation |
|---|---|---|
| C64 | 164.1, 110.1 | 180° |
| R100 | 51.3, 122.8 | −90° |
| C92 | 52.4, 127.5 | −90° |

These complete native pad groups now match the exported netlist:

| Net | Connected pads |
|---|---|
| DRV_EN_MCU | U2.33, U15.1, U56.1, R208.1 |
| DRV_ENABLE | U15.4, U3.33, R209.1, R210.1 |
| BRK_OK | U53.3, U53.4, U55.3, U59.2, R214.1, R213.1 |
| RAILS_OK | U27.4, U25.2, U59.1 |
| NRST | U2.7, U28.1, R100.2, C92.1, U57.3, U58.2, J4.10 |

Together with the preceding R210/R213-to-MCU connections, the two feedback
signal paths now reach PC6/PC7. R209's ground end joins the driver's local ground
island. C92's ground end joins U28 ground; R100's supply end joins U28's VCC pins.
U28 still needs its global supply and ground feeds.

Connected C64 and C167/C168/C169/C170/C212 to their associated IC supplies and
returns. R212's AGND end and R214's GND end are connected. Brake logic VCC/GND
joins the arm/OV supply islands, and U52 AVCC/AGND joins the U10 analog islands.
The MCU AGND island remains separate. The AVCC distribution link joins the
capacitor terminals, preserving the narrower local IC escapes.

Added 284 trace segments and 52 vias for 43 endpoint joins plus a short reserved
NRST escape at U57. New signals/local escapes use 0.2 mm tracks; four distribution
links use 0.4 mm tracks. New vias are 0.5 mm diameter with 0.2 mm drills.
Ground transitions use In1.Cu; signal/supply transitions use In2.Cu and local
F.Cu/B.Cu. The longest new endpoint route is about 97.6 mm. Reference-plane
continuity, coupling and transient behavior still require the completed stackup.

The read-only planner now traverses existing same-net vias instead of treating
all via holes as forbidden layer transitions. Reserving U57's NRST escape before
planning local ground routes prevents those routes from enclosing its pad.
Both refinements were checked by native post-application DRC and full pad-group
comparison. All source mutations used Konnect MCP; no rules were relaxed.

## Verification

Saved PCB SHA-256:
`75acad1710e8fdf4f14dd4427daf5f170f164e21767d46394076cb33d0b11ef3`.

| Check | Result |
|---|---|
| Native missing connections | 529, down from 572 |
| Tracks / vias / copper zones | 1935 / 268 / 0 |
| Other DRC errors / warnings | 0 / 391 |
| Components / numbered-pad parity | 357 / 1208; zero discrepancies |
| Whole-board native pad connectivity | All 786 predicted groups match exactly |
| Preserved preceding copper | All 1867 items, with exact geometry and assignments |
| Live schematic synchronization | No-op |
| Staged / underside components | 0 / 31 |

The prediction starts with all pre-routing native groups and unions only the
43 planned endpoint pairs. The saved PCB's complete numbered-pad partition
matches, including retained connections. This checks physical copper continuity,
not active component behavior or fault response. Repeated pad numbers such as
U3's exposed-pad/thermal-via lands are checked by their separate native UUIDs.

DRC's unconnected-item list stops at 499; the native count above is uncapped.
Warnings comprise 199 footprint/library differences, 63 silkscreen-over-copper,
53 silkscreen overlaps, 43 text-height findings, 32 dangling tracks and one
dangling via. Only the PCB changed among the sixteen protected source hashes
tracked from recovery.

Evidence is in `.scratch/v4-56v-implementation/pcb-interlock-distribution/`:
baseline archive, placement plans/journals, `local-plan.json`, reserved escape,
`expected-connectivity.json`, `local-audit.json`, `local-metadata.json`,
`local-parity.json`, `drc-local.json` and `sync-final.json`. All seven native
images under `kicad/odrive-v4-mono/exports/interlock-distribution-2026-09-08/`
were visually inspected: board top/bottom, logic front/back, reset, brake bypass
detail and inner copper. Back detail text is mirrored because those views look
through from above. No component 3D models are associated with the board.

## Remaining work

Complete regulator placement/bypasses and global power/reference feeds, including
the source of AVCC, MCU analog reference distribution, U25/U27/U28 power and
the 12 V/5 V power-good inputs. Rechecked U3.26 against TI: it is the shunt
amplifier supply/reference input VREF; its local capacitor does not provide an
AVCC source. See [TI DRV835x pin functions, page 9](https://www.ti.com/lit/ds/symlink/drv8353.pdf).

R211's DCBUS feed, brake current-sense/threshold/gate paths, motor gate/source and
Kelvin connections, remaining interfaces, copper planes and thermal review are
still open. Startup/brownout and OV/brake coordination, independent watchdog and
external stop, exact BOM/package qualification, complete controller firmware,
manufacturing and bench validation remain required by the
[implementation plan](v4-mono-56v-implementation.md). No hardware was programmed
or energized.
