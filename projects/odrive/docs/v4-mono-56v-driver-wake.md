# STM32 driver GPIO preparation and DRV8353 wake owner

## Implemented scope

`firmware/mono56/src/driver_io.c` implements the mono GPIO and EXTI preparation.
`src/driver_wake.cpp` owns explicit sleep/wake timing, retained permission faults
and the board callbacks required by the DRV8353 register session. Both production
paths compile for Cortex-M4. Host tests connect the actual GPIO/wake code to the
actual register session with simulated registers and SPI replies.

The standalone bus diagnostic does **not** instantiate this owner. It continues
to inhibit the motor permanently. The optional [driver diagnostic](v4-mono-56v-driver-diagnostic.md)
now connects the bus service, startup owner and SPI3 with COAST retained. No device
has been flashed, and physical sleep/wake, pin transitions and edge capture have
not been qualified. This owner never enables PWM or releases COAST by itself.

## Physical mapping and ownership

The current exported schematic connects:

| Function | STM32 pin | Behavior in this implementation |
|---|---|---|
| INHA / INHB / INHC | PA8 / PA9 / PA10 | Push-pull GPIO LOW |
| INLA / INLB / INLC | PB13 / PB14 / PB15 | Push-pull GPIO LOW |
| Driver enable request | PB12 | LOW at preparation; one guarded rising request |
| Actual driver enable | PC6 | Input, no pull; falling-edge capture on EXTI6 |
| Brake permission | PC7 | Input, no pull; falling-edge capture on EXTI7 |
| Shared driver/rail nFAULT | PD2 | Input, no pull; falling-edge capture on EXTI2 |

Preparation inhibits PB12/TIM1 before changing PWM pin modes. It stops TIM1,
disables its DMA/interrupt requests and channel outputs, and holds all six PWM
pins LOW using output-latch preloads. The previous PWM/DMA owner must already
be stopped; this is not an on-the-fly takeover protocol for an active motor.
Other GPIO modes and alternate-function mappings are preserved, including PB11
brake control and PC10..13 SPI. Readback checks GPIO mode, pulls, output type,
output latch and input level, as well as TIM1 and capture configuration. These
checks describe MCU pin state; they do not measure external MOSFET gate voltages.

EXTI2/6/7 are exclusive. EXTI IMR and falling-edge detection are enabled, while
NVIC delivery for EXTI2 and EXTI9_5 must stay disabled. An already enabled shared
vector or existing owner of these lines is rejected. This allows polled startup
capture without relying on masked EXTI inputs retaining pulses. The eventual
interrupt service must replace this ownership contract before running PWM.
The implementation follows the EXTI mapping/pending-register model in
[ST RM0090, chapter 12](https://www.st.com/resource/en/reference_manual/rm0090-stm32f407-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).
Complete manual download failed in this environment; the indexed manufacturer
chapter and local CMSIS definitions were inspected, not a full reference-manual
audit. Physical pulse width, input filtering and capture behavior remain open.

## Startup sequence and timing

The caller supplies a nonblocking wrapping microsecond clock, a fresh retained
bus-permission callback, sleep/wake durations, feedback timeout and maximum
service gap. Parameters are mandatory. The host fixture uses 2000 µs sleep and
wake with 250 µs feedback/service limits; these are not production defaults.
Sleep/wake values below 1001 µs are rejected to include counter quantization
around the datasheet's listed 1 ms times. Clock tolerance and actual board
startup still need qualification. A stopped clock cannot complete startup, but
this module is not an independent watchdog for a later clock/CPU failure.

[TI SLVSDY6A sections 7.5, 7.6 and 8.4](https://www.ti.com/lit/ds/symlink/drv8353.pdf)
distinguish full sleep, which resets registers and disables SPI, from a short
ENABLE fault-reset pulse, which preserves configuration. The implementation
requires the following sequence:

1. Inhibit and prepare all six PWM GPIOs. Require a fresh valid bus and brake
   permission; wait for actual ENABLE feedback LOW within the configured limit.
2. Start sleep timing **after** observing LOW. Any subsequent enable/brake
   falling edge is retained; a HIGH observation during sleep rejects the session.
3. After the full sleep duration, recheck bus permission with interrupts masked
   immediately before the local GPIO/edge checks and single PB12 rising request.
   The callback must work without interrupts and must not block. This closes a
   CPU interrupt race with bus supervision; it is not an analog fault deadline.
4. Wait for actual ENABLE HIGH, then timestamp the confirmed observation and
   count the full wake duration. A request bit alone cannot start wake timing.
5. Require healthy nFAULT and feedback after wake. Clear only the initial PD2
   wake-history bit, once, then sample levels and pending history again. Initial
   wake undervoltage may assert nFAULT; later falling edges cannot be erased by
   repeating qualification. ENABLE and brake history are never cleared here.
6. `permitted()` now services/rechecks the owner and can allow register setup.
   `Drv8353::configure_coasted()` still writes, locks and verifies all settings.
   GPIOs stay LOW; current calibration and motor arming are separate unfinished
   requirements.

Every active service checks clock direction, service lateness, bus permission,
GPIO configuration, quiet outputs, request/feedback consistency and retained
edges. Any failure inhibits PB12/TIM1 and preserves the first reason. Recovery
of levels, time passing, or another `begin()` cannot rearm. Explicit owner reset
and register-session reset are both required for a new startup. Teardown ends
the EXTI session; pending hardware state is not a persistent diagnostic archive.
The retained software reason must be read before explicit reset.

## Integration and evidence

Create one static/long-lived `DriverWake` owner, service it from one serialized
foreground context, and supply `wake.io(mono56_drv8353_spi3_exchange)` to the
register session. The SPI3 adapter ignores the context; the remaining callbacks
use the wake owner. SPI3 initialization and scheduling remain the caller's job.
Each register transaction checks permission before and after transfer. A lost
edge inside a frame or a transport failure reaches the hardware-inhibit path.
Do not run the blocking configuration sequence in the high-rate current ISR.

This owner requires quiet GPIOs even after becoming awake. The
[timing handoff](v4-mono-56v-timing-handoff.md) now permits internal TIM1 counting
after verified normal-CSA restoration, without changing those GPIOs or releasing
COAST. It adds a nonrenewing IRQ guard and rejects foreground-service calls from
exception context. The full suite now passes 911 GPIO/wake assertions. Output
handoff is still required before use in a running axis.
Physical fault reaction is not bounded by the service-gap setting alone:
a late call is detected when service resumes. There is no independent watchdog,
external stop implementation or physical fault-injection evidence yet.

The initial component checker passed 430 GPIO/wake checks plus the existing 5613 bus,
SPI and driver checks. Eight deliberately faulty IO/wake copies compile and are
rejected: omitted sleep, wake timed from request, ignored enable history, repeated
fault clearing, ignored atomic bus permission, disabled capture, one PWM left
high and ignored service lateness. Review also corrected acceptance of feedback
first observed after its timeout, even if the current level had recovered. Evidence is under
`.scratch/v4-56v-implementation/firmware-components/`, `negative-driver-wake/`
and `monitor-image/`. Tests exercise each PWM input, request duplication,
initial/retained faults, feedback delays, counter wrap/backward jumps, service
lateness, a bus-permission race and errors inside register transactions. The
bus diagnostic still links with unused startup-owner code removed by the linker.
See [the full acceptance requirements](v4-mono-56v-implementation.md).
