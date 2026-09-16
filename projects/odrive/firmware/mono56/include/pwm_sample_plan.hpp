#pragma once
#include <cstdint>

namespace odrive::mono56 {
// Fixed board clock contract: TIM1=168 MHz, PSC=0, CKD=0; PCLK2=84 MHz;
// ADC2/3 independent, 21 MHz, 12-bit, 15 sample cycles, no regular sequence.
// Channels 1..3: center-aligned PWM1, active-high CHx and CHxN, complementary.
// Channel 4: PWM2 OC4REF -> TRGO rising on upcount, exactly once per full cycle.
struct PwmSampleConfig {
    std::uint32_t half_period_ticks;
    std::uint32_t dead_time_ns;
    // Required board-qualified bounds, NOT data-sheet typical/default values.
    // From low-side MCU input rise until gate/shunt/CSA/RC signal is settled;
    // includes the driver's own delay/dead time, MOSFET commutation and filtering.
    std::uint32_t low_side_settle_ns;
    std::uint32_t edge_margin_ns;
    std::uint32_t min_input_pulse_ns;
    // Maximum underflow-to-both-ADCs-armed time, and conversion-complete-to-
    // both-data-observed time. Includes masking/preemption/handler execution.
    std::uint32_t arm_budget_ns, completion_service_ns;
};
enum class PwmSampleError {
    none,
    invalid_config,
    dead_time_range,
    duty_range,
    short_pulse,
    no_sample_window,
    capture_deadline
};
struct PwmSamplePlan {
    PwmSampleError error = PwmSampleError::invalid_config;
    std::uint32_t ccr_a = 0, ccr_b = 0, ccr_c = 0, ccr4 = 0;
    std::uint32_t period_ticks = 0, dead_time_ticks = 0;
    std::uint32_t quiet_begin_tick = 0, quiet_end_tick = 0, conversion_end_tick = 0;
    std::uint32_t min_trigger_spacing_us = 0, capture_deadline_us = 0;
    std::uint8_t dead_time_code = 0;
    [[nodiscard]] bool valid() const { return error == PwmSampleError::none; }
};
// Pure prospective timing calculation. Does not touch hardware, grant PWM
// permission, or prove low_side_window_valid for an acquired CurrentFrame.
// The runtime owner must prove these are the ACTIVE compares for the entire
// cycle, arm before ccr4, reject deadline/missed-update faults, and guarantee no
// software UG/extra trigger or compare transfer interrupts the sampling window.
// A/B/C compares are actual PWM1 high-side duties: duty = CCR / ARR.
// Requests are never silently clamped or rescaled. Errors return no usable plan.
[[nodiscard]] PwmSamplePlan make_pwm_sample_plan(const PwmSampleConfig &, std::uint32_t ccr_a,
                                                 std::uint32_t ccr_b, std::uint32_t ccr_c);
} // namespace odrive::mono56
