#include "bus_supervision.hpp"
#include "motor_inhibit.h"

#include <cmath>

#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Bus supervision requires IEEE finite/NaN semantics"
#endif

namespace odrive::mono56 {

void BusSupervisor::latch_fault(BusFault fault, MeasurementError error) {
    mono56_motor_inhibit();
    latest_.valid = false;
    if (phase_ != Phase::fault) {
        result_.fault = fault;
        result_.measurement = {error};
    }
    phase_ = Phase::fault;
    if (owns_adc_) {
        if (mono56_adc1_shutdown() == MONO56_ADC_NOT_INITIALIZED) owns_adc_ = false;
    }
}

bool BusSupervisor::begin(const BusSupervisionConfig& config) {
    mono56_motor_inhibit();
    if (phase_ != Phase::stopped || owns_adc_) {
        latch_fault(BusFault::invalid_state);
        return false;
    }
    const auto& m = config.measurement_limits;
    if (!config.clock_us || config.capture_period_us == 0 ||
        config.capture_period_us >= 0x80000000u ||
        config.acquisition_deadline_us < 25 ||
        config.acquisition_deadline_us > config.capture_period_us ||
        config.startup_deadline_us < 10u + config.acquisition_deadline_us ||
        config.startup_deadline_us >= 0x80000000u ||
        m.max_age_us >= 0x80000000u ||
        static_cast<std::uint64_t>(m.max_age_us) <
            static_cast<std::uint64_t>(config.capture_period_us) + config.acquisition_deadline_us ||
        m.max_pair_skew_us < config.acquisition_deadline_us || m.max_pair_skew_us > m.max_age_us ||
        !std::isfinite(m.vdda_min_v) || !std::isfinite(m.vdda_max_v) ||
        m.vdda_min_v < 2.4f || m.vdda_max_v > 3.6f || m.vdda_min_v >= m.vdda_max_v ||
        !std::isfinite(config.undervoltage_v) || !std::isfinite(config.overvoltage_v) ||
        config.undervoltage_v <= 0 || config.overvoltage_v <= config.undervoltage_v ||
        config.overvoltage_v >= bus_divider_ratio * m.vdda_min_v) {
        latch_fault(BusFault::invalid_config);
        return false;
    }
    config_ = config;
    result_ = {};
    latest_ = {};
    triggered_ = false;
    began_at_ = last_update_ = config_.clock_us();
    result_.acquisition = mono56_adc1_init(config_.clock_us, 84000000,
                                          config_.acquisition_deadline_us);
    if (result_.acquisition != MONO56_ADC_WARMING) {
        latch_fault(BusFault::acquisition);
        return false;
    }
    owns_adc_ = true;
    phase_ = Phase::starting;
    return true;
}

BusSupervisionResult BusSupervisor::update() {
    if (phase_ == Phase::stopped || phase_ == Phase::fault) {
        mono56_motor_inhibit();
        return result_;
    }
    auto now = config_.clock_us();
    if (static_cast<std::uint32_t>(now - last_update_) >= 0x80000000u) {
        latch_fault(BusFault::clock);
        return result_;
    }
    last_update_ = now;
    mono56_adc_frame frame{};
    result_.acquisition = mono56_adc1_take(&frame);
    switch (result_.acquisition) {
    case MONO56_ADC_FRAME_READY:
        latest_ = frame;
        break;
    case MONO56_ADC_IDLE:
    case MONO56_ADC_WARMING:
    case MONO56_ADC_PENDING:
        break;
    default:
        latch_fault(BusFault::acquisition);
        return result_;
    }
    now = config_.clock_us(); // take() may have observed completion after entry.
    if (phase_ == Phase::starting &&
        static_cast<std::uint32_t>(now - began_at_) > config_.startup_deadline_us) {
        latch_fault(BusFault::startup_timeout);
        return result_;
    }
    if (latest_.valid) {
        result_.sampled_at_us = latest_.started_at_us;
        result_.measurement = measure_acquired_bus(latest_, config_.factory_calibration,
                                                   now, config_.measurement_limits);
        if (!result_.measurement.valid()) {
            latch_fault(BusFault::measurement, result_.measurement.error);
            return result_;
        }
        if (result_.measurement.bus_v < config_.undervoltage_v) {
            latch_fault(BusFault::undervoltage);
            return result_;
        }
        if (result_.measurement.bus_v > config_.overvoltage_v) {
            latch_fault(BusFault::overvoltage);
            return result_;
        }
        phase_ = Phase::monitoring;
    } else {
        mono56_motor_inhibit();
    }
    if (!triggered_ || static_cast<std::uint32_t>(now - last_trigger_) >= config_.capture_period_us) {
        result_.acquisition = mono56_adc1_start();
        if (result_.acquisition == MONO56_ADC_PENDING) {
            triggered_ = true;
            last_trigger_ = now;
        } else if (result_.acquisition != MONO56_ADC_WARMING) {
            latch_fault(BusFault::acquisition);
        }
    }
    return result_;
}

bool BusSupervisor::stop() {
    mono56_motor_inhibit();
    latest_.valid = false;
    result_.measurement = {MeasurementError::missing_sample};
    if (owns_adc_) {
        result_.acquisition = mono56_adc1_shutdown();
        if (result_.acquisition != MONO56_ADC_NOT_INITIALIZED) {
            phase_ = Phase::fault;
            result_.fault = BusFault::acquisition;
            return false;
        }
        owns_adc_ = false;
    }
    phase_ = Phase::stopped;
    return true;
}

} // namespace odrive::mono56
