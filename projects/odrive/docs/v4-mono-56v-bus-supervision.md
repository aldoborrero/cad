# Mono 56 V bus supervision and motor inhibition

## Implemented scope

`firmware/mono56/` now connects finite ADC1 acquisition to calibrated bus
measurement and a retained bus fault. `BusSupervisor` starts inhibited, schedules
captures, checks their validity and voltage limits, and calls the STM32F405 motor
inhibit primitive before withdrawing measurement readiness on a fault.

This is a firmware component, not the mono motor-control board port. A subsequent
[standalone diagnostic image](v4-mono-56v-diagnostic-image.md) now supplies startup
and IRQ service around it, with the motor permanently inhibited. The component
by itself is not a flashable image.
There is no startup/vector table, interrupt installation, PWM/current loop,
DRV8353 register configuration, encoder integration or motor-arm implementation
here. Hardware permissions on PC6/PC7 are not yet consumed by this supervisor;
`bus_ready()` only reports the bus condition, never overall permission to run.

## Behavior and ownership

One serialized board/control owner must retain the supervisor and call `update()`
before consuming each result. The same owner must govern eventual arming. ADC1
and DMA2 stream 0 belong exclusively to this acquisition path. A failed attempt
to acquire an already-owned ADC does not shut that ADC down.

- `begin(config)` inhibits PB12/TIM1 before validating configuration or acquiring
  ADC1. It requires explicit voltage, acquisition, startup and freshness limits.
  It cannot recover a running or faulted instance implicitly.
- A complete, reference-compensated frame within limits provides bus readiness.
  A previously completed frame remains usable between captures only within its
  original age bound. A partial new transfer never supplies a replacement value.
- Invalid, stale, clipped or implausible measurements; acquisition errors;
  backward service-clock observations; startup timeout; undervoltage and
  overvoltage latch faults. The first cause remains available. The output voltage
  becomes NaN and readiness is withdrawn; later healthy samples do not rearm.
- Explicit `stop()` followed by `begin()` permits a fresh measurement attempt.
  Both inhibit the motor. A successful new reading itself produces no enable
  edge or PWM activation. The board's retained axis fault and explicit arm
  protocol still need implementation.

The clock is a monotonic wrapping 32-bit microsecond counter. Caller/configuration
intervals must stay below half its range. Configuration enforces ADC deadline no
longer than capture period, age allowance at least period plus capture deadline,
and a pair-span allowance covering the capture deadline. The 21 MHz ADC path
requires configured minimum VDDA at least 2.4 V. These consistency checks do not
select or qualify production settings.

The tests use **125 µs period, 50 µs acquisition deadline, 300 µs startup deadline,
250 µs maximum age, 10 V undervoltage and 58 V overvoltage** as arbitrary fixtures.
In particular, **58 V remains rejected by the conditional hardware/firmware OV
coordination analysis**; it is not a production default.

### Service deadline is separate from capture cadence

A 125 µs periodic caller alone cannot observe a roughly 25 µs capture within a
50 µs deadline. Board integration must provide timely completion service, for
example a serialized DMA completion handler together with periodic dispatch and
timeout checks. The component does not enable DMA interrupts or install handlers.
The existing ADC1 continuous scan and injected-bus owner must be removed from the
mono port, with the remaining analog measurements assigned a deliberate schedule.

A stalled caller cannot execute this fault path. Independent MCU-lockup detection,
interrupt priorities, maximum observation/shutdown latency, clock initialization
and physical fault timing remain acceptance requirements.

## STM32 motor inhibit primitive

`mono56_motor_inhibit()` saves PRIMASK, disables interrupts, enables/read-backs
GPIOB and TIM1 peripheral clocks, preloads PB12 low and selects push-pull GPIO
output, clears TIM1 BDTR MOE and AOE, executes a data synchronization barrier and
restores the original interrupt mask. PB12 is `DRV_EN_MCU` on MCU physical pin 33.
The primitive does not write the PB11 brake request or reset the brake state.
Other GPIO modes and timer break/dead-time configuration are preserved.

Clearing AOE follows ST's recommended treatment of retained fault protection in
[ES0182 Rev 19, section 2.7.1](https://www.st.com/resource/en/errata_sheet/es0182-stm32f405407xx-and-stm32f415417xx-device-errata-stmicroelectronics.pdf).
The eventual TIM1 initialization must leave AOE disabled and its lock settings
compatible with this treatment. The inspected upstream v3 timer initializes
LOCKLEVEL_OFF and AUTOMATICOUTPUT_DISABLE; those conditions are not yet established
by a mono startup implementation.

Register-level inhibition does not establish a measured stop latency, safe gate
waveforms or dissipation of mechanical energy. A disabled bridge can still
passively rectify a rotating motor onto the bus. Brake energy and hardware
watchdog/external-stop qualification remain open.

## Verification and build evidence

The host executable runs the production supervisor, acquisition and inhibition
sources against the STM32F405 CMSIS register layouts with simulated addresses,
DMA events and CPU interrupt primitives. It covers successful scheduling and
fresh-cache use, timeout and transport errors, voltage/measurement faults,
retention and explicit recovery, delayed first frame, time wrap, invalid
configuration, foreign ADC ownership, interrupt-mask restoration and preservation
of the brake pin configuration. These simulations do not model analog behavior,
DMA bus timing, pin transitions or timer lock behavior.

`check_mono_firmware.py --arm-gcc /path/to/arm-none-eabi-gcc ...` compiles all four
production C/C++ sources for Cortex-M4/Thumb with the hard-float ABI, checks ELF
attributes and combines them with a relocatable link. Undefined symbols in that
combined component object cause failure. `--arm-clang` additionally compiles the
two production C drivers. The test runner requires all three CTest registrations
and executables; it removes previous success evidence before starting a new run.

GNU ARM GCC 15.3.0 from the pinned Nix inputs was used. C++ uses the toolchain's
standard headers, without `-ffreestanding`, as in upstream's C++ build; GCC 15
rejects `<cmath>` in freestanding mode. No runtime libraries are linked by this
component check. The fetched default `arm-embedded` compiler reports only one
multilib (`.;`); compatibility of its runtime libraries with the complete
Cortex-M4 hard-float image has **not** been established.

Evidence is under `.scratch/v4-56v-implementation/firmware-components/`, including
commands, tool versions, source/header hashes and object hashes. Deliberately
faulty copies and their rejection results live in `negative-bus-supervision/`.
See the [implementation acceptance matrix](v4-mono-56v-implementation.md) for the
remaining hardware, PCB, firmware, manufacturing and bench requirements.
