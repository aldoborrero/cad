#include "current_capture.h"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_CURRENT_CAPTURE_TEST
#include "current_capture_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

static volatile mono56_capture_status state = MONO56_CAPTURE_UNINITIALIZED;
static mono56_capture_config config;
static bool owned, adc_owned, triggered;
static uint32_t began, last_trigger_after, compare_deadline;
static volatile mono56_adc23_status adc_status = MONO56_ADC23_NOT_INITIALIZED;
static mono56_adc23_frame mailbox;
static uint32_t time_us(void) { return TIM5->CNT; }
static bool faulted(void) { return state >= MONO56_CAPTURE_BAD_CONFIG; }
static bool timer_valid(bool pending) {
    return (RCC->APB1ENR & RCC_APB1ENR_TIM5EN) && (RCC->APB2ENR & RCC_APB2ENR_TIM1EN) &&
           TIM1->CR1 == 0 && TIM1->CR2 == TIM_CR2_MMS_1 && TIM1->SMCR == 0 && TIM1->DIER == 0 &&
           TIM1->CCER == 0 && TIM1->RCR == 0 && !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) &&
           TIM5->CR1 == TIM_CR1_CEN && TIM5->PSC == 83 && TIM5->ARR == 0xffffffffu &&
           TIM5->SMCR == 0 && TIM5->CCMR1 == 0 && TIM5->CCER == 0 &&
           TIM5->DIER == (pending ? TIM_DIER_CC1IE : 0u) &&
           (!pending || TIM5->CCR1 == compare_deadline) && NVIC_GetPriorityGrouping() == 3 &&
           NVIC_GetPriority(ADC_IRQn) == 1 && NVIC_GetPriority(TIM5_IRQn) == 1 &&
           NVIC_GetEnableIRQ(ADC_IRQn) && NVIC_GetEnableIRQ(TIM5_IRQn) &&
           !(ADC1->CR1 & (ADC_CR1_JEOCIE | ADC_CR1_EOCIE | ADC_CR1_OVRIE | ADC_CR1_AWDIE));
}
static mono56_capture_status fail(mono56_capture_status error) {
    if (!faulted())
        state = error;
    mailbox.valid = false;
    mono56_motor_inhibit();
    if (owned) {
        TIM5->DIER = 0;
        NVIC_DisableIRQ(TIM5_IRQn);
        NVIC_DisableIRQ(ADC_IRQn);
    }
    if (adc_owned)
        mono56_adc23_shutdown();
    return state;
}
static bool check_permission(void) {
    if (!config.permitted(config.context)) {
        fail(MONO56_CAPTURE_PERMISSION);
        return false;
    }
    if (!timer_valid(state == MONO56_CAPTURE_PENDING)) {
        fail(MONO56_CAPTURE_TIMER_CHANGED);
        return false;
    }
    return true;
}
static void service(void) {
    if (state != MONO56_CAPTURE_PENDING)
        return;
    if (!check_permission())
        return;
    if ((uint32_t)(time_us() - began) > config.deadline_us) {
        fail(MONO56_CAPTURE_TIMEOUT);
        return;
    }
    mono56_adc23_frame frame;
    adc_status = mono56_adc23_take(&frame);
    if (adc_status == MONO56_ADC23_PENDING)
        return;
    if (adc_status != MONO56_ADC23_FRAME_READY || !frame.valid) {
        fail(MONO56_CAPTURE_ADC_ERROR);
        return;
    }
    if ((uint32_t)(time_us() - began) > config.deadline_us) {
        fail(MONO56_CAPTURE_TIMEOUT);
        return;
    }
    if (!check_permission())
        return;
    TIM5->DIER = 0;
    TIM5->SR = ~TIM_SR_CC1IF;
    mailbox.b_raw = frame.b_raw;
    mailbox.c_raw = frame.c_raw;
    mailbox.armed_at_us = frame.armed_at_us;
    mailbox.observed_complete_at_us = frame.observed_complete_at_us;
    mailbox.valid = true;
    __DMB();
    state = MONO56_CAPTURE_READY;
}
mono56_capture_status mono56_current_capture_init(const mono56_capture_config *c) {
    if (state != MONO56_CAPTURE_UNINITIALIZED)
        return MONO56_CAPTURE_BUSY;
    if (!c || !c->permitted || c->deadline_us < 3u || c->period_us >= 0x80000000u ||
        (uint64_t)c->deadline_us + 1u >= c->period_us)
        return fail(MONO56_CAPTURE_BAD_CONFIG);
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    config = *c;
    if (!config.permitted(config.context))
        fail(MONO56_CAPTURE_PERMISSION);
    else if (NVIC_GetEnableIRQ(ADC_IRQn) || NVIC_GetEnableIRQ(TIM5_IRQn) ||
             NVIC_GetPriorityGrouping() != 3 || !(RCC->APB1ENR & RCC_APB1ENR_TIM5EN) ||
             !(RCC->APB2ENR & RCC_APB2ENR_TIM1EN) || TIM5->CR1 != TIM_CR1_CEN || TIM5->PSC != 83 ||
             TIM5->ARR != 0xffffffffu || TIM5->DIER || TIM5->SMCR || TIM5->CCMR1 || TIM5->CCER ||
             TIM1->CR1 || TIM1->CR2 || TIM1->SMCR || TIM1->DIER || TIM1->CCER ||
             (TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) ||
             (ADC1->CR1 & (ADC_CR1_JEOCIE | ADC_CR1_EOCIE | ADC_CR1_OVRIE | ADC_CR1_AWDIE)))
        fail(MONO56_CAPTURE_OWNERSHIP);
    else {
        owned = true;
        TIM1->RCR = 0;
        TIM1->CR2 = TIM_CR2_MMS_1; // Update event -> TRGO, with CEN=0.
        TIM1->SR = 0;
        adc_status = mono56_adc23_init(time_us, 84000000u, c->deadline_us, c->period_us);
        if (adc_status != MONO56_ADC23_WARMING)
            fail(MONO56_CAPTURE_ADC_ERROR);
        else {
            adc_owned = true;
            triggered = false;
            mailbox.valid = false;
            TIM5->SR = ~TIM_SR_CC1IF;
            NVIC_SetPriority(ADC_IRQn, 1);
            NVIC_SetPriority(TIM5_IRQn, 1); // Serialized; above the priority-2 bus service.
            NVIC_ClearPendingIRQ(ADC_IRQn);
            NVIC_ClearPendingIRQ(TIM5_IRQn);
            NVIC_EnableIRQ(ADC_IRQn);
            NVIC_EnableIRQ(TIM5_IRQn);
            state = MONO56_CAPTURE_IDLE;
        }
    }
    __DSB();
    __set_PRIMASK(mask);
    return state;
}
mono56_capture_status mono56_current_capture_start(void) {
    if (state == MONO56_CAPTURE_UNINITIALIZED || faulted())
        return state;
    if (state != MONO56_CAPTURE_IDLE)
        return MONO56_CAPTURE_BUSY;
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    if (!check_permission()) {
        __set_PRIMASK(mask);
        return state;
    }
    const uint32_t now = time_us();
    if (triggered) {
        const uint32_t elapsed = now - last_trigger_after;
        if (elapsed >= 0x80000000u)
            fail(MONO56_CAPTURE_TIMEOUT);
        else if (elapsed < config.period_us) {
            __set_PRIMASK(mask);
            return MONO56_CAPTURE_BUSY;
        }
        if (faulted()) {
            __set_PRIMASK(mask);
            return state;
        }
    }
    began = now;
    adc_status = mono56_adc23_arm();
    if (adc_status == MONO56_ADC23_WARMING) {
        __set_PRIMASK(mask);
        return MONO56_CAPTURE_WARMING;
    }
    if (adc_status != MONO56_ADC23_PENDING)
        fail(MONO56_CAPTURE_ADC_ERROR);
    else {
        compare_deadline = began + config.deadline_us + 1u;
        TIM5->CCR1 = compare_deadline;
        TIM5->SR = ~TIM_SR_CC1IF;
        TIM5->DIER = TIM_DIER_CC1IE;
        state = MONO56_CAPTURE_PENDING;
        if ((uint32_t)(time_us() - began) > config.deadline_us)
            fail(MONO56_CAPTURE_TIMEOUT);
        else if (check_permission()) {
            // Only this stopped-timer owner generates events. Minimum spacing
            // is measured from AFTER the prior actual UG write, not its request.
            TIM1->EGR = TIM_EGR_UG;
            __DSB();
            last_trigger_after = time_us();
            triggered = true;
            if ((uint32_t)(last_trigger_after - began) > config.deadline_us)
                fail(MONO56_CAPTURE_TIMEOUT);
        }
    }
    __set_PRIMASK(mask);
    return state;
}
mono56_capture_status mono56_current_capture_take(mono56_adc23_frame *out) {
    if (!out) {
        if (state == MONO56_CAPTURE_UNINITIALIZED)
            return MONO56_CAPTURE_BAD_CONFIG;
        return fail(MONO56_CAPTURE_BAD_CONFIG);
    }
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    out->valid = false;
    service(); // Also enforces the deadline if vector delivery has been lost.
    const mono56_capture_status result = state;
    if (state == MONO56_CAPTURE_READY && check_permission()) {
        out->b_raw = mailbox.b_raw;
        out->c_raw = mailbox.c_raw;
        out->armed_at_us = mailbox.armed_at_us;
        out->observed_complete_at_us = mailbox.observed_complete_at_us;
        out->valid = mailbox.valid;
        mailbox.valid = false;
        state = MONO56_CAPTURE_IDLE;
    }
    const mono56_capture_status returned = faulted() ? state : result;
    __set_PRIMASK(mask);
    return returned;
}
void mono56_current_capture_adc_irq(void) { service(); }
void mono56_current_capture_deadline_irq(void) {
    if (TIM5->SR & TIM_SR_CC1IF) {
        TIM5->SR = ~TIM_SR_CC1IF;
        service();
    }
}
mono56_capture_status mono56_current_capture_status(void) { return state; }
mono56_adc23_status mono56_current_capture_adc_status(void) { return adc_status; }
bool mono56_current_capture_release(void) {
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (state != MONO56_CAPTURE_IDLE || !owned || !adc_owned || mailbox.valid)
        fail(MONO56_CAPTURE_OWNERSHIP);
    else if (check_permission()) {
        // No event or unread data remains. Keep ENABLE untouched: the caller's
        // calibrated register session survives this peripheral ownership change.
        TIM5->DIER = 0;
        TIM5->SR = ~TIM_SR_CC1IF;
        NVIC_DisableIRQ(ADC_IRQn);
        NVIC_DisableIRQ(TIM5_IRQn);
        TIM1->CR2 = 0;
        mono56_adc23_shutdown();
        __DSB();
        if (!config.permitted(config.context))
            fail(MONO56_CAPTURE_PERMISSION);
        else if (TIM1->CR1 || TIM1->CR2 || TIM1->DIER || TIM1->CCER ||
                 (TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) || TIM5->DIER ||
                 NVIC_GetEnableIRQ(ADC_IRQn) || NVIC_GetEnableIRQ(TIM5_IRQn) || ADC2->CR1 ||
                 ADC2->CR2 || ADC3->CR1 || ADC3->CR2)
            fail(MONO56_CAPTURE_TIMER_CHANGED);
        else {
            owned = adc_owned = triggered = false;
            mailbox.valid = false;
            adc_status = MONO56_ADC23_NOT_INITIALIZED;
            state = MONO56_CAPTURE_UNINITIALIZED;
            ok = true;
        }
    }
    __set_PRIMASK(mask);
    return ok;
}
void mono56_current_capture_shutdown(void) {
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    mono56_motor_inhibit();
    if (owned) {
        TIM5->DIER = 0;
        TIM5->SR = ~TIM_SR_CC1IF;
        NVIC_DisableIRQ(TIM5_IRQn);
        NVIC_DisableIRQ(ADC_IRQn);
        TIM1->CR2 = 0;
    }
    if (adc_owned)
        mono56_adc23_shutdown();
    owned = adc_owned = triggered = false;
    mailbox.valid = false;
    state = MONO56_CAPTURE_UNINITIALIZED;
    __set_PRIMASK(mask);
}
