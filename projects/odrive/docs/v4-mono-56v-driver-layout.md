# ODrive v4-mono 56 V — driver placement checkpoint

This placement checkpoint is superseded by
[initial driver routing](v4-mono-56v-driver-routing.md), which also moves four
buck parts and records the current counts.

All 16 added driver-supply/interface components are now placed on the board.
The buck and driver bypass networks still need routing. This supersedes the
placement/count status in the [local OV checkpoint](v4-mono-56v-ov-layout.md),
whose six routed connection groups remain intact.

## Placement changes

The former space above U3 could not accommodate the 13 mm inductor courtyard
and its support circuits. J2 moved from (158.8, 55.4) to (124, 55.4) mm; F1 moved
4 mm left to (108, 71.5) mm. The phase-A power group moved 4 mm left, phase C
6 mm right, and selected phase-B components 1.2 mm down. U3 moved 2.4 mm down
to (163.32, 73) mm. Gate resistors, shunts, snubbers and nearby capacitors moved
with their groups; C22 and driver bypass positions were adjusted individually.

Nine added components occupy F.Cu: C200, C201, C202, C203, C204, C207, D200,
L200 and R202. L200 is above the driver, with D200 between them and the output
capacitor next to the inductor's opposite terminal. C203 is adjacent to the VIN
side; C202 is the larger nearby input capacitor. The existing VGLS, charge-pump,
VM and VREF bypass parts now follow their relevant side of U3 more closely.

Seven added passives occupy B.Cu: R203–R207 and C205/C206. This provides space
for the timing, feedback and ripple network near U3's buck pins while leaving
the exposed-pad via region clear of component bodies. R203's DCBUS pad faces
away from the feedback divider. The board now requires component assembly on
both sides; connector positions and assembly/enclosure clearances need mechanical
review with the actual parts.

The placement was guided by [DRV8353 section 11.1](https://www.ti.com/lit/ds/symlink/drv8353.pdf#page=78):
local bypassing, short switching and gate loops, and separation of feedback from
the inductor. It does not yet prove those routing goals. Input/diode/output return
loops, reference planes, gate/source pairs, Kelvin sensing and thermal copper
remain to be designed and verified.

## Copper affected by movement

Ten existing segments required replacement: six snubber segments, three U3
escape stubs and the input-to-fuse trace. The snubbers and driver stubs moved
with their owners; the M0_SO1 stub was shortened to clear C28. The fuse input
now uses three 3 mm segments below D1's large tab, rather than a direct diagonal
that would short to DCBUS. Keeping the former width does not qualify its current
or temperature rise; input power routing remains subject to the final design.

There are 12 replacement segments and no additional vias in this placement step.
All other 1404 copper items from the preceding checkpoint retain their exact
geometry, layers, widths, drills, net assignments and lock state. The board has
1267 tracks, 149 vias and no copper zones.

## Verification and limits

Saved board SHA-256:
`bd340cbcba71e4b2316800b0b1f58e4dbe99089c38413b7ee2c7acedec204ffc`.

| Check | Result |
|---|---|
| Changed component positions/orientations/sides | 71 |
| Components / numbered-pad correspondence | 357 / 1208; zero discrepancies |
| Final synchronization plan | No-op |
| Missing connections, native connectivity | 666 |
| Missing connections listed by DRC | 499, report ceiling |
| Other DRC errors / warnings | 0 / 360 |
| New components still staged | 15 |
| Component assembly sides | F.Cu plus seven B.Cu passives |

The 360 warnings comprise 199 footprint/library mismatches, 46 silkscreen-over-
copper findings, 43 text-height findings, 39 silkscreen overlaps, 32 dangling
tracks and one dangling via. No rules were relaxed. Pin-net correspondence does
not qualify package artwork or resolve those library mismatch warnings.

Ten exact physical connection groups pass native KiCad connectivity checks:
the six preceding OV groups, J1.1–F1.1, and the three resistor/capacitor snubber
pairs. The driver/buck networks are still unconnected; their placement has not
reduced the global missing-connection count. Fifteen interlock/brake/divider
components remain in staging: C208/C209/C212/C213, R208–R214, U56–U59.

The checks do not establish mechanical fit, switching behavior, usable current,
thermal limits, fault response or a functional motor controller. No schematic,
firmware, manufacturing order or device programming changed in this step.

## Evidence and tool behavior

Evidence is in `.scratch/v4-56v-implementation/pcb-driver-layout/`: the before
archive, front/back plans, `placement-diff.json`, mutation progress, final DRC,
`driver-audit.json`, `driver-metadata.json`, `driver-parity.json` and
`sync-final.json`. `audit-driver.py` reads native board connectivity and geometry
without changing the board. `components-final.json` records final positions;
earlier plans precede clearance and bypass-order corrections.

Konnect's flip tool requires a closed board. After saving, the original editor
process was terminated, the seven flips and placements applied through Konnect's
revision-checked file mode, and KiCad reopened. Its first IPC read returned
AS_NOT_READY during startup; the same instance subsequently answered and verified
all seven back-side placements. No direct text edits were made to CAD sources.

Top/bottom renders and front/back native layer details are under
`kicad/odrive-v4-mono/exports/driver-placement-2026-09-08/`. All four PNGs were
visually inspected. Layer details use board coordinates viewed from above, so
back-side text appears mirrored; the bottom render provides the underside view.
The board still lacks component 3D associations, so these images show pads and
artwork rather than complete assembled bodies.
