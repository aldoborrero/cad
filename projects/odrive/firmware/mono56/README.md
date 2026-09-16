# ODrive mono 56 V firmware components

This directory contains the beginning of the mono firmware implementation.
It is **not an implemented ODrive motor-control board port**. A standalone
[diagnostic image](../../docs/v4-mono-56v-diagnostic-image.md) now links startup,
IRQ-driven acquisition and SWD status, with the motor permanently inhibited;
its physical boot/timing behavior has not been tested. An explicit JSON profile
selects the [integrated driver diagnostic](../../docs/v4-mono-56v-driver-diagnostic.md),
which can wake/configure the driver while retaining COAST and keeping PWM inputs LOW.
`mono56_measurement` supplies reference-compensated bus measurement. A two-rank
ADC1/DMA acquisition component now feeds that conversion and compiles for ARM.
A bus supervisor now retains measurement/acquisition/voltage faults and inhibits
PB12/TIM1. A [DRV8353 register session](../../docs/v4-mono-56v-drv8353-firmware.md)
now supplies explicit configuration, lock/readback and retained faults through
board IO callbacks. The [SPI3 transport](../../docs/v4-mono-56v-spi3-transport.md)
now connects that session to STM32 peripheral code, with bounded transactions and
retained transport errors. A [GPIO/sleep-wake owner](../../docs/v4-mono-56v-driver-wake.md)
now provides the board callbacks and retains feedback/fault history while all six
PWM GPIOs stay LOW. A [phase-current module](../../docs/v4-mono-56v-phase-current.md)
now converts supplied B/C samples using separate zero estimates, explicit
shunts/gain/polarity and validity limits. The DRV8353 session now supplies
verified B/C manual input-short entry/exit, tested through SPI3 with the zero
estimator and synthetic samples. An [ADC2/3 acquisition driver](../../docs/v4-mono-56v-current-acquisition.md)
now captures a pair from a shared TIM1_TRGO event while preserving ADC1/DMA.
The [current-zero diagnostic](../../docs/v4-mono-56v-current-diagnostic.md) now
connects stopped-TIM1 triggers, ADC/TIM5 IRQ/deadline service and manual B/C
calibration, with original current/VDDA timestamps and retained COAST.
A [PWM sampling planner](../../docs/v4-mono-56v-pwm-sampling.md) now computes
prospective duty/dead-time/ADC windows. A [continuous TIM1 cycle owner](../../docs/v4-mono-56v-pwm-cycle.md)
now implements preload history, ADC-arm notifications and boundary/command deadlines
with PWM outputs still inhibited. A [continuous ADC capture owner](../../docs/v4-mono-56v-pwm-capture.md)
now supplies per-cycle deadlines and single-delivery raw frames. A
[calibration-to-timing handoff](../../docs/v4-mono-56v-timing-handoff.md) now releases
stopped capture without lowering ENABLE and preserves the verified driver session
for internal timing. Its permission checks cannot renew foreground progress from
an interrupt. The [calibrated timing diagnostic](../../docs/v4-mono-56v-timing-diagnostic.md)
now integrates that handoff, IRQ frame consumption/next-command service,
foreground SPI and retained faults in an optional executable image. Qualified
current-frame construction and calibrated output handoff remain to be integrated.
All fifteen production component C/C++ sources compile for
Cortex-M4 and combine without unresolved symbols. The diagnostic image supplies a separate TIM7/DMA
service; integration with the actual PWM/current loop, other analog inputs,
retained axis faults, PWM handoff and motor control
remain to be implemented. See [supervision behavior and limits](../../docs/v4-mono-56v-bus-supervision.md).

The integration baseline inspected is ODrive `fw-v0.5.6`, commit
`a308314ed2ca613164b81e7bbdfacc53cd1859ff`, locally under
`.scratch/odrive/firmware/`. That upstream checkout was not modified.
See [the port contract](../../docs/firmware-port.md) and
[measurement design and remaining coordination work](../../docs/v4-mono-56v-bus-measurement.md).

## Build and check the component on the host

Run from the repository root:

```bash
cmake -S projects/odrive/firmware/mono56 \
  -B .scratch/v4-56v-implementation/firmware-host-build -DCMAKE_BUILD_TYPE=Release
cmake --build .scratch/v4-56v-implementation/firmware-host-build
ctest --test-dir .scratch/v4-56v-implementation/firmware-host-build --output-on-failure
```

Requires CMake, a C++17 compiler and its build tool. This builds a static library
and host tests, not an ARM image. The measurement library does not allocate memory,
throw exceptions, access peripherals or retain a last-good value. Compile without
fast-math/finite-math-only: invalid readings use an explicit error plus NaN values,
and configuration validation requires finite-number semantics.

## Call contract

1. Read the selected STM32F405's 16-bit factory calibration at the documented
   address in `bus_voltage.hpp`; a constant address here does not read hardware.
2. Supply coherent, right-aligned 12-bit bus and VREFINT ADC snapshots. Set
   `valid` only after real conversions complete, including internal-reference
   startup and acquisition settling. The function cannot detect a DMA buffer
   that is stale but given a new timestamp by the caller.
3. Give both samples timestamps from the same monotonic microsecond counter.
   Limits for age, sample skew and VDDA are mandatory integration parameters;
   the 1000/100 µs values in tests are fixtures, not production defaults.
4. Call `measure_bus_voltage()` and test `valid()` before consuming either
   voltage. A missing or rejected result must inhibit startup/arming or fault
   the running axis. Do not replace rejection with a fixed 3.3 V conversion or
   reuse a last-good bus voltage indefinitely.

The result is an estimated voltage, not a permission to run. It does not select
bus thresholds, establish regenerated-energy capacity, clear an axis fault, or
rearm the hardware interlock. It also does not distinguish a disconnected bus
sense input from an actual zero bus voltage; the port must handle undervoltage.

## Check all components and compile their production ARM paths

Supply the CMSIS root from the pinned upstream checkout and GNU ARM GCC (with
its sibling g++, ld, nm and readelf tools). Optionally add an ARM-capable Clang
for a second compiler check of the C drivers:

```bash
python3 projects/odrive/tools/check_mono_firmware.py \
  --cmsis-root .scratch/odrive/firmware/Firmware/ThirdParty/CMSIS \
  --arm-gcc /path/to/arm-none-eabi-gcc \
  --arm-clang /path/to/clang
```

Use `--cmake /path/to/cmake` if it is not on PATH. No sources or toolchains are
fetched automatically. In this NixOS workspace the verified Clang is
`/nix/store/rm8isfm4fd14is3fv3h4m459rbiy91bx-clang-21.1.8/bin/clang`.
The verified GCC binary is
`/nix/store/iv3vf37ki8n3g2kchylx2zy8wag499k6-arm-none-eabi-gcc-wrapper-15.3.0/bin/arm-none-eabi-gcc`.
The tool runs all 52 host tests, including 15 current diagnostic scenarios,
14 timing diagnostic scenarios and nine driver diagnostic scenarios.
Component suites cover conversion, supervision, SPI, wake, current zero and
ADC/capture behavior. GNU ARM compiles all fifteen component sources and checks
Cortex-M4/hard-float attributes and combined dependencies; Clang independently
compiles the seven C components. Exact commands, test output and source hashes
are recorded under `.scratch/v4-56v-implementation/firmware-components/`.
The linked diagnostic images are verified by the separate builder below.

To enable acquisition and supervision tests directly with CMake, also pass
`-DMONO56_CMSIS_ROOT="$PWD/.scratch/odrive/firmware/Firmware/ThirdParty/CMSIS"`.
Without that argument CMake explicitly reports that peripheral tests are omitted;
the basic host build is not evidence for acquisition or inhibition behavior.

`adc1_acquisition.h` exposes exclusive ADC1/DMA ownership, explicit startup/start,
single-delivery take, and shutdown. `acquired_bus.hpp` checks the entire capture
interval before conversion. There is no ISR or automatic frame scheduling in this
component. See [acquisition behavior and board integration requirements](../../docs/v4-mono-56v-adc-acquisition.md)
before connecting it to the controller. The legacy ADC1 injected bus conversion
and continuous general-purpose scan cannot coexist with this owner.

## Build the standalone diagnostic image

`tools/build_mono_monitor.py` compiles and links the Cortex-M4 image with explicit
CMSIS/toolchain and diagnostic UV/OV arguments. It generates ELF/BIN/HEX and
checks vectors, executable attributes and DMA SRAM placement. It does not program
a device. See [the bus-only command and limitations](../../docs/v4-mono-56v-diagnostic-image.md).
Add an explicit `--driver-config profile.json` to build the COAST-only driver
variant; see [its profile format, SWD fields and limits](../../docs/v4-mono-56v-driver-diagnostic.md).

Add `--current-config current-profile.json` alongside the driver profile for
one manual B/C zero calibration with COAST retained. See
[the complete profile, trigger ownership and acceptance limits](../../docs/v4-mono-56v-current-diagnostic.md).
