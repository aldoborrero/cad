#pragma once

#include "adc1_acquisition.h"
#include "bus_voltage.hpp"

namespace odrive::mono56 {
// Validates the entire acquisition interval, not only two nominal timestamps.
// Includes observation latency conservatively in the maximum pair separation.
[[nodiscard]] inline BusMeasurement measure_acquired_bus(
    const mono56_adc_frame& frame, std::uint16_t calibration,
    std::uint32_t now_us, const MeasurementLimits& limits) {
    // This acquisition runs at 21 MHz; the ADC's lower-VDDA range only permits
    // up to 18 MHz. Do not accept a configuration that treats it as qualified.
    if (limits.vdda_min_v < 2.4f) return {MeasurementError::invalid_limits};
    if (!frame.valid) return {MeasurementError::missing_sample};
    const std::uint32_t span = frame.observed_complete_at_us - frame.started_at_us;
    if (span >= 0x80000000u ||
        (std::uint32_t)(now_us - frame.observed_complete_at_us) >= 0x80000000u) {
        return {MeasurementError::stale_or_future_sample};
    }
    if (span > limits.max_pair_skew_us) return {MeasurementError::excessive_pair_skew};
    // Both samples are at least as recent as the software trigger timestamp.
    // The span guard above separately bounds their worst-case separation.
    return measure_bus_voltage(
        {frame.bus_raw, frame.started_at_us, true},
        {frame.reference_raw, frame.started_at_us, true}, calibration, now_us, limits);
}
} // namespace odrive::mono56
