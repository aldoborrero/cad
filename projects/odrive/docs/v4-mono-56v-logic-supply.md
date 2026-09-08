# ODrive v4-mono 56 V — logic-supply recovery

The subsequent [part-selection checkpoint](v4-mono-56v-logic-parts.md) supersedes
the generic inductors/U21, R118/R215 values and PCB counts below. This document
records the preceding recovery and the feedback-to-ground repair.

The 12 V LM5164 now has a Type-3 ripple-injection network and a revised timing
resistor. The schematic-to-PCB synchronization is complete, but the three new
parts are staged outside the outline. Neither the 12 V nor 5 V switching stage
has a completed layout or physical qualification.

## Circuit changes

The previous 301 kΩ timing resistor and 100 µH nominal inductor give about
100.6 kHz and 0.94 A peak-to-peak current ripple at 56 V in the ideal CCM model.
At a 1 A load, the corresponding peak exceeds the converter's minimum peak
current-limit threshold. The ceramic-output circuit also lacked a deliberate
ripple-generation network.

Changed R118 to 82.5 kΩ, 1%. Added R215 = 75 kΩ, 1%, 0805; C214 = 10 nF,
100 V, C0G, 5%, 0603; and C215 = 330 pF, 50 V, C0G, 5%, 0603. R215 connects
SW12 to RIPPLE12, C214 connects RIPPLE12 to +12V, and C215 couples RIPPLE12 to
FB12. Recorded U20's MPN as LM5164DDAR and explicit 1% tolerances for R110/R111.
The divider remains 90.9 kΩ / 10 kΩ; L1 remains a generic nominal 100 µH part.

The topology and selection equations follow the
[TI LM5164 Rev. D datasheet, section 7.2.2.6](https://www.ti.com/lit/ds/symlink/lm5164.pdf).
TI specifies a 12 mV minimum feedback ripple at minimum input voltage and
recommends 20 mV at typical conditions. Its current-limit table gives a
1.25 A minimum peak threshold. Exact passive MPNs, effective inductance and
capacitance, switching losses, and temperature margins still require review.

The first placement of the new schematic network overlapped J5's ground wire,
accidentally merging FB12 with GND. The exported-netlist check caught this;
it was not merely a drawing overlap. Moved only the three new symbols and their
six wires/four labels down 25.4 mm through Konnect. A fresh root export now
preserves all 1086 previous node assignments exactly and adds only the six
intended nodes. The repaired sheet was rendered and visually inspected.
Older sheet notes still need editorial cleanup, including the obsolete claim
that the DRV8353 buck is unused.

## Calculation and verification

`tools/analyze_logic_supply.py` reads the exported values and checks the intended
pin connections before reporting an overall pass. Its passive two-capacitor
model includes coupling-capacitor loading by the feedback divider. It does not
model the converter's complete control loop.

| Calculated screen | Result |
|---|---:|
| Nominal divider output, before ripple offset | 12.108 V |
| Nominal CCM frequency | 366.9 kHz |
| Nominal loaded FB ripple | 34.06 mV |
| Corner frequency interval | 270.1–589.3 kHz |
| Corner peak current at 1 A load | 1.042–1.237 A |
| Corner loaded FB ripple | 12.68–53.16 mV |
| Minimum CA / CB selection margins | 2.33 / 1.13 |
| Evaluated corners / passing screens | 2048 / 9 |

The sweep assumes input values of 24, 56, 65 and 95 V; reference limits;
1% resistors; 5% capacitors; effective inductance of 80–120% nominal; and an
engineering timing allowance of 0.65–1.3. These timing and inductance allowances
are assumptions, not guaranteed device limits. The 95 V calculation is a
converter screen, not an approved operating voltage for this board. The small
worst-case current margin needs confirmation with actual parts and losses.
The output interval excludes feedback bias and ripple-induced DC offset.

An independent RK4 integration using capacitor charge as its state, starting
with discharged capacitors, agrees with the analytical periodic solution at
24, 56 and 95 V. Maximum ripple difference is below 0.1 nV. Eight deliberately
invalid exports are rejected: old timing, excessive ripple resistance, small
CA, small CB, CA returned to ground, feedback returned to ground, the original
missing network, and the accidentally shorted intermediate schematic.
These checks validate the calculation and selected topology checks; they do
not prove startup, DCM/burst behavior, closed-loop stability or thermal behavior.

The expanded manufacturer-pin/intended-connection contract passes 2439 checks
across 124 components. Fresh ERC reports zero errors and 59 warnings: 41 shared
local/global label names, 14 isolated-pin labels, three library-symbol issues
and one root-sheet wire endpoint. Warnings still require full review.

## PCB checkpoint

Saved board SHA-256:
`0c86de00fd8cd408676087e660d7c860e3b684b63248b0ebca5b2dc324b58504`.

| Check | Result |
|---|---:|
| Components / numbered pads / exported nodes | 360 / 1214 / 1092 |
| Native missing connections | 524 |
| Tracks / vias / copper zones | 1979 / 272 / 0 |
| Other DRC errors / warnings | 0 / 398 |
| Staged / underside components | 3 / 36 |
| Preserved preceding copper items | All 2251, exact geometry and nets |
| Whole-board physical pad groups | All 782 predicted groups match |
| Pad-net parity / final live sync | Pass / no-op |

All 1208 preceding numbered pads retain their positions, sizes and nets;
existing component placements are unchanged. The six new pads are isolated,
as expected. The five additional missing connections are the unrouted new
network. R215, C214 and C215 are at (100, 180), (110, 180), and (120, 180) mm
respectively, pending placement with the complete U20 switching stage.
Among the 17 protected source hashes captured before this recovery, only
`rails.kicad_sch` and the PCB changed. Firmware was unchanged.

## JLCPCB access and next work

Konnect's JLCPCB search now works with the downloaded local catalogue at
`.scratch/v4-56v-implementation/rails-recovery/jlcpcb.db`. The MCP download
contains 786769 parts from the public kicad-jlcpcb-tools feed. Searches must
pass this path as `output_path`; the default database path is still absent.
Catalogue stock is snapshot evidence, not live assembly availability.

The catalogue incorrectly describes LMR51430XFDDCR as 1.1 MHz.
[TI's device comparison table](https://www.ti.com/lit/ds/symlink/lmr51430.pdf)
identifies it as 500 kHz FPWM. U21 remains a generic LMR51430 without a selected
MPN, so its operating frequency is not yet specified. Its existing 4.7 µH
inductor and output-capacitor combination are not qualified by this checkpoint.

Next: select and qualify actual L1/L2 and capacitor parts, specify the U21
variant, complete the regulator/load/startup review, then compact and route both
buck stages and distribute 5 V, VCC, AVCC and references. The overall
[implementation requirements](v4-mono-56v-implementation.md) remain open.

Evidence is under `.scratch/v4-56v-implementation/rails-recovery/`: source
archive/hashes, MCP journals, before/intermediate/repaired netlists, schematic
renders, independent numerical check, negative checks, pin contract, ERC,
native PCB preservation/connectivity audit, parity, DRC and live sync.
