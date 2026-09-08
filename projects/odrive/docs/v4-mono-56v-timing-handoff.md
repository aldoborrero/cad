# Mono 56 V calibration-to-timing handoff

## Implemented behavior

The stopped-capture owner can now release its peripherals without lowering ENABLE.
`mono56_current_capture_release()` requires an owned, idle capture with no unread
frame and fresh external permission. It releases TIM5 compare 1, the ADC/TIM5
vectors, stopped TIM1 TRGO and ADC2/3, while preserving TIM5 time and ADC1/DMA.
Permission and peripheral readback are checked again after teardown. Failure
retains a reason and inhibits; success returns the old owner to uninitialized.
Duplicate release, a pending conversion or an unread pair cannot succeed.

`DriverWake::begin_timing()` preserves the existing ENABLE edge and retained
feedback history. It requires the same wake owner's driver callbacks, a configured
COAST session, restored normal CSA inputs and a fresh full register verification.
The old stopped-capture TRGO must already be released. This is a foreground
operation with interrupts enabled; it publishes the new mode under an IRQ mask.

Timing mode allows internal TIM1 counting/interrupts while all six PWM pins remain
GPIO LOW and CCER/MOE/AOE remain clear. It does not release COAST, authorize power
switching, transfer a current zero or establish a valid shunt conduction window.

## Permission and integration contract

The timing permission callback must be IRQ safe, nonblocking and check fresh
bus/session/fault state without SPI or heartbeat renewal. It is distinct from the
startup callback, which may feed the foreground monitor's heartbeat.
`timing_permitted()` checks this callback, the foreground service interval, GPIO
configuration, actual ENABLE/brake/nFAULT levels and retained falling edges. It
preserves a caller's IRQ mask and never extends the foreground service interval.
`update()` and the normal SPI permission callback renew that interval only from
thread mode. `begin()`, `begin_timing()` and `update()` reject exception context
using IPSR, including when PRIMASK is clear.

The intended caller sequence is:

1. Consume the final stopped calibration frame and verify normal CSA restoration
   through the existing driver session.
2. Release the idle stopped-capture owner while retaining the qualified session.
3. Enter DriverWake timing mode with a separate nonrenewing permission callback.
4. Initialize continuous capture, observe ADC stabilization, then start internal
   timing and service the TIM1/ADC/TIM5 vector wrappers.
5. Consume every frame and queue its successor within the cycle's deadlines,
   while separately servicing foreground progress and retained faults.

After successful release, do not call the old capture shutdown while the new owner
is active: shutdown intentionally inhibits the motor. Normal-input restoration
and zero/session validity remain the caller's responsibility.

The optional [timing diagnostic](v4-mono-56v-timing-diagnostic.md) now implements
this sequence, including mode-specific IRQ routing and frame/next-command service
during foreground SPI transactions. The original current-zero image still ends
with stopped capture owned and idle. Qualified output/current-control handoff
remains separate.

## Evidence and remaining work

The counts and three-image sizes below record the component milestone before
the optional timing diagnostic. See its linked report for current integrated
image evidence and remaining controller/output work.

The host suites pass 176 stopped-capture, 911 GPIO/wake and 7809 continuous-capture
assertions. Tests cover final-frame consumption/release, unchanged ENABLE, real
peripheral transfer to three continuous cycles, register/gain drift, alternate
IO binding, active calibration, retained fault edges, foreground starvation and
interrupt misuse. Driver/SPI-session and timer/ADC-transfer models are separate;
this is not an executable end-to-end firmware test.

Eleven deliberately faulty handoff/release copies compile and fail the tests:
IRQ lease renewal, ignored live PWM state or ENABLE history, active manual CSA
shorts, omitted register verification or callback binding, foreground update from
an IRQ, bypassed thread-mode handoff checks, ENABLE inhibition on successful
release, unread-frame release and ignored post-release permission. The eight
startup-wake, six stopped-capture and seven continuous-capture faulty copies also
remain rejected. Bypassing only the initial handoff IPSR check is insufficient to
admit an IRQ: the nested foreground permission/update check rejects it too.

All 38 host tests and fifteen ARM components pass the component checker. Seven C
components also compile with ARM Clang. Rebuilt diagnostic image text/data/BSS
sizes are 4656/108/104 (bus), 11628/160/280 (driver) and 18640/320/540 (current).
No image starts continuous timing or motor PWM. Build profiles remain unqualified
fixtures, and no device was programmed.

Evidence is under `.scratch/v4-56v-implementation/`: `timing-handoff-check.log`,
`negative-timing-handoff/`, `negative-driver-wake/`, `negative-capture/`,
`negative-pwm-capture/` and the three diagnostic image directories. The next work
is executable scheduling/IRQ handoff and a coherent current-frame adapter, then
qualified output handoff, current control and encoder integration. Electrical,
PCB, manufacturing and bench acceptance remain open.
