#include "phase_current.hpp"
#include <algorithm>
#include <cmath>
#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ > 0)
#error "Current validation requires IEEE finite/NaN semantics"
#endif
namespace odrive::mono56 {
namespace {
constexpr std::uint32_t half_range = 0x80000000u;
bool positive(float v) { return std::isfinite(v) && v > 0; }
bool close_times(std::uint32_t a, std::uint32_t b, std::uint32_t limit) {
    return std::min(static_cast<std::uint32_t>(a - b), static_cast<std::uint32_t>(b - a)) <= limit;
}
CurrentError validate_frame(const CurrentFrame &f, const CurrentConfig &c, std::uint32_t now) {
    if (!f.b.valid || !f.c.valid || !f.supply.valid)
        return CurrentError::missing_frame;
    if (static_cast<std::uint32_t>(now - f.b.sampled_at_us) > c.max_age_us ||
        static_cast<std::uint32_t>(now - f.c.sampled_at_us) > c.max_age_us ||
        static_cast<std::uint32_t>(now - f.supply.sampled_at_us) > c.max_age_us)
        return CurrentError::stale_frame;
    if (!close_times(f.b.sampled_at_us, f.c.sampled_at_us, c.max_pair_skew_us) ||
        !close_times(f.b.sampled_at_us, f.supply.sampled_at_us, c.max_supply_skew_us) ||
        !close_times(f.c.sampled_at_us, f.supply.sampled_at_us, c.max_supply_skew_us))
        return CurrentError::skew;
    const float supply = f.supply.vdda_v;
    if (!std::isfinite(supply) || supply < c.vdda_min_v || supply > c.vdda_max_v)
        return CurrentError::invalid_supply;
    for (auto raw : {f.b.raw, f.c.raw}) {
        const float v = raw * (supply / adc_full_scale);
        if (raw == 0 || raw >= 4095 || v <= c.rail_margin_v || v >= supply - c.rail_margin_v)
            return CurrentError::clipped;
    }
    return CurrentError::none;
}
} // namespace
bool valid_current_config(const CurrentConfig &c) {
    if (!positive(c.shunt_b_ohm) || !positive(c.shunt_c_ohm) ||
        !(c.gain == 5 || c.gain == 10 || c.gain == 20 || c.gain == 40) ||
        !(c.polarity_b == 1 || c.polarity_b == -1) || !(c.polarity_c == 1 || c.polarity_c == -1) ||
        !c.max_age_us || c.max_age_us >= half_range || c.max_pair_skew_us > c.max_age_us ||
        c.max_supply_skew_us > c.max_age_us || !c.max_zero_age_us ||
        c.max_zero_age_us >= half_range || !std::isfinite(c.vdda_min_v) ||
        !std::isfinite(c.vdda_max_v) || c.vdda_min_v < 2.4f || c.vdda_max_v > 3.6f ||
        c.vdda_min_v >= c.vdda_max_v || !std::isfinite(c.rail_margin_v) ||
        c.rail_margin_v < 0.25f || !positive(c.max_abs_phase_current_a) ||
        !positive(c.max_zero_offset_codes) || c.max_zero_offset_codes >= 2048 ||
        !positive(c.max_calibration_supply_change_v) ||
        c.max_calibration_supply_change_v > c.vdda_max_v - c.vdda_min_v)
        return false;
    const float headroom = c.vdda_min_v / 2 - c.rail_margin_v -
                           c.max_zero_offset_codes * c.vdda_max_v / adc_full_scale;
    const float required =
        c.max_abs_phase_current_a * c.gain * std::max(c.shunt_b_ohm, c.shunt_c_ohm);
    return positive(headroom) && positive(required) && required < headroom &&
           positive(adc_full_scale * c.gain * c.shunt_b_ohm) &&
           positive(adc_full_scale * c.gain * c.shunt_c_ohm);
}
PhaseCurrents measure_phase_currents(const CurrentFrame &f, const CurrentZero &z,
                                     const CurrentConfig &c, std::uint32_t now) {
    if (!valid_current_config(c))
        return {CurrentError::invalid_config};
    const auto error = validate_frame(f, c, now);
    if (error != CurrentError::none)
        return {error};
    if (f.calibration_inputs_shorted)
        return {CurrentError::calibration_mode};
    if (!f.low_side_window_valid)
        return {CurrentError::invalid_window};
    if (!z.valid || z.gain != c.gain || !std::isfinite(z.b_code) || !std::isfinite(z.c_code) ||
        std::abs(z.b_code - 2048) > c.max_zero_offset_codes ||
        std::abs(z.c_code - 2048) > c.max_zero_offset_codes || !std::isfinite(z.vdda_v) ||
        z.vdda_v < c.vdda_min_v || z.vdda_v > c.vdda_max_v)
        return {CurrentError::invalid_zero};
    if (!f.driver_session || f.driver_session != z.driver_session)
        return {CurrentError::session_mismatch};
    if (static_cast<std::uint32_t>(now - z.completed_at_us) > c.max_zero_age_us)
        return {CurrentError::calibration_stale};
    if (std::abs(f.supply.vdda_v - z.vdda_v) > c.max_calibration_supply_change_v)
        return {CurrentError::calibration_supply_changed};
    const float b = c.polarity_b * (f.b.raw - z.b_code) * f.supply.vdda_v /
                    (adc_full_scale * c.gain * c.shunt_b_ohm);
    const float cc = c.polarity_c * (f.c.raw - z.c_code) * f.supply.vdda_v /
                     (adc_full_scale * c.gain * c.shunt_c_ohm);
    const float a = -(b + cc);
    if (!std::isfinite(a) || !std::isfinite(b) || !std::isfinite(cc) ||
        std::abs(a) > c.max_abs_phase_current_a || std::abs(b) > c.max_abs_phase_current_a ||
        std::abs(cc) > c.max_abs_phase_current_a)
        return {CurrentError::current_limit};
    return {CurrentError::none, a, b, cc};
}
bool CurrentZeroEstimator::fail(CurrentError e) {
    if (error_ == CurrentError::none)
        error_ = e;
    state_ = CurrentZeroState::fault;
    zero_.valid = false;
    return false;
}
bool CurrentZeroEstimator::begin(const CurrentConfig &c, const CurrentZeroConfig &r,
                                 std::uint32_t session, std::uint32_t now) {
    if (state_ != CurrentZeroState::idle)
        return fail(CurrentError::invalid_state);
    if (!valid_current_config(c) || !session || r.samples < 2 || r.samples > 4096 || !r.settle_us ||
        r.settle_us >= half_range || !r.min_span_us || r.timeout_us >= half_range ||
        static_cast<std::uint64_t>(r.settle_us) + r.min_span_us > r.timeout_us ||
        !r.max_peak_to_peak_codes || r.max_peak_to_peak_codes >= 4095)
        return fail(CurrentError::invalid_config);
    config_ = c;
    request_ = r;
    began_ = last_now_ = now;
    zero_.driver_session = session;
    zero_.gain = c.gain;
    state_ = CurrentZeroState::collecting;
    return true;
}
CurrentZeroState CurrentZeroEstimator::add(const CurrentFrame &f, std::uint32_t now) {
    if (state_ == CurrentZeroState::fault)
        return state_;
    if (state_ != CurrentZeroState::collecting) {
        fail(CurrentError::invalid_state);
        return state_;
    }
    if (static_cast<std::uint32_t>(now - last_now_) >= half_range ||
        static_cast<std::uint32_t>(now - began_) > request_.timeout_us) {
        fail(CurrentError::calibration_timeout);
        return state_;
    }
    last_now_ = now;
    const auto error = validate_frame(f, config_, now);
    if (error != CurrentError::none) {
        fail(error);
        return state_;
    }
    if (f.driver_session != zero_.driver_session) {
        fail(CurrentError::session_mismatch);
        return state_;
    }
    if (!f.calibration_inputs_shorted) {
        fail(CurrentError::calibration_mode);
        return state_;
    }
    for (auto stamp : {f.b.sampled_at_us, f.c.sampled_at_us})
        if (static_cast<std::uint32_t>(stamp - began_) >= half_range ||
            static_cast<std::uint32_t>(stamp - began_) < request_.settle_us) {
            fail(CurrentError::calibration_not_settled);
            return state_;
        }
    if (count_ && (static_cast<std::uint32_t>(f.b.sampled_at_us - last_b_) == 0 ||
                   static_cast<std::uint32_t>(f.c.sampled_at_us - last_c_) == 0 ||
                   static_cast<std::uint32_t>(f.b.sampled_at_us - last_b_) >= half_range ||
                   static_cast<std::uint32_t>(f.c.sampled_at_us - last_c_) >= half_range)) {
        fail(CurrentError::duplicate_frame);
        return state_;
    }
    if (std::abs(static_cast<float>(f.b.raw) - 2048) > config_.max_zero_offset_codes ||
        std::abs(static_cast<float>(f.c.raw) - 2048) > config_.max_zero_offset_codes) {
        fail(CurrentError::zero_offset);
        return state_;
    }
    if (!count_) {
        first_b_ = f.b.sampled_at_us;
        first_c_ = f.c.sampled_at_us;
        supply_min_ = supply_max_ = f.supply.vdda_v;
    }
    last_b_ = f.b.sampled_at_us;
    last_c_ = f.c.sampled_at_us;
    min_b_ = std::min(min_b_, f.b.raw);
    max_b_ = std::max(max_b_, f.b.raw);
    min_c_ = std::min(min_c_, f.c.raw);
    max_c_ = std::max(max_c_, f.c.raw);
    supply_min_ = std::min(supply_min_, f.supply.vdda_v);
    supply_max_ = std::max(supply_max_, f.supply.vdda_v);
    if (max_b_ - min_b_ > request_.max_peak_to_peak_codes ||
        max_c_ - min_c_ > request_.max_peak_to_peak_codes) {
        fail(CurrentError::zero_noise);
        return state_;
    }
    if (supply_max_ - supply_min_ > config_.max_calibration_supply_change_v) {
        fail(CurrentError::calibration_supply_changed);
        return state_;
    }
    sum_b_ += f.b.raw;
    sum_c_ += f.c.raw;
    ++count_;
    // Running mean preserves a constant supply exactly, including at a configured
    // supply boundary. Summing thousands of floats can drift outside that bound.
    if (count_ == 1)
        supply_mean_ = f.supply.vdda_v;
    else
        supply_mean_ += (f.supply.vdda_v - supply_mean_) / count_;
    if (count_ == request_.samples) {
        if (static_cast<std::uint32_t>(f.b.sampled_at_us - first_b_) < request_.min_span_us ||
            static_cast<std::uint32_t>(f.c.sampled_at_us - first_c_) < request_.min_span_us) {
            fail(CurrentError::calibration_too_short);
            return state_;
        }
        zero_.b_code = static_cast<float>(sum_b_) / count_;
        zero_.c_code = static_cast<float>(sum_c_) / count_;
        zero_.vdda_v = supply_mean_;
        zero_.completed_at_us = now;
        zero_.valid = true;
        state_ = CurrentZeroState::ready;
    }
    return state_;
}
void CurrentZeroEstimator::reset() {
    state_ = CurrentZeroState::idle;
    error_ = CurrentError::none;
    zero_.valid = false;
    count_ = sum_b_ = sum_c_ = 0;
    min_b_ = min_c_ = 4095;
    max_b_ = max_c_ = 0;
    supply_mean_ = 0;
    // begin()/the first frame replace all other session/configuration fields.
}
} // namespace odrive::mono56
