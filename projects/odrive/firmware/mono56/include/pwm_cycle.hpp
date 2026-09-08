#pragma once
#include "pwm_sample_plan.hpp"

namespace odrive::mono56 {
enum class PwmCycleState { uninitialized, ready, running, fault };
enum class PwmCycleError {
    none,
    invalid_config,
    ownership,
    invalid_state,
    permission,
    bad_plan,
    timer_changed,
    boundary_late,
    wrong_phase,
    command_missing,
    command_generation,
    command_busy,
    commit_late,
    trigger_spacing,
    consumer
};
struct PwmCycleObservation {
    PwmSamplePlan plan;
    std::uint32_t cycle = 0, phase_ticks = 0;
    std::uint32_t began_lower_us = 0, began_upper_us = 0;
    std::uint32_t min_trigger_spacing_us = 0, adc_deadline_us = 0;
    bool valid = false;
};
struct PwmCycleConfig {
    PwmSampleConfig sampling;
    void *context;
    // Nonblocking, IRQ-safe, no SPI. Checks live bus/driver/brake/session
    // permission independently of this timer. Does not feed its own heartbeat.
    bool (*permitted)(void *);
    // Called once at initial start and every verified underflow, with IRQs
    // masked. The companion current owner arms before plan.ccr4 and must fit
    // sampling.arm_budget_ns; false inhibits immediately. No reentrant calls.
    bool (*cycle_started)(void *, const PwmCycleObservation *);
    std::uint32_t boundary_budget_ns, commit_budget_ns;
    // Same values used by the companion ADC2/3 owner. Varying CCR4 changes
    // inter-trigger spacing; every successive plan must preserve this bound.
    std::uint32_t adc_deadline_us, min_trigger_spacing_us;
};
// Exclusive TIM1 counter/compare and TIM5 compare-2 watchdog owner. Requires
// TIM5 already running at 1 MHz, NVIC group 3 and unused TIM1_UP/TIM5 vectors.
// Reserves TIM5 compare 1 for a companion ADC deadline owner. That owner must
// share the TIM5 dispatcher/priority rather than initialize this vector again.
// This stage runs the counter and internal OC4REF/TRGO only: CCER/MOE/AOE stay
// zero and the six PWM pins stay GPIO LOW. It establishes cycle timing, NOT
// actual shunt conduction or motor permission. Output handoff remains separate.
bool pwm_cycle_init(const PwmCycleConfig &);
bool pwm_cycle_start(std::uint32_t a, std::uint32_t b, std::uint32_t c);
// One next-cycle command. During upcount it is queued in software. After apex
// it is written atomically to preloads, then becomes active at underflow.
// Missing/duplicate/stale commands inhibit; commands are never silently held.
bool pwm_cycle_queue(std::uint32_t cycle, std::uint32_t a, std::uint32_t b, std::uint32_t c);
// Verifies present timer phase/configuration and returns original cycle bounds.
// Readback registers are preloads; update-phase history establishes active plan.
// Never use valid alone as CurrentFrame.low_side_window_valid.
bool pwm_cycle_observe(PwmCycleObservation *);
PwmCycleState pwm_cycle_state();
PwmCycleError pwm_cycle_error();
void pwm_cycle_update_irq();
void pwm_cycle_watchdog_irq();
// Companion capture failure, including inside cycle_started. Retains an earlier
// cycle error and stops without clearing ownership/history. No restart.
void pwm_cycle_abort();
void pwm_cycle_shutdown();
} // namespace odrive::mono56
