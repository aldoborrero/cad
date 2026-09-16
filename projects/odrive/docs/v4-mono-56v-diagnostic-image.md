# STM32F405 mono diagnostic image

## Purpose and current evidence

This page describes the default bus-only image. An explicit driver JSON profile
selects the separate [COAST-only driver diagnostic](v4-mono-56v-driver-diagnostic.md),
which can raise ENABLE while keeping all PWM inputs LOW.

`firmware/mono56/monitor/` builds a standalone diagnostic ELF/BIN/HEX at
`0x08000000`. It starts the STM32F405RGT6, measures the bus through the new ADC/DMA
path, applies the bus supervisor and exposes diagnostics through SWD. **It never
arms the motor or enables motor PWM. It is not the functional motor-control port.**

The image links without a C/C++ runtime, has no unresolved symbols or static
constructors, and reserves the last 256 KiB of the MCU's 1 MiB Flash address space
for the upstream NVM region. The current bus-only build uses 4656 bytes of text, 108 bytes
of initialized RAM and 104 bytes of BSS. Linker checks reserve at least 8 KiB of
stack space; actual maximum stack usage has not been measured.

Static checks verify the Cortex-M4 hard-float ELF, initial stack and Thumb reset
vector, TIM7 and DMA2 stream 0 vectors, inhibiting exception handlers and ADC DMA
buffer placement/alignment in normal SRAM. The IRQ-service host test passes 43
checks with simulated register events. Five faulty service copies (wrong IRQ
priority, lost completion service, lost permanent inhibition, wrong period and
masking healthy DMA) are rejected. These supplement the existing 150 conversion,
111 acquisition and 578 supervision checks. Neither these tests nor successful
linking establish that the image boots, meets timing or measures accurately on a
physical board. No device has been programmed.

## Startup and service

The exported schematic specifies Y1 = 8 MHz and U2 = STM32F405RGT6. The startup
uses HSE/4 × 168/2 for 168 MHz HCLK, APB1 /4 and APB2 /2. That gives 84 MHz timer
clocks on APB1 and 21 MHz ADC after its /4 prescaler. This matches the inspected
upstream v3 clock configuration. Relevant device constraints are in
[ST DS8626 Rev 12](https://www.st.com/resource/en/datasheet/dm00037051.pdf).

Reset first inhibits PB12/TIM1, then copies `.data`, clears `.bss`, sets VTOR and
enables the FPU before entering C++. Clock-ready waits have finite iteration
limits; they are not calibrated millisecond timers. The image assumes a hardware
reset entry and **VDD at least 2.7 V for 168 MHz with five Flash wait states**.
It does not implement bootloader clock handoff. Clock failure or a CPU exception
enters a terminal diagnostic handler, inhibits the motor and masks interrupts.
HSE clock security is enabled. Flash instruction/data caches are enabled;
prefetch is left off following the ADC-noise discussion in
[ST ES0182 Rev 19](https://www.st.com/resource/en/errata_sheet/es0182-stm32f405407xx-and-stm32f415417xx-device-errata-stmicroelectronics.pdf).
Startup, rail ramps and failure behavior still require board measurements.

TIM5 is a free-running 32-bit 1 MHz timestamp counter. TIM7 provides the 125 µs
periodic dispatch. DMA2 stream 0 completion and error interrupts service finished
captures promptly. Both IRQs have preemption priority 2 with priority grouping 3,
so their supervisor/ADC accesses cannot preempt one another. This is a standalone
scheduling arrangement, not yet the existing ODrive PWM/current-loop integration.
TIM5 must be reconciled with upstream's GPIO pulse-capture use in the full port.

The supervisor uses a 50 µs acquisition-observation deadline. **That is not a
50 µs guarantee of physical shutdown:** with a missing completion event, the
next 125 µs periodic call detects the timeout. ISR latency, clock tolerance and
fault response have not been measured. A stopped CPU needs independent lockup
protection, which this image does not implement.

The MCU brake request on PB11 initializes low. PC6 and PC7 are inputs without
pulls and report actual driver-enable/brake-permission feedback. The hardware OV
brake path remains independent of the MCU request. Bus readiness is only a
measurement status; feedback is diagnostic here and does not grant an arm.
Every service call enforces the image's permanent motor-inhibit policy. Bus
faults retain the first cause and disable DMA IRQ service, while periodic
inhibition and diagnostics continue. Recovery requires a reset of this image.

## Reproduce the image

From the repository root, supply an explicit CMSIS root and GNU ARM toolchain:

```bash
python3 projects/odrive/tools/build_mono_monitor.py \
  --cmsis-root .scratch/odrive/firmware/Firmware/ThirdParty/CMSIS \
  --arm-gcc /path/to/arm-none-eabi-gcc \
  --undervoltage 10 --overvoltage 58
```

**10/58 V above are diagnostic test settings, not qualified production limits.**
The conditional 56 V protection analysis still rejects a 58 V firmware setting's
coordination with earliest hardware OV. The CLI requires explicit finite limits
and records them in the evidence; it does not choose application limits.

The verified GNU ARM executable in this NixOS workspace is
`/nix/store/iv3vf37ki8n3g2kchylx2zy8wag499k6-arm-none-eabi-gcc-wrapper-15.3.0/bin/arm-none-eabi-gcc`.
It was obtained from this repository's pinned nixpkgs via
`pkgs.pkgsCross.arm-embedded.stdenv.cc`. The CMSIS headers are from the previously
inspected upstream `fw-v0.5.6` commit
`a308314ed2ca613164b81e7bbdfacc53cd1859ff`; that checkout remains unchanged.
These helpers do not fetch dependencies. A clean Nix-packaged source/toolchain
build for the eventual full controller is still pending.

Outputs default to `.scratch/v4-56v-implementation/monitor-image/`:

- `mono56-monitor.elf`: linked image with symbols and debug information.
- `mono56-monitor.bin` / `.hex`: generated image formats, not programmed by the tool.
- `monitor.map`, `vectors.bin`, `validation.json`: memory/vector checks, settings,
  exact commands, tool version and source/artifact hashes.

`tools/check_mono_firmware.py` separately runs the host tests and production
component compilation. It does not itself link this diagnostic image; run both
commands when changing shared code. A build failure must not be treated as a
successful image merely because an earlier artifact exists in the output folder.

## SWD observations for later bench work

The ELF contains `mono56_monitor`, defined in `monitor/monitor.h`. `magic` is
`0x4d353644`, format version 1. It exposes timer/DMA IRQ counts, timestamp,
bus readiness and voltage, estimated VDDA, supervisor/acquisition/measurement
error enums and PC6/PC7 feedback. For a live multiword snapshot, read `sequence`
before and after the structure and accept equal even values. `fatal_code != 0`
or `bus_ready == 0` means voltage fields must not be consumed as a valid reading.

| Fatal code | Meaning |
|---|---|
| 1 | CPU exception/unhandled IRQ; inspect `exception_number` |
| 2 | Unsupported initial clock state |
| 3 | Regulator-ready wait expired |
| 4 | HSE-ready wait expired |
| 5 | PLL-ready wait expired |
| 6 | Flash-latency readback failed |
| 7 | System-clock switch failed |
| 8 | Bus supervisor initialization failed; inspect bus/acquisition errors |

A debugger halt does not freeze TIM5/TIM7 or DMA in this image. Resuming after a
halt can therefore report a stale/late acquisition and retain a fault. That is
expected; a reset restarts the diagnostic run. No USB/CAN protocol, motor-control
commands, driver SPI, current calibration, encoder processing or physical brake
qualification is implemented by this image.

The next integration work is the real mono board/controller target: DRV8353
configuration and faults, current ADC/PWM mapping, analog-input scheduling,
retained axis/arm policy, encoder and user interface. Hardware/PCB/manufacturing
acceptance remains tracked in [the full plan](v4-mono-56v-implementation.md).
