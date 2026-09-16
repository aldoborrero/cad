#include "pwm_sample_plan.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <vector>

using namespace odrive::mono56;
namespace {
unsigned checks = 0;
void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
unsigned ns_ticks(unsigned ns) {
    // Exact rational oracle: binary floating point can put an exact tick just
    // above its boundary, e.g. ceil(125 * 0.168), and invent an extra tick.
    return static_cast<unsigned>((static_cast<std::uint64_t>(ns) * 168000000 + 999999999) /
                                 1000000000);
}
std::array<unsigned, 256> dead_times() {
    std::array<unsigned, 256> result{};
    unsigned index = 0;
    // Enumerate the four RM0090 hardware ranges, rather than decode bitfields.
    for (unsigned delay = 0; delay <= 127; ++delay)
        result[index++] = delay;
    for (unsigned delay = 128; delay <= 254; delay += 2)
        result[index++] = delay;
    for (unsigned delay = 256; delay <= 504; delay += 8)
        result[index++] = delay;
    for (unsigned delay = 512; delay <= 1008; delay += 16)
        result[index++] = delay;
    return result;
}
PwmSampleConfig fixture() { return {3500, 200, 2500, 100, 500, 2000, 2000}; }

// Independent discrete counter/output model. It walks three complete PWM1
// cycles, applies turn-on dead time to both complementary pins, records actual
// low-input rises and searches every upcount trigger for a quiet conversion.
// It does not use the planner's max-compare quiet-window expressions.
void waveform_oracle(const PwmSampleConfig &c, std::array<unsigned, 3> compares) {
    const auto plan = make_pwm_sample_plan(c, compares[0], compares[1], compares[2]);
    const unsigned arr = c.half_period_ticks, period = 2 * arr;
    const auto delays = dead_times();
    const auto dt = std::lower_bound(delays.begin(), delays.end(), ns_ticks(c.dead_time_ns));
    expect(dt != delays.end(), "oracle fixture has encodable dead time");
    const auto dead = *dt;
    std::array<bool, 3> old_ref{}, old_high{}, old_low{};
    std::array<unsigned, 3> changed{}, low_rise{}, high_width{}, low_width{};
    std::array<bool, 3> saw_high{}, saw_low{};
    std::vector<bool> settled(3 * period), raw_low(3 * period);
    bool pulses_valid = true, no_overlap = true;
    const auto settle = ns_ticks(c.low_side_settle_ns) + ns_ticks(c.edge_margin_ns) + 1;
    for (unsigned t = 0; t < 3 * period; ++t) {
        const unsigned pos = t % period;
        const bool down = pos >= arr;
        const unsigned counter = down ? period - pos : pos;
        bool all_settled = true, all_low = true;
        for (unsigned ch = 0; ch < 3; ++ch) {
            const bool ref = down ? counter <= compares[ch] : counter < compares[ch];
            if (t == 0 || ref != old_ref[ch])
                changed[ch] = t;
            const bool high = ref && t - changed[ch] >= dead;
            const bool low = !ref && t - changed[ch] >= dead;
            if (t >= period) {
                saw_high[ch] = saw_high[ch] || high;
                saw_low[ch] = saw_low[ch] || low;
            }
            no_overlap &= !(high && low);
            if (low && !old_low[ch])
                low_rise[ch] = t;
            if (!high && old_high[ch] && t > period)
                pulses_valid &= high_width[ch] >= ns_ticks(c.min_input_pulse_ns);
            if (!low && old_low[ch] && t > period)
                pulses_valid &= low_width[ch] >= ns_ticks(c.min_input_pulse_ns);
            high_width[ch] = high ? high_width[ch] + 1 : 0;
            low_width[ch] = low ? low_width[ch] + 1 : 0;
            all_settled &= low && t - low_rise[ch] >= settle;
            all_low &= !ref;
            old_ref[ch] = ref;
            old_high[ch] = high;
            old_low[ch] = low;
        }
        settled[t] = all_settled;
        raw_low[t] = all_low;
    }
    expect(no_overlap, "modeled complementary GPIO inputs never overlap");
    for (unsigned ch = 0; ch < 3; ++ch)
        pulses_valid &= saw_high[ch] && saw_low[ch];
    const auto margin = ns_ticks(c.edge_margin_ns) + 1;
    std::vector<unsigned> bad(period + 1);
    for (unsigned t = 0; t < period; ++t) {
        bool quiet = settled[period + t];
        for (unsigned future = 0; future < margin; ++future)
            quiet &= raw_low[period + t + future];
        bad[t + 1] = bad[t] + !quiet;
    }
    const unsigned spacing = static_cast<unsigned>(std::floor(period / 168.0));
    bool possible = false, chosen_valid = false;
    for (unsigned trigger = 1; trigger < arr; ++trigger) {
        // Include the latest conversion endpoint in the independent waveform.
        const auto end = trigger + 242;
        if (end >= period)
            continue;
        const auto deadline =
            std::max(3u, static_cast<unsigned>(std::ceil(
                             (trigger + 242 + ns_ticks(c.completion_service_ns)) / 168.0)));
        const bool good = pulses_valid && trigger > ns_ticks(c.arm_budget_ns) &&
                          bad[end + 1] == bad[trigger] && deadline + 1 < spacing;
        possible |= good;
        if (trigger == plan.ccr4)
            chosen_valid = good;
    }
    expect(plan.valid() == possible, "planner accepts exactly the independently feasible cycles");
    if (plan.valid()) {
        expect(chosen_valid,
               "chosen trigger keeps entire conversion inside settled low-side window");
        expect(plan.ccr_a == compares[0] && plan.ccr_b == compares[1] && plan.ccr_c == compares[2],
               "requested voltage duties are not silently clipped or permuted");
        expect(plan.period_ticks == period && plan.dead_time_ticks == dead &&
                   plan.min_trigger_spacing_us == spacing && plan.capture_deadline_us + 1 < spacing,
               "plan preserves frequency, realized dead time and ADC deadline separation");
    } else
        expect(plan.ccr4 == 0 && plan.period_ticks == 0 && plan.dead_time_ticks == 0,
               "rejected request carries no usable old timer plan");
}
} // namespace
int main() {
    auto c = fixture();
    auto p = make_pwm_sample_plan(c, 1750, 1750, 1750);
    expect(p.valid(), "24 kHz fixture has a valid sampling window");
    expect(p.dead_time_code == 34 && p.dead_time_ticks == 34,
           "200 ns MCU dead time rounds upward to 34 timer ticks");
    expect(p.ccr4 == 3379 && p.conversion_end_tick == 3621 && p.capture_deadline_us == 24 &&
               p.min_trigger_spacing_us == 41,
           "fixture conversion includes external trigger latency and full SAR time");
    expect(make_pwm_sample_plan(c, 58, 1750, 1750).error == PwmSampleError::short_pulse &&
               make_pwm_sample_plan(c, 59, 1750, 1750).valid(),
           "minimum input pulse includes actual timer dead time");
    expect(make_pwm_sample_plan(c, 3027, 1750, 1750).valid() &&
               make_pwm_sample_plan(c, 3028, 1750, 1750).error == PwmSampleError::no_sample_window,
           "one-tick boundary for the settled all-low interval is enforced");
    for (auto value : {0u, 3500u, 3501u, std::numeric_limits<unsigned>::max()})
        for (unsigned phase = 0; phase < 3; ++phase) {
            std::array<unsigned, 3> compares{1750, 1750, 1750};
            compares[phase] = value;
            expect(make_pwm_sample_plan(c, compares[0], compares[1], compares[2]).error ==
                       PwmSampleError::duty_range,
                   "out-of-range/static rail duty rejected on every phase");
        }
    for (unsigned field = 0; field < 7; ++field)
        for (auto value : {0u, std::numeric_limits<unsigned>::max()}) {
            auto invalid = fixture();
            std::array<unsigned *, 7> fields{&invalid.half_period_ticks,    &invalid.dead_time_ns,
                                             &invalid.low_side_settle_ns,   &invalid.edge_margin_ns,
                                             &invalid.min_input_pulse_ns,   &invalid.arm_budget_ns,
                                             &invalid.completion_service_ns};
            *fields[field] = value;
            expect(make_pwm_sample_plan(invalid, 1750, 1750, 1750).error ==
                       PwmSampleError::invalid_config,
                   "missing/overflowing clock and timing inputs rejected before arithmetic");
        }
    // Every requested nanosecond across all four nonlinear DTG ranges.
    const auto delays = dead_times();
    for (unsigned ns = 1; ns <= 6000; ++ns) {
        auto config = fixture();
        config.half_period_ticks = 65535;
        config.dead_time_ns = ns;
        const auto plan = make_pwm_sample_plan(config, 15000, 16000, 17000);
        const auto chosen = std::lower_bound(delays.begin(), delays.end(), ns_ticks(ns));
        expect(plan.valid() && plan.dead_time_code == chosen - delays.begin() &&
                   plan.dead_time_ticks == *chosen &&
                   static_cast<std::uint64_t>(plan.dead_time_ticks) * 1000000000 >=
                       static_cast<std::uint64_t>(ns) * 168000000,
               "DTG always uses the shortest representable delay no smaller than requested");
    }
    c.dead_time_ns = 6001;
    expect(make_pwm_sample_plan(c, 1750, 1750, 1750).error == PwmSampleError::dead_time_range,
           "dead time above hardware range is rejected, never truncated");
    c = fixture();
    // Enough analog window exists, but servicing a centered capture is too late.
    // The planner must search earlier, not reject an otherwise possible cycle.
    c.completion_service_ns = 20000;
    p = make_pwm_sample_plan(c, 700, 800, 900);
    expect(p.valid() && p.ccr4 < 3379 && p.capture_deadline_us == 39,
           "completion budget moves trigger earlier while preserving the analog window");
    waveform_oracle(c, {700, 800, 900});
    c.completion_service_ns = 1000000;
    expect(make_pwm_sample_plan(c, 700, 800, 900).error == PwmSampleError::capture_deadline,
           "impossible service budget cannot accept a fresh-looking late frame");
    for (auto a : {59u, 1750u, 2800u, 3027u, 3028u, 3400u})
        for (auto b : {59u, 1750u, 2800u, 3027u, 3028u, 3400u})
            waveform_oracle(fixture(), {a, b, 1700});
    // Deterministic random sweeps vary all three phases, period and timing.
    unsigned rng = 0x835356;
    auto random = [&]() {
        rng = rng * 1664525u + 1013904223u;
        return rng;
    };
    for (unsigned trial = 0; trial < 250; ++trial) {
        auto config = fixture();
        config.half_period_ticks = 500 + random() % 4000;
        config.dead_time_ns = 1 + random() % 1500;
        config.low_side_settle_ns = 1 + random() % 5000;
        config.edge_margin_ns = 1 + random() % 100;
        config.min_input_pulse_ns = 1 + random() % 1000;
        config.arm_budget_ns = 1 + random() % 5000;
        config.completion_service_ns = 1 + random() % 20000;
        std::array<unsigned, 3> compares{};
        for (auto &value : compares)
            value = 1 + random() % (config.half_period_ticks - 1);
        waveform_oracle(config, compares);
    }
    std::cout << checks << " PWM sampling-plan checks passed with independent counter waveforms.\n";
}
