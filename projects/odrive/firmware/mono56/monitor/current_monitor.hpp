#pragma once
#include "drv8353.hpp"
#include "phase_current.hpp"

namespace odrive::mono56 {
struct CurrentMonitorConfig {
    CurrentConfig current;
    CurrentZeroConfig zero;
    std::uint32_t period_us, capture_deadline_us;
};
enum class CurrentMonitorState {
    uninitialized,
    settling,
    collecting,
    completed,
    fault,
    transferred
};
enum class CurrentMonitorError {
    none,
    invalid_config,
    permission,
    registers,
    capture,
    timeout,
    bounds,
    supply,
    estimator
};
struct CurrentMonitorDiagnostics {
    std::uint32_t magic, version, sequence, observed_at_us;
    std::uint32_t state, error, capture_status, adc_status, estimator_error;
    std::uint32_t samples, b_raw, c_raw, armed_at_us, observed_complete_at_us, supply_at_us;
    float supply_v, b_zero_code, c_zero_code, zero_supply_v;
    std::uint32_t zero_completed_at_us, calibration_completed;
};
// Foreground only, called after qualified wake and verified COAST. No reentry
// or retry. Completion is a diagnostic report, never motor/current permission.
bool current_monitor_step(Drv8353 &driver);
void current_monitor_abort();
bool current_monitor_completed();
bool current_monitor_release(CurrentZero *);
} // namespace odrive::mono56
extern "C" {
extern volatile odrive::mono56::CurrentMonitorDiagnostics mono56_current_monitor;
void ADC_IRQHandler();
void TIM5_IRQHandler();
}
