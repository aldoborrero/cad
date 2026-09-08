#include "driver_wake.hpp"
#include "driver_io.h"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_DRIVER_IO_TEST
#include "driver_io_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

namespace odrive::mono56 {
bool DriverWake::fail(DriverWakeError error) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (error_ == DriverWakeError::none)
        error_ = error;
    state_ = DriverWakeState::fault;
    mono56_motor_inhibit();
    __set_PRIMASK(mask);
    return false;
}
bool DriverWake::begin(const DriverWakeConfig &c) {
    if (__get_IPSR() || state_ != DriverWakeState::idle)
        return fail(DriverWakeError::invalid_state);
    if (!c.clock_us || !c.bus_permitted || c.sleep_us < 1001 || c.wake_us < 1001 ||
        c.sleep_us > 1000000 || c.wake_us > 1000000 || !c.feedback_timeout_us ||
        c.feedback_timeout_us > 1000000 || !c.max_service_gap_us || c.max_service_gap_us > 1000000)
        return fail(DriverWakeError::invalid_config);
    config_ = c;
    if (!mono56_driver_io_prepare())
        return fail(DriverWakeError::gpio_owner);
    phase_at_ = last_observed_ = config_.clock_us();
    state_ = DriverWakeState::waiting_off;
    return update() != DriverWakeState::fault;
}
DriverWakeState DriverWake::update() {
    if (__get_IPSR()) {
        fail(DriverWakeError::invalid_state);
        return state_;
    }
    if (state_ == DriverWakeState::timing) {
        check_timing(true);
        return state_;
    }
    if (state_ == DriverWakeState::idle)
        return state_;
    if (state_ == DriverWakeState::fault) {
        mono56_motor_inhibit();
        return state_;
    }
    const bool bus_ok = config_.bus_permitted(config_.bus_context);
    const auto r = mono56_driver_io_read();
    // Timestamp AFTER observing feedback: sleep/wake durations must never
    // include time preceding the confirmed LOW/HIGH level.
    const auto now = config_.clock_us();
    const auto gap = static_cast<std::uint32_t>(now - last_observed_);
    if (gap >= 0x80000000u) {
        fail(DriverWakeError::clock_error);
        return state_;
    }
    if (gap > config_.max_service_gap_us) {
        fail(DriverWakeError::service_late);
        return state_;
    }
    last_observed_ = now;
    if (!bus_ok)
        fail(DriverWakeError::bus_permission);
    else if (!r.valid)
        fail(DriverWakeError::gpio_configuration);
    else if (!r.quiet)
        fail(DriverWakeError::outputs_not_quiet);
    else if (!r.brake_ok || (r.falling_edges & MONO56_DRIVER_BRAKE_EDGE))
        fail(DriverWakeError::brake_permission);
    else if (r.falling_edges & MONO56_DRIVER_ENABLE_EDGE)
        fail(DriverWakeError::enable_history);
    if (state_ == DriverWakeState::fault)
        return state_;
    const bool expect_request = state_ == DriverWakeState::waiting_on ||
                                state_ == DriverWakeState::waking ||
                                state_ == DriverWakeState::awake;
    if (r.requested != expect_request) {
        fail(DriverWakeError::request_mismatch);
        return state_;
    }
    const auto elapsed = static_cast<std::uint32_t>(now - phase_at_);
    switch (state_) {
    case DriverWakeState::waiting_off:
        if (elapsed > config_.feedback_timeout_us) {
            fail(DriverWakeError::feedback_timeout);
        } else if (!r.enable_feedback) {
            state_ = DriverWakeState::sleeping;
            phase_at_ = now;
        }
        break;
    case DriverWakeState::sleeping:
        if (r.enable_feedback) {
            fail(DriverWakeError::enable_history);
        } else if (elapsed >= config_.sleep_us) {
            if (!mono56_driver_io_request_enable(config_.bus_permitted, config_.bus_context)) {
                fail(DriverWakeError::gpio_configuration);
                break;
            }
            state_ = DriverWakeState::waiting_on;
            phase_at_ = now;
        }
        break;
    case DriverWakeState::waiting_on:
        if (elapsed > config_.feedback_timeout_us) {
            fail(DriverWakeError::feedback_timeout);
        } else if (r.enable_feedback) {
            state_ = DriverWakeState::waking;
            phase_at_ = now;
        }
        break;
    case DriverWakeState::waking:
        if (!r.enable_feedback) {
            fail(DriverWakeError::enable_history);
        } else if (elapsed >= config_.wake_us) {
            if (!mono56_driver_io_qualify_nfault())
                fail(DriverWakeError::nfault);
            else
                state_ = DriverWakeState::awake;
        }
        break;
    case DriverWakeState::awake:
        if (!r.enable_feedback)
            fail(DriverWakeError::enable_history);
        else if (!r.nfault_high || (r.falling_edges & MONO56_DRIVER_FAULT_EDGE))
            fail(DriverWakeError::nfault);
        break;
    default:
        fail(DriverWakeError::invalid_state);
    }
    return state_;
}
void DriverWake::reset() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    mono56_driver_io_shutdown();
    state_ = DriverWakeState::idle;
    error_ = DriverWakeError::none;
    config_ = {};
    timing_ = {};
    __set_PRIMASK(mask);
}
bool DriverWake::permitted() {
    const auto result = update();
    return result == DriverWakeState::awake || result == DriverWakeState::timing;
}
bool DriverWake::begin_timing(Drv8353 &driver, const DriverTimingPermission &permission) {
    // SPI and the existing startup callbacks are foreground-only. Validate the
    // old state before entering the short atomic publication below.
    if (__get_IPSR() || __get_PRIMASK() || state_ != DriverWakeState::awake ||
        !permission.permitted)
        return fail(DriverWakeError::invalid_state);
    if (driver.io_.context != this || driver.io_.awake_and_permitted != awake_callback ||
        driver.io_.outputs_quiet != quiet_callback || driver.io_.nfault_high != nfault_callback ||
        driver.io_.inhibit != inhibit_callback || !driver.configured() || !driver.coasted() ||
        driver.calibrating() || !driver.check())
        return fail(DriverWakeError::register_session);
    if (update() != DriverWakeState::awake)
        return false;
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    const auto inputs = mono56_driver_io_read();
    if (!inputs.valid || !inputs.quiet || TIM1->CR2 != 0)
        fail(DriverWakeError::outputs_not_quiet);
    else {
        timing_ = permission;
        __DMB();
        state_ = DriverWakeState::timing;
        ok = check_timing(false);
    }
    __set_PRIMASK(mask);
    return ok;
}
bool DriverWake::check_timing(bool renew) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (state_ != DriverWakeState::timing)
        fail(DriverWakeError::invalid_state);
    else {
        const bool bus_ok = timing_.permitted(timing_.context);
        const auto inputs = mono56_driver_io_read();
        const auto now = config_.clock_us();
        const auto gap = static_cast<std::uint32_t>(now - last_observed_);
        if (!bus_ok)
            fail(DriverWakeError::bus_permission);
        else if (gap >= 0x80000000u)
            fail(DriverWakeError::clock_error);
        else if (gap > config_.max_service_gap_us)
            fail(DriverWakeError::service_late);
        else if (!inputs.valid)
            fail(DriverWakeError::gpio_configuration);
        else if (!inputs.pwm_inhibited)
            fail(DriverWakeError::outputs_not_quiet);
        else if (!inputs.requested)
            fail(DriverWakeError::request_mismatch);
        else if (!inputs.brake_ok || (inputs.falling_edges & MONO56_DRIVER_BRAKE_EDGE))
            fail(DriverWakeError::brake_permission);
        else if (!inputs.enable_feedback || (inputs.falling_edges & MONO56_DRIVER_ENABLE_EDGE))
            fail(DriverWakeError::enable_history);
        else if (!inputs.nfault_high || (inputs.falling_edges & MONO56_DRIVER_FAULT_EDGE))
            fail(DriverWakeError::nfault);
        else {
            if (renew)
                last_observed_ = now;
            ok = true;
        }
    }
    __set_PRIMASK(mask);
    return ok;
}
bool DriverWake::timing_permitted() { return check_timing(false); }
bool DriverWake::awake_callback(void *context) {
    return static_cast<DriverWake *>(context)->permitted();
}
bool DriverWake::quiet_callback(void *) {
    const auto r = mono56_driver_io_read();
    return r.valid && r.quiet;
}
bool DriverWake::nfault_callback(void *) { return mono56_driver_io_read().nfault_high; }
void DriverWake::inhibit_callback(void *context) {
    static_cast<DriverWake *>(context)->fail(DriverWakeError::register_session);
}
} // namespace odrive::mono56
