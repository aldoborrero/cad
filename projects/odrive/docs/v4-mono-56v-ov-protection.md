# ODrive v4-mono 56 V — independent overvoltage detection

> A [reference-compensated firmware conversion component](v4-mono-56v-bus-measurement.md)
> now exists with host tests. The fixed-reference screen below remains historical;
> the expanded calibrated screen still rejects 58 V coordination. ADC acquisition,
> control-loop integration and complete physical coordination remain pending.

## Status

The schematic now senses DCBUS directly through a dedicated OV network. U12 is
TLV3201AIDBVR and U13 is REF35125QDBVR, powered from VCC/GND. The ADC retains
its separate 22:1 divider and TLV9062 buffer. Loss or saturation of that buffer
no longer removes the OV detector's bus input. This is independence from the
ADC signal path, **not independence from VCC or the complete supply chain**.

Ideal external-network thresholds are 60.015 V trip / 55.026 V release. The
conditional sweep gives 58.66–61.03 V rising and 53.78–56.66 V falling. These
combine specified device limits and engineering allowances, not guaranteed
system bounds. The source/motor envelope, firmware coordination, brake energy,
transients and physical fault behavior remain unqualified.

This supersedes the earlier shared-buffer/TLV431 implementation with 60.047 /
54.994 V nominal thresholds. Its 100 pF C62 and 220 ohm R96 treatment applied
only to that former shunt reference. **Do not restore those values in this circuit.**

## Implemented circuit

| Reference | Selection / connection | Purpose |
|---|---|---|
| U12 | TLV3201AIDBVR, SOT-23-5 | Comparator; OUT 1, GND 2, IN+ 3, IN− 4, VCC 5 |
| U13 | REF35125QDBVR, SOT-23-6 | 1.25 V series reference; GND 1/2, EN 3 and VIN 4 to VCC, NR 5 NC, VREF 6 |
| R93 | 455 kΩ, DCBUS → OV_SENSE, 1206 | Direct bus input, replacing the buffered-ADC input |
| R94 | 10 kΩ, OV_SENSE → GND | Lower divider arm |
| R95 | 301 kΩ, OV_LATCH → OV_SENSE | Positive feedback |
| C211 | 100 pF / 50 V C0G, 5%, OV_SENSE → GND | Approximately 0.948 µs nominal input filter |
| C62 | 1 µF / 16 V X7R, 10%, VREF_OV → GND | Reference output capacitor |
| C210 | 1 µF / 16 V X7R, 10%, VCC → GND | Reference input bypass |
| R96 | Removed | The series reference does not use shunt bias |

R93/R94/R95 require 0.1% and ≤25 ppm/K. R93 now requests at least 0.25 W at
70°C and 200 V working voltage; its near-trip dissipation is about 7.59 mW.
Exact precision-resistor MPNs and assembly availability are pending. C62 must
provide 0.1–10 µF effective capacitance with ESR ≤0.4 Ω; C210 must provide at
least 0.1 µF effective. Nominal values alone do not qualify those requirements.
C61 remains the comparator's 100 nF bypass. Konnect places the comparator's
power pins in unit B; both units belong to the same physical five-pin device.

The [REF35 pin and electrical tables](https://www.ti.com/lit/ds/symlink/ref35.pdf)
provide the reference mapping and capacitor requirements. The stock reference
symbol's footprint property did not propagate when instantiated; it was set
explicitly through MCP and checked in the exported component contract.
The [TLV3201 datasheet](https://www.ti.com/lit/ds/symlink/tlv3201.pdf) supplies the
comparator mapping and error limits; a project-local symbol implements it.
Its 1.2 mV typical internal hysteresis has no specified maximum. The ideal
thresholds below omit internal hysteresis; the sweep allows 0–3 mV per edge.

VREF_OV also feeds U26, the existing 5 V supervisor. Its ideal threshold changes
from 4.4764 V to 4.5125 V with the unchanged 26.1 kΩ / 10 kΩ divider. That consumer
is included in the pin contract and reference load allowance. Its own complete
threshold, startup and brownout analysis remains open. A failed reference can
still affect both functions; no single-component-fault coverage is claimed.

## Calculation and coordination

For Ri = R93, Rg = R94 and Rh = R95, KCL at the comparator input gives:

```text
Vbus = (Vref + Vos ± Hedge) × (1 + Ri/Rg + Ri/Rh)
       − Vout × Ri/Rh + Iinput × Ri + Vground_shift
```

The positive hysteresis sign applies on rising bus voltage. Unlike the old
formula, there is no ADC divider gain or buffer offset in the OV equation.
`analyze_ov_threshold.py` reads exported values and rejects an incompatible
input/reference topology before evaluating this model.

| Screen | Result |
|---|---|
| Ideal external-network trip / release | 60.015 / 55.026 V |
| Conditional rising interval | 58.66–61.03 V |
| Conditional falling interval | 53.78–56.66 V |
| Reference interval under stated budget | 1.24660–1.25340 V |
| Fixed-3.3-V firmware conversion, 58 V setting sensitivity | 54.56–61.47 V actual bus |
| Nominal bulk-only energy between ideal thresholds | 0.505 J |

The reference budget includes initial accuracy, its temperature **box** over the
whole specified −40..105°C span, line regulation, a 10 µA load allowance and
200 ppm for aging/noise/thermal hysteresis. The working temperature screen is
−40..85°C. Comparator terms include 4 mV offset plus 2 mV for bias/supply effects;
output limits are conservatively borrowed from the 2.7 V / 4 mA table for the
lighter 3.3 V load. That interpolation, internal hysteresis, PCB leakage and
±0.1 V ground offset remain engineering allowances requiring qualification.

**Firmware coordination is not established.** Although the conditional hardware
minimum exceeds an ideal 58 V, firmware conversion based on fixed 3.3 V is
sensitive to AVCC. The displayed firmware interval also includes divider error,
buffer offset and clamp leakage, but excludes converter INL/gain/offset and
reaction time. Calibration/reference tracking and the final operating limits
must be specified together. Do not merely lower a constant to make a check pass.
The script reports passing schematic screens separately from the failed
coordination screen and never reports physical coordination as qualified.

R70/R211 remain two series 10.5 kΩ / 1206 resistors over R71 = 1 kΩ, with
0.1% / 25 ppm/K requirements and a **22:1 firmware ratio**. Each upper resistor
dissipates 78.1 mW at 60 V; exact MPNs must meet the 0.25 W at 70°C / 200 V
requirements. ADC clamp leakage and supply-off backfeed remain to be qualified.

The direct OV path limits current through R93 to approximately 0.221 mA in a
100 V screen, but this does not qualify unpowered input clamps or rail backfeed.
Reference settling, comparator startup, brownout, ground transients and the
entire comparator-to-brake delay require system analysis and bench measurement.

## Bulk bank and remaining brake work


The selected [Nichicon UHW2A221MHD](https://www.nichicon.com/en-us/part/uhw2a221mhd/6250/)
is 220 µF ±20%, 100 V, nominally 12.5 mm diameter × 25 mm high, with 5 mm lead
spacing. C4–C11 now use `CP_Radial_D12.5mm_P5.00mm`; the old footprint was 10 mm
diameter. The installed footprint has 5 mm pad spacing and 1.2 mm holes; the
[package drawing](https://www.nichicon.com/getmedia/fcd51685-9bcf-4441-98c2-6ed79a71564f/e-uhw5-11.pdf)
lists 0.6 mm leads for this size. The board placement and enclosure clearance
have not been updated. Provide clearance for dimensional tolerance and the vent.

The manufacturer's ripple rating is 2.21 A per capacitor at 105°C/100 kHz, with
frequency factors in the datasheet. Eight times that number is not an approved
bank rating: current sharing, waveform spectrum, impedance, cooling and lifetime
must be checked. The nominal bank remains 1760 µF. Its simple R1*C constant is
0.176 s, not the old annotation's 0.35 s; actual charging depends on Q1's ramp.
Q1/R1 pulse energy and SOA remain open.

The 100 V capacitor selection does not increase the permitted operating voltage
or qualify the TVS/MOSFET transient margin. The [brake OC/reset logic](v4-mono-56v-brake-interlock.md) has since been corrected;
its startup and complete analog response remain unqualified. R160 still has the unresolved
`50R/150R` value and 2512 footprint, despite the earlier proposal specifying a
TO-263 power resistor. A 150 Ω resistor would absorb only 24 W at 60 V. The
0.505 J bank-only calculation excludes energy still entering from the motor.
Do not use it to claim a working dump path. Resistor/package selection, external
brake sizing, overcurrent response and loss of the brake's supply remain open.

## Verification

All KiCad changes used patched Konnect MCP. The fresh export has 350 components.
Six existing pin-net assignments changed intentionally: R93.1 to DCBUS,
R94.2/C62.2 to GND, and the three former U13 terminals to their new functions.
R96 was removed; U13 has three additional terminals and C210/C211 were added.
All other existing exported pin-net assignments are preserved.

The contract checks 85 components / 2062 assertions and passes. Five corrupted
exports are rejected by both the contract and OV screening: ADC reconnection,
reference powered from AVCC, wrong reference ground, restored 100 pF reference
output capacitor, and old feedback resistance. Driver-supply and enable-interlock
checks still pass. These are schematic/model checks, not physical fault tests.

Sensing SVG was inspected and the new reference's wire/label placement adjusted.
945 surplus coincident junction objects were removed through MCP, retaining one
at each location; exported connectivity is checked before and after cleanup.
Other legacy field/label overlaps remain. ERC is 0 errors / 60 warnings; the
existing annotation warning remains unresolved. PCB and firmware are unchanged.

Evidence lives in `.scratch/v4-56v-implementation/`: `mono-direct-ov.xml`,
`direct-ov-analysis.json`, `direct-ov-validation.json`, `erc-direct-ov.json`,
`direct-ov-junction-cleanup.json`, and `svg-direct-ov/`. No new live JLCPCB stock
or assembly availability is claimed; resistor selection and procurement checks
remain part of the manufacturing work.
