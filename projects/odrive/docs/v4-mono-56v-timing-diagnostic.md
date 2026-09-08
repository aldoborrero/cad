# Mono 56 V calibrated internal-timing diagnostic

## Implemented image

`build_mono_monitor.py --timing-config <profile.json>` adds a fourth explicit mode,
requiring driver and current profiles. It completes manual B/C zero calibration,
restores normal CSA inputs, releases stopped capture without lowering ENABLE,
verifies the same driver session and starts continuous internal TIM1/ADC2/3 capture.
COAST remains locked, all six PWM pins remain GPIO LOW and CCER/MOE/AOE remain clear.
It does not drive the motor, prove shunt conduction, convert raw samples into
phase-current permissions or implement current control. No board was programmed.

## Scheduling and faults

DriverMonitor publishes timing IRQ routing before enabling the new capture owner.
ADC, TIM1 update and TIM5 vectors then dispatch continuous capture; prior current-zero
mode retains stopped-capture dispatch. Vector 41 points to
`TIM1_UP_TIM10_IRQHandler` only in timing mode.

Capture IRQs consume one paired frame, obtain coherent VDDA with its original
timestamp, check capture age/skew, supply correlation and the preserved zero's
age/session/gain/supply agreement, then queue the fixed next-cycle compares. This
continues during foreground SPI transactions. A foreground-only consumer would
miss cycle deadlines during those transactions. The foreground services DriverWake
and verifies driver registers. Register drift is detected by those scheduled SPI
checks; software cannot instantly observe an unreported hardware register change.

IRQ permission calls DriverWake's nonrenewing timing guard with a separate fresh-bus
callback. Current IRQs cannot disguise stalled foreground progress. On any retained
capture, bus, driver or scheduler fault, `pwm_capture_abort()` inhibits ENABLE,
retains capture/cycle errors, disables owned ADC/TIM1/TIM5 interrupt service and
closes ADC2/3. This prevents a faulted handler repeatedly entering with uncleared
JEOC flags. Recovered levels cannot restart the reset-only session. ADC1/DMA and
the TIM5 timebase remain available for supervision and diagnostics.

## Profile and SWD data

The profile requires exactly these objects. This is the synthetic fixture,
**not qualified 56 V operating or latency settings**:

```json
{
  "sampling": {
    "half_period_ticks": 3500,
    "dead_time_ns": 200,
    "low_side_settle_ns": 2500,
    "edge_margin_ns": 100,
    "min_input_pulse_ns": 500,
    "arm_budget_ns": 2000,
    "completion_service_ns": 2000
  },
  "timing": {
    "boundary_budget_ns": 1000,
    "commit_budget_ns": 1000,
    "adc_deadline_us": 30,
    "min_trigger_spacing_us": 32
  },
  "compares": {"a": 1200, "b": 1500, "c": 1900}
}
```

The builder checks fields, integer ranges, compare bounds and capture spacing.
Production planner/capture initialization additionally rejects infeasible plans
before starting TIM1. JSON validation does not prove real CPU or analog budgets.

`mono56_timing_monitor` uses magic `M56T`, version 1 and an even sequence after
publication. It exposes state/first error, capture/cycle errors, sample count and
cycle generation, B/C raw codes, original arm/completion and VDDA timestamps,
preserved zero codes/time and driver session. `frame_valid` describes the last
coherent raw diagnostic record. Check original timestamps and sample count:
`observed_at_us` may advance without a new sample. Also inspect the live
`mono56_driver_monitor_fault` and bus fatal state; an older snapshot can outlive
foreground progress. No diagnostic record grants motor permission.

## Evidence and next work

Fourteen integrated scenarios pass 20056 assertions, including 195 healthy normal
captures after eight calibration samples. The model uses the real monitor, SPI,
ADC and timer-owner code; it tracks active preloads, 168 MHz timer ticks, quantized
microsecond observations and a 242-tick conversion. New records are checked against
the hardware cycle/trigger bounds, with bus/SPI progress, one ENABLE session and
preserved calibration. The model does not measure CPU instruction/interrupt cost,
analog settling or gate-driver behavior.

Cases include missing B/C, lost ADC/update IRQ service, nFAULT/brake history, bus
OV, gain drift, stalled foreground, supply skew/drift, stale bus data and expired
zero. Seven compiled faulty integrations fail: omitted IRQ consumption or next
command, refreshed zero time, ignored zero age or supply correlation, incomplete
interrupt shutdown and wrong ADC routing. Eight invalid profile/dependency cases
fail before compilation.

All 52 host tests pass. Fifteen components compile/combine for ARM and seven C
sources also compile with ARM Clang. All four images pass static vector/memory/link
checks. Timing text/data/BSS is 29316/704/864 bytes. Evidence and source hashes are
under `.scratch/v4-56v-implementation/firmware-components/`, `timing-monitor-image/`,
`negative-timing-monitor/` and `negative-timing-profiles/`.

Qualified current-frame/output handoff, current control, encoder and physical
timing/analog validation remain next. The PCB still predates schematic corrections;
electrical, manufacturing and bench acceptance remain open. See
[the full requirements](v4-mono-56v-implementation.md).
