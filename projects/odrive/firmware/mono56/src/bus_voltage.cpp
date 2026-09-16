#include "bus_voltage.hpp"

#include <cmath>

#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Bus measurement validity checks require IEEE NaN/finite semantics"
#endif

namespace odrive::mono56 {

BusMeasurement measure_bus_voltage(
    const AdcSample& bus, const AdcSample& reference,
    std::uint16_t factory_vrefint_cal, std::uint32_t now_us,
    const MeasurementLimits& limits) {
    if (limits.max_age_us == 0 || limits.max_age_us >= 0x80000000u ||
        limits.max_pair_skew_us > limits.max_age_us ||
        !std::isfinite(limits.vdda_min_v) || !std::isfinite(limits.vdda_max_v) ||
        limits.vdda_min_v < 1.8f || limits.vdda_max_v > 3.6f ||
        limits.vdda_min_v >= limits.vdda_max_v) {
        return {MeasurementError::invalid_limits};
    }
    if (!bus.valid || !reference.valid) {
        return {MeasurementError::missing_sample};
    }
    // Sanity window only: datasheet 1.18..1.24 V plus 10 mV allowance.
    // This rejects erased/implausible calibration, not subtle corruption.
    const float calibrated_vref =
        factory_vrefint_cal * vrefint_cal_supply_v / adc_full_scale;
    if (calibrated_vref < 1.17f || calibrated_vref > 1.25f) {
        return {MeasurementError::invalid_calibration};
    }
    if (reference.raw == 0 || reference.raw >= 4095) {
        return {MeasurementError::invalid_reference};
    }
    if (bus.raw >= 4095) {
        return {MeasurementError::bus_adc_saturated};
    }
    // Unsigned elapsed time also rejects future samples for the permitted
    // half-range interval. A normal uint32_t wrap is handled without a reset.
    const std::uint32_t bus_age = now_us - bus.sampled_at_us;
    const std::uint32_t reference_age = now_us - reference.sampled_at_us;
    if (bus_age > limits.max_age_us || reference_age > limits.max_age_us) {
        return {MeasurementError::stale_or_future_sample};
    }
    const auto skew = bus_age > reference_age ? bus_age - reference_age
                                              : reference_age - bus_age;
    if (skew > limits.max_pair_skew_us) {
        return {MeasurementError::excessive_pair_skew};
    }
    const float vdda = vrefint_cal_supply_v * factory_vrefint_cal / reference.raw;
    if (vdda < limits.vdda_min_v || vdda > limits.vdda_max_v) {
        return {MeasurementError::supply_out_of_range};
    }
    return {MeasurementError::none,
            bus.raw * vdda * bus_divider_ratio / adc_full_scale, vdda};
}

} // namespace odrive::mono56
