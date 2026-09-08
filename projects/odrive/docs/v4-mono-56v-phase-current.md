# Mono 56 V phase-current conversion and software zero calibration

## Implemented scope

`firmware/mono56/include/phase_current.hpp` and `src/phase_current.cpp` now
convert a supplied B/C sample pair into signed phase currents and estimate the
two channel offsets from a bounded collection of calibration samples. They have
no peripheral access and do not grant motor permission. A separate
[ADC2/ADC3 acquisition driver](v4-mono-56v-current-acquisition.md) now captures
supplied TIM1_TRGO events. Trigger/IRQ scheduling, PWM sampling windows,
diagnostic integration and physical measurements remain
pending. The separate [DRV8353 session](v4-mono-56v-drv8353-firmware.md) now
implements verified manual B/C calibration register entry and exit.

## Schematic correspondence

The reviewed XML is `.scratch/v4-56v-implementation/mono-brake-motor-link.xml`.
The pin contract now fixes these routes and values:

| Phase | Shunt | U3 positive / negative / output pins | Filter | MCU endpoint |
|---|---|---|---|---|
| B | R23, 1 mΩ | SPB 14 / SNB 13 / SOB 24 | SO1: R73/C72, R79/C78 | PC0, pin 8, channel 10 |
| C | R24, 1 mΩ | SPC 21 / SNC 22 / SOC 23 | SO2: R74/C73, R80/C79 | PC1, pin 9, channel 11 |
| A, optional | R22, 1 mΩ | SPA 11 / SNA 12 / SOA 25 | SO3: R77/C76, R83/C82, JP1 | PA2, pin 16, channel 2 |

Each filter has a 100 Ω series resistor and 1 nF to AGND followed by another
100 Ω series resistor and 47 pF to AGND. JP1 is a closed solder bridge. Each
four-terminal schematic shunt has pin 1 toward the low-side MOSFET sources,
pin 4 to PGND, and separate pins 2/3 toward SP/SN. U3 VREF and U2 VDDA share AVCC.
The exact shunt MPN, physical terminal-to-pad roles, rating and routed Kelvin
geometry have not been qualified. A netlist cannot establish those properties.

PC0/PC1/PA2 offer ADC123 channels 10/11/2 in
[ST DS8626, Table 7](https://www.st.com/resource/en/datasheet/dm00037051.pdf).
The intended two-channel acquisition is ADC2 for B and ADC3 for C; it is not
implemented by this conversion module. Phase A is reconstructed as `-(B+C)`,
which assumes a three-wire motor. Optional direct A sensing is not consumed.

The historical firmware-port proposal used 500 µΩ. Applying that value to the
present 1 mΩ schematic doubles the reported current. Neither the old value nor
its claimed ±165 A usable range is a mono 56 V specification.

## Conversion contract

The bidirectional amplifier output is `VREF/2 + gain * (SP-SN)`; supported gains
are 5, 10, 20 and 40. Its specified linear output interval is 0.25 V through
`VREF-0.25 V`. With 3.3 V, gain 20 and 1 mΩ, that gives an ideal ±70 A interval
before offset, tolerance, filtering, ADC and thermal margins. It is not a board
current rating. See [TI SLVSDY6A, sections 7.5 and 8.3.4.1](https://www.ti.com/tw/lit/gpn/drv8353).

The implemented conversion is:

```text
B = polarity_B * (raw_B - zero_B) * VDDA / (4096 * gain * R_B)
C = polarity_C * (raw_C - zero_C) * VDDA / (4096 * gain * R_C)
A = -(B + C)
```

Both polarities are explicit ±1 configuration inputs relative to SP−SN. The
integration must establish the motor-current convention and verify it on the
board. Signal names alone do not establish it.

The caller supplies original sample timestamps, a measured VDDA with its own
original timestamp, the actual driver-session generation, and verified sampling
and calibration states. Flags supplied by a test do not establish physical
conduction or settling. B/C require a qualified common low-side conduction
window; their difference in acquisition time must meet the configured bound.

The module rejects missing, stale/future, skewed, clipped or out-of-range samples;
invalid gain/shunts/polarities; invalid, expired or different-session offsets;
excessive VDDA change since calibration; calibration-mode samples during normal
measurement; and invalid conduction windows. Configuration reserves output
headroom for its current limit and allowed zero offset at the minimum supply.
The absolute current limit applies to all three phases, including reconstructed
A. Every rejected conversion returns an error and three NaNs. The eventual axis
owner must act on rejection; this pure function does not inhibit the bridge.

## Zero collection and its limits

Manual CSA_CAL shorts the amplifier inputs and disconnects them from the load;
it differs from the automatic trimming sequence. The owner must select and
verify manual mode and the B/C calibration bits before collection, then restore
and verify normal inputs before measuring phase current. TI recommends an off
period to reduce switching noise during manual calibration. See
[TI section 8.3.4.3](https://www.ti.com/tw/lit/gpn/drv8353).

`CurrentZeroEstimator` does not perform those SPI operations; the owner can now
use `Drv8353::begin_current_calibration()` and `end_current_calibration()`.
COAST alone is
insufficient evidence of zero shunt current: a moving motor can rectify through
the disabled bridge. The collection start time must follow verified entry into
manual input-short mode. The owner must allow analog/filter/ADC settling and
supply an independently qualified settling time.

The estimator requires 2–4096 samples, a minimum settling interval, a minimum
observed span on **each** channel, a collection deadline, bounded channel noise
and VDDA variation, and offsets near the configured midpoint allowance. It
rejects duplicate/backward sample timestamps and backward service time. On the
last accepted sample it records separate mean offsets, mean VDDA, the gain,
driver session and completion time. A failure discards readiness and retains
the first error until explicit reset. Calling `begin()` cannot bypass a fault.

Timeout checking occurs when `add()` is called. If acquisition stops altogether,
the owner must enforce its own service deadline; the estimator stays unready.
A reset/configuration generation must invalidate the old calibration. The
session tag is supplied by that owner, not generated by this helper.

Offset subtraction uses ADC codes, with bounded supply change since calibration.
A single zero measurement cannot separate amplifier voltage offset from ADC
code offset or characterize temperature drift. No absolute accuracy, recalibration
interval, thermal behavior or safety limit has been established by these tests.

## Verification

The fixture uses 1 mΩ, gain 20, +1 polarities, VDDA 3.0–3.6 V, 0.30 V rail margin,
40 A phase limit, 16-code zero allowance and 0.05 V calibration supply-change
budget. Eight samples span 700 µs after 10 µs settling, within a 2000 µs timeout.
These are test inputs, not an approved hardware profile.

- 596 assertions exercise conversion against an independent double-precision
  oracle across gains, supplies and signs, invalid inputs, calibration noise,
  duplicate timestamps, per-channel settling/span, counter wrap and fault reset.
- Seven faulty source copies compile and are rejected: fixed midpoint, doubled
  scaling, omitted A limit, ignored window, old-session zero reuse, ignored noise
  and omitted C-channel span. Evidence: `.scratch/v4-56v-implementation/negative-current/validation.json`.
- The full 17-test firmware suite passes; nine production component sources
  compile/combine for Cortex-M4 without unresolved symbols. Evidence:
  `.scratch/v4-56v-implementation/firmware-components/validation.json`.
- The schematic contract checks 116 components / 2368 assertions. Five altered
  XML copies are rejected: old shunt value, swapped ADC phases, shorted Kelvin
  sense nodes, filter bypass and open phase-A bridge. Evidence:
  `.scratch/v4-56v-implementation/current-pin-contract/validation.json`.

The [manual current-zero diagnostic](v4-mono-56v-current-diagnostic.md) now
connects verified CSA transitions, actual ADC2/3 peripheral code, stopped-TIM1
triggers and shared IRQ/deadline service to this estimator, with simulated
peripheral integration tests and a linked ARM image. The
[PWM sampling planner](v4-mono-56v-pwm-sampling.md) now computes prospective
conduction/settling windows. Running-timer ownership and observed-cycle binding
must still establish the validity flag before normal phase-current conversion.
Physical accuracy and the complete motor controller remain unqualified.
