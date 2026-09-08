#pragma once

#include "acquired_bus.hpp"

namespace odrive::mono56 {

struct BusSupervisionConfig {
    mono56_clock_us_fn clock_us;
    std::uint16_t factory_calibration;
    std::uint32_t capture_period_us;
    std::uint32_t acquisition_deadline_us;
    std::uint32_t startup_deadline_us;
    MeasurementLimits measurement_limits;
    float undervoltage_v;
    float overvoltage_v;
};

enum class BusFault { none, invalid_config, invalid_state, acquisition, measurement,
                      startup_timeout, clock, undervoltage, overvoltage };

struct BusSupervisionResult {
    BusFault fault = BusFault::none;
    mono56_adc_status acquisition = MONO56_ADC_NOT_INITIALIZED;
    BusMeasurement measurement{MeasurementError::missing_sample};
    // Original acquisition trigger time, never refreshed by rereading a frame.
    std::uint32_t sampled_at_us = 0;
    // Only the bus-measurement condition, not overall permission/driver readiness.
    [[nodiscard]] bool bus_ready() const {
        return fault == BusFault::none && measurement.valid();
    }
};

// One serialized board/control owner; this is not thread-safe or an independent
// watchdog. The caller must invoke update() on schedule and before consuming a
// measurement. No method raises PB12 or enables PWM. Explicit stop()+begin() is
// needed to recover a latched fault, and that recovery still leaves the motor off.
class BusSupervisor {
public:
    BusSupervisor() = default;
    BusSupervisor(const BusSupervisor&) = delete;
    BusSupervisor& operator=(const BusSupervisor&) = delete;
    [[nodiscard]] bool begin(const BusSupervisionConfig& config);
    [[nodiscard]] BusSupervisionResult update();
    [[nodiscard]] bool stop();

private:
    enum class Phase { stopped, starting, monitoring, fault };
    void latch_fault(BusFault fault, MeasurementError error = MeasurementError::missing_sample);
    BusSupervisionConfig config_{};
    Phase phase_ = Phase::stopped;
    BusSupervisionResult result_{};
    mono56_adc_frame latest_{};
    bool owns_adc_ = false;
    bool triggered_ = false;
    std::uint32_t began_at_ = 0, last_update_ = 0, last_trigger_ = 0;
};

} // namespace odrive::mono56
