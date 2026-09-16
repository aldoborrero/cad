# Mono 56 V continuous PWM current capture

## Implemented scope

`firmware/mono56/include/pwm_capture.hpp` and `src/pwm_capture.cpp` connect the
[continuous TIM1 cycle owner](v4-mono-56v-pwm-cycle.md) to the production ADC2/3
acquisition driver. Each verified underflow arms a B/C pair and a TIM5 compare-1
capture deadline. ADC interrupt service binds completed raw data to the observed
active cycle and publishes one frame for the controller to consume.

The code compiles for STM32F405 and is exercised with modeled timer/ADC hardware.
The optional [timing diagnostic](v4-mono-56v-timing-diagnostic.md) now calls it after
zero calibration and verified driver/peripheral handoff. The prior bus, COAST-only
driver and stopped-TIM1 current-zero modes remain available. No device was programmed.
PWM GPIOs, CCER/MOE/AOE and the physical output handoff remain under the inhibited
cycle owner's contract. A valid capture establishes raw data and cycle timing;
it does not establish low-side conduction or authorize current control.

## Ownership and sequence

The capture owner initializes the cycle engine, ADC2/3 and the shared ADC vector.
It requires exclusive ownership and rejects an active ADC1 interrupt user; ADC1
continues to use its DMA bus/reference acquisition. TIM1 update, ADC and TIM5
service are serialized at priority 1 with priority grouping 3. The three vector
wrappers are `pwm_capture_update_irq`, `pwm_capture_adc_irq` and
`pwm_capture_deadline_irq`. The latter dispatches both TIM5 compare channels.

The cycle owner retains compare 2 for timer-boundary/command deadlines. Capture
uses compare 1, modifying only its own interrupt-enable/flag bits. It never
reinitializes TIM5 or resets its free-running 1 MHz counter. Both owners retain
first errors; capture failure aborts the cycle engine without resetting its
fault/history, inhibits PB12/MOE/AOE, disables owned ADC interrupt service and
shuts down ADC2/3. Explicit shutdown also releases a failed initialization attempt
without disabling a foreign ADC vector or changing the bus timebase.

Initialization enters `warming`. An early start returns false without a fault
until the ADC stabilization interval has elapsed. One successful start arms cycle
zero. Later underflows require the previous pair to have been consumed and the
cycle number to advance exactly once. A pending or unread pair faults before
another acquisition can overwrite it. There is no implicit retry or automatic
holding of an old PWM command.

The external permission callback remains required, nonblocking and IRQ safe. It
must check live bus/driver/brake/session state and cannot renew its own heartbeat.
It performs no SPI. The [DriverWake timing handoff](v4-mono-56v-timing-handoff.md)
now permits internal TIM1 operation with PWM pins inhibited. The executable
driver monitor still needs corresponding guard/scheduler/vector integration.

## Deadline, data and delivery contract

The independent capture deadline is based on the original conservative underflow
bound: `began_lower_us + adc_deadline_us + 1`. The added microsecond represents
the first counter value that is definitely past the inclusive deadline. The
configured deadline includes arming, wait for the planned edge, conversion, data
reads and verification. Timer spacing is checked by the cycle owner, including
changes to CCR4 between cycles.

Every pending-operation permission check also enforces capture expiry. An incoming
command cannot bypass a timeout when interrupt delivery has been lost. ADC service
checks both channels through the acquisition driver; one completed channel is
masked while waiting for its partner. Expiry never salvages late JEOC flags.
Polling can recover a complete pair only before its deadline.

After both ADC values have been read, the owner verifies the current active cycle
and original underflow bounds again, rejects completion before the planned trigger
phase, and checks expiry after that verification. It preserves `armed_at_us` and
`observed_complete_at_us`; these are conservative bounds, not separately measured
B/C sample instants. The completed pair cancels only compare 1, preserving the
cycle watchdog. Its mailbox is delivered once. A final cycle check after copying
the mailbox rejects an underflow during delivery and leaves the caller's top-level
`valid` false. An unread frame cannot silently become the next cycle's frame.

`PwmCaptureFrame.valid`, its ADC validity and its cycle validity are all necessary
inputs to the later current-frame adapter. None may directly set
`CurrentFrame.low_side_window_valid`. That adapter must also associate coherent
VDDA and original supply time, qualified driver session/zero/gain and observed
normal-input/output-window evidence. Current conversion/limits and the controller
must reject invalid frames rather than reuse previous current readings.

## Validation and limits

7809 capture assertions pass, including stopped-owner release and three subsequent
continuous cycles without lowering ENABLE. The healthy run acquires twelve consecutive pairs
and submits varying next-cycle commands using the returned generation. The shared
hardware model has distinct active and preload registers, actual ADC2/3 register
acquisition, 242-tick conversions, quantized TIM5 time and interleaved IRQ service.
It also runs the existing 6341 cycle-owner assertions without changing their result.
The model is shared in `tests/pwm_timer_test_model.hpp` to keep the same hardware
semantics for the component and combined-capture suites.

Capture cases cover missing B, missing C, both missing, lost ADC/deadline IRQs,
permission loss, stopped timer, changed capture/ADC registers, wrong generation,
premature completion, unread/duplicate delivery, failed initialization cleanup,
foreign ADC interrupt ownership, microsecond-clock wrap and preservation of an
already masked caller. Delayed barriers exercise expiry during post-read
verification and an underflow during mailbox copying.

Seven compiled faulty capture owners fail: ignored expiry, swapped phase data,
refreshed arming timestamp, overwritten unread frame, accepted pre-trigger data,
omitted final delivery-boundary check and omitted post-read expiry check. The
seven earlier faulty cycle owners are also rejected with the shared model.
Evidence and hashes are under `.scratch/v4-56v-implementation/negative-pwm-capture/`
and `negative-pwm-cycle/`.

The initial ARM link exposed a compiler-generated `memcpy` dependency for capture
structures. The freestanding memory implementation now provides nonoverlapping
byte copy as well as byte fill. Volatile byte accesses support unaligned normal
RAM without recursive compiler loop replacement. 106912 guard/source-preservation,
length, value and independent-alignment checks pass. GCC and Clang ARM disassembly
contains both functions without branch-link calls; this is not a latency result.

All 38 host tests pass and fifteen production component sources compile/combine
for Cortex-M4 hard-float without unresolved symbols. Seven C components also
compile with ARM Clang. All three existing diagnostic images rebuild and pass
static vector/memory checks; unused capture/cycle code is discarded. There is no
measurement of CPU interrupt latency, analog accuracy or gate timing. The test
profiles are unqualified fixtures, not selected 56 V operating limits.

Next is the explicit calibration-to-running handoff and the driver/output evidence
needed to construct qualified current frames with coherent VDDA. Then connect the
current loop and encoder to the executable firmware. Electrical/thermal/regenerative
limits, PCB synchronization, manufacturing and bench acceptance remain requirements
of the full mono 56 V controller.
