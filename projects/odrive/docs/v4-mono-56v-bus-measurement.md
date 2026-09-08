# ODrive v4-mono 56 V — reference-compensated bus measurement

> A [two-rank ADC1 acquisition component](v4-mono-56v-adc-acquisition.md) now
> feeds this conversion and compiles for ARM. The original integration discussion
> below describes the earlier conversion-only step. The board scheduler, remaining
> analog channels, controller integration and complete firmware image remain open.

The first firmware component now converts the bus ADC reading using the MCU's
factory-calibrated VREFINT measurement. This removes the fixed-AVCC assumption
from the conversion. It does **not** close the complete firmware port or establish
coordination with the hardware OV threshold. No KiCad source changes were needed
for this step; the schematic remains at 357 components.

## Conversion and acquisition requirements

`firmware/mono56/src/bus_voltage.cpp` implements:

```text
VDDA_estimate = 3.3 * factory_VREFINT_count / measured_VREFINT_count
VBUS_estimate = bus_count * VDDA_estimate * 22 / 4096
```

STM32F405 factory calibration occupies `0x1FFF7A2A..0x1FFF7A2B` (12-bit
measurement at 3.3 V). VREFINT needs 10 µs sampling and up to 10 µs startup;
the selected LQFP64 package's ADC reference is internally tied to VDDA.
The source is [ST DS8626, Tables 72/73 and ADC supply connections](https://www.st.com/resource/en/datasheet/dm00037051.pdf).
The [ST LL ADC driver](https://github.com/STMicroelectronics/stm32f4xx-hal-driver/blob/master/Inc/stm32f4xx_ll_adc.h)
confirms the address, conversion formula and ±10 mV factory supply tolerance.

The library rejects missing samples, implausible calibration, zero/clipped
reference readings, saturated bus readings, stale/future timestamps, excessive
sample separation, invalid limits and VDDA outside the caller's configured
range. Rejected results carry an explicit error and NaN voltages. A subsequent
bad input cannot inherit a previous valid measurement. Calibration's 1.17–1.25 V
sanity window is an engineering allowance, not a corruption detector or a claim
of calibration accuracy. Zero bus ADC code remains a valid voltage estimate;
undervoltage handling belongs to the axis fault policy.

The public API intentionally has no production timing defaults. Sample freshness
limits do not bound supply slew: even two fresh samples may have different VDDA.
The caller must publish ADC data and its actual acquisition timestamp together,
and must not timestamp an unchanged DMA buffer as a new conversion.

## Upstream integration still required

The inspected ODrive `fw-v0.5.6` commit is
`a308314ed2ca613164b81e7bbdfacc53cd1859ff`. Its
`Firmware/MotorControl/low_level.cpp` currently does a fixed-reference conversion
in `vbus_sense_adc_cb()`. The regular ADC1 scan covers channels 0–15 with 15-cycle
sampling, while injected ADC1 channel 6 measures the bus. The mono schematic
retains PA6/ADC1_IN6 for `VBUS_S`.

VREFINT is ADC1 channel 17. At the existing 21 MHz ADC clock, 15 cycles give
about 0.714 µs, far below 10 µs. The available 480-cycle setting gives 22.857 µs;
startup must also be observed before accepting the first conversion. Do not
append VREFINT as a seventeenth rank to the existing sixteen-rank sequence.
The mono acquisition port needs an explicit channel/rank map, a revised DMA
buffer, timestamps and validity, and an interruption/scheduling analysis against
the current-sense injected conversions. Sampling time belongs to the ADC channel,
so regular/injected configuration of a shared channel must remain consistent.

The new component is host compiled only. It is not yet called by an ADC ISR or
ODrive's controller. ARM build/link, peripheral setup, DMA coherence, ISR latency,
CPU cost, all other fixed-reference conversions, and retained axis-fault handling
remain open. In particular, a missing measurement must prevent arm/start or fault
a running axis; no fallback to 3.3 V or stale voltage is permitted. This policy
must be implemented in the board port, not inferred from a passing library test.

## Conditional coordination screen

`analyze_ov_threshold.py` now checks bus-sense topology as well as hardware OV
connections, then evaluates 8192 corners of the calibrated conversion. Additional
terms include ±5 mV VREFINT temperature spread, independent ±5.5 count allowances
for calibration/reference/bus conversions, ±10 mV calibration-supply tolerance,
±0.5% intersample VDDA mismatch and ±0.1 V analog-ground offset. Existing divider,
buffer and clamp allowances remain. ADC TUE is characterized at 30 MHz and used
as an allowance for the planned 21 MHz acquisition; these are conditional screens,
not guaranteed system limits. See [ST ADC/reference characteristics](https://www.st.com/resource/en/datasheet/dm00037051.pdf).

| Illustrative firmware setting | Conditional actual trip | Margin to earliest hardware trip, before delay |
|---|---|---|
| 56.0 V | 54.151–57.884 V | +0.779 V |
| 56.5 V | 54.639–58.396 V | +0.266 V |
| 57.0 V | 55.126–58.909 V | −0.246 V |
| 58.0 V | 56.102–59.934 V | −1.272 V |

The earlier fixed-3.3 V 58 V screen was 54.560–61.472 V and omitted ADC converter
and ground-offset terms. It is retained as a historical sensitivity comparison,
not a matched error-budget comparison. Reference compensation helps, but the
58 V setting still cannot be shown to precede hardware OV under the expanded
budget. The zero-static-margin setting is about 56.760 V; it is **not an acceptable
default**, since it leaves no reaction-time or energy margin. None of the table's
settings is selected as a production threshold.

Source maximum voltage, allowed normal-operation margin, regenerative power,
minimum effective bus capacitance and reaction time must constrain final settings.
Board calibration, reduced divider/clamp errors or another measurement design may
be needed if the resulting window is too narrow. Threshold adjustment alone must
not conceal that tradeoff. The hardware OV screen remains 58.662–61.029 V rising;
its allowances and physical qualification are still open.

## Validation evidence

The C++17 host build passes 150 checks: a quantized ideal-ADC sweep from 0–65 V
at three VDDA levels, input rejection, age/skew boundaries, timer wrap and dropout
after a valid reading. Maximum error in that ideal sweep is 0.02932 V; it is not
an analog accuracy bound. Three deliberately modified copies fail the tests:
fixed 3.3 V, old 19:1 divider and removed age rejection. Fast-math compilation is
also rejected because it invalidates the required finite/NaN semantics.

Build with the commands in [the component README](../firmware/mono56/README.md).
Scratch evidence: `firmware-host-build/`, `bus-measurement-validation.json` and
`ov-vrefint-compensation.json` under `.scratch/v4-56v-implementation/`. No
manufacturing outputs or flashable firmware were produced by this step.
