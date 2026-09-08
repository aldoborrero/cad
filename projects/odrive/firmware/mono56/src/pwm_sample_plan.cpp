#include "pwm_sample_plan.hpp"
#include <algorithm>

namespace odrive::mono56 {
namespace {
// All ns inputs are capped at 1 ms before multiplication (<=168,000,000).
// Ceiling guarantees neither a fractional tick nor DTG's nonlinear encoding
// shortens any requested bound. PSC=CKD=0 is part of this module's contract.
std::uint32_t ticks(std::uint32_t ns) { return (ns * 168u + 999u) / 1000u; }
std::uint32_t decode_dead_time(std::uint32_t code) {
    if (code < 128)
        return code;
    if (code < 192)
        return (64 + (code & 63)) * 2;
    if (code < 224)
        return (32 + (code & 31)) * 8;
    return (32 + (code & 31)) * 16;
}
PwmSamplePlan fail(PwmSampleError e) {
    PwmSamplePlan plan;
    plan.error = e;
    return plan;
}
} // namespace
PwmSamplePlan make_pwm_sample_plan(const PwmSampleConfig &c, std::uint32_t a, std::uint32_t b,
                                   std::uint32_t cc) {
    if (c.half_period_ticks < 2 || c.half_period_ticks > 65535)
        return fail(PwmSampleError::invalid_config);
    for (auto ns : {c.dead_time_ns, c.low_side_settle_ns, c.edge_margin_ns, c.min_input_pulse_ns,
                    c.arm_budget_ns, c.completion_service_ns})
        if (!ns || ns > 1000000)
            return fail(PwmSampleError::invalid_config);
    const auto requested_dead = ticks(c.dead_time_ns);
    std::uint32_t code = 0;
    while (code < 256 && decode_dead_time(code) < requested_dead)
        ++code;
    if (code == 256)
        return fail(PwmSampleError::dead_time_range);
    const auto dead = decode_dead_time(code);
    const auto arr = c.half_period_ticks;
    for (auto compare : {a, b, cc}) {
        if (!compare || compare >= arr)
            return fail(PwmSampleError::duty_range);
        // Complementary turn-on is delayed, turn-off is not. Full pulse widths
        // are twice the corresponding half-period lengths, less actual DTG.
        const auto shortest_reference_pulse = 2 * std::min(compare, arr - compare);
        if (shortest_reference_pulse < dead + ticks(c.min_input_pulse_ns))
            return fail(PwmSampleError::short_pulse);
    }
    const auto last_rising_compare = std::max({a, b, cc});
    const auto margin = ticks(c.edge_margin_ns) + 1u; // Include one edge/compare tick.
    const auto quiet_begin = last_rising_compare + dead + ticks(c.low_side_settle_ns) + margin;
    const auto next_falling_compare = 2 * arr - last_rising_compare;
    if (margin >= next_falling_compare)
        return fail(PwmSampleError::no_sample_window);
    const auto quiet_end = next_falling_compare - margin;
    // DS8626: injected trigger latency <=3 ADC clocks + 1 PCLK2 clock.
    // Sampling+12-bit conversion =15+12 ADC clocks. At the fixed board clocks
    // this is (3+15+12)*8+2 =242 TIM1 ticks. Reserve the whole conversion, not
    // just the final sample instant, inside a quiet all-low-side interval.
    constexpr std::uint32_t conversion_ticks = (3 + 15 + 12) * 8 + 2;
    if (quiet_end < conversion_ticks)
        return fail(PwmSampleError::no_sample_window);
    const auto earliest = std::max(quiet_begin, ticks(c.arm_budget_ns) + 1u);
    auto latest = std::min(arr - 1, quiet_end - conversion_ticks);
    if (earliest > latest)
        return fail(PwmSampleError::no_sample_window);
    const auto spacing_us = 2 * arr / 168; // Floor the true full-period spacing.
    if (spacing_us < 5)
        return fail(PwmSampleError::capture_deadline);
    const auto completion_ticks = conversion_ticks + ticks(c.completion_service_ns);
    // ADC ownership requires deadline_us+1 < spacing_us. Reserve that margin
    // while selecting the trigger, rather than rejecting a late preferred
    // trigger when an earlier valid one exists.
    const auto available_ticks = (spacing_us - 2) * 168;
    if (completion_ticks > available_ticks)
        return fail(PwmSampleError::capture_deadline);
    latest = std::min(latest, available_ticks - completion_ticks);
    if (earliest > latest)
        return fail(PwmSampleError::capture_deadline);
    // Prefer a conversion straddling the apex; shift toward the available
    // settled interval if necessary. Keep CCR4 strictly inside the upcount.
    const auto preferred = arr > conversion_ticks / 2 ? arr - conversion_ticks / 2 : 1u;
    const auto trigger = std::clamp(preferred, earliest, latest);
    const auto deadline_ticks = trigger + completion_ticks;
    const auto deadline_us = std::max<std::uint32_t>(3, (deadline_ticks + 167) / 168);
    PwmSamplePlan p;
    p.error = PwmSampleError::none;
    p.ccr_a = a;
    p.ccr_b = b;
    p.ccr_c = cc;
    p.ccr4 = trigger;
    p.period_ticks = 2 * arr;
    p.dead_time_ticks = dead;
    p.dead_time_code = static_cast<std::uint8_t>(code);
    p.quiet_begin_tick = quiet_begin;
    p.quiet_end_tick = quiet_end;
    p.conversion_end_tick = trigger + conversion_ticks;
    p.capture_deadline_us = deadline_us;
    p.min_trigger_spacing_us = spacing_us;
    return p;
}
} // namespace odrive::mono56
