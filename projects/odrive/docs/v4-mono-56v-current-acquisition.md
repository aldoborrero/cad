# Mono 56 V ADC2/ADC3 current acquisition

## Implemented scope

`firmware/mono56/include/adc23_acquisition.h` and `src/adc23_acquisition.c` now
own a bounded B/C acquisition through the STM32F405 injected ADC sequencers.
ADC2 reads PC0/channel 10 and ADC3 reads PC1/channel 11, following the checked
[schematic current paths](v4-mono-56v-phase-current.md). Both accept a rising
TIM1_TRGO event in independent mode; ADC1 remains available for bus/reference DMA.

The peripheral driver is implemented and ARM compiled. TIM1 trigger generation,
shared ADC vector dispatch, calibration scheduling, valid PWM sampling windows
and the full controller integration are not implemented by this component.
The optional [current-zero diagnostic](v4-mono-56v-current-diagnostic.md) now
provides stopped-TIM1 triggers, ADC/TIM5 IRQ/deadline service and manual zero
calibration around this component. Simulated events do not qualify physical
ADC alignment, analog settling or current accuracy.

## Peripheral configuration and ownership

The fixed configuration uses PCLK2=84 MHz with shared ADC prescaler /4 (21 MHz),
12-bit right-aligned results, one injected conversion, 15 sampling cycles and
zero hardware offsets. JL=0 selects the channel in JSQ4 and returns the result in
JDR1. JAUTO, regular conversion triggers, continuous conversion and multimode
are disabled. TIM1_TRGO is JEXTSEL=1 with rising-edge JEXTEN=1. These encodings
are checked against local ST CMSIS/HAL and
[ST's ADC extension definitions](https://github.com/STMicroelectronics/stm32f4xx-hal-driver/blob/master/Inc/stm32f4xx_hal_adc_ex.h).

Initialization rejects ADC2/3 already enabled or interrupt-owned, common
multimode/DMA settings, and a prescaler incompatible with an active ADC1. It
preserves ADC1, DMA2, reference enables and other PC GPIO settings. It configures
only PC0/PC1 as analog without pulls and allows at least 10 µs stabilization
after both ADCs are enabled. No shared peripheral reset is used.

JEOC and JSTRT are software-cleared status flags, whereas the regular EOC flag
can also clear on a DR read. The implementation explicitly clears only its owned
ADC2/3 flags. See [RM0090 section 13.13.1](https://www.st.com.cn/resource/en/reference_manual/rm0090-stm32f405415-stm32f407417-stm32f427437-and-stm32f429439-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).
The full manual download failed (HTTP/2 reset, then HTTP/1.1 timeout); the register
review used indexed manufacturer sections and local ST headers/HAL source.

## Capture and timing contract

1. The board initializes the acquisition before motor operation, with an
   explicit monotonic microsecond clock, deadline and guaranteed minimum trigger
   spacing. All calls use one serialized execution owner. This module neither
   installs nor changes NVIC vectors or interrupt priorities.
2. `mono56_adc23_arm()` enables both injected trigger paths and JEOC interrupts
   before the next common event. Its timestamp is recorded before enabling either
   ADC; it preserves the caller's IRQ mask during setup. It does not start a
   timer, issue a software conversion or generate a TRGO event.
3. The TIM1 owner supplies the next trigger within the capture deadline. The
   same source reaches both ADCs. An event between their two enable writes can
   miss one ADC; the driver must then time out, not combine a later partner.
4. `mono56_adc23_take()` waits for both JEOC/JSTRT pairs. If one ADC completes
   first, it disables that channel's JEOC interrupt and external trigger while
   leaving its data unread. The other channel can still interrupt. This prevents
   the first channel from continuously asserting the shared ADC interrupt.
5. Once both finish, the driver closes both trigger paths, checks flags, reads
   both JDR1 registers, and rechecks time/configuration/status before publishing.
   It clears its flags and returns to idle. Every other return clears `out.valid`;
   a pair is delivered only once.

`deadline_us` must be at least 3 µs, and `deadline_us + 1` must be strictly less
than `min_trigger_spacing_us`. The extra microsecond accounts for timestamp
quantization. The deadline covers time from arming to trigger, conversion,
interrupt latency and data observation. It is checked after setup and before
and after result reads. The fixture uses 10 µs and 40 µs respectively; these
values are not a qualified PWM schedule.

The **timer owner must establish the minimum spacing** from actual TIM1
configuration and event generation, including software updates and reset events.
This component does not measure spacing or validate timer configuration. Its
coherency argument depends on there being no second trigger before the capture
expires. It must not be used with an unchecked timer cadence or an arbitrary
software-trigger stream. A normal counter wrap is supported; backward time is
rejected. A stopped clock needs an independent system watchdog/service mechanism.

Returned `armed_at_us` and `observed_complete_at_us` describe the quantized capture
interval, not individually measured B/C acquisition instants. The acquisition
owner must preserve these bounds when adapting to current conversion/calibration;
it must not invent exact matching timestamps or infer zero skew from one shared
software timestamp. Fine ADC alignment and the low-side conduction/settling
window require timer integration and physical qualification. Minimum calibration
span must account for uncertainty within the capture interval.

## Failure behavior

Configuration changes to channel, gain-related ADC data format/offset, sample
time, trigger route, interrupts, common mode/clock or GPIO mode invalidate the
capture. Missing, late or malformed completion, unexpected regular/overrun/
watchdog flags, and values outside 12-bit range also fail. The first acquisition
fault remains retained until explicit shutdown. Shutdown disables only ADC2/3
and their interrupts; ADC1/DMA/reference operation remains intact.

This component does not inhibit the motor itself. The acquisition/axis owner
must inhibit on failure and enforce the deadline even if the ADC IRQ never
arrives. `take()` performs no blocking wait. The shared ADC IRQ dispatcher must
also service ADC1 when applicable. An overlapping arm returns BUSY without
replacing the pending capture; the scheduler must handle that missed request.

Manual CSA input shorting, driver-session identity, VDDA measurements, retained
zero estimates, analog settling after entering/leaving calibration, and PWM
permission belong to the surrounding owner. `FRAME_READY` alone proves none of
those conditions. See [DRV8353 transitions](v4-mono-56v-drv8353-firmware.md).

## Verification and next integration

208 host assertions cover channel/rank/reference configuration, partial
completion in either order, missing partners, a partner from a later cycle,
one-time delivery, stale flags, backward/wrapping clocks, delayed setup and reads,
late status/configuration changes, retained faults and explicit restart. Shared
ADC1/ADC2/ADC3/DMA register models verify both initialization orders and completion
of a bus/reference DMA frame while current capture runs or shuts down.

Seven faulty copies compile and fail assertions: wrong channel, duplicate B
result, retimestamped data, omitted partial IRQ masking, omitted final deadline,
ADC1 reset during current shutdown, and ignored late conversion errors. Evidence
is `.scratch/v4-56v-implementation/negative-adc23/validation.json`.

All 34 firmware tests now pass. Eleven production component sources compile/
combine for Cortex-M4 hard-float without unresolved symbols; the six C sources
also compile with ARM Clang. Evidence and source hashes are in
`.scratch/v4-56v-implementation/firmware-components/validation.json`.
The optional current diagnostic links actual trigger/ADC/deadline/calibration
ownership. The bus-only and driver-only variants do not acquire current.

The next step is qualification of the normal-path PWM sampling window and
integration with current control. The diagnostic's stopped TIM1 software-update
trigger is only for manual calibration with COAST and PWM inputs LOW.
The PCB corrections and physical bring-up remain required work.
