# ODrive v4-mono 56 V — ADC1 acquisition component

The bus/reference acquisition component is implemented and compiled for Cortex-M4.
It feeds the existing voltage-conversion component through `measure_acquired_bus()`.
The complete mono board scheduler, ISR ownership and motor-control integration
are still pending; this is not a linked or flashable firmware image. No KiCad
sources changed in this step.

## Selected acquisition

ADC1 owns a software-triggered, two-rank regular sequence: PA6/channel 6 for bus
voltage, then internal channel 17 for VREFINT. DMA2 stream 0/channel 0 transfers
two halfwords into a fixed buffer in normal mode. There is no circular buffer,
injected ADC1 conversion or automatic next-frame trigger. ADC2/ADC3 registers
are preserved; their current-sense configuration remains the board port's job.

The component requires PCLK2 = 84 MHz and sets the shared ADC prescaler to /4.
It refuses to change that prescaler while another ADC is active, unless /4 is
already selected, and rejects multimode or an already-owned ADC1/DMA stream.
The caller must provide a truthful clock configuration and keep it stable.
VDDA must remain at least 2.4 V for this ADC clock; the adapter rejects limits
that would accept a lower supply range. Startup/brownout behavior before valid
conversion is still a hardware qualification requirement.
PA6 alone is switched to analog/no-pull. The buffer must lie in DMA-accessible
SRAM; the production driver checks its address and rejects CCM placement.

| Stage | Configuration | Nominal duration at 21 MHz |
|---|---|---|
| Startup wait | ADC/VREFINT enabled before first trigger | At least 10 µs |
| Bus conversion | 15 sample + 12 conversion cycles | 1.286 µs |
| Reference conversion | 480 sample + 12 conversion cycles | 23.429 µs |
| Complete sequence | 519 ADC cycles | 24.714 µs, excluding trigger/software/DMA/service overhead |

These timings use [ST DS8626, ADC and VREFINT characteristics](https://www.st.com/resource/en/datasheet/dm00037051.pdf).
Register layouts/masks and DMA mapping were checked against the STM32F405 CMSIS
and ADC HAL sources in the pinned ODrive baseline. The full RM0090 download was
unavailable during this step; no full manual or physical timing audit is claimed.
The 25 µs minimum accepted deadline is a configuration sanity limit, not a
production recommendation. The tests use a 100 µs deadline as a fixture.

## Completion, age and fault behavior

`mono56_adc1_init()` requires exclusive ownership, a microsecond clock callback
and an explicit deadline. `start()` waits for startup and prevents overlapping
frames. `take()` publishes a frame only after transfer complete, NDTR zero and
DMA enable cleared; partial DMA completion never produces a valid frame. The
buffer is stable because normal-mode DMA has stopped. Memory barriers remain in
the production code. Each completed frame is delivered once.

The driver records a timestamp immediately before SWSTART and another after it
has observed completion and copied the data. Both physical samples lie within
that interval, subject to correct clock implementation. `measure_acquired_bus()`
checks the entire interval against the permitted pair separation and uses the
trigger timestamp as a conservative oldest bound for both samples. Thus delayed
servicing cannot turn an old acquisition into a freshly dated measurement. The
callback must have suitable resolution, run monotonically modulo uint32_t, and
not pause/change rate during acquisition; a board timer implementation remains
required.

DMA errors, ADC overrun, inconsistent transfer count and timeout invalidate the
output and stop further acquisition. They remain retained until explicit
shutdown and initialization. The module does not automatically recover a fault.
If DMA disable acknowledgement is delayed, shutdown reports busy without an
unbounded wait. The board must keep motor outputs inhibited during recovery.

Normal pending/idle status is distinct from an acquisition fault. The board
should pass a temporary output frame to `take()`, retain a successfully acquired
frame only within its allowed age, and revalidate it at each use. A new pending
capture does not permit indefinite use of the old frame. An acquisition fault
must invalidate the retained measurement immediately and fault the running axis.
That controller policy is not yet implemented by this low-level component.

## Board integration requirements

The inspected ODrive baseline is `a308314ed2ca613164b81e7bbdfacc53cd1859ff`.
Its `start_general_purpose_adc()` and ADC1 initialization must not run alongside
this exclusive ADC1 owner. `fetch_and_reset_adcs()` currently waits for ADC1 JEOC
and reads JDR1; the mono implementation must replace that dependency with this
validated frame, while separately retaining current-conversion timing checks.
The removed axis's regular ADC2/ADC3 requirements must also be removed correctly.

The upstream 168 MHz timer, 3500-count half-period and repetition counter 2 give
24 kHz PWM and an 8 kHz control period of 125 µs. A 24.714 µs acquisition fits
nominally within that period, but **fit alone does not prove scheduling**. The
port must choose when to trigger/take frames, budget software/DMA service latency,
phase relative to switching noise, permitted age/skew and bus slew, and verify
current acquisition concurrently. The driver installs no interrupt handler and
enables no NVIC/DMA interrupts; the board owns its service schedule.

ADC1 is currently dedicated to the pair. Thermistors, the auxiliary multiplexer
and other analog channels still need a complete mono acquisition schedule; this
component must not be treated as preserving the legacy sixteen-channel scan.
The calibration read, driver/PWM configuration, feedback and retained fault policy,
ARM link/startup and actual motor-control integration remain open.

Relevant [ST ES0182 Rev 19 errata](https://www.st.com/resource/en/errata_sheet/es0182-stm32f405407xx-and-stm32f415417xx-device-errata-stmicroelectronics.pdf)
were reviewed: the implementation reads back RCC enables and keeps the sequence
fixed while converting. ADC noise mitigation and the complete system's concurrent
DMA2 use still need review. ADC register simulation cannot qualify those effects,
analog settling or physical bus-transient response.

## Validation

`check_mono_firmware.py` builds both host tests against the actual STM32F405 CMSIS
header, then compiles the production C driver with ARM-capable Clang for
Cortex-M4/Thumb, FPv4-SP-D16 and hard-float ABI. It verifies a 32-bit ARM ELF
object and records source/header hashes, command outputs and compiler version.
The object has no undefined external symbols; it is still only an object file.

- Existing bus conversion: 150 passing checks.
- Acquisition and converter integration: 111 passing checks, covering startup,
  peripheral conflicts, preservation of other ADC/GPIO settings, partial/repeated
  frames, errors, exact deadline, delayed DMA disable, timestamps and wrap.
- Seven modified driver copies are rejected: wrong bus channel, short reference
  sampling, circular DMA, ignored transfer count, ignored ADC overrun, ignored DMA
  errors and a false fresh timestamp. These copies never replace production code.

The host substitutes peripheral addresses and emulates specific register events,
including DMA flag clearing. It is not an ADC/DMA silicon simulator. SRAM placement
and real memory barriers require the target path; no physical board was tested.
Evidence is under `.scratch/v4-56v-implementation/firmware-components/` and
`negative-adc-acquisition/`. Build instructions are in
[the firmware README](../firmware/mono56/README.md).
