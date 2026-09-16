# STM32F405 SPI3 transport for DRV8353

## Implemented scope

`firmware/mono56/src/spi3_transport.c` now supplies the CMSIS peripheral transport
for `Drv8353Io.exchange` through `mono56_drv8353_spi3_exchange`. The register
session and transport run together in simulated-peripheral tests and compile for
Cortex-M4. A [GPIO/wake owner](v4-mono-56v-driver-wake.md) now supplies startup permission
callbacks and retained EXTI history. The [driver diagnostic](v4-mono-56v-driver-diagnostic.md)
now schedules them together. Manual B/C CSA transitions are implemented in the
register session and exercised through this adapter with synthetic zero samples.
Physical wake qualification, scheduled ADC-based calibration and
the motor-controller port remain pending. The bus-only
standalone diagnostic image does not initialize SPI3 or call the driver.

## Peripheral and timing contract

The exported mono schematic maps SPI3 SCK/MISO/MOSI to PC10/PC11/PC12 (AF6),
with active-low nCS on PC13. The transport owns these four pins and SPI3
exclusively. Other GPIO modes and alternate functions are preserved, including
PC6/PC7 feedback. nCS is preloaded high before output-mode selection; PC13 uses
low output speed. No internal pulls are selected; MISO uses schematic R202.
The caller must establish quiet motor outputs before initialization.

The peripheral uses 16-bit, MSB-first, full-duplex mode 1 (CPOL=0, CPHA=1),
software NSS, and no CRC, DMA, SPI interrupts or I2S. PCLK1 must remain 42 MHz;
BR=/128 gives 328125 Hz and a nominal 48.762 µs wire time per word. The configured
clock argument is a caller contract, not a measurement of the RCC clock tree.

[TI SLVSDY6A sections 7.6 and 8.5](https://www.ti.com/lit/ds/symlink/drv8353.pdf)
require 16 clocks per transaction, at least 400 ns between active-low selections,
and 50 ns nCS setup/hold. Each transfer waits two microsecond-counter increments
for the high interval, setup and hold. With a qualified 1 µs counter, quantization
leaves approximately 1 µs minimum elapsed time, before clock-error allowances.
This is an initial conservative implementation, not a measured signal-integrity
or latency qualification. The open-drain MISO rise time and PC13 loading still
need physical verification.

Each frame writes and reads the SPI data register once using volatile halfword
access. It waits for TXE before writing, RXNE before reading, then TXE and BSY=0
before the hold interval and nCS release. RXNE alone is insufficient for release.
Only a final successful deadline/error/configuration observation publishes data.

## Failure and ownership contract

Initialization requires a nonblocking monotonic wrapping microsecond callback
and an explicit 60..1000 µs transaction deadline. The 200 µs host fixture is not
a production choice. Every polling iteration checks elapsed time, backward-clock
jumps, SPI error flags and control-register drift. A separate 200000-iteration
budget terminates polling if the counter freezes; this is not a calibrated
wall-clock bound or an independent watchdog. Normal unsigned counter wrap works.
The deadline includes spacing/setup/hold and final completion observation.

Timeout, clock error, poll exhaustion, overrun/mode/CRC/frame error, stale receive
state or changed configuration deassert nCS, disable SPI and retain the transport
failure. No receive word is published and no implicit retry occurs. An interrupted
frame may already have changed a device register; software cannot undo it or
assume normal abort timing. The register-session layer invokes its mandatory
motor-inhibit callback on a failed exchange. The transport itself does not actuate
ENABLE, TIM1 or the brake.

Recovery requires explicit shutdown and initialization plus the board owner's
new qualified driver session. Shutdown resets only the owned SPI3 peripheral.
Initialization rejects an active foreign SPI/I2S peripheral or pending data;
non-owner shutdown leaves it alone. This is not a shared-bus arbitration layer.
Calls must use one serialized execution context. Active reentrant transfer or
shutdown calls return BUSY; this guard does not make the module thread-safe.
Interrupts remain enabled. Do not run configuration or full readback in the
high-rate current ISR: a configuration uses 31 frames and a normal full check
uses 10, each with its own deadline. Scheduling, service cadence and retained
fault edges belong to the pending board owner.

## Verification and remaining integration

Run `tools/check_mono_firmware.py` with CMSIS, GNU ARM GCC and optionally Clang
as described in the [firmware README](../firmware/mono56/README.md). Tests model
separate TXE, RXNE and BSY events, GPIO selection, clock failures, retained errors
and the complete register-session-to-SPI3 path. All 998 SPI3 checks pass, including B/C manual entry/exit connected to the zero
estimator using synthetic analog samples. The original eight
deliberately faulty transport copies compile and fail assertions for wrong CS,
frame width, clock phase, BSY handling, overrun handling, missing setup/hold and
wrong peripheral reset. The counter model permits repeated identical readings;
advancing time on every read had initially hidden an omitted setup delay. Host hooks model data-register
side effects; they do not prove physical bus behavior. Independent inspection of
the GNU ARM object confirmed `strh`/`ldrh` at SPI3 DR (0x40003c0c), PC13 BSRR
writes and the final TXE/BSY mask.

Evidence is under `.scratch/v4-56v-implementation/firmware-components/` and
`negative-spi3/`, with source hashes, build commands and faulty-copy results.
The bus-only diagnostic now uses 4628 text, 108 data and 100 BSS bytes;
unused SPI/DRV code is removed by section garbage collection. No device has been
programmed and no SPI waveform or gate transition has been measured.

Explicit sleep/wake and retained permission handling now have a separate owner
with all six PWM inputs low. The optional driver diagnostic now schedules that
owner and configures the driver while retaining COAST. Enabling PWM also requires qualified current
acquisition, calibration, limits and encoder/control integration. See
[full implementation acceptance](v4-mono-56v-implementation.md).
