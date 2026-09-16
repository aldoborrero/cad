# Mono 56 V continuous PWM cycle ownership

## Implemented scope

`firmware/mono56/include/pwm_cycle.hpp` and `src/pwm_cycle.cpp` own a continuously
running TIM1 counter, its four compare preloads, cycle history and an independent
TIM5 compare-2 watchdog. They consume the [sampling planner](v4-mono-56v-pwm-sampling.md)
and notify a required consumer at each verified cycle start. The host integration
uses the production ADC2/3 acquisition driver to arm and retrieve synthetic B/C
conversions triggered by modeled OC4REF edges.

This stage deliberately keeps CCER/MOE/AOE zero and all six PWM pins GPIO LOW.
It neither releases driver COAST nor proves low-side conduction. An observation's
`valid` flag establishes timer history only; it must never directly set
`CurrentFrame.low_side_window_valid`. The existing diagnostic images do not call
this module, and their TIM1 update vector still uses the default handler.
No device was programmed and no CAD source changed.

## Preload and trigger sequence

The timer contract is fixed: TIM1 168 MHz, PSC=CKD=0, center-aligned mode 2,
ARPE/URS enabled, RCR=0, PWM1 with preloads on channels 1–3, PWM2 with preload on
channel 4 and OC4REF selected as TRGO. Internal OC4REF supplies one rising trigger
on the upcount. Compare readback returns preload values; software must retain the
history of what actually transferred into active registers.

Both apex and underflow update events are serviced. During upcount, the next
A/B/C/CCR4 command stays in software. At apex, the unchanged preloads transfer;
only afterward may the next four values be written. They become active together
at underflow, which advances the cycle identifier. Thus an ADC conversion spanning
apex sees unchanged active compares even when the next command is already staged.
A command arriving just after apex can commit immediately on downcount.

The four-register write masks interrupts and sets UDIS to prevent a hardware
transfer partway through the write. It checks direction, remaining count, elapsed
TIM1/TIM5 time and readback before restoring updates. Crossing a suppressed edge
or exceeding the explicit commit budget faults the owner; it never fabricates a
successful next cycle. These preload, UDIS and master-trigger semantics follow
[ST RM0090, advanced-control timers](https://www.st.com/resource/en/reference_manual/rm0090-stm32f407-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).

Initialization requires unused TIM1/TIM5 interrupt ownership, inactive TIM10 on
the shared update vector, quiet GPIO outputs and unarmed external ADC triggers.
The initial UG transfers compares with ADC triggering idle. ADCs are armed by the
cycle-start callback after the counter starts and before the scheduled edge.
The callback is nonreentrant, nonblocking and IRQ masked. Its complete duration
must fit the explicit underflow-to-arm budget. Pending update flags and independent
elapsed time prevent a whole-cycle delay from aliasing to a small counter value.

## Timing and fault contract

Each observation carries the active plan, cycle number, unrolled phase and the
original quantized lower/upper underflow bounds. An observation checks that its
counter phase intersects elapsed TIM5 time and that no boundary occurred during
the copy. It does not claim exact individual ADC sample instants.

Constant PWM frequency alone does not guarantee constant trigger spacing when
CCR4 changes. Every transition checks:

```
actual trigger gap in TIM1 ticks = period_ticks + next.ccr4 - active.ccr4
floor(actual gap / 168) >= companion min_trigger_spacing_us
```

The configured ADC deadline and minimum spacing are the same values required by
the companion acquisition owner. Each plan must fit that deadline, and the ADC
contract requires `deadline_us + 1 < min_trigger_spacing_us`. A valid individual
plan can still be rejected as an invalid transition. Commands are never clipped,
repeated automatically or replaced by a second command for the same generation.

TIM5 must already be running freely at 1 MHz. Compare 2 detects a missing timer
boundary and, after apex, a missing command before the next underflow. Compare 1
is reserved for the future companion ADC capture deadline. TIM1 update and TIM5
use priority 1 with grouping 3. The companion must share the TIM5 dispatcher and
priority, not initialize the same interrupt independently.

The required permission callback checks fresh bus/driver/brake/session permission
without SPI and without renewing its own heartbeat. Register/phase drift, lost
permission, missed boundaries, missing/duplicate/stale commands, late commits,
invalid trigger spacing or consumer failure retain the first error, lower PB12,
clear MOE/AOE, stop TIM1 and disable owned update/watchdog service. Recovery needs
explicit shutdown; a successful later permission check cannot restart the timer.
The companion remains responsible for shutting down its ADC ownership on failure.
TIM5 continues to serve the bus timebase.

These checks assume exclusive peripheral ownership, fixed board clocks and a
functioning CPU/TIM5. They do not replace an independent hardware watchdog or
measure interrupt execution time. The fixture's 1 µs boundary/commit budgets,
2 µs arm budget and 30/32 µs ADC deadline/spacing are synthetic test inputs;
feasible CPU latency and analog settling require measurement and qualification.

## Evidence and remaining integration

6341 assertions pass in a discrete 168 MHz timer model with separate active and
preload registers, update suppression, quantized independent TIM5 time, actual
ADC2/3 register acquisition, 242-tick conversions and interleaved interrupt service.
The healthy sequence spans twelve complete cycles, checks active compares on every
conversion tick and preserves the ADC1/DMA reference configuration. Cases include
microsecond-clock wrap, missed service, stopped/reset counter, late callbacks and
writes, a boundary during observation, pending-apex recovery, wrong generation,
duplicate commands, changed priorities/registers and conflicting ownership.

Seven deliberately faulty copies compile and fail: omitted UDIS, publishing
preloads as active, omitted variable-trigger-spacing checks, ignored watchdog
expiry, weakened elapsed-phase checks, accepting duplicate commands and omitted
commit budget. Their evidence and source/object hashes are under
`.scratch/v4-56v-implementation/negative-pwm-cycle/`.

All 37 host tests pass; fourteen production components compile/combine for
Cortex-M4 hard-float without unresolved symbols, and the seven C components also
compile with Clang. The bus, driver and current-zero diagnostic images rebuild
with static vector/memory checks. Unused cycle-owner code is discarded by the
linker; these images do not exercise continuous TIM1 on hardware.

A [production capture companion](v4-mono-56v-pwm-capture.md) now owns per-cycle
ADC deadlines, rejects partial/late pairs and supplies single-delivery raw frames
with original active-cycle/arm/completion bounds. Next is qualified current-frame
construction with coherent supply timestamps, explicit calibration-to-running
handoff and running-driver permission/output transition.
The existing stopped-TIM1 capture shutdown lowers ENABLE, and DriverWake requires
a stopped timer; neither can be reused unchanged for that transition.
Controller/encoder operation, electrical limits, PCB synchronization, manufacturing
and bench acceptance remain requirements of the full mono 56 V controller.
