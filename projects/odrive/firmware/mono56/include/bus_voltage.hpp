#pragma once

#include <cstdint>
#include <limits>

namespace odrive::mono56 {

// STM32F405RGT6, 12-bit right-aligned ADC. DS8626 Rev 12, Table 73.
inline constexpr std::uintptr_t vrefint_cal_address = 0x1FFF7A2A;
inline constexpr float vrefint_cal_supply_v = 3.3f;
inline constexpr float adc_full_scale = 4096.0f;
inline constexpr float bus_divider_ratio = 22.0f;

struct AdcSample {
    std::uint16_t raw = 0;
    std::uint32_t sampled_at_us = 0;
    bool valid = false;
};

// Required integration choices, not qualified defaults. Both samples must use
// the same monotonic uint32_t clock; maximum permitted age must be < 2^31 us.
struct MeasurementLimits {
    std::uint32_t max_age_us;
    std::uint32_t max_pair_skew_us;
    float vdda_min_v;
    float vdda_max_v;
};

enum class MeasurementError {
    none,
    invalid_limits,
    missing_sample,
    invalid_calibration,
    invalid_reference,
    bus_adc_saturated,
    stale_or_future_sample,
    excessive_pair_skew,
    supply_out_of_range,
};

struct BusMeasurement {
    MeasurementError error;
    float bus_v = std::numeric_limits<float>::quiet_NaN();
    float vdda_v = std::numeric_limits<float>::quiet_NaN();
    [[nodiscard]] bool valid() const { return error == MeasurementError::none; }
};

// Pure conversion: no memory-mapped reads, dynamic allocation, or retained last
// good voltage. The ADC owner supplies a coherent snapshot and checked timing.
// Invalid results must inhibit arming and cause a retained fault if running;
// callers must test valid(), not rely on comparisons against the NaN payload.
[[nodiscard]] BusMeasurement measure_bus_voltage(
    const AdcSample& bus, const AdcSample& reference,
    std::uint16_t factory_vrefint_cal, std::uint32_t now_us,
    const MeasurementLimits& limits);

} // namespace odrive::mono56
