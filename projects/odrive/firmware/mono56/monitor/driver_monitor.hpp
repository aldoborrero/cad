#pragma once
#include "driver_wake.hpp"
#include <cstdint>
namespace odrive::mono56 {
struct DriverMonitorConfig {
    Drv8353Config gate;
    std::uint32_t sleep_us, wake_us, feedback_timeout_us, max_service_gap_us;
    std::uint32_t spi_deadline_us, bus_wait_timeout_us, register_check_period_us;
};
enum class DriverMonitorState { uninitialized, waiting_bus, waking, coasted, fault };
enum class DriverMonitorError {
    none,
    invalid_config,
    invalid_state,
    bus_startup_timeout,
    bus_permission,
    wake,
    spi,
    registers,
    gpio,
    enable_history,
    brake,
    nfault,
    foreground_late,
    current
};
struct DriverMonitorDiagnostics {
    std::uint32_t magic, version, sequence, observed_at_us;
    std::uint32_t state, error, wake_state, wake_error, spi_status, register_error;
    std::uint32_t configured_coasted, fault_registers_valid, packed_faults, failed_address;
    std::uint32_t checks_completed;
};
} // namespace odrive::mono56
extern "C" {
extern volatile odrive::mono56::DriverMonitorDiagnostics mono56_driver_monitor;
// First-fault latch is separate from the foreground-only coherent snapshot.
// A fatal/stalled foreground may leave the snapshot old; inspect this word too.
extern volatile std::uint32_t mono56_driver_monitor_fault;
bool mono56_driver_monitor_begin();
void mono56_driver_monitor_step();
// Called after bus/current IRQ service. Never performs SPI or renews foreground
// progress. Timing mode calls DriverWake's IRQ guard and aborts owned acquisition
// on failure; startup mode directly checks GPIO/heartbeat history.
void mono56_driver_monitor_irq_guard();
// Qualified capture permission; callable from masked foreground or IRQ.
// Does not renew the foreground heartbeat or perform SPI.
bool mono56_driver_monitor_current_permitted(void *);
bool mono56_driver_monitor_timing_permitted(void *);
bool mono56_driver_monitor_timing_active();
}
