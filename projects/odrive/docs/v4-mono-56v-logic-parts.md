# ODrive v4-mono 56 V — logic-supply part selection

> The subsequent [5 V layout checkpoint](v4-mono-56v-5v-layout.md) places L2
> on the board and supersedes the PCB counts and staging status below.

Selected actual inductors and the 5 V regulator variant, verified their land
patterns, and synchronized the PCB. The switching stages still require a new
local layout, effective-capacitance/load review and physical qualification.
This supersedes the generic-part and timing values in the preceding
[logic-supply recovery checkpoint](v4-mono-56v-logic-supply.md).

## Selected components

| Reference | Selected part | Design consequence |
|---|---|---|
| L1 | Würth 7447709101, 100 µH ±20% | 120 V operating rating; 10 mm maximum height; no vias or sensitive traces below its body |
| L2 | Coilcraft XAL7070-682MEC, 6.8 µH ±20% | Replaces generic 4.7 µH; 7 mm maximum mounted height; marked winding start connects to SW5 |
| U21 | TI LMR51430XFDDCR | Specifies 500 kHz FPWM; replaces unspecified LMR51430 variant |
| R118 / R215 | 75 kΩ / 68.1 kΩ, 1% | Adds allowance for inductance reduction while retaining adequate feedback ripple |

[Würth's drawing](https://www.we-online.com/components/products/datasheet/7447709101.pdf)
specifies L1's 2.9 × 5.4 mm lands, 9.9 mm center spacing, 110 mΩ maximum DCR,
and typical 3.1 A saturation current at 10% inductance reduction. The installed
`L_Wuerth_WE-PD-Typ-LS` lands match after rotating the drawing by 90 degrees.
L1's existing position does not satisfy the no-via/sensitive-trace restriction;
it must move as part of the switching-stage layout.

[Coilcraft's drawing and specifications](https://www.coilcraft.com/getmedia/1ba55433-bcc8-4838-9b21-382f497e12e0/xal7070.pdf)
give L2 a 60 V operating rating, 19.62 mΩ maximum DCR, and typical 12.8 A
saturation current at 25°C and 30% inductance reduction. Created
`odrive-mono:Coilcraft_XAL7070_682` with 1.92 × 6.5 mm rectangular lands,
4.82 mm center spacing, and a winding-start bar on the pad-1 side.
The courtyard contains the 7.7 × 8.0 mm maximum body plus 0.25 mm clearance.
Hot inductance, switching losses and fault-current overshoot remain unqualified.

[TI's device table and DDC0006A drawing](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
identify the selected 500 kHz FPWM variant. Its example output filter uses
6.8 µH and two 22 µF ceramic capacitors. Created `odrive-mono:TI_DDC0006A`
with 1.1 × 0.6 mm lands, 0.05 mm corner radius, 2.7 mm row spacing and
0.95 mm pitch. Its courtyard includes the maximum 1.75 × 3.05 mm body.
The existing additional 68 µF polymer output capacitor and all exact capacitor
MPNs still require loop/startup and effective-capacitance review.

Native footprint inspection verifies all ten selected-device lands against
those dimensions. Konnect's footprint generator based its initial courtyards
on pad envelopes, so both custom courtyards and silkscreen were explicitly
corrected through MCP before their PCB installation.

Konnect's local JLCPCB catalogue returned C6463690 for L1, C3911753 for L2,
and C5219260 for U21. These are catalogue-snapshot mappings, not current assembly
stock guarantees. The U21 catalogue description incorrectly says 1.1 MHz;
the manufacturer table determines the selection.

## Electrical screens and their limits

The LM5164 screen now allows effective inductance down to 72 µH: 20% initial
tolerance followed by a further 10% reduction allowance. This is a qualification
requirement, not measured hot/DC-bias data. With the revised timing/ripple
resistors, all nine screens pass over 2048 corners. Peak current at the 1 A
design load stays below 1.240 A in this ideal model; minimum loaded FB ripple
is 12.71 mV. Independent charge-state integration was rerun for the new values.
Full control-loop, switching-loss, startup and temperature qualification remain
open; the previous model's voltage and timing assumptions still apply.

A separate 64-corner ideal CCM screen for the existing 1 A, 5 V rail target
uses 10–14 V input, 450–560 kHz frequency, 72–120% effective inductance and
assumed 1% feedback resistors. Peak current is 1.273–1.739 A, below the minimum
3.67 A peak threshold. The maximum listed threshold is 6.68 A; this is not a
bound on real fault current including propagation delay. The calculated output
interval is 4.831–5.157 V before other errors and distribution drop. Exact
feedback tolerances and connector voltage budgets still need review. This
does not establish a 3 A system supply or a complete regulator qualification.

## PCB verification

The replacement footprints preserved all prior physical pad groups initially,
but DRC found thirteen geometric errors: L2's larger pads/courtyard collided
with adjacent copper and components, and U21's new bootstrap pad reduced
clearance to M0_TEMP. This demonstrates why net-aware connectivity alone
cannot establish freedom from shorts between different nets.

Local placement searches did not find room for L2. Staged it at (135, 180) mm
for the complete buck rearrangement. Kept U21 at (65, 129.5) mm and replaced
three M0_TEMP segments, preserving their fixed endpoints and existing via.
No rules were relaxed. L1 remains at (74.5, 120) mm pending its proper layout.

Saved PCB SHA-256:
`59e2917db2c9f3c5ad44e3a45a7cb6de46acd703c78e32992118ef94c676ff1d`.

| Check | Result |
|---|---:|
| Components / numbered pads / exported nodes | 360 / 1214 / 1092 |
| Native missing connections | 525 |
| Tracks / vias / zones | 1979 / 272 / 0 |
| Other DRC errors / warnings | 0 / 400 |
| Staged / underside parts | 4 / 36 |
| Preserved copper / replaced segments | 2248 / 3 |
| Predicted physical groups | All 783 match |
| Schematic pin contract | 2472 checks / 126 components pass |
| Pad-net parity / live sync | Pass / no-op |

Connectivity prediction preserves all previous groups except L2's deliberately
isolated pads. Replacement pad identities are matched by reference and number;
unchanged pads retain UUID identity, including repeated thermal-pad numbers.
R215/C214/C215 remain staged alongside L2. Warning counts are 199 footprint
differences, 69 silk-over-copper, 56 silk overlaps, 42 text-height issues,
33 dangling tracks and one dangling via. Firmware was unchanged.

Native top, schematic and detail images were inspected in
`kicad/odrive-v4-mono/exports/logic-parts-2026-09-08/`.
Evidence, manufacturer PDFs and journals are under
`.scratch/v4-56v-implementation/logic-parts/`.

## KiCad launch correction

The old editor had exited. Reopening the internal `kicad-base` binary directly
omitted Nix's Python environment and caused the wxPython warning reported by
the user. Saved through MCP, closed the identified instance, and relaunched
with the full `kicad` package's `pcbnew` wrapper. That environment imports
wxPython 4.2.5 / wxWidgets 3.2.11 and restores live IPC. Use `pcbnew` from the
development shell, not the internal base binary. A textual save diff initially
looked like added copper; UUID/geometry comparison proved it was only ordering.
