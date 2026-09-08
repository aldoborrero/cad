#include "current_monitor.hpp"
#include "current_capture.h"
#include "driver_monitor.hpp"
#include "monitor.h"
#include "monitor_current_config.h"
#include "monitor_driver_config.h"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif
#include <algorithm>
#ifdef MONO56_MONITOR_TIMING
#include "timing_monitor.hpp"
#endif

using namespace odrive::mono56;
extern "C" {
volatile CurrentMonitorDiagnostics mono56_current_monitor;
}
namespace {
CurrentZeroEstimator estimator;
CurrentMonitorState state = CurrentMonitorState::uninitialized;
CurrentMonitorError error = CurrentMonitorError::none;
std::uint32_t began = 0, last_start = 0, samples = 0;
mono56_adc23_frame last_frame{};
CurrentSupply last_supply{};
// Single foreground owner; static storage avoids compiler-generated memset
// for aggregate/padding initialization in the no-CRT diagnostic image.
CurrentFrame sample{};
bool started = false;
std::uint32_t clock_us() {
#ifdef MONO56_DIAGNOSTIC_TEST
    return mono56_diagnostic_test_clock();
#else
    return TIM5->CNT;
#endif
}
bool fail(CurrentMonitorError e) {
    if (error == CurrentMonitorError::none)
        error = e;
    state = CurrentMonitorState::fault;
    mono56_motor_inhibit();
    return false;
}
void publish() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    ++mono56_current_monitor.sequence;
    __DMB();
    mono56_current_monitor.magic = 0x4d353643; // M56C
    mono56_current_monitor.version = 1;
    mono56_current_monitor.observed_at_us = clock_us();
    mono56_current_monitor.state = static_cast<std::uint32_t>(state);
    mono56_current_monitor.error = static_cast<std::uint32_t>(error);
    mono56_current_monitor.capture_status = mono56_current_capture_status();
    mono56_current_monitor.adc_status = mono56_current_capture_adc_status();
    mono56_current_monitor.estimator_error = static_cast<std::uint32_t>(estimator.error());
    mono56_current_monitor.samples = samples;
    mono56_current_monitor.b_raw = last_frame.b_raw;
    mono56_current_monitor.c_raw = last_frame.c_raw;
    mono56_current_monitor.armed_at_us = last_frame.armed_at_us;
    mono56_current_monitor.observed_complete_at_us = last_frame.observed_complete_at_us;
    mono56_current_monitor.supply_at_us = last_supply.sampled_at_us;
    mono56_current_monitor.supply_v = last_supply.vdda_v;
    const auto zero = estimator.zero();
    mono56_current_monitor.b_zero_code = zero.b_code;
    mono56_current_monitor.c_zero_code = zero.c_code;
    mono56_current_monitor.zero_supply_v = zero.vdda_v;
    mono56_current_monitor.zero_completed_at_us = zero.completed_at_us;
    mono56_current_monitor.calibration_completed =
        !mono56_driver_monitor_fault && zero.valid &&
        ((state == CurrentMonitorState::completed &&
          mono56_current_capture_status() == MONO56_CAPTURE_IDLE) ||
         state == CurrentMonitorState::transferred);
    __DMB();
    ++mono56_current_monitor.sequence;
    __set_PRIMASK(mask);
}
bool service(Drv8353 &driver) {
    const auto &c = monitor_current_config;
    if (state == CurrentMonitorState::fault)
        return false;
    if (!mono56_driver_monitor_current_permitted(nullptr))
        return fail(CurrentMonitorError::permission);
    if (state == CurrentMonitorState::completed)
        return true;
    if (state == CurrentMonitorState::uninitialized) {
        // Bound arithmetic before adding capture uncertainty to the zero span.
        if (!valid_current_config(c.current) ||
            c.current.gain != monitor_driver_config.gate.csa_gain ||
            c.current.shunt_b_ohm != 0.001f || c.current.shunt_c_ohm != 0.001f ||
            c.capture_deadline_us < 3 || c.capture_deadline_us >= 1000000 ||
            c.period_us <= c.capture_deadline_us + 1 || c.period_us > 1000000 ||
            c.current.max_pair_skew_us < c.capture_deadline_us + 1 || c.zero.timeout_us > 1000000 ||
            c.zero.min_span_us > 1000000 || c.zero.settle_us > 1000000 || c.zero.samples < 2 ||
            c.zero.samples > 4096 || !c.zero.settle_us || !c.zero.min_span_us ||
            !c.zero.max_peak_to_peak_codes || c.zero.max_peak_to_peak_codes >= 4095 ||
            static_cast<std::uint64_t>(c.zero.settle_us) + c.zero.min_span_us +
                    c.capture_deadline_us + 1 >
                c.zero.timeout_us)
            return fail(CurrentMonitorError::invalid_config);
        const mono56_capture_config capture{mono56_driver_monitor_current_permitted, nullptr,
                                            c.period_us, c.capture_deadline_us};
        if (mono56_current_capture_init(&capture) != MONO56_CAPTURE_IDLE)
            return fail(CurrentMonitorError::capture);
        if (!driver.begin_current_calibration())
            return fail(CurrentMonitorError::registers);
        began = clock_us(); // Settling begins AFTER the verified register transaction.
        auto zero_request = c.zero;
        // Both samples lie somewhere in their capture bounds. Requiring this
        // extra span prevents an early last sample/late first sample from
        // appearing to meet the requested physical collection duration.
        zero_request.min_span_us += c.capture_deadline_us + 1;
        if (!estimator.begin(c.current, zero_request, 1, began))
            return fail(CurrentMonitorError::estimator);
        state = CurrentMonitorState::settling;
    }
    auto now = clock_us();
    if (static_cast<std::uint32_t>(now - began) > c.zero.timeout_us)
        return fail(CurrentMonitorError::timeout); // Includes no-frame silence.
    if (!driver.calibrating() || !driver.coasted())
        return fail(CurrentMonitorError::registers);
    if (static_cast<std::uint32_t>(now - began) < c.zero.settle_us)
        return true;
    state = CurrentMonitorState::collecting;
    mono56_adc23_frame frame;
    const auto captured = mono56_current_capture_take(&frame);
    if (captured >= MONO56_CAPTURE_BAD_CONFIG || captured == MONO56_CAPTURE_UNINITIALIZED)
        return fail(CurrentMonitorError::capture);
    if (captured == MONO56_CAPTURE_READY) {
        last_frame = frame;
        last_supply.valid = mono56_monitor_supply(&last_supply.vdda_v, &last_supply.sampled_at_us);
        if (!last_supply.valid)
            return fail(CurrentMonitorError::supply);
        const auto duration =
            static_cast<std::uint32_t>(frame.observed_complete_at_us - frame.armed_at_us);
        const auto width = static_cast<std::uint64_t>(duration) + 1;
        const auto separation =
            std::min(static_cast<std::uint32_t>(last_supply.sampled_at_us - frame.armed_at_us),
                     static_cast<std::uint32_t>(frame.armed_at_us - last_supply.sampled_at_us));
        if (!frame.valid || duration > c.capture_deadline_us ||
            width > c.current.max_pair_skew_us || separation + width > c.current.max_supply_skew_us)
            return fail(CurrentMonitorError::bounds);
        // Earliest bounds conservatively age both readings. The interval checks
        // above establish skew; equal stored stamps do not claim simultaneity.
        sample.b.raw = frame.b_raw;
        sample.c.raw = frame.c_raw;
        sample.b.sampled_at_us = sample.c.sampled_at_us = frame.armed_at_us;
        sample.b.valid = sample.c.valid = true;
        sample.supply = last_supply;
        sample.driver_session = 1;
        sample.low_side_window_valid = false;
        sample.calibration_inputs_shorted = driver.calibrating();
        const auto result = estimator.add(sample, clock_us());
        if (result == CurrentZeroState::fault)
            return fail(CurrentMonitorError::estimator);
        ++samples;
        if (result == CurrentZeroState::ready) {
            // shutdown() would lower ENABLE before these SPI writes. Leave the
            // idle capture owner allocated; normal input restoration comes first.
            if (!driver.end_current_calibration())
                return fail(CurrentMonitorError::registers);
            if (!mono56_driver_monitor_current_permitted(nullptr))
                return fail(CurrentMonitorError::permission);
            state = CurrentMonitorState::completed;
            return true;
        }
    }
    if (mono56_current_capture_status() != MONO56_CAPTURE_IDLE)
        return true;
    now = clock_us();
    if (started && static_cast<std::uint32_t>(now - last_start) < c.period_us)
        return true;
    // Verify manual input shorts immediately before every capture. This owner
    // performs no SPI while a capture or unread mailbox is outstanding.
    if (!driver.check())
        return fail(CurrentMonitorError::registers);
    if (static_cast<std::uint32_t>(clock_us() - began) > c.zero.timeout_us)
        return fail(CurrentMonitorError::timeout);
    const auto result = mono56_current_capture_start();
    if (result != MONO56_CAPTURE_PENDING)
        return fail(CurrentMonitorError::capture);
    last_start = clock_us();
    started = true;
    return true;
}
} // namespace
namespace odrive::mono56 {
bool current_monitor_step(Drv8353 &driver) {
    const bool ok = service(driver);
    publish();
    return ok;
}
void current_monitor_abort() {
    fail(CurrentMonitorError::permission);
    publish();
}
bool current_monitor_completed() { return state == CurrentMonitorState::completed; }
bool current_monitor_release(CurrentZero *out) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (out)
        out->valid = false;
    if (!out || state != CurrentMonitorState::completed || !estimator.zero().valid)
        fail(CurrentMonitorError::estimator);
    else if (!mono56_current_capture_release())
        fail(CurrentMonitorError::capture);
    else {
        *out = estimator.zero();
        state = CurrentMonitorState::transferred;
        ok = true;
    }
    publish();
    __set_PRIMASK(mask);
    return ok;
}
} // namespace odrive::mono56
extern "C" void ADC_IRQHandler() {
#ifdef MONO56_MONITOR_TIMING
    if (mono56_driver_monitor_timing_active())
        timing_monitor_adc_irq();
    else
#endif
        mono56_current_capture_adc_irq();
    mono56_driver_monitor_irq_guard();
}
extern "C" void TIM5_IRQHandler() {
#ifdef MONO56_MONITOR_TIMING
    if (mono56_driver_monitor_timing_active())
        timing_monitor_deadline_irq();
    else
#endif
        mono56_current_capture_deadline_irq();
    mono56_driver_monitor_irq_guard();
}
#ifdef MONO56_MONITOR_TIMING
extern "C" void TIM1_UP_TIM10_IRQHandler() {
    timing_monitor_update_irq();
    mono56_driver_monitor_irq_guard();
}
#endif
