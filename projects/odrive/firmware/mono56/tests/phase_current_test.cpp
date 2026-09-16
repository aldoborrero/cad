#include "phase_current.hpp"
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
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
CurrentConfig config() {
    return {0.001f, 0.001f, 20, 1, 1, 100, 5, 50, 1000000, 3.0f, 3.6f, 0.30f, 40.0f, 16.0f, 0.05f};
}
CurrentFrame frame(uint32_t stamp = 10, uint16_t b = 2050, uint16_t c = 2045) {
    return {{b, stamp, true}, {c, stamp + 1, true}, {3.3f, stamp, true}, 7, false, true};
}
CurrentZero calibrated() {
    CurrentZeroEstimator z;
    expect(z.begin(config(), {8, 10, 700, 2000, 4}, 7, 0),
           "zero collection begins with explicit limits");
    expect(!z.zero().valid, "begin never fabricates a zero");
    for (unsigned i = 0; i < 8; ++i) {
        const auto state = z.add(frame(10 + 100 * i), 12 + 100 * i);
        expect(state == (i == 7 ? CurrentZeroState::ready : CurrentZeroState::collecting),
               "zero needs the full sample count and observed span");
    }
    auto result = z.zero();
    expect(result.valid && result.b_code == 2050 && result.c_code == 2045 &&
               result.completed_at_us == 712,
           "separate channel offsets and completion timestamp retained");
    return result;
}
void rejected(CurrentFrame f, CurrentZero z, CurrentConfig c, uint32_t now, CurrentError error) {
    auto value = measure_phase_currents(f, z, c, now);
    expect(value.error == error && !value.valid() && std::isnan(value.a) && std::isnan(value.b) &&
               std::isnan(value.c),
           "invalid current never returns plausible numeric phases");
}
} // namespace
int main() {
    auto c = config();
    auto z = calibrated();
    auto f = frame(800, 2298, 1921);
    f.calibration_inputs_shorted = false;
    f.low_side_window_valid = true;
    auto value = measure_phase_currents(f, z, c, 802);
    expect(value.valid() && std::abs(value.b - 9.990234375) < 0.00001 &&
               std::abs(value.c + 4.9951171875) < 0.00001 &&
               std::abs(value.a + 4.9951171875) < 0.00001,
           "B/C use their own measured zero; A is negative B+C");
    auto half_shunt = c;
    half_shunt.shunt_b_ohm = 0.0005f;
    expect(std::abs(measure_phase_currents(f, z, half_shunt, 802).b - 2 * value.b) < 0.00001f,
           "500 uohm assumption doubles the inferred current versus the exported 1 mohm shunt");
    auto reversed = c;
    reversed.polarity_b = reversed.polarity_c = -1;
    auto negative = measure_phase_currents(f, z, reversed, 802);
    expect(negative.valid() && std::abs(negative.b + value.b) < 0.00001f &&
               std::abs(negative.a + value.a) < 0.00001f,
           "phase polarity is an explicit integration choice");
    // Independent double-precision oracle over gain, supply and signed raw displacement.
    for (uint8_t gain : {5, 10, 20, 40})
        for (float supply : {3.0f, 3.3f, 3.6f}) {
            auto g = c;
            g.gain = gain;
            g.max_abs_phase_current_a = 20;
            auto zero = z;
            zero.gain = gain;
            zero.vdda_v = supply;
            for (int displacement = -100; displacement <= 100; displacement += 5) {
                auto sample = f;
                sample.supply.vdda_v = supply;
                sample.b.raw = 2050 + displacement;
                sample.c.raw = 2045 - displacement;
                auto result = measure_phase_currents(sample, zero, g, 802);
                const double expected =
                    displacement * static_cast<double>(supply) / (4096.0 * gain * 0.001);
                expect(result.valid() && std::abs(result.b - expected) < 0.00002 &&
                           std::abs(result.c + expected) < 0.00002 && std::abs(result.a) < 0.00002,
                       "gain/supply/sign sweep agrees with independent numeric oracle");
            }
        }
    {
        auto sample = f;
        sample.b.valid = false;
        rejected(sample, z, c, 802, CurrentError::missing_frame);
    }
    rejected(f, z, c, 901, CurrentError::stale_frame);
    {
        auto sample = f;
        sample.c.sampled_at_us = 806;
        rejected(sample, z, c, 807, CurrentError::skew);
    }
    {
        auto sample = f;
        sample.supply.sampled_at_us = 749;
        rejected(sample, z, c, 802, CurrentError::skew);
    }
    {
        auto sample = f;
        sample.supply.vdda_v = std::numeric_limits<float>::quiet_NaN();
        rejected(sample, z, c, 802, CurrentError::invalid_supply);
    }
    for (uint16_t raw : {0, 1, 300, 3800, 4095, 65535}) {
        auto sample = f;
        sample.b.raw = raw;
        rejected(sample, z, c, 802, CurrentError::clipped);
    }
    {
        auto sample = f;
        sample.calibration_inputs_shorted = true;
        rejected(sample, z, c, 802, CurrentError::calibration_mode);
    }
    {
        auto sample = f;
        sample.low_side_window_valid = false;
        rejected(sample, z, c, 802, CurrentError::invalid_window);
    }
    {
        auto zero = z;
        zero.valid = false;
        rejected(f, zero, c, 802, CurrentError::invalid_zero);
    }
    {
        auto zero = z;
        zero.gain = 10;
        rejected(f, zero, c, 802, CurrentError::invalid_zero);
    }
    {
        auto sample = f;
        sample.driver_session = 8;
        rejected(sample, z, c, 802, CurrentError::session_mismatch);
    }
    {
        auto sample = f;
        sample.supply.vdda_v = 3.4f;
        rejected(sample, z, c, 802, CurrentError::calibration_supply_changed);
    }
    {
        auto zero = z;
        zero.completed_at_us = 900;
        rejected(f, zero, c, 802, CurrentError::calibration_stale);
    }
    {
        auto sample = frame(1000800, 2298, 1921);
        sample.calibration_inputs_shorted = false;
        sample.low_side_window_valid = true;
        rejected(sample, z, c, 1000802, CurrentError::calibration_stale);
    }
    {
        auto sample = f;
        sample.b.raw = 2800;
        sample.c.raw = 2800;
        rejected(sample, z, c, 802, CurrentError::current_limit);
    }
    for (unsigned mutation = 0; mutation < 10; ++mutation) {
        auto bad = c;
        if (mutation == 0)
            bad.shunt_b_ohm = 0;
        if (mutation == 1)
            bad.shunt_c_ohm = std::numeric_limits<float>::infinity();
        if (mutation == 2)
            bad.gain = 80;
        if (mutation == 3)
            bad.polarity_b = 0;
        if (mutation == 4)
            bad.max_age_us = 0x80000000u;
        if (mutation == 5)
            bad.vdda_min_v = 2.3f;
        if (mutation == 6)
            bad.rail_margin_v = 0.24f;
        if (mutation == 7)
            bad.max_abs_phase_current_a = 100;
        if (mutation == 8)
            bad.max_zero_offset_codes = 2048;
        if (mutation == 9)
            bad.max_calibration_supply_change_v = 0;
        rejected(f, z, bad, 802, CurrentError::invalid_config);
    }
    for (unsigned mutation = 0; mutation < 10; ++mutation) {
        CurrentZeroEstimator estimator;
        expect(estimator.begin(c, {8, 10, 700, 2000, 4}, 7, 0),
               "negative calibration fixture begins");
        expect(estimator.add(frame(), 12) == CurrentZeroState::collecting,
               "first calibration frame accepted");
        auto bad = frame(110);
        uint32_t now = 112;
        CurrentError expected = CurrentError::calibration_mode;
        if (mutation == 0)
            bad.calibration_inputs_shorted = false;
        if (mutation == 1) {
            bad.driver_session = 8;
            expected = CurrentError::session_mismatch;
        }
        if (mutation == 2) {
            bad.b.raw = 2100;
            expected = CurrentError::zero_offset;
        }
        if (mutation == 3) {
            bad.c.raw = 2050;
            expected = CurrentError::zero_noise;
        }
        if (mutation == 4) {
            bad = frame();
            now = 13;
            expected = CurrentError::duplicate_frame;
        }
        if (mutation == 5) {
            now = 2001;
            expected = CurrentError::calibration_timeout;
        }
        if (mutation == 6) {
            now = 11;
            expected = CurrentError::calibration_timeout;
        }
        if (mutation == 7) {
            bad.supply.vdda_v = 3.36f;
            expected = CurrentError::calibration_supply_changed;
        }
        if (mutation == 8) {
            // Both samples remain fresh; only the B/C separation is invalid.
            bad.c.sampled_at_us = 104;
            expected = CurrentError::skew;
        }
        if (mutation == 9) {
            bad.b.valid = false;
            expected = CurrentError::missing_frame;
        }
        estimator.add(bad, now);
        if (estimator.error() != expected)
            std::cerr << "calibration case " << mutation << ": expected "
                      << static_cast<int>(expected) << ", got "
                      << static_cast<int>(estimator.error()) << '\n';
        expect(estimator.state() == CurrentZeroState::fault && estimator.error() == expected &&
                   !estimator.zero().valid,
               "bad calibration frame discards readiness and retains first error");
        expect(!estimator.begin(c, {8, 10, 700, 2000, 4}, 7, 0) && estimator.error() == expected,
               "begin cannot bypass failed calibration");
        estimator.reset();
        expect(estimator.begin(c, {8, 10, 700, 2000, 4}, 9, 100),
               "explicit new-session calibration after reset");
    }
    {
        CurrentZeroEstimator e;
        expect(e.begin(c, {2, 10, 700, 2000, 4}, 7, 0), "minimum-span fixture");
        e.add(frame(), 12);
        e.add(frame(110), 112);
        expect(e.error() == CurrentError::calibration_too_short,
               "sample count alone cannot complete calibration");
    }
    {
        CurrentZeroEstimator e;
        expect(e.begin(c, {2, 10, 100, 2000, 4}, 7, 0), "per-channel span fixture");
        auto first = frame(10);
        first.c.sampled_at_us = 15;
        e.add(first, 16);
        auto last = frame(110);
        last.c.sampled_at_us = 110;
        e.add(last, 112);
        expect(e.error() == CurrentError::calibration_too_short,
               "both sampled channels must cover the minimum calibration span");
    }
    {
        CurrentZeroEstimator e;
        expect(e.begin(c, {2, 10, 100, 2000, 4}, 7, 0), "settling fixture");
        e.add(frame(9), 12);
        expect(e.error() == CurrentError::calibration_not_settled, "pre-settling samples rejected");
    }
    {
        CurrentZeroEstimator e;
        uint32_t start = 0xfffffff0;
        expect(e.begin(c, {2, 10, 100, 2000, 4}, 7, start), "wrap fixture begins");
        e.add(frame(start + 10), start + 12);
        e.add(frame(start + 110), start + 112);
        expect(e.zero().valid, "calibration timestamps handle normal counter wrap");
    }
    {
        CurrentZeroEstimator e;
        auto boundary = c;
        boundary.vdda_min_v = 3.3f;
        expect(e.begin(boundary, {4096, 10, 4095, 5000, 4}, 7, 0),
               "maximum collection length at the lower supply boundary");
        for (unsigned i = 0; i < 4096; ++i)
            e.add(frame(10 + i), 12 + i);
        auto sample = frame(4110);
        sample.calibration_inputs_shorted = false;
        sample.low_side_window_valid = true;
        expect(e.zero().valid && e.zero().vdda_v == 3.3f &&
                   measure_phase_currents(sample, e.zero(), boundary, 4112).valid(),
               "float accumulation cannot invalidate a constant in-range reference");
    }
    std::cout << checks
              << " current conversion/zero-estimation checks passed with synthetic samples.\n";
}
