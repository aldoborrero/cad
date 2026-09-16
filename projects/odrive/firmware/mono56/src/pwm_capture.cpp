#include "pwm_capture.hpp"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_PWM_CAPTURE_TEST
#include "pwm_cycle_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

namespace odrive::mono56 {
namespace {
volatile PwmCaptureState state = PwmCaptureState::uninitialized;
volatile PwmCaptureError error = PwmCaptureError::none;
volatile mono56_adc23_status adc_status = MONO56_ADC23_NOT_INITIALIZED;
PwmCaptureConfig config{};
PwmCycleObservation started;
PwmCaptureFrame mailbox;
bool cycle_owned = false, adc_owned = false, irq_owned = false, has_cycle = false;
bool cycle_attempted = false;
std::uint32_t enabled_at = 0, deadline_at = 0;
std::uint32_t clock_us() { return TIM5->CNT; }
bool fail(PwmCaptureError reason) {
    if (error == PwmCaptureError::none)
        error = reason;
    state = PwmCaptureState::fault;
    mailbox.valid = false;
    mono56_motor_inhibit();
    if (cycle_owned) {
        TIM5->DIER &= ~TIM_DIER_CC1IE;
        pwm_cycle_abort();
        NVIC_DisableIRQ(TIM5_IRQn);
    }
    if (irq_owned)
        NVIC_DisableIRQ(ADC_IRQn);
    if (adc_owned)
        mono56_adc23_shutdown();
    return false;
}
bool permission(void *) {
    return state != PwmCaptureState::fault && config.permitted(config.context);
}
bool configuration_valid() {
    const bool pending = state == PwmCaptureState::pending;
    return (RCC->APB1ENR & RCC_APB1ENR_TIM5EN) && TIM5->CR1 == TIM_CR1_CEN && TIM5->PSC == 83 &&
           TIM5->ARR == 0xffffffffu && TIM5->SMCR == 0 && TIM5->CCMR1 == 0 && TIM5->CCER == 0 &&
           !(TIM5->DIER & ~(TIM_DIER_CC1IE | TIM_DIER_CC2IE)) &&
           ((TIM5->DIER & TIM_DIER_CC1IE) != 0) == pending &&
           (!pending || TIM5->CCR1 == deadline_at) && NVIC_GetPriorityGrouping() == 3 &&
           NVIC_GetEnableIRQ(ADC_IRQn) && NVIC_GetPriority(ADC_IRQn) == 1 &&
           NVIC_GetEnableIRQ(TIM5_IRQn) && NVIC_GetPriority(TIM5_IRQn) == 1 &&
           !(ADC1->CR1 & (ADC_CR1_JEOCIE | ADC_CR1_EOCIE | ADC_CR1_OVRIE | ADC_CR1_AWDIE));
}
bool deadline_valid();
bool check() {
    if (state == PwmCaptureState::fault || state == PwmCaptureState::uninitialized)
        return false;
    if (pwm_cycle_state() == PwmCycleState::fault)
        return fail(PwmCaptureError::cycle);
    if (!permission(nullptr))
        return fail(PwmCaptureError::permission);
    if (!configuration_valid())
        return fail(PwmCaptureError::timer_changed);
    return state != PwmCaptureState::pending || deadline_valid();
}
bool deadline_valid() {
    if (static_cast<std::uint32_t>(clock_us() - started.began_lower_us) > config.adc_deadline_us)
        return fail(PwmCaptureError::timeout);
    return true;
}
bool begin_cycle(void *, const PwmCycleObservation *event) {
    // Called by the cycle owner with IRQs masked. Do not reenter observe/queue:
    // this callback is itself part of establishing the new cycle.
    if (state == PwmCaptureState::fault)
        return false;
    if ((has_cycle && state != PwmCaptureState::idle) ||
        (!has_cycle && state != PwmCaptureState::warming))
        return fail(PwmCaptureError::unconsumed);
    if (!check())
        return false;
    if (!event || !event->valid || !event->plan.valid() ||
        event->adc_deadline_us != config.adc_deadline_us ||
        event->min_trigger_spacing_us != config.min_trigger_spacing_us ||
        (has_cycle ? (started.cycle == 0xffffffffu || event->cycle != started.cycle + 1)
                   : event->cycle != 0))
        return fail(PwmCaptureError::generation);
    started = *event;
    has_cycle = true;
    deadline_at = started.began_lower_us + config.adc_deadline_us + 1;
    TIM5->CCR1 = deadline_at;
    TIM5->SR = ~TIM_SR_CC1IF;
    TIM5->DIER |= TIM_DIER_CC1IE;
    state = PwmCaptureState::pending;
    __DSB();
    if (!deadline_valid())
        return false;
    adc_status = mono56_adc23_arm();
    if (adc_status != MONO56_ADC23_PENDING)
        return fail(PwmCaptureError::adc);
    return deadline_valid() && check();
}
bool observe(PwmCycleObservation *event) {
    if (!pwm_cycle_observe(event)) {
        // A pending underflow can invoke begin_cycle and retain its more precise
        // unconsumed/generation error before the outer timer service returns.
        if (state != PwmCaptureState::fault)
            fail(PwmCaptureError::cycle);
        return false;
    }
    if (!event->valid || event->cycle != started.cycle ||
        event->began_lower_us != started.began_lower_us ||
        event->began_upper_us != started.began_upper_us)
        return fail(PwmCaptureError::generation);
    return true;
}
void service() {
    if (!check() || state != PwmCaptureState::pending)
        return;
    if (!deadline_valid())
        return;
    PwmCycleObservation event;
    if (!observe(&event))
        return;
    mono56_adc23_frame raw;
    adc_status = mono56_adc23_take(&raw);
    if (adc_status == MONO56_ADC23_PENDING)
        return;
    if (adc_status != MONO56_ADC23_FRAME_READY || !raw.valid) {
        fail(PwmCaptureError::adc);
        return;
    }
    if (!deadline_valid() || !check() || !observe(&event) || !deadline_valid())
        return;
    if (event.phase_ticks < event.plan.ccr4) {
        fail(PwmCaptureError::unexpected_phase);
        return;
    }
    // Raw timestamps are bounds from the acquisition driver. Keep them intact
    // and verify they belong to this cycle's original lifetime.
    if (static_cast<std::uint32_t>(raw.armed_at_us - started.began_lower_us) >
            config.adc_deadline_us ||
        static_cast<std::uint32_t>(raw.observed_complete_at_us - started.began_lower_us) >
            config.adc_deadline_us) {
        fail(PwmCaptureError::timeout);
        return;
    }
    TIM5->DIER &= ~TIM_DIER_CC1IE;
    TIM5->SR = ~TIM_SR_CC1IF;
    mailbox.cycle = event;
    mailbox.adc = raw;
    mailbox.valid = true;
    __DMB();
    state = PwmCaptureState::ready;
}
} // namespace
bool pwm_capture_init(const PwmCaptureConfig &c) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (state != PwmCaptureState::uninitialized)
        fail(PwmCaptureError::invalid_state);
    else if (!c.permitted || c.adc_deadline_us < 3 || c.min_trigger_spacing_us >= 0x80000000u ||
             static_cast<std::uint64_t>(c.adc_deadline_us) + 1 >= c.min_trigger_spacing_us)
        fail(PwmCaptureError::invalid_config);
    else if (pwm_cycle_state() != PwmCycleState::uninitialized || NVIC_GetEnableIRQ(ADC_IRQn) ||
             (ADC1->CR1 & (ADC_CR1_JEOCIE | ADC_CR1_EOCIE | ADC_CR1_OVRIE | ADC_CR1_AWDIE)))
        fail(PwmCaptureError::ownership);
    else {
        config = c;
        const PwmCycleConfig timer{c.sampling,           nullptr,
                                   permission,           begin_cycle,
                                   c.boundary_budget_ns, c.commit_budget_ns,
                                   c.adc_deadline_us,    c.min_trigger_spacing_us};
        cycle_attempted = true;
        if (!pwm_cycle_init(timer))
            fail(PwmCaptureError::cycle);
        else {
            cycle_owned = true;
            adc_status =
                mono56_adc23_init(clock_us, 84000000, c.adc_deadline_us, c.min_trigger_spacing_us);
            if (adc_status != MONO56_ADC23_WARMING)
                fail(PwmCaptureError::adc);
            else {
                adc_owned = irq_owned = true;
                enabled_at = clock_us();
                has_cycle = false;
                mailbox.valid = false;
                NVIC_SetPriority(ADC_IRQn, 1);
                NVIC_ClearPendingIRQ(ADC_IRQn);
                NVIC_EnableIRQ(ADC_IRQn);
                state = PwmCaptureState::warming;
            }
        }
    }
    __DSB();
    __set_PRIMASK(mask);
    return state == PwmCaptureState::warming;
}
bool pwm_capture_start(std::uint32_t a, std::uint32_t b, std::uint32_t c) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (state != PwmCaptureState::fault && state != PwmCaptureState::warming)
        fail(PwmCaptureError::invalid_state);
    else if (check()) {
        const auto age = static_cast<std::uint32_t>(clock_us() - enabled_at);
        if (age >= 0x80000000u)
            fail(PwmCaptureError::timeout);
        else if (age >= 10) {
            ok = pwm_cycle_start(a, b, c);
            if (!ok && state != PwmCaptureState::fault)
                fail(PwmCaptureError::cycle);
        }
    }
    __set_PRIMASK(mask);
    return ok;
}
bool pwm_capture_queue(std::uint32_t target, std::uint32_t a, std::uint32_t b, std::uint32_t c) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (check()) {
        if (!has_cycle)
            fail(PwmCaptureError::invalid_state);
        else {
            ok = pwm_cycle_queue(target, a, b, c);
            if (!ok && state != PwmCaptureState::fault)
                fail(PwmCaptureError::cycle);
        }
    }
    __set_PRIMASK(mask);
    return ok;
}
bool pwm_capture_take(PwmCaptureFrame *out) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (!out)
        fail(PwmCaptureError::invalid_config);
    else {
        out->valid = false;
        service();
        PwmCycleObservation event;
        if (state == PwmCaptureState::ready && check() && observe(&event)) {
            *out = mailbox;
            out->valid = false;
            __DSB();
            if (check() && observe(&event)) {
                out->valid = mailbox.valid;
                mailbox.valid = false;
                state = PwmCaptureState::idle;
                ok = out->valid;
            }
        }
    }
    __set_PRIMASK(mask);
    return ok;
}
void pwm_capture_adc_irq() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    service();
    __set_PRIMASK(mask);
}
void pwm_capture_update_irq() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (check()) {
        pwm_cycle_update_irq();
        check();
    }
    __set_PRIMASK(mask);
}
void pwm_capture_deadline_irq() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (check()) {
        if (TIM5->SR & TIM_SR_CC1IF) {
            TIM5->SR = ~TIM_SR_CC1IF;
            if (state == PwmCaptureState::pending)
                deadline_valid(); // Never consume late ADC flags on expiry.
        }
        pwm_cycle_watchdog_irq();
        check();
    }
    __set_PRIMASK(mask);
}
PwmCaptureState pwm_capture_state() { return state; }
PwmCaptureError pwm_capture_error() { return error; }
mono56_adc23_status pwm_capture_adc_status() { return adc_status; }
void pwm_capture_abort() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    fail(PwmCaptureError::permission);
    __set_PRIMASK(mask);
}
void pwm_capture_shutdown() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    mono56_motor_inhibit();
    if (irq_owned)
        NVIC_DisableIRQ(ADC_IRQn);
    if (cycle_owned) {
        TIM5->DIER &= ~TIM_DIER_CC1IE;
        TIM5->SR = ~TIM_SR_CC1IF;
    }
    if (cycle_attempted)
        pwm_cycle_shutdown();
    if (adc_owned)
        mono56_adc23_shutdown();
    cycle_attempted = cycle_owned = adc_owned = irq_owned = has_cycle = false;
    mailbox.valid = false;
    state = PwmCaptureState::uninitialized;
    error = PwmCaptureError::none;
    adc_status = MONO56_ADC23_NOT_INITIALIZED;
    __set_PRIMASK(mask);
}
} // namespace odrive::mono56
