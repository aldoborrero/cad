# ODrive v4-mono 56 V — brake load and cooling screen

> Expanded checkpoint: [conditional OC and mounting direction](v4-mono-56v-brake-oc.md)
> adds tolerances, a provisional 4.7 Ω external-load case and a cooled TO-247
> default-resistor proposal. The nominal calculations below remain historical
> evidence; no candidate has been installed.

The inherited brake-resistor recommendation is not a qualified 56 V design.
A fresh saved-schematic export confirms R160 is still `50R/150R`, on a generic
2512 footprint, without an exact MPN. The proposed 150 Ω onboard branch needs
an explicit cooling design. The historical 2 Ω external resistor also exceeds
the present nominal brake overcurrent threshold at the screened voltages.
No PCB, schematic, library or firmware was modified in this review.

## Reproducible model

[`analyze_brake_load.py`](../tools/analyze_brake_load.py) verifies the exported
R160/J13 parallel branches, MOSFET source/drain nets, Kelvin shunt, amplifier,
comparator/divider and eight bulk capacitors before applying its equations.
Inputs and assumptions are in
[`v4-mono-56v-brake-load.json`](../spec/v4-mono-56v-brake-load.json).

```sh
python projects/odrive/tools/analyze_brake_load.py   --netlist /path/to/saved-kicad-export.xml   --output /tmp/brake-load-analysis.json
```

The output distinguishes the installed unresolved value from a candidate
150 Ω branch; it does not substitute that candidate into the schematic.
A successfully completed analysis is not a release gate. The application bus,
regen energy, duty, motor, source behavior and cooling remain unspecified.

## Cooling constraint

[Bourns' PWR263S-35 datasheet](https://bourns.com/docs/Product-Datasheets/pwr263s-35.pdf)
specifies 35 W at 25 °C **case** temperature, 3.7 °C/W element-to-case thermal
resistance and derating to zero at 155 °C. Its 39 × 30 × 1.6 mm double-sided
70 µm copper FR4 reference board supports 3.5 W at 25 °C ambient. The backplate
is electrically isolated. PWR263S-35-1500FE denotes 150 Ω, 1%, tape and reel;
TCR is ±100 ppm/°C. None of these data establishes this PCB's cooling.

The static screen assumes continuous conduction at 61.029 V and a provisional
125 °C element-temperature design target. Including 1% initial tolerance and
adverse TCR over −55…125 °C gives 147.015 Ω minimum and **25.334 W**. These are
engineering screening assumptions, not user-specified operating conditions.

| Derived requirement | Result |
|---|---:|
| Maximum case temperature from manufacturer derating alone | 60.90 °C |
| Maximum case temperature for the provisional 125 °C element target | 31.26 °C |
| Maximum case-to-ambient thermal resistance at 25 °C ambient, 125 °C target | 0.247 °C/W |
| Feasible at 40 or 50 °C ambient without cooling below ambient, same target | No |

Thus a larger land pattern alone cannot qualify this candidate. Its suitability
must be reconsidered with a lower thermal-resistance package or a defined
heatsink/mounting system. The 125 °C target is a design margin to review, not a
manufacturer maximum. Changing it does not remove the need to reject an
unsupported bare-PCB 35 W assumption. Average-power calculations also do not
qualify fault pulses or repeated regenerative bursts.

## External resistor versus overcurrent protection

The saved 3.3 kΩ/10 kΩ divider, nominal 3.3 V AVCC, INA181A2 gain 50 and
2 mΩ R164 give **24.812 A nominal OC**. Including nominal shunt resistance,
neglecting MOSFET/wiring resistance, and retaining the 150 Ω parallel branch:

| External load at 60 V | Total brake current | External dissipation while on | Nominal OC margin |
|---|---:|---:|---:|
| None | 0.400 A | 0 W | +24.412 A |
| 2 Ω | 30.369 A | 1796.36 W | −5.557 A |
| 3.3 Ω | 18.570 A | 1089.56 W | +6.242 A |
| 4.7 Ω | 13.160 A | 765.29 W | +11.652 A |

At 61.029 V the nominal external-resistance boundary is 2.499 Ω. This is **not
a permissible minimum resistance**: tolerance, rail variation, gain/offset,
comparator behavior, ground error and response delays remain unbounded here.
The 3.3/4.7 Ω rows are comparison cases, not selected or approved parts.
A 2 Ω load is incompatible with the nominal threshold in these scenarios;
raising the threshold without qualifying the whole power path is not a fix.

## Stored energy is not sustained regeneration

With nominal C4–C11 totaling 1.76 mF, discharging from 61.029 to 55 V releases
0.616 J. With only the 150 Ω candidate branch and an established bulk return,
the ideal time is 27.46 ms, assuming no incoming source or motor energy.
A 2 Ω parallel load would nominally trip OC, so its calculated uninterrupted
discharge time is hypothetical and not a predicted operating result.

For a separate illustrative **100 W constant incoming-power** case, the
onboard branch cannot hold the starting voltage: the ideal model reaches
65 V from 61.029 V in **5.993 ms**, despite continuous brake conduction.
65 V is an illustration, not an approved board limit. The nominal 150 Ω branch
therefore cannot be described as a universally sufficient regenerative dump.
The default integrated discharge path and required motor-braking capacity must
both be specified; neither requirement has been removed.

## Evidence and next implementation

Fresh export preserves all 1092 prior net nodes; all 21 protected CAD files
retain their hashes. PCB remains at 389 opens / 414 warnings / zero other DRC
errors from the preceding verified checkpoint; DRC was not rerun for this
analysis-only change. Eeschema PID 31060 was observed still running, so the
pending save/close requirement for schematic synchronization remains.

Independent validation checks KCL/power conservation across twelve load cases,
three nominal OC boundaries, four capacitor discharge times and the regen
example using RK4 voltage integration. Six malformed exports are rejected
(sense reversal, wrong comparator input, connector/return changes, wrong gain,
and ambiguous shunt value). Python formatting and lint pass.

Evidence is in `.scratch/v4-56v-implementation/brake-resistor/`, including
`current.xml`, `analysis.json`, `model-validation.json`, `validate-model.py`
and protected hashes. Konnect initially could not find its database; a local
scratch server configuration pointed to the existing rails-recovery snapshot.
The exact `PWR263S-35-1500` search returned no entries. This is not proof of
live unavailability; procurement remains open. Direct PDF download returned
HTTP 403; the manufacturer's document was read through the web PDF tool.

Next: choose a thermally viable default-resistor mounting arrangement, bound
the brake OC threshold and external load together, then place R160/R164 and
the brake power/Kelvin/gate paths. Preserve the complete single-board controller
and default discharge function. No replacement footprint was created before
resolving whether this package is suitable.
