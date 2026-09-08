#include "bus_voltage.hpp"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>

using namespace odrive::mono56;

namespace {
int checks = 0;
void expect(bool condition, const char* message) {
    ++checks;
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}

std::uint16_t adc_code(double input_v, double supply_v) {
    // Independent ideal ADC stimulus, quantized to the nearest code.
    return static_cast<std::uint16_t>(std::lround(input_v / supply_v * 4096.0));
}

void expect_error(const BusMeasurement& result, MeasurementError error) {
    expect(!result.valid() && result.error == error, "invalid sample reason");
    expect(std::isnan(result.bus_v) && std::isnan(result.vdda_v),
           "invalid measurement must not publish a usable voltage");
}
} // namespace

int main() {
    // These limits are test fixtures, not a production timing specification.
    const MeasurementLimits limits{1000, 100, 3.0f, 3.6f};
    const std::uint16_t calibration = adc_code(1.21, 3.3);
    double maximum_error = 0;
    for (double supply : {3.135, 3.3, 3.465}) {
        for (double bus_v : {0.0, 12.0, 24.0, 48.0, 56.0, 58.0, 60.0, 65.0}) {
            auto result = measure_bus_voltage(
                {adc_code(bus_v / 22.0, supply), 1000, true},
                {adc_code(1.21, supply), 1000, true}, calibration, 1050, limits);
            expect(result.valid(), "ideal ADC sweep is accepted");
            const double error = std::abs(result.bus_v - bus_v);
            maximum_error = std::fmax(maximum_error, error);
            expect(error < 0.07, "reference tracking removes nominal supply variation");
            expect(std::abs(result.vdda_v - supply) < 0.003, "VDDA estimate");
        }
    }
    // Fixed conversion overestimates at low VDDA and underestimates at high VDDA.
    expect(std::abs(adc_code(58.0 / 22.0, 3.465) * 3.3 * 22.0 / 4096.0 - 58.0) > 2.7,
           "regression stimulus exposes the old fixed-reference error");
    const AdcSample bus{3000, 1000, true}, reference{calibration, 1000, true};
    auto run = [&](AdcSample b, AdcSample r, std::uint16_t cal, std::uint32_t now,
                   MeasurementLimits lim) {
        return measure_bus_voltage(b, r, cal, now, lim);
    };
    expect_error(run({}, reference, calibration, 1050, limits), MeasurementError::missing_sample);
    expect_error(run(bus, {}, calibration, 1050, limits), MeasurementError::missing_sample);
    for (auto cal : {0, 1, 1000, 2000, 4095, 65535}) {
        expect_error(run(bus, reference, cal, 1050, limits), MeasurementError::invalid_calibration);
    }
    for (auto raw : {0, 4095, 65535}) {
        auto r = reference; r.raw = raw;
        expect_error(run(bus, r, calibration, 1050, limits), MeasurementError::invalid_reference);
    }
    for (auto raw : {4095, 65535}) {
        auto b = bus; b.raw = raw;
        expect_error(run(b, reference, calibration, 1050, limits), MeasurementError::bus_adc_saturated);
    }
    for (bool change_bus : {false, true}) {
        for (auto timestamp : {0u, 1051u}) {
            auto b = bus, r = reference;
            (change_bus ? b : r).sampled_at_us = timestamp;
            expect_error(run(b, r, calibration, 1050, limits), MeasurementError::stale_or_future_sample);
        }
    }
    expect(run(bus, reference, calibration, 2000, limits).valid(), "exact maximum age accepted");
    expect_error(run(bus, reference, calibration, 2001, limits), MeasurementError::stale_or_future_sample);
    for (bool change_bus : {false, true}) {
        auto b = bus, r = reference;
        (change_bus ? b : r).sampled_at_us = 900;
        expect(run(b, r, calibration, 1050, limits).valid(), "exact maximum skew accepted");
        (change_bus ? b : r).sampled_at_us = 899;
        expect_error(run(b, r, calibration, 1050, limits), MeasurementError::excessive_pair_skew);
    }
    auto wrapped_bus = bus, wrapped_ref = reference;
    wrapped_bus.sampled_at_us = 0xfffffff0u;
    wrapped_ref.sampled_at_us = 0xffffffe0u;
    expect(run(wrapped_bus, wrapped_ref, calibration, 20, limits).valid(), "timestamp wrap accepted");
    expect_error(run(wrapped_bus, wrapped_ref, calibration, 2000, limits), MeasurementError::stale_or_future_sample);
    for (double supply : {2.8, 3.8}) {
        auto r = reference; r.raw = adc_code(1.21, supply);
        expect_error(run(bus, r, calibration, 1050, limits), MeasurementError::supply_out_of_range);
    }
    for (auto age : {0u, 0x80000000u, 0xffffffffu}) {
        auto lim = limits; lim.max_age_us = age;
        expect_error(run(bus, reference, calibration, 1050, lim), MeasurementError::invalid_limits);
    }
    auto lim = limits; lim.max_pair_skew_us = 1001;
    expect_error(run(bus, reference, calibration, 1050, lim), MeasurementError::invalid_limits);
    for (float invalid : {0.0f, 3.6f, std::numeric_limits<float>::quiet_NaN(),
                          std::numeric_limits<float>::infinity()}) {
        lim = limits; lim.vdda_min_v = invalid;
        expect_error(run(bus, reference, calibration, 1050, lim), MeasurementError::invalid_limits);
    }
    for (float invalid : {3.0f, 3.7f, std::numeric_limits<float>::quiet_NaN(),
                          std::numeric_limits<float>::infinity()}) {
        lim = limits; lim.vdda_max_v = invalid;
        expect_error(run(bus, reference, calibration, 1050, lim), MeasurementError::invalid_limits);
    }
    // No cached last-good value may survive a subsequent invalid input.
    expect(run(bus, reference, calibration, 1050, limits).valid(), "valid before dropout");
    expect_error(run(bus, {}, calibration, 1050, limits), MeasurementError::missing_sample);
    std::cout << checks << " checks passed; ideal quantized sweep max error "
              << maximum_error << " V. Not a hardware accuracy bound.\n";
}
