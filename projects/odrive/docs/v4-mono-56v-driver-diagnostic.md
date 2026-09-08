# Integrated DRV8353 diagnostic image, with COAST retained

## Implemented behavior

The optional driver diagnostic now links reset/startup, ADC1/DMA bus supervision,
GPIO sleep/wake, SPI3 and DRV8353 configuration in one STM32F405 ELF/BIN/HEX.
It waits for a fresh valid bus, holds all six PWM inputs LOW, makes one guarded
ENABLE request, waits for actual feedback and wake time, then writes/locks/reads
back the explicit gate profile. Successful configuration retains COAST. It
periodically checks status and the full register set; it never calls COAST
release or starts TIM1 PWM. This is a diagnostic startup path, not the complete
motor-controller firmware.

The default [bus-only image](v4-mono-56v-diagnostic-image.md) still inhibits
ENABLE permanently. Selecting the new variant requires an explicit JSON profile;
**this variant can raise driver ENABLE**, with the six PWM GPIOs held LOW.
No board has been programmed or tested physically. Bus thresholds, gate settings,
sleep/wake timing, regenerative protection and physical stop behavior remain
unqualified for the intended 56 V application.

## IRQ and foreground ownership

TIM7 and DMA2 stream 0 keep the existing same-priority serialized bus service.
`BusSupervisionResult` now carries the original acquisition trigger timestamp;
rereading a retained sample never refreshes it. A private IRQ-published permission
snapshot is read with PRIMASK saved/restored. Permission requires a healthy
result, sample age at most 250 µs and service age at most 125 µs. These match the
current diagnostic's fixed measurement/service settings; they are not general
controller defaults or a proof of analog measurement accuracy.

Foreground owns the `DriverWake` and `Drv8353` objects and all SPI transfers.
Their permission callback refreshes a separate foreground heartbeat. The bus IRQ
then checks the heartbeat, GPIO configuration/quiet outputs, brake/enable history
and qualified nFAULT history. It can directly inhibit and latch a first fault,
but never calls SPI or mutates the foreground objects. The IRQ cannot renew the
heartbeat it checks. The guarded ENABLE request rechecks bus permission with
interrupts masked, closing the previously reviewed CPU interrupt race.

A blocking configuration or full register check still permits bus IRQ service.
The wake owner checks permission before and after each SPI frame, so IRQ faults
propagate into the register session. No new transactions or ENABLE requests are
issued after the diagnostic fault latch is set. Recovery requires resetting the
image; there is no automatic retry or SWD command to clear/rearm it.

EXTI2/6/7 are armed to retain falling edges, but their NVIC vectors stay disabled.
Their pending state is polled by the existing bus IRQ and foreground callbacks.
This is not a dedicated external-fault ISR. The foreground-gap setting is detected
at a later IRQ; it is not a physical shutdown-time guarantee. If the CPU, timer
or global interrupt service stops, this software guard is not an independent
watchdog. Qualification of fault pulses, interrupt latency and gate waveforms,
plus the independent watchdog/external-stop requirements, remains open.

## Build with an explicit profile

Add `--driver-config /path/to/profile.json` to the existing diagnostic build:

```bash
python3 projects/odrive/tools/build_mono_monitor.py \
  --cmsis-root .scratch/odrive/firmware/Firmware/ThirdParty/CMSIS \
  --arm-gcc /path/to/arm-none-eabi-gcc \
  --undervoltage 10 --overvoltage 58 \
  --driver-config /path/to/profile.json
```

The 10/58 V arguments are only the build/test fixture, not qualified bus limits.
The JSON must have exactly two objects, `gate` and `timing`, with all fields:

| Object | Required positive integer fields |
|---|---|
| `gate` | `hs_source_ma`, `hs_sink_ma`, `ls_source_ma`, `ls_sink_ma`, `drive_time_ns`, `dead_time_ns`, `vds_trip_mv`, `ocp_deglitch_us`, `csa_gain`, `sense_trip_mv` |
| `timing` | `sleep_us`, `wake_us`, `feedback_timeout_us`, `max_service_gap_us`, `spi_deadline_us`, `bus_wait_timeout_us`, `register_check_period_us` |

No profile is selected automatically. Five malformed/invalid profile fixtures
(boolean gain, missing VDS field, SPI/service mismatch, narrowing overflow and
short sleep) are rejected before compilation. Exact supported gate settings are validated
by the register engine before startup can request ENABLE. The build tool checks
JSON shape/types/ranges and basic timing relations; unsupported gate encodings
within those ranges halt startup with fatal code 9. Runtime checks are retained
in addition to input validation. The generated `monitor_driver_config.h`, input
JSON, source hashes, compiler commands and artifact hashes are recorded together.

The evidence fixture is `.scratch/v4-56v-implementation/driver-monitor-fixture.json`:
150/300 mA source/sink for HS and LS, 2000 ns drive, 200 ns dead time, 200 mV VDS,
2 µs deglitch, gain 20 and 250 mV sense. Timing uses 2000 µs sleep/wake, 250 µs
feedback/service limits, 200 µs SPI deadline and 1000 µs bus wait/register-check
period. This is an encoding/integration fixture, **not a qualified motor or FET
switching profile**. Application motor/current/cooling/source requirements are
still needed to select production values.

Outputs default to `.scratch/v4-56v-implementation/driver-monitor-image/`, separate
from the bus-only output directory. The current driver image uses 10980 text,
160 initialized data and 272 BSS bytes. The bus-only image now uses 4656/108/104
bytes; its increase carries the original sample timestamp and private permission
publication. Both link without runtime libraries, undefined symbols or static
constructors and retain the existing Flash/stack/vector/DMA-memory checks.
The driver build additionally verifies that startup/SPI adapter symbols are linked
and COAST-release code is absent. This static evidence does not prove a board boot.

## Diagnostics and verification

Keep inspecting `mono56_monitor` for bus measurements and fatal startup/CPU errors.
The driver variant also exposes `mono56_driver_monitor` (magic `0x4d353647`,
version 1) with an even sequence for coherent foreground snapshots. It records
state/error, wake state/error, SPI status, register error, configured-in-COAST
status, available fault registers/failed address and completed register checks.
Publication briefly masks interrupts. An IRQ/transport failure invalidates an
unrelated old healthy register pair; a complete pair read for a device fault
remains available. Field and enum definitions are in
`firmware/mono56/monitor/driver_monitor.hpp`.

`mono56_driver_monitor_fault` is a separate live first-fault word. Read it as well
as the snapshot: a stalled or fatal foreground can leave an old snapshot behind.
Neither a cached `configured_coasted` field nor a healthy historical register pair
is proof of current permission when this latch or the base fatal code is nonzero.

All 16 registered host tests pass. Nine integration scenarios contribute 2592
assertions across separate runs: healthy startup, bus OV, missing SPI receive,
recovered nFAULT pulse, brake loss, COAST register drift, foreground stall, stale
bus publication and missing first conversion. They use the real production
components with one shared simulated peripheral set and interleave ADC/timer
IRQs during SPI transfers. The previous component tests also pass, including
new checks that only a completed new acquisition advances the sample timestamp.
Five compile-valid faulty integration copies are rejected for lost healthy ENABLE,
missing IRQ guard, missing register monitoring, stale permission and ignored
nFAULT IRQ handling.

Evidence lives in `firmware-components/`, `driver-monitor-image/`, `monitor-image/`
and `negative-driver-monitor/` under `.scratch/v4-56v-implementation/`. No physical
SPI, gate switching, current calibration, encoder/FOC or regenerative/thermal
validation is claimed. Those remain part of the
[full controller acceptance](v4-mono-56v-implementation.md).

The optional [current-zero diagnostic](v4-mono-56v-current-diagnostic.md) adds
manual calibration via `--current-config`, with its own image and ADC/TIM5
IRQ ownership. The driver-only mode described here does not perform calibration.
