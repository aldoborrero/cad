#include "driver_monitor.hpp"
#include "driver_io.h"
#include "monitor.h"
#include "monitor_driver_config.h"
#include "motor_inhibit.h"
#include "spi3_transport.h"
#include "stm32f405xx.h"
#ifdef MONO56_MONITOR_TIMING
#include "timing_monitor.hpp"
#endif
#ifdef MONO56_MONITOR_CURRENT
#include "current_capture.h"
#include "current_monitor.hpp"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

using namespace odrive::mono56;
extern "C" {
volatile DriverMonitorDiagnostics mono56_driver_monitor;
volatile std::uint32_t mono56_driver_monitor_fault;
}
namespace {
DriverWake wake;
Drv8353 driver(wake.io(mono56_drv8353_spi3_exchange));
DriverMonitorState state = DriverMonitorState::uninitialized;
volatile std::uint32_t guard_active = 0, watch_feedback = 0, watch_nfault = 0, heartbeat = 0;
std::uint32_t started = 0, last_check = 0, checks_completed = 0;
#ifdef MONO56_MONITOR_TIMING
volatile bool timing_active = false;
bool timing_bus_permission(void *) {
    return !mono56_driver_monitor_fault && mono56_monitor_bus_permitted(nullptr);
}
#endif
std::uint32_t clock_us() {
#ifdef MONO56_DIAGNOSTIC_TEST
    return mono56_diagnostic_test_clock();
#else
    return TIM5->CNT;
#endif
}
void trip(DriverMonitorError error) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (!mono56_driver_monitor_fault)
        mono56_driver_monitor_fault = static_cast<std::uint32_t>(error);
    mono56_motor_inhibit();
#ifdef MONO56_MONITOR_TIMING
    if (timing_active)
        timing_monitor_abort();
#endif
    __set_PRIMASK(mask);
}
bool bus_permission(void *) {
    // Only foreground wake/register callbacks feed this heartbeat. The IRQ
    // guard uses the underlying bus accessor and cannot renew its own lease.
    heartbeat = clock_us();
    return !mono56_driver_monitor_fault && mono56_monitor_bus_permitted(nullptr);
}
void publish() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    ++mono56_driver_monitor.sequence;
    __DMB();
    mono56_driver_monitor.magic = 0x4d353647; // M56G
    mono56_driver_monitor.version = 1;
    mono56_driver_monitor.observed_at_us = clock_us();
    mono56_driver_monitor.state = static_cast<std::uint32_t>(state);
    mono56_driver_monitor.error = mono56_driver_monitor_fault;
    mono56_driver_monitor.wake_state = static_cast<std::uint32_t>(wake.state());
    mono56_driver_monitor.wake_error = static_cast<std::uint32_t>(wake.error());
    mono56_driver_monitor.spi_status = static_cast<std::uint32_t>(mono56_spi3_status());
    mono56_driver_monitor.register_error = static_cast<std::uint32_t>(driver.error());
    mono56_driver_monitor.configured_coasted = !mono56_driver_monitor_fault && driver.coasted();
    const auto faults = driver.faults();
    // An IRQ-only failure must not relabel an old healthy register pair as a
    // current fault snapshot. Preserve a pair read for a real device fault.
    mono56_driver_monitor.fault_registers_valid =
        faults.valid &&
        (!mono56_driver_monitor_fault || driver.error() == Drv8353Error::hardware_fault);
    mono56_driver_monitor.packed_faults = faults.packed();
    mono56_driver_monitor.failed_address = driver.failed_address();
    mono56_driver_monitor.checks_completed = checks_completed;
    __DMB();
    ++mono56_driver_monitor.sequence;
    __set_PRIMASK(mask);
}
} // namespace

extern "C" bool mono56_driver_monitor_begin() {
    mono56_motor_inhibit();
    if (state != DriverMonitorState::uninitialized || __get_PRIMASK() == 0) {
        trip(DriverMonitorError::invalid_state);
        return false;
    }
    const auto &c = monitor_driver_config;
    Drv8353Registers encoded;
    if (!make_drv8353_registers(c.gate, encoded) || c.sleep_us < 1001 || c.sleep_us > 1000000 ||
        c.wake_us < 1001 || c.wake_us > 1000000 || !c.feedback_timeout_us ||
        c.feedback_timeout_us > 1000000 || c.max_service_gap_us < 125 ||
        c.max_service_gap_us > 1000000 || c.spi_deadline_us < 60 || c.spi_deadline_us > 1000 ||
        c.spi_deadline_us >= c.max_service_gap_us || !c.bus_wait_timeout_us ||
        c.bus_wait_timeout_us > 1000000 || !c.register_check_period_us ||
        c.register_check_period_us > 1000000) {
        trip(DriverMonitorError::invalid_config);
        return false;
    }
    started = clock_us();
    state = DriverMonitorState::waiting_bus;
    publish();
    return true;
}
extern "C" void mono56_driver_monitor_irq_guard() {
#ifdef MONO56_MONITOR_CURRENT
    if (mono56_current_capture_status() >= MONO56_CAPTURE_BAD_CONFIG)
        trip(DriverMonitorError::current);
#endif
    if (mono56_driver_monitor_fault) {
        mono56_motor_inhibit();
        return;
    }
    if (!guard_active)
        return;
#ifdef MONO56_MONITOR_TIMING
    if (timing_active) {
        if (timing_monitor_faulted())
            trip(DriverMonitorError::current);
        else if (!wake.timing_permitted())
            trip(DriverMonitorError::wake);
        return;
    }
#endif
    const auto r = mono56_driver_io_read();
    if (!mono56_monitor_bus_permitted(nullptr))
        trip(DriverMonitorError::bus_permission);
    else if (static_cast<std::uint32_t>(TIM5->CNT - heartbeat) >
             monitor_driver_config.max_service_gap_us)
        trip(DriverMonitorError::foreground_late);
    else if (!r.valid || !r.quiet)
        trip(DriverMonitorError::gpio);
    else if (!r.brake_ok || (r.falling_edges & MONO56_DRIVER_BRAKE_EDGE))
        trip(DriverMonitorError::brake);
    else if ((r.falling_edges & MONO56_DRIVER_ENABLE_EDGE) ||
             (watch_feedback && !r.enable_feedback))
        trip(DriverMonitorError::enable_history);
    else if (watch_nfault && (!r.nfault_high || (r.falling_edges & MONO56_DRIVER_FAULT_EDGE)))
        trip(DriverMonitorError::nfault);
}
extern "C" bool mono56_driver_monitor_current_permitted(void *) {
    mono56_driver_monitor_irq_guard();
    const auto r = mono56_driver_io_read();
    return !mono56_driver_monitor_fault && guard_active && watch_feedback && watch_nfault &&
           r.valid && r.quiet && r.requested && r.enable_feedback && r.brake_ok && r.nfault_high &&
           !r.falling_edges;
}
#ifdef MONO56_MONITOR_TIMING
extern "C" bool mono56_driver_monitor_timing_active() { return timing_active; }
extern "C" bool mono56_driver_monitor_timing_permitted(void *) {
    mono56_driver_monitor_irq_guard();
    return timing_active && !mono56_driver_monitor_fault;
}
#endif
extern "C" void mono56_driver_monitor_step() {
    const auto &c = monitor_driver_config;
    if (state == DriverMonitorState::uninitialized)
        trip(DriverMonitorError::invalid_state);
    if (!mono56_driver_monitor_fault && state == DriverMonitorState::waiting_bus) {
        mono56_motor_inhibit();
        const auto now = clock_us();
        if (mono56_monitor_bus_faulted())
            trip(DriverMonitorError::bus_permission);
        else if (static_cast<std::uint32_t>(now - started) > c.bus_wait_timeout_us)
            trip(DriverMonitorError::bus_startup_timeout);
        else if (mono56_monitor_bus_permitted(nullptr)) {
            const DriverWakeConfig config{clock_us,
                                          nullptr,
                                          bus_permission,
                                          c.sleep_us,
                                          c.wake_us,
                                          c.feedback_timeout_us,
                                          c.max_service_gap_us};
            if (!wake.begin(config))
                trip(DriverMonitorError::wake);
            else if (mono56_spi3_init(clock_us, 42000000, c.spi_deadline_us) != MONO56_SPI_READY)
                trip(DriverMonitorError::spi);
            else {
                heartbeat = clock_us();
                guard_active = 1;
                state = DriverMonitorState::waking;
            }
        }
    } else if (!mono56_driver_monitor_fault &&
               (state == DriverMonitorState::waking || state == DriverMonitorState::coasted)) {
        const auto phase = wake.update();
        if (phase == DriverWakeState::fault)
            trip(DriverMonitorError::wake);
        else {
            watch_feedback = phase == DriverWakeState::waking || phase == DriverWakeState::awake ||
                             phase == DriverWakeState::timing;
            watch_nfault = phase == DriverWakeState::awake || phase == DriverWakeState::timing;
            if (phase == DriverWakeState::awake && state == DriverMonitorState::waking) {
                if (!driver.configure_coasted(c.gate))
                    trip(DriverMonitorError::registers);
                else {
                    state = DriverMonitorState::coasted;
                    last_check = clock_us();
                }
            } else if (state == DriverMonitorState::coasted &&
#ifdef MONO56_MONITOR_CURRENT
                       (current_monitor_completed()
#ifdef MONO56_MONITOR_TIMING
                        || timing_active
#endif
                        ) &&
#endif
                       static_cast<std::uint32_t>(clock_us() - last_check) >=
                           c.register_check_period_us) {
                if (!driver.check() || !driver.coasted())
                    trip(DriverMonitorError::registers);
                else {
                    ++checks_completed;
                    last_check = clock_us();
                }
            }
        }
    }
#ifdef MONO56_MONITOR_CURRENT
#ifdef MONO56_MONITOR_TIMING
    if (!mono56_driver_monitor_fault && state == DriverMonitorState::coasted) {
        if (timing_active) {
            if (!timing_monitor_step())
                trip(DriverMonitorError::current);
        } else if (!current_monitor_step(driver))
            trip(DriverMonitorError::current);
        else if (current_monitor_completed()) {
            CurrentZero zero;
            if (!current_monitor_release(&zero) ||
                !wake.begin_timing(driver, {nullptr, timing_bus_permission}))
                trip(DriverMonitorError::current);
            else {
                // Publish routing before capture initialization enables vectors.
                const auto mask = __get_PRIMASK();
                __disable_irq();
                timing_active = true;
                __DMB();
                if (!timing_monitor_begin(zero))
                    trip(DriverMonitorError::current);
                __set_PRIMASK(mask);
            }
        }
    }
    if (mono56_driver_monitor_fault && timing_active)
        timing_monitor_abort();
#else
    if (!mono56_driver_monitor_fault && state == DriverMonitorState::coasted &&
        !current_monitor_step(driver))
        trip(DriverMonitorError::current);
#endif
    if (mono56_driver_monitor_fault)
        current_monitor_abort();
#endif
    if (mono56_driver_monitor_fault) {
        mono56_motor_inhibit();
        state = DriverMonitorState::fault;
    }
    publish();
}
