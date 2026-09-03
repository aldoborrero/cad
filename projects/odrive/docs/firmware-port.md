# Firmware port: DRV8301 → DRV8353RS

Analysis of ODrive firmware `fw-v0.5.6` (last open-source release, MIT; shallow clone at
`.scratch/odrive/firmware`). Conclusion up front: **the port is small and well-contained
— one new driver class plus board-config plumbing; no control-loop changes.** The v4
hardware decisions that keep it that way are listed at the end.

## How the firmware sees the gate driver

`Firmware/Drivers/DRV8301/` is 321 lines and is the *only* DRV8301-aware code. The class
implements two abstract interfaces from `Drivers/gate_driver.hpp`:

- `GateDriverBase` — `set_enabled()`, `is_ready()`
- `OpAmpBase` — `is_ready()`, `get_midpoint()`, `get_max_output_swing()`

`Board/v3/board.cpp:39-51` instantiates two of them on a shared SPI3 arbiter with
per-driver `nCS`, a **shared EN** (actuated outside the driver) and a **shared nFAULT**.
`Motor` (`board.cpp:76-95`) takes the same object twice, as `gate_driver` and as `opamp`,
plus `1/SHUNT_RESISTANCE` and `current_sensor_mask = 0b110` (phases B+C sensed, A
reconstructed). A `Drv8353` class implementing the same two interfaces drops in with no
changes to `motor.cpp`/`axis.cpp`.

## What actually changes

| Surface | DRV8301 (today) | DRV8353RS | Port work |
|---|---|---|---|
| SPI frame | 16-bit: R/W b15, addr b14-11, data b10-0 | identical layout | `build_ctrl_word` reusable as-is |
| Registers | 2 status + 2 control | 3 status (0x00-0x02) + 4 control (0x03-0x06) | new register map, same read/write helpers |
| CSA gain | {10, 20, 40, 80} V/V (`config()` table) | **{5, 10, 20, 40} V/V** | new table; 20 V/V on 500 µΩ ≈ ±165 A usable range |
| SO midpoint/swing | hardcoded `0.5` norm., ±1.35 V of ±1.65 V (`drv8301.hpp:82-88`) | VREF/2 bidirectional; swing ≈ ±(VREF/2 − 0.25 V) | new constants; depends on VREF wiring (see below) |
| Fault bits | `FaultType_e` mirrors raw status regs 1:1 (per-FET OC, OTW/OTSD, PVDD_UV, GVDD_UV/OV) | different layout: VDS_OCP + SA/SB/SC_OC + UVLO + CPUV + OTW/OTSD + per-FET VGS gate faults | new enum + mapping; user-visible `drv_fault` values change |
| Gate current | fixed choices in CTRL1 (1.7 A peak) | **smart gate drive**: IDRIVEP/IDRIVEN + TDRIVE, chosen per FET Qg | new config fields; values come from the v4 FET selection |
| Dead time | DTC pin (hardware) | register-programmable | pick from FET switching char.; one more config field |
| OCP threshold | OC_ADJ vs Rdson (`(21<<6)` ≈ 150 A@100 °C today) | VDS_LVL vs Rdson | **per-BOM-variant constant** — 24 V and 56 V FETs have different Rdson |
| Init quirks | EN low ≥20 µs resets; CTRL1 written 5× ("write tends to be ignored", `drv8301.cpp:84-88`) | ENABLE low = sleep, regs lost >1 ms; t_wake ≈ 1 ms | keep the write-then-verify flow; the 5× quirk is 8301-specific, drop it |

## Board/version plumbing

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
2. **Keep 500 µΩ shunts** so `SHUNT_RESISTANCE` and the current ranges stay familiar
   (20 V/V ≈ ±165 A). Kelvin/net-tie treatment as in v3.5.
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
