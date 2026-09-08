#pragma once
#include "adc23_acquisition.h"
#include "pwm_cycle.hpp"

namespace odrive::mono56 {
enum class PwmCaptureState { uninitialized, warming, idle, pending, ready, fault };
enum class PwmCaptureError {
    none,
    invalid_config,
    invalid_state,
    ownership,
    permission,
    timer_changed,
    cycle,
    adc,
    timeout,
    unconsumed,
    generation,
    unexpected_phase
};
struct PwmCaptureConfig {
    PwmSampleConfig sampling;
    void *context;
    // Nonblocking, IRQ-safe, no SPI, no self-renewed heartbeat. This stage still
    // requires GPIO LOW PWM; running-driver/output permission is later work.
    bool (*permitted)(void *);
    std::uint32_t boundary_budget_ns, commit_budget_ns;
    std::uint32_t adc_deadline_us, min_trigger_spacing_us;
};
struct PwmCaptureFrame {
    // Observed active cycle after both ADC values have been read, preserving
    // original cycle/arm/completion bounds. No per-channel instant is invented.
    PwmCycleObservation cycle;
    mono56_adc23_frame adc{};
    bool valid = false;
};
// Owns the PWM cycle engine plus ADC2/3 and the ADC vector. TIM5 compare 1 is
// the capture deadline; compare 2 remains the cycle watchdog. Shared TIM5 uses
// one dispatcher/priority. ADC1 must use DMA without ADC-vector interrupts.
// Requires fresh peripheral ownership; cannot coexist with stopped capture.
// No COAST release, GPIO alternate-function switch or current-window permission.
bool pwm_capture_init(const PwmCaptureConfig &);
// Init enters warming. Start returns false without a fault until >=10 us have
// elapsed; a successful start is allowed once and immediately arms cycle zero.
bool pwm_capture_start(std::uint32_t a, std::uint32_t b, std::uint32_t c);
bool pwm_capture_queue(std::uint32_t next_cycle, std::uint32_t a, std::uint32_t b, std::uint32_t c);
// One delivery per cycle, serialized with IRQ service. Polling may service a
// pending pair before its deadline; a timeout never salvages late JEOC flags.
// The controller must consume and submit its command before the next cycle.
// valid means timed raw capture, NOT CurrentFrame.low_side_window_valid.
bool pwm_capture_take(PwmCaptureFrame *);
void pwm_capture_adc_irq();
void pwm_capture_update_irq();
void pwm_capture_deadline_irq();
PwmCaptureState pwm_capture_state();
PwmCaptureError pwm_capture_error();
mono56_adc23_status pwm_capture_adc_status();
// External session/scheduler fault: stop owned acquisition and retain errors.
void pwm_capture_abort();
void pwm_capture_shutdown();
} // namespace odrive::mono56
