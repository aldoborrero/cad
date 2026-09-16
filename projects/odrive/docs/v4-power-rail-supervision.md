# Modular power PCB — rail supervision

Status: schematic implemented and 17 additional components placed; new wiring
is not routed. See the [PCB checkpoint](v4-power-implementation.md).

U505 is TPS3808G50DBVR and U506 is TPS3808G33DBVR. Both use digital P3V3 for
power, with independent SENSE inputs on P5V and P3V3_A. Losing the analog rail
therefore does not remove its monitor's supply. MR receives P3V3_OK; CT is
intentionally unconnected. Each monitor has a 100 nF bypass, 10 kΩ output
pull-up to P3V3 and a test point. These parts detect undervoltage only.

The DBV pin mapping is RESET=1, GND=2, MR=3, CT=4, SENSE=5, VDD=6. The stock
KiCad TPS3808DBV symbol matches this package. Falling thresholds are nominally
4.65 V and 3.07 V, with respective full-temperature tolerances of ±2% and
±1.5%. Fixed-version hysteresis is at most 2.5% of VIT. CT-open release delay
is 12–28 ms. The listed 20 µs SENSE-to-RESET assertion time is **typical**, not
a guaranteed maximum. These specifications come from
[TI TPS3808, sections 4–6](https://www.ti.com/lit/ds/symlink/tps3808.pdf).

## Permission chain

Three SN74LVC1G08 gates U507–U509 implement:

```text
DIGITAL_12_OK = P3V3_OK AND PG12_N
ANALOG_5_OK   = P5V_OK AND P3V3_A_OK
RAILS_OK     = DIGITAL_12_OK AND ANALOG_5_OK
```

Despite its historical suffix, PG12_N is high when U500 reports power good.
U616 then implements `WAKE_READY = POWER_INTERFACE_OK AND WAKE_WITH_WD`.
The existing wake gate removes DRV_ENABLE when WAKE_READY falls; U615 then
clears stored arm and masks PWM. Returning rail status does not re-arm a held
request. The monitors also delay release after digital reset or sensed-rail
recovery.

WAKE_CONDITIONS_OK comes from the [stop/link circuit](v4-power-stop-link.md).
Its WAKE_FAULTS_OK source is now implemented on the
[retained-fault sheet](v4-power-fault-memory.md), which also generates
ARM_FAULTS_OK. Rail loss clears acknowledgement as well as stored arm;
recovery requires an explicit healthy ACK before a fresh arm edge. Raw
CORE_PROTECTIONS_OK/WAKE_PROTECTIONS_OK sources, brake and electrical input
protection remain unfinished. This is not a complete shutdown chain.
The local asserted-signal timing allocation excludes the monitor's detection
delay; that delay cannot be replaced by its typical value in a worst-case proof.

## Five-volt recovery margin

R510/R511 retain 73.2 kΩ / 10 kΩ but now specify 0.1% initial tolerance.
The LMR51430 reference limits are 0.591–0.609 V and FB leakage is listed up to
50 nA under its stated test conditions. See
[TI LMR51430, section 7.5](https://www.ti.com/lit/ds/symlink/lmr51430.pdf).

A conservative static screen applies the full leakage magnitude in either
direction, with divider tolerance at opposing extremes:

```text
V5_min = 0.591 × (1 + Rt_min/Rb_max) − 50 nA × Rt_max
V5_max = 0.609 × (1 + Rt_max/Rb_min) + 50 nA × Rt_max
V_release_screen = 4.65 × 1.02 × 1.025 = 4.861575 V
```

| Divider tolerance | V5 minimum | V5 maximum | Minimum minus release screen |
|---|---:|---:|---:|
| Previous 1% | 4.827758 V | 5.160635 V | −33.8 mV |
| Adopted 0.1% | 4.904813 V | 5.079468 V | +43.2 mV |

The previous tolerances could prevent recovery. The revised positive margin
excludes resistor drift, ripple, ground error and load transients. Exact resistor
MPNs and temperature tracking must close that budget. It is not a measured
supply envelope or an overvoltage limit. Analog-regulator margin and reset ramp
behavior also need corner and bench qualification.

## Checks

The native saved netlist passes the complete component/pad/value contract.
The extended [Boolean checker](../tools/check_modular_arm.py) at the rail-only checkpoint passed 4,736
sequence observations and rejected ten deliberately bypassed connections. The
subsequent stop/link checkpoint extends those checks.
Each of four rail status failures disables the driver, clears stored arm and
requires a new request edge after recovery, across every PWM pattern and both
initial stored states. The test also changes PWM inputs during held-request
recovery to check that outputs remain masked.

Supervisor outputs are injected stimuli in this model. It does not simulate
analog thresholds, supply ramps, assertion/recovery timing, component faults or
PCB parasitics. New placement passes courtyard/copper clearance checks under
the current draft rules; global routing and manufacturing qualification remain.

The [controller-supply branch](v4-power-control-supply.md) now defines
`POWER_INTERFACE_OK = RAILS_OK AND P5V_C_OK`. Branch status therefore adds an
independent qualification to wake and retained acknowledgement. RAILS_OK itself
keeps the four original rail-monitor inputs above.
