# Mono 56 V PWM sampling plan

## Implemented scope

`firmware/mono56/include/pwm_sample_plan.hpp` and `src/pwm_sample_plan.cpp`
calculate prospective compare values and a current-sampling interval for one
center-aligned PWM cycle. The planner preserves requested A/B/C duties, rounds
timer dead time upward, checks minimum input pulse widths, finds a settled
all-low-side interval and reserves ADC/IRQ completion time before the next
trigger. Impossible requests return an error and no usable timer plan.

This component is implemented and ARM compiled. It does **not** configure a
running timer, release COAST, set MOE, switch pins to alternate functions, or
mark an acquired current frame's window valid. The existing
[current-zero diagnostic](v4-mono-56v-current-diagnostic.md) remains a stopped-TIM1
manual-calibration image. A [continuous TIM1 cycle owner](v4-mono-56v-pwm-cycle.md)
now consumes plans with outputs inhibited, and a [capture companion](v4-mono-56v-pwm-capture.md)
supplies ADC deadlines and raw cycle-bound frames. Qualified current-frame
construction and calibrated output handoff remain pending; physical timing and
current accuracy remain unqualified.

## Explicit timer and conduction contract

The proposed runtime configuration uses TIM1 at 168 MHz, PSC=0 and CKD=0,
center-aligned PWM1 on channels 1–3, active-high complementary CHx/CHxN outputs,
and PWM2 on channel 4 with OC4REF as rising-edge TRGO. A/B/C high-side duty is
`CCR/ARR`: low-side conduction surrounds the counter apex. CCR4 stays strictly
between zero and ARR and rises once during the upcount. The phase compares must
remain active and unchanged through the complete sampling interval.
These register relationships follow [ST RM0090](https://www.st.com/resource/en/reference_manual/rm0090-stm32f407-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).

This differs from upstream `fw-v0.5.6` `Board/v3/Src/tim.c`, which uses PWM2 for
the phase channels and update-event TRGO with RCR=2. Its duty conversion and
alternating update/current/control schedule cannot be copied unchanged. The
local upstream source is an integration reference, not an active mono target.

The DRV8353's six-input mode commands low-side conduction with INL high and INH
low. Both inputs low, as in the current diagnostic's GPIO state, produce Hi-Z;
they cannot establish a shunt conduction window. Driver propagation, internal
dead time, FET transitions, CSA settling and the board's RC network all need
allowance. The CSA's listed settling conditions alone do not qualify the whole
board path. See [TI DRV8353, table 1 and electrical characteristics](https://www.ti.com/tw/lit/gpn/drv8353).

The initial policy samples with **all three low sides settled**. Including A
avoids a phase-A commutation inside the B/C conversion interval. This limits
available modulation at high duty; requests outside that envelope are rejected,
not silently reduced. A future controller must handle modulation saturation
explicitly. Alternative active-vector sampling would require a different,
independently qualified window policy.

## Inputs and timing calculation

All bounds are mandatory and must ultimately be qualified against the board:

| Input | Meaning |
|---|---|
| `half_period_ticks` | ARR, 2–65535; full PWM period is twice this value |
| `dead_time_ns` | Requested TIM1 complementary-output dead time |
| `low_side_settle_ns` | Maximum MCU low-input-rise to settled gate/shunt/CSA/filter response |
| `edge_margin_ns` | Additional exclusion margin around switching boundaries |
| `min_input_pulse_ns` | Minimum usable high/low pulse at the gate driver's MCU inputs |
| `arm_budget_ns` | Maximum underflow-to-both-ADCs-armed latency |
| `completion_service_ns` | Maximum conversion-complete-to-both-data-observed latency |

Nanoseconds are converted with integer ceiling; each must be positive and at
most 1 ms before arithmetic. DTG is selected from the actual four nonlinear
hardware ranges and must never shorten the requested dead time. Values beyond
the hardware range fail. Pulse checks subtract the realized dead time from
both complementary input pulse lengths, including pulses around counter wrap.

The ADC contract remains independent ADC2/ADC3 at 21 MHz, 12-bit resolution and
15 sampling cycles, with PCLK2=84 MHz and no regular sequence on those ADCs.
ST specifies an injected-trigger latency of three ADC clocks plus one PCLK2
clock for an external trigger. With sampling and conversion, the planner reserves
242 TIM1 ticks from trigger to latest conversion completion. This covers the
entire conversion, not merely the hold instant.
See [DS8626 Rev 12, table 67 and footnote 7](https://www.st.com/resource/en/datasheet/dm00037051.pdf).

The planner prefers a conversion spanning the apex. It can move the trigger
within the settled interval, including earlier when IRQ service would otherwise
miss the next-cycle deadline. It rounds full-period spacing down to microseconds
and the capture deadline up, preserving the acquisition contract
`deadline_us + 1 < min_trigger_spacing_us` for a repeated plan. Changing CCR4
changes the interval between successive triggers: the cycle owner must separately
check `period_ticks + next.ccr4 - active.ccr4` against its companion ADC spacing
contract. The planner's period-based value alone cannot prove that transition.
One extra timer tick protects the
switching boundaries. No rounding or compare clipping increases requested duty.

## Synthetic example

The host fixture uses ARR=3500 (24 kHz), 200 ns MCU dead time, 2500 ns settling,
100 ns edge margin, 500 ns minimum pulse and 2000 ns for each service budget.
These are test inputs, not qualified component or system limits.

| Output for A=B=C=1750 | Value |
|---|---:|
| Realized dead time | Code 34 / 34 ticks, approximately 202.38 ns |
| Common trigger CCR4 | 3379, on upcount |
| Latest conversion completion | Tick 3621, after apex |
| Capture deadline | 24 µs |
| Conservative trigger spacing | 41 µs (actual period approximately 41.667 µs) |

For this fixture, a largest phase compare of 3027 is accepted and 3028 is
rejected because the settled interval begins too late for an upcount trigger.
This is a policy/timing-fixture boundary, not a qualified duty limit for the
56 V board. A different gate/analog/timing budget changes it.

## Evidence and runtime requirements

7380 assertions pass. A separate discrete counter model walks three PWM cycles,
applies complementary turn-on delays, observes pulse widths and low-input rises,
then searches every eligible upcount trigger for a quiet conversion. It agrees
with the planner across duty boundaries and 250 varied timing/three-phase cases.
All requested nanoseconds from 1 to 6000 exercise every DTG range. Six compiled
faulty copies are rejected: downward time rounding, ignored A edges, omitted
pulse dead time, omitted external-trigger latency, omitted IRQ service and a
changed B duty. Evidence is in `.scratch/v4-56v-implementation/negative-pwm-plan/`.

The ARM compiler lowers plan initialization to `memset`. A small freestanding
byte-fill implementation now supplies that dependency without an external libc
or CRT. Its volatile byte stores prevent recursive loop recognition and permit
unaligned normal RAM. 41120 checks cover lengths, alignments, byte values,
returned pointers and guard preservation; ARM objects have no recursive calls.
This is not a memory-mapped peripheral access API.

All 36 host tests pass. Thirteen component sources compile/combine for Cortex-M4
hard-float without unresolved dependencies; the seven C sources also compile
with ARM Clang. This proves component buildability and modeled timing properties,
not timer execution or CPU latency. Existing diagnostic images do not use the
planner; unused planning/runtime code is removed by the linker.

The following integration requirements remain the contract. The [cycle owner](v4-mono-56v-pwm-cycle.md)
now implements the preload history and timer boundary/command checks, with modeled
ADC binding. The [capture companion](v4-mono-56v-pwm-capture.md) supplies raw frames
and capture deadlines; physical output handoff and qualified current-frame
construction remain pending:

1. A deliberate GPIO-to-TIM1 and COAST-to-PWM handoff with fresh bus/driver/brake
   permission, calibrated normal inputs, retained faults and no automatic rearm.
2. A proven preload-transfer phase, atomic A/B/C/CCR4 cycle updates and a cycle
   identifier binding ADC data to the actually active compares. An update at the
   apex must not change compares during this conversion interval. RCR/UG/startup
   phasing needs explicit handling; using update TRGO can create extra events.
3. ADC arming before the planned edge, paired completion and independent deadline
   inhibition, including missed IRQs, a stopped counter and late control updates.
4. A current-frame adapter using observed active-cycle evidence and original
   sample/reference times. `plan.valid()` alone must never set
   `CurrentFrame.low_side_window_valid`.

Then integrate the actual current loop and encoder and qualify waveforms,
settling, polarity, noise, faults, thermals and regeneration on hardware.
PCB synchronization and electrical/manufacturing acceptance remain open.
