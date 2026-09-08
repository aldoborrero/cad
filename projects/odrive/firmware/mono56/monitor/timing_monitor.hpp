#pragma once
#include "phase_current.hpp"
#include "pwm_capture.hpp"

namespace odrive::mono56 {
struct TimingMonitorConfig {
    PwmSampleConfig sampling;
    std::uint32_t boundary_budget_ns, commit_budget_ns, adc_deadline_us, min_trigger_spacing_us;
    std::uint32_t a, b, c;
};
enum class TimingMonitorState { uninitialized, warming, running, fault };
enum class TimingMonitorError {
    none,
    invalid_state,
    configuration,
    permission,
    capture,
    bounds,
    supply,
    zero
};
struct TimingMonitorDiagnostics {
    std::uint32_t magic, version, sequence, observed_at_us, state, error;
    std::uint32_t capture_state, capture_error, cycle_error, samples, cycle;
    std::uint32_t b_raw, c_raw, armed_at_us, complete_at_us, supply_at_us;
    float supply_v, b_zero_code, c_zero_code;
    std::uint32_t zero_completed_at_us, driver_session, frame_valid;
};
// After stopped capture release and DriverWake timing handoff. Reset-only,
// fixed internal compares, COAST retained. Never grants a conduction window.
bool timing_monitor_begin(const CurrentZero &);
bool timing_monitor_step();
void timing_monitor_abort();
void timing_monitor_adc_irq();
void timing_monitor_update_irq();
void timing_monitor_deadline_irq();
bool timing_monitor_faulted();
} // namespace odrive::mono56
extern "C" {
extern volatile odrive::mono56::TimingMonitorDiagnostics mono56_timing_monitor;
void TIM1_UP_TIM10_IRQHandler();
}
