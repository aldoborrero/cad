# Mono 56 V current-zero diagnostic

## Scope and acceptance

The optional `--current-config` image connects the existing bus supervision,
driver wake/SPI session, ADC2/ADC3 capture and software zero estimator. It runs
one verified manual B/C calibration, restores normal amplifier inputs and keeps
monitoring the bus and driver with COAST retained and all six PWM GPIOs LOW.
This diagnostic integration is implemented and tested with simulated peripherals.
No image has been flashed and no physical current accuracy or timing is qualified.

The source is `firmware/mono56/monitor/current_monitor.cpp`, with trigger/deadline
ownership in `src/current_capture.c`. The [acquisition contract](v4-mono-56v-current-acquisition.md)
and [phase-current scaling](v4-mono-56v-phase-current.md) remain applicable.
The schematic uses 1 mΩ shunts and SOB=B/PC0, SOC=C/PC1. This diagnostic rejects
other shunt values; gain comes from the same explicit DRV8353 profile.

## Trigger, IRQ and permission ownership

TIM1 stays stopped: CEN, DIER, CCER, MOE and AOE remain clear. Its update TRGO
source produces exactly one common trigger from each software UG event, after
both injected paths are armed. This is not two separate ADC software starts.
The capture owner validates timer/ADC/NVIC ownership and configuration, checks
permission again immediately before the event, and enforces minimum spacing
from after the previous actual UG write.

TIM5 remains the existing 1 MHz free-running clock. Its compare 1 channel now
enforces the capture deadline without waiting for foreground service. ADC and
TIM5 vectors dispatch to the capture service at priority 1, serialized with each
other and above the priority-2 bus TIM7/DMA handlers. Only ADC2/3 use the shared
ADC vector in this diagnostic; an ADC1 interrupt owner is rejected.

Permission checks fresh bus data, the qualified wake/fault history, live ENABLE
and brake feedback, quiet PWM GPIOs and the foreground heartbeat. Capture IRQs
perform no SPI and cannot renew that heartbeat. Any capture fault immediately
inhibits PB12/TIM1; the IRQ wrapper also records the driver diagnostic's first
fault. Missing ADC service therefore cannot silently hold ENABLE indefinitely.

The bus publisher masks interrupts while updating its private readiness,
timestamps and VDDA fields. `mono56_monitor_supply()` reads those fields as one
coherent snapshot and preserves the original ADC1 acquisition timestamp. Reader
masking alone was insufficient: a priority-1 IRQ could otherwise preempt a
priority-2 publisher halfway through its update.

## Calibration sequence and time bounds

1. Complete bus supervision, qualified driver wake and locked COAST configuration.
2. Initialize the capture owner; enter verified manual CSA_CAL_B/C through SPI.
3. Start the requested settling interval after the complete verified transition.
4. Before each capture, check all driver configuration/status registers. There
   is no foreground SPI transaction while a capture or unread mailbox is pending.
5. Collect a paired ADC result through the IRQ mailbox, read coherent live VDDA,
   and reject stale, clipped, noisy, uncorrelated or malformed data. Collection
   also has an overall timeout, including intervals with no delivered frames.
6. On a valid estimate, restore normal B/C inputs through the verified SPI
   transition before reporting completion. Do not call capture shutdown first:
   it lowers ENABLE and would prevent those restoration writes.

The capture owner remains allocated and idle after completion. Driver and bus
monitoring continue; there is no automatic recalibration or recovery/rearm.
The driver session is fixed to 1 because this image only supports reset entry
and one wake session. It does not transfer the zero into an active motor axis.

The component now offers an explicit idle-only
[release and timing handoff](v4-mono-56v-timing-handoff.md) that preserves ENABLE.
The optional [timing diagnostic](v4-mono-56v-timing-diagnostic.md) calls it with
corresponding guard, vector and scheduling ownership changes. Without that
additional profile, this current-zero image retains its stopped final state.

ADC bounds are quantized `armed_at_us` and `observed_complete_at_us`, not exact
per-channel sampling instants. The adapter uses the earliest bound for freshness
and separately requires the whole interval width, including one microsecond of
quantization, to fit the pair-skew limit. The distance from the VDDA timestamp
to the earliest current bound plus that width must fit the supply-skew limit.
It adds `capture_deadline_us + 1` to the zero estimator's minimum span, so an
uncertain first/last sampling instant cannot masquerade as a sufficiently long
physical observation interval. Neither dispatch nor SPI restoration refreshes
the original capture, supply or zero-completion timestamps.

## Explicit build profile

Supply `--driver-config` as described in the
[driver diagnostic](v4-mono-56v-driver-diagnostic.md), and add `--current-config`.
The current file requires exactly the following integer fields. This example
is the synthetic test fixture, **not a qualified 56 V electrical profile**:

```json
{
  "current": {
    "shunt_b_uohm": 1000,
    "shunt_c_uohm": 1000,
    "polarity_b": 1,
    "polarity_c": 1,
    "max_age_us": 250,
    "max_pair_skew_us": 25,
    "max_supply_skew_us": 250,
    "max_zero_age_us": 1000000,
    "vdda_min_mv": 3000,
    "vdda_max_mv": 3600,
    "rail_margin_mv": 300,
    "max_abs_phase_current_ma": 40000,
    "max_zero_offset_codes": 16,
    "max_calibration_supply_change_mv": 50
  },
  "zero": {
    "samples": 8,
    "settle_us": 100,
    "min_span_us": 6900,
    "timeout_us": 30000,
    "max_peak_to_peak_codes": 4
  },
  "capture": {"period_us": 1000, "deadline_us": 10}
}
```

```bash
python3 projects/odrive/tools/build_mono_monitor.py \
  --cmsis-root .scratch/odrive/firmware/Firmware/ThirdParty/CMSIS \
  --arm-gcc /path/to/arm-none-eabi-gcc \
  --undervoltage 10 --overvoltage 58 \
  --driver-config /path/to/driver-profile.json \
  --current-config /path/to/current-profile.json
```

The default output directory is `.scratch/v4-56v-implementation/current-monitor-image/`.
ELF/BIN/HEX and `validation.json` include source/artifact hashes and both profiles.
Static checks verify the ADC/TIM5 vectors, linked calibration transitions,
Thumb/hard-float attributes and SRAM/Flash limits, and reject linked COAST release.
The fixture image uses 17992 text / 320 data / 532 BSS bytes. Its nominal 1 ms
period is a minimum trigger spacing; foreground SPI/check scheduling can extend
it. It is not a PWM sampling frequency or a real-time performance measurement.

## SWD and verification limits

`mono56_current_monitor` has magic `0x4d353643` (M56C), version 1 and an even/odd
sequence counter. Read matching even sequences around the snapshot. It reports
state/error, capture/ADC/estimator errors, sample count, last B/C raw values,
original capture and VDDA timestamps, VDDA, separate zero codes and completion
time. `calibration_completed` is a diagnostic result, not permission for PWM.

Always inspect the live `mono56_driver_monitor_fault` and the bus diagnostic's
`fatal_code` too. An IRQ/fatal fault can inhibit before the foreground updates
the current snapshot. A previously completed report is not evidence of a live,
healthy driver session. The foreground invalidates completion when it resumes.

The integration test shares one GPIO/ADC/DMA/TIM/SPI register model across the
production owners. It simulates common UG-triggered conversion, paired ADC IRQs,
compare deadlines, bus DMA and SPI traffic. Fifteen scenarios / 8687 assertions cover completion,
missing B/C, lost ADC service, noise, CSA drift, ignored input restoration, VDDA
drift, overall timeout, stale consumption, supply skew, wrong shunt scaling,
foreground stall, uncertain calibration span and a post-completion bus fault.
All 34 host tests pass; eleven component sources compile/combine for ARM and
six C sources also compile with ARM Clang. The linked image validates the
production monitor paths separately from the component objects.

The stopped-trigger component has 144 simulated assertions; atomic bus
publication/access has 51. Six faulty capture copies and a publisher without
IRQ masking are rejected. Six faulty current diagnostic copies compile and fail; nine invalid profiles
are rejected before compilation. Their evidence is kept in `.scratch/v4-56v-implementation/negative-current-monitor/`
and `negative-current-profiles/`. These are software checks, not hardware tests.

Next work is the normal current-sampling window tied to actual PWM conduction,
followed by controller/encoder integration. ADC/analog settling, actual IRQ
latency, current polarity and accuracy still require bench measurements. PCB
synchronization and power/Kelvin/thermal review, electrical limits, regeneration,
manufacturing outputs and physical motor/fault tests remain required before the
56 V controller is functional.
