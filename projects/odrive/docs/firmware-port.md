# Firmware port: DRV8301 → DRV8353RS

> **2026-09-08 mono revision:** this is an upstream integration survey, not an
> implemented or validated complete firmware port. A reference-compensated bus
> conversion, ADC1 acquisition and retained bus supervision now exist. A standalone
> diagnostic ELF links startup and TIM7/DMA service with the motor inhibited.
> The [DRV8353 register session](v4-mono-56v-drv8353-firmware.md) now compiles for ARM
> and has simulated SPI tests. The [SPI3 transport](v4-mono-56v-spi3-transport.md)
> connects the exchange callback to STM32 peripheral code. A [GPIO/wake owner](v4-mono-56v-driver-wake.md)
> now supplies startup permission and retained edge handling. The optional
> [driver diagnostic](v4-mono-56v-driver-diagnostic.md) integrates bus IRQs, wake and
> SPI configuration with COAST retained. Physical qualification and current-control
> integration remain pending.
> The current mono design changes PC6 to enable feedback and PC7 to brake-permission
> feedback and requires explicit rearming and driver initialization
> after interlock trips. The bus divider is now **22:1**, superseding the old
> 19:1 scaling; threshold coordination is still unresolved. See the
> [OV correction](v4-mono-56v-ov-protection.md). Follow the [mono firmware contract](v4-mono-56v-enable-interlock.md)
> and [current acceptance status](v4-mono-56v-implementation.md). Shunt values,
> gain, limits, timing and fault responses are still unresolved; the effort
> estimate and pin-preservation assumptions below are historical hypotheses.

Analysis of ODrive firmware `fw-v0.5.6` (MIT; source inspected at
`.scratch/odrive/firmware`). The driver interfaces provide an integration point;
the complete mono board port and its control-loop implications require validation.

## Current mono bus-voltage requirement

Use the 22:1 ADC divider, but do not assume that updating the divider constant
closes protection coordination. A 58 V setting with a fixed 3.3 V conversion
has a 54.56–61.47 V actual-bus sensitivity interval under the documented AVCC,
divider, buffer and clamp allowances. ADC converter and reaction-time errors
are not included. The independent hardware OV input screens at 58.66–61.03 V.
The firmware port must budget ADC-reference tracking or calibration and its
remaining error, sampling/filtering delay and fault reaction against the final
source/brake envelope. The first conversion component now uses calibrated
VREFINT and rejects invalid/stale inputs; it is not yet connected to the motor
controller. A [two-rank ADC1/DMA component](v4-mono-56v-adc-acquisition.md) now
feeds the conversion; diagnostic TIM7/DMA scheduling is implemented, while
PWM/current-loop scheduling remains pending.
The expanded conditional budget still rejects a 58 V
setting before hardware OV, even before reaction delay. See [the measurement
implementation and integration contract](v4-mono-56v-bus-measurement.md).
See [the OV calculation and assumptions](v4-mono-56v-ov-protection.md).

## Current mono PWM sampling requirement

The [prospective PWM sampling planner](v4-mono-56v-pwm-sampling.md) uses an
explicit PWM1/high-side duty convention and PWM2 OC4REF rising TRGO with a
settled all-low-side conversion window. Upstream `Board/v3/Src/tim.c` uses PWM2
for the phases and update TRGO with RCR=2. Its compare conversion, preload phase
and dual-axis acquisition schedule cannot be copied unchanged. A [continuous TIM1
cycle owner](v4-mono-56v-pwm-cycle.md) now implements preload history and boundary/command
deadlines with outputs inhibited. A [continuous ADC capture owner](v4-mono-56v-pwm-capture.md)
now provides per-cycle deadlines and single-delivery raw frames, tested with the
ADC2/3 driver. A [calibration-to-timing handoff](v4-mono-56v-timing-handoff.md)
now preserves ENABLE and the verified register session while releasing stopped
capture and allowing internal counting. The
[calibrated timing diagnostic](v4-mono-56v-timing-diagnostic.md) now integrates
scheduling and IRQ ownership, consuming raw frames and queuing fixed next-cycle
compares during foreground SPI. Qualified current-frame construction, calibrated
output handoff and controller integration remain pending.
The [manual current-zero diagnostic](v4-mono-56v-current-diagnostic.md) already
integrates CSA transitions, stopped-TIM1 capture and zero estimation in COAST.

## Current mono brake-reset requirement

The brake memory now uses a fault-dominant OR-AND feedback latch. Valid NRST low
restores permission only while overcurrent is absent; no release edge is needed.
Overcurrent dominates reset and remains retained after recovery while NRST is
high. Keep BRAKE_PWM low throughout reset/startup and never implement a reset
retry loop for brake overload. A fault that clears while reset remains asserted
permits braking again. PC7 now reads `BRK_OK_FB` through 10 kΩ and must be an
input with no pull, not TIM8_CH2. U59/U57 clear motor permission when brake
permission falls. Firmware must retain that fault, disable PWM, lower PB12,
and require a deliberate restart after healthy conditions are restored. Reading
permission does not diagnose an open or undersized brake resistor. Rail-ramp
qualification, diagnostic firmware and lost-brake energy handling remain pending. See
[the current brake hardware contract](v4-mono-56v-brake-interlock.md).

## How the firmware sees the gate driver

`Firmware/Drivers/DRV8301/` is 321 lines and is the *only* DRV8301-aware code. The class
implements two abstract interfaces from `Drivers/gate_driver.hpp`:

- `GateDriverBase` — `set_enabled()`, `is_ready()`
- `OpAmpBase` — `is_ready()`, `get_midpoint()`, `get_max_output_swing()`

`Board/v3/board.cpp:39-51` instantiates two of them on a shared SPI3 arbiter with
per-driver `nCS`, a **shared EN** (actuated outside the driver) and a **shared nFAULT**.
`Motor` (`board.cpp:76-95`) takes the same object twice, as `gate_driver` and as `opamp`,
plus `1/SHUNT_RESISTANCE` and `current_sensor_mask = 0b110` (phases B+C sensed, A
reconstructed). These interfaces are potential integration hooks. The current mono
design also changes ADC ownership, feedback pins and startup/fault behavior; a
drop-in port with unchanged motor/axis integration has not been established.

## What actually changes

| Surface | DRV8301 (today) | DRV8353RS | Port work |
|---|---|---|---|
| SPI frame | 16-bit: R/W b15, addr b14-11, data b10-0 | identical layout | `build_ctrl_word` reusable as-is |
| Registers | 2 status + 2 control | 2 status (0x00–0x01), controls 0x02–0x06; 0x07 contains CAL_MODE and reserved bits | new register map; preserve reserved bits |
| CSA gain | {10, 20, 40, 80} V/V (`config()` table) | **{5, 10, 20, 40} V/V** | new table; current mono shunts are 1 mΩ: ideal ±70 A at 3.3 V / 20 V/V before margins, not a board rating |
| SO midpoint/swing | hardcoded `0.5` norm., ±1.35 V of ±1.65 V (`drv8301.hpp:82-88`) | VREF/2 bidirectional; swing ≈ ±(VREF/2 − 0.25 V) | new constants; depends on VREF wiring (see below) |
| Fault bits | `FaultType_e` mirrors raw status regs 1:1 (per-FET OC, OTW/OTSD, PVDD_UV, GVDD_UV/OV) | different layout: VDS_OCP + SA/SB/SC_OC + UVLO + CPUV + OTW/OTSD + per-FET VGS gate faults | new enum + mapping; user-visible `drv_fault` values change |
| Gate current | fixed choices in CTRL1 (1.7 A peak) | **smart gate drive**: IDRIVEP/IDRIVEN + TDRIVE, chosen per FET Qg | new config fields; values come from the v4 FET selection |
| Dead time | DTC pin (hardware) | register-programmable | pick from FET switching char.; one more config field |
| OCP threshold | OC_ADJ vs Rdson (`(21<<6)` ≈ 150 A@100 °C today) | VDS_LVL vs Rdson | **per-BOM-variant constant** — 24 V and 56 V FETs have different Rdson |
| Init quirks | EN low ≥20 µs resets; CTRL1 written 5× ("write tends to be ignored", `drv8301.cpp:84-88`) | ENABLE low = sleep, regs lost >1 ms; t_wake ≈ 1 ms | keep the write-then-verify flow; the 5× quirk is 8301-specific, drop it |

The DRV8353RS register addresses above were corrected against
[TI Table 9](https://www.ti.com/lit/gpn/drv8353): the former table incorrectly
classified driver control at 0x02 as a third status register. The remaining
historical constants must be checked during the port.

## Board/version plumbing

The upstream private `Board/v4` target is STM32F7; it must not be reused merely
because this STM32F405 mono design is also called v4. A separate mono target and
reproducible source preparation are still required.

Hardware identity comes from OTP (`HW_VERSION_MAJOR/MINOR/VOLTAGE`, `board.cpp:30`) and
`Board/v3/Inc/board.h` selects per-version constants at compile time (`SHUNT_RESISTANCE`
675 µΩ vs 500 µΩ, thermistor ADC channels, voltage limits). A v4 board = a new version
entry (either `HW_VERSION_MAJOR 4` config in the same tree, or a `Board/v4/` copy)
selecting the `Drv8353` driver, its shunt value, and per-variant (24 V/56 V) VDS_LVL +
voltage limits. Timers (TIM1/TIM8), ADC assignment and the encoder/GPIO map stay valid
as long as v4 preserves the v3.5/v3.6 STM32 pinout — which is a stated v4 constraint.

## Hardware decisions that keep the port small

1. **Preserve the v3.5/v3.6 STM32 pin map** (SPI3 + per-driver nCS, shared EN, shared
   nFAULT, SO1/SO2 on the same ADC pins, TIM1/TIM8 PWM pins). Then the port never
   touches `board.h` pin definitions.
2. **Use the actual mono shunts: R22–R24 are 1 mΩ.** The former 500 µΩ
   proposal and ±165 A usable-range claim do not describe this schematic. Using
   500 µΩ would double the inferred current. Exact shunt MPN, rating and Kelvin
   routing remain to be qualified. See [current conversion and calibration](v4-mono-56v-phase-current.md).
3. **VREF of the CSAs from the 3.3 V analog rail** (bidirectional mode) so
   `get_midpoint()` is a clean VREF/2 and scales with the ADC reference.
4. **Wire the third CSA (SOA) to a spare ADC-capable pin anyway.** Firmware keeps
   `current_sensor_mask = 0b110` and ignores it on day one; upgrading to 3-phase
   sensing later is a firmware-only change (ADC scheduling in `motor.cpp`), impossible
   to retrofit in hardware.
5. **Pick FETs before finalizing firmware constants**: IDRIVE, TDRIVE, dead time and
   VDS_LVL all derive from the FET's Qg/Qgd and Rdson, per BOM variant.

## Estimated effort

- `Drivers/DRV8353/drv8353.{cpp,hpp}`: ~350 lines, modeled line-by-line on the 8301
  driver (same state machine: config → init → startup checks → ready; same
  `do_checks()` nFAULT monitoring contract, <8 ms interval).
- Board config: ~100 lines (version entry, driver instantiation, constants).
- No changes to `motor.cpp`, `axis.cpp`, control loops, or comms.
- Risk: user-visible `drv_fault` codes change meaning; document the new mapping for
  odrivetool users.
