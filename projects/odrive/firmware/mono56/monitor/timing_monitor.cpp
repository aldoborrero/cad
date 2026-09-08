#include "timing_monitor.hpp"
#include "driver_monitor.hpp"
#include "monitor.h"
#include "monitor_current_config.h"
#include "monitor_timing_config.h"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif
#include <algorithm>
#include <cmath>

using namespace odrive::mono56;
extern "C" {
volatile TimingMonitorDiagnostics mono56_timing_monitor;
}
namespace {
volatile TimingMonitorState state = TimingMonitorState::uninitialized;
volatile TimingMonitorError error = TimingMonitorError::none;
CurrentZero zero;
PwmCaptureFrame frame;
CurrentSupply supply{};
std::uint32_t samples = 0;
bool frame_valid = false;
bool fail(TimingMonitorError e) {
    if (error == TimingMonitorError::none)
        error = e;
    state = TimingMonitorState::fault;
    frame_valid = false;
    mono56_motor_inhibit();
    pwm_capture_abort();
    return false;
}
void publish() {
    ++mono56_timing_monitor.sequence;
    __DMB();
    mono56_timing_monitor.magic = 0x4d353654; // M56T
    mono56_timing_monitor.version = 1;
    mono56_timing_monitor.observed_at_us = TIM5->CNT;
    mono56_timing_monitor.state = static_cast<std::uint32_t>(state);
    mono56_timing_monitor.error = static_cast<std::uint32_t>(error);
    mono56_timing_monitor.capture_state = static_cast<std::uint32_t>(pwm_capture_state());
    mono56_timing_monitor.capture_error = static_cast<std::uint32_t>(pwm_capture_error());
    mono56_timing_monitor.cycle_error = static_cast<std::uint32_t>(pwm_cycle_error());
    mono56_timing_monitor.samples = samples;
    mono56_timing_monitor.cycle = frame.cycle.cycle;
    mono56_timing_monitor.b_raw = frame.adc.b_raw;
    mono56_timing_monitor.c_raw = frame.adc.c_raw;
    mono56_timing_monitor.armed_at_us = frame.adc.armed_at_us;
    mono56_timing_monitor.complete_at_us = frame.adc.observed_complete_at_us;
    mono56_timing_monitor.supply_at_us = supply.sampled_at_us;
    mono56_timing_monitor.supply_v = supply.vdda_v;
    mono56_timing_monitor.b_zero_code = zero.b_code;
    mono56_timing_monitor.c_zero_code = zero.c_code;
    mono56_timing_monitor.zero_completed_at_us = zero.completed_at_us;
    mono56_timing_monitor.driver_session = zero.driver_session;
    mono56_timing_monitor.frame_valid = frame_valid && !mono56_driver_monitor_fault;
    __DMB();
    ++mono56_timing_monitor.sequence;
}
bool permission() { return mono56_driver_monitor_timing_permitted(nullptr); }
bool zero_valid() {
    return zero.valid && zero.driver_session == 1 &&
           zero.gain == monitor_current_config.current.gain &&
           static_cast<std::uint32_t>(TIM5->CNT - zero.completed_at_us) <=
               monitor_current_config.current.max_zero_age_us;
}
void consume() {
    if (state != TimingMonitorState::running)
        return;
    if (!permission()) {
        fail(TimingMonitorError::permission);
        return;
    }
    PwmCaptureFrame next;
    if (!pwm_capture_take(&next)) {
        if (pwm_capture_state() == PwmCaptureState::fault)
            fail(TimingMonitorError::capture);
        return;
    }
    frame_valid = false;
    frame = next;
    const auto &c = monitor_current_config.current;
    const auto &t = monitor_timing_config;
    supply.valid = mono56_monitor_supply(&supply.vdda_v, &supply.sampled_at_us);
    const auto width = static_cast<std::uint64_t>(static_cast<std::uint32_t>(
                           frame.adc.observed_complete_at_us - frame.adc.armed_at_us)) +
                       1;
    const auto separation =
        std::min(static_cast<std::uint32_t>(supply.sampled_at_us - frame.adc.armed_at_us),
                 static_cast<std::uint32_t>(frame.adc.armed_at_us - supply.sampled_at_us));
    if (!frame.valid || !frame.adc.valid || !frame.cycle.valid || width > c.max_pair_skew_us ||
        static_cast<std::uint32_t>(TIM5->CNT - frame.adc.armed_at_us) > c.max_age_us)
        fail(TimingMonitorError::bounds);
    else if (!supply.valid || !std::isfinite(supply.vdda_v) || supply.vdda_v < c.vdda_min_v ||
             supply.vdda_v > c.vdda_max_v || separation + width > c.max_supply_skew_us)
        fail(TimingMonitorError::supply);
    else if (!zero_valid() ||
             std::abs(supply.vdda_v - zero.vdda_v) > c.max_calibration_supply_change_v)
        fail(TimingMonitorError::zero);
    else if (!pwm_capture_queue(frame.cycle.cycle + 1, t.a, t.b, t.c))
        fail(TimingMonitorError::capture);
    else {
        ++samples;
        frame_valid = true; // Timed raw diagnostic data, not valid phase currents.
    }
}
void irq(void (*service)()) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (state != TimingMonitorState::running || !permission())
        fail(TimingMonitorError::permission);
    else {
        service();
        consume();
    }
    publish();
    __set_PRIMASK(mask);
}
} // namespace
namespace odrive::mono56 {
bool timing_monitor_begin(const CurrentZero &calibration) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    zero = calibration;
    const auto &c = monitor_timing_config;
    const auto plan = make_pwm_sample_plan(c.sampling, c.a, c.b, c.c);
    const PwmCaptureConfig capture{c.sampling,
                                   nullptr,
                                   mono56_driver_monitor_timing_permitted,
                                   c.boundary_budget_ns,
                                   c.commit_budget_ns,
                                   c.adc_deadline_us,
                                   c.min_trigger_spacing_us};
    if (state != TimingMonitorState::uninitialized)
        fail(TimingMonitorError::invalid_state);
    else if (!plan.valid() || !valid_current_config(monitor_current_config.current))
        fail(TimingMonitorError::configuration);
    else if (!zero_valid())
        fail(TimingMonitorError::zero);
    else if (!permission())
        fail(TimingMonitorError::permission);
    else if (!pwm_capture_init(capture))
        fail(TimingMonitorError::capture);
    else {
        state = TimingMonitorState::warming;
        ok = true;
    }
    publish();
    __set_PRIMASK(mask);
    return ok;
}
bool timing_monitor_step() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (!permission())
        fail(TimingMonitorError::permission);
    else if (state == TimingMonitorState::warming) {
        const auto &c = monitor_timing_config;
        if (pwm_capture_start(c.a, c.b, c.c))
            state = TimingMonitorState::running;
        else if (pwm_capture_state() == PwmCaptureState::fault)
            fail(TimingMonitorError::capture);
    } else if (state != TimingMonitorState::running ||
               pwm_capture_state() == PwmCaptureState::fault)
        fail(TimingMonitorError::capture);
    if (!zero_valid())
        fail(TimingMonitorError::zero);
    publish();
    const bool ok = state != TimingMonitorState::fault;
    __set_PRIMASK(mask);
    return ok;
}
void timing_monitor_abort() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    fail(TimingMonitorError::permission);
    publish();
    __set_PRIMASK(mask);
}
bool timing_monitor_faulted() { return state == TimingMonitorState::fault; }
void timing_monitor_adc_irq() { irq(pwm_capture_adc_irq); }
void timing_monitor_update_irq() { irq(pwm_capture_update_irq); }
void timing_monitor_deadline_irq() { irq(pwm_capture_deadline_irq); }
} // namespace odrive::mono56
