#pragma once
#include "bus_voltage.hpp"
#include <cstdint>

namespace odrive::mono56 {
struct CurrentSupply {
    float vdda_v;
    std::uint32_t sampled_at_us;
    bool valid;
};
struct CurrentFrame {
    AdcSample b, c; // SOB -> PC0; SOC -> PC1. These are NOT phases A/B.
    CurrentSupply supply;
    std::uint32_t driver_session;
    bool low_side_window_valid;
    bool calibration_inputs_shorted;
};
struct CurrentConfig {
    float shunt_b_ohm, shunt_c_ohm;
    std::uint8_t gain;
    // Explicit motor-current sign relative to positive SPx-SNx shunt voltage.
    // Neither pin names nor the old ODrive driver establish this board's sign.
    std::int8_t polarity_b, polarity_c;
    std::uint32_t max_age_us, max_pair_skew_us, max_supply_skew_us, max_zero_age_us;
    float vdda_min_v, vdda_max_v, rail_margin_v, max_abs_phase_current_a;
    float max_zero_offset_codes, max_calibration_supply_change_v;
};
enum class CurrentError {
    none,
    invalid_config,
    missing_frame,
    stale_frame,
    skew,
    invalid_supply,
    clipped,
    invalid_window,
    calibration_mode,
    invalid_zero,
    session_mismatch,
    calibration_stale,
    calibration_supply_changed,
    current_limit,
    invalid_state,
    calibration_timeout,
    calibration_not_settled,
    duplicate_frame,
    zero_offset,
    zero_noise,
    calibration_too_short
};
struct CurrentZero {
    float b_code = 0, c_code = 0, vdda_v = 0;
    std::uint32_t completed_at_us = 0, driver_session = 0;
    std::uint8_t gain = 0;
    bool valid = false;
};
struct PhaseCurrents {
    CurrentError error;
    float a = std::numeric_limits<float>::quiet_NaN();
    float b = std::numeric_limits<float>::quiet_NaN();
    float c = std::numeric_limits<float>::quiet_NaN();
    [[nodiscard]] bool valid() const { return error == CurrentError::none; }
};
[[nodiscard]] bool valid_current_config(const CurrentConfig &config);
// Two low-side shunts yield B/C only in a qualified simultaneous conduction /
// settling window. A = -(B+C) additionally assumes a three-wire motor. This
// function does not establish the window, act on PWM, or grant motor permission.
[[nodiscard]] PhaseCurrents measure_phase_currents(const CurrentFrame &frame,
                                                   const CurrentZero &zero,
                                                   const CurrentConfig &config,
                                                   std::uint32_t now_us);
struct CurrentZeroConfig {
    std::uint32_t samples, settle_us, min_span_us, timeout_us;
    std::uint16_t max_peak_to_peak_codes;
};
enum class CurrentZeroState { idle, collecting, ready, fault };
// Software zero estimator. The caller must first put the DRV8353 B/C amplifiers
// into verified MANUAL CSA_CAL mode while COASTed. COAST alone cannot prove zero
// current (a moving motor may rectify). This class never writes those registers.
class CurrentZeroEstimator {
  public:
    [[nodiscard]] bool begin(const CurrentConfig &, const CurrentZeroConfig &,
                             std::uint32_t driver_session, std::uint32_t now_us);
    CurrentZeroState add(const CurrentFrame &, std::uint32_t now_us);
    void reset();
    [[nodiscard]] CurrentZeroState state() const { return state_; }
    [[nodiscard]] CurrentError error() const { return error_; }
    [[nodiscard]] CurrentZero zero() const { return zero_; }

  private:
    bool fail(CurrentError);
    CurrentConfig config_{};
    CurrentZeroConfig request_{};
    CurrentZero zero_{};
    CurrentZeroState state_ = CurrentZeroState::idle;
    CurrentError error_ = CurrentError::none;
    std::uint32_t began_ = 0, last_now_ = 0, first_b_ = 0, first_c_ = 0, last_b_ = 0, last_c_ = 0;
    std::uint32_t count_ = 0, sum_b_ = 0, sum_c_ = 0;
    std::uint16_t min_b_ = 4095, min_c_ = 4095, max_b_ = 0, max_c_ = 0;
    float supply_mean_ = 0, supply_min_ = 0, supply_max_ = 0;
};
} // namespace odrive::mono56
