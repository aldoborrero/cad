# ODrive v4-mono 56 V — conditional brake OC and mounting direction

> Later checkpoint: [specific land and geometric placement preflight](v4-mono-56v-brake-mount.md)
> are prepared. No resistor or mounting has been adopted in the controller.

The expanded analysis supports **4.7 Ω as a provisional external-load design
case**, and a cooled TO-247 150 Ω resistor as the preferred direction for the
integrated default branch. Neither is installed or qualified. The complete
controller and its default discharge function remain in scope.

## Conditional static overcurrent interval

The saved nominal circuit gives 24.812 A. The expanded model evaluates 2048
corners and gives **21.160–28.860 A**. This interval combines published limits
and explicit engineering allowances; it is not a guaranteed production bound.

[TI INA181 Rev H](https://www.ti.com/lit/ds/symlink/ina181.pdf) supplies the
1% full-temperature gain error, general 500 µV offset, 1 µV/°C offset drift,
40 µV/V supply sensitivity and 84 dB full-temperature CMRR used here. Gain drift
is not added again to the gain error that already covers temperature. The
12 V input characterization condition is translated conservatively to the
proposed low-side input range, rather than assuming the special zero-volt
offset limit applies throughout operation.

[TI TLV3201 Rev C](https://www.ti.com/lit/ds/symlink/tlv3201.pdf) gives 4 mV
full-temperature offset at midsupply and 5 nA input bias. Its hysteresis entry
is typical, not a maximum. The model therefore marks its 8 mV comparator-error
budget and 0–3 mV rising-edge hysteresis budget as engineering allowances.

Other explicit allowances are AVCC 3.135–3.465 V, divider resistors ±2%, the
prospective shunt ±4%, local output-reference error ±5 mV, Kelvin differential
error ±0.5 mV and board leakage ±10 nA. The exact installed shunt/divider MPNs
remain unresolved. Startup and rail collapse are excluded; the model rejects
supplies outside its powered-device range. Every origin is recorded in
[`v4-mono-56v-brake-load.json`](../spec/v4-mono-56v-brake-load.json).

The amplifier output stays at least 0.244 V inside the gain specification's
0.5 V to AVCC−0.5 V output window at the evaluated crossings. Dynamic loading,
recovery, current rise during fault response and sensor failures remain open.
**28.860 A is not a safe peak-current rating.**

## External load comparison

A provisional 20% reserve below the minimum screened trip gives a steady-current
ceiling of **16.928 A**. Both the onboard 150 Ω branch and external resistor use
±10% total engineering resistance envelopes here, including the newer mounting
proposal. Separate adverse extrema give a conservative compatibility check.

| External nominal load at 61.029 V | Screened brake current | Meets provisional reserve |
|---|---:|---|
| None | 0.370–0.452 A | Yes, but insufficient for arbitrary regen |
| 2 Ω | 28.083–34.320 A | No |
| 3.3 Ω | 17.172–20.987 A | No |
| 4.7 Ω | 12.169–14.873 A | Yes |

The calculated minimum nominal external resistance for this reserve is 4.114 Ω
at 61.029 V. That is a conditional design result, not an approved minimum load.
4.7 Ω provides room for this screen; its exact part, pulse energy, average power,
repetition and required motor-braking performance remain to be selected.

## Preferred default-resistor mounting

The preferred mechanical direction is a **150 Ω Vishay LTO 100-class TO-247**
through-hole resistor connected to the controller PCB and screwed to a dedicated
heatsink. [Vishay's current document](https://www.vishay.com/docs/50051/lto100.pdf)
gives 1.5 °C/W element-to-case and 100 W at 25 °C case, derated to zero at
175 °C. The ceramic mounts directly to the heatsink. Its free-air rating is
only 3.5 W. The document has differing TCR entries, including typical values;
the calculation uses a separate ±10% engineering resistance budget.

With 135 Ω minimum, 61.029 V continuous conduction and 50 °C ambient:

| Requirement/result | Value |
|---|---:|
| Worst screened resistor power | 27.589 W |
| Required case-to-ambient resistance, including interface | ≤1.0 °C/W |
| Calculated case temperature at that budget | 77.59 °C |
| Calculated element temperature | 118.97 °C |
| Margin to provisional 125 °C target | 6.03 °C |

These temperatures assume the thermal path exists; it has not been designed or
measured. The dedicated-heatsink requirement avoids silently spending this
budget on heat from other parts. Any shared sink must include those sources.
Default-resistor hardware must be included in the controller assembly.

For comparison, [Bourns' current PWR221T-50 data](https://www.bourns.com/docs/Product-Datasheets/pwr221t-50.pdf)
gives 2.5 °C/W. The same power/ambient/element target would require approximately
0.219 °C/W case-to-ambient, leaving a substantially harder cooling task.

`LTO100F150R0FTE3` is an ordering code derived from the manufacturer's convention,
not a verified purchasable selection. Local Konnect/JLC snapshot searches for
`LTO100F150` and `PWR221T-50-1500` returned no entries; live sourcing is open.
Before CAD adoption, verify exact part data, leads/holes, body and fastener
clearance, heatsink attachment, assembly access and thermal performance. No
footprint or board position was invented without those checks.

## Evidence

The existing [`analyze_brake_load.py`](../tools/analyze_brake_load.py) now emits
both conditional OC and mounting screens alongside the preceding nominal and
energy calculations. `brake-oc/analysis.json` records the input/spec hashes.
Scratch evidence lives in `.scratch/v4-56v-implementation/brake-oc/`.

Validation checks both extreme witnesses against divider KCL and amplifier
transfer, an independent conservative interval enclosure, 20,000 deterministic
interior samples, nominal recovery with zero error allowances and all three
load-boundary inversions. Six invalid OC specifications are rejected. The
mounting case passes its static requirements; poorer cooling and hotter ambient
cases fail. Prior power-conservation, independent RK4 and six invalid-netlist
checks still pass. Formatting/lint pass.

All 21 protected CAD files retain their hashes. PCB counts remain the preceding
389 opens / 414 warnings / zero other DRC errors; DRC was not rerun for this
analysis-only change. Eeschema PID 31060 is still running, so schematic adoption
continues to require saving and closing that hierarchy. The next concrete CAD
step is to qualify the TO-247 land/mounting geometry and rearrange the brake
cell with R164 and its Kelvin/gate paths.
