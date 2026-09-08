#include "adc23_acquisition.h"
#include "stm32f405xx.h"
#ifdef MONO56_ADC23_TEST
#include "adc23_test_registers.h"
#endif
#ifdef MONO56_CURRENT_CAPTURE_TEST
#include "current_capture_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

#define COMMON_MASK (ADC_CCR_MULTI | ADC_CCR_DMA | ADC_CCR_DDS | ADC_CCR_ADCPRE)
#define BASE_CR2 (ADC_CR2_ADON | ADC_CR2_JEXTSEL_0) // TIM1_TRGO, right-aligned, one shot
#define COMPLETE_FLAGS (ADC_SR_JSTRT | ADC_SR_JEOC)
#define UNEXPECTED_FLAGS (ADC_SR_OVR | ADC_SR_STRT | ADC_SR_EOC | ADC_SR_AWD)
#define IRQ_FLAGS (ADC_CR1_JEOCIE | ADC_CR1_EOCIE | ADC_CR1_OVRIE | ADC_CR1_AWDIE)

static mono56_clock_us_fn time_us;
static mono56_adc23_status state = MONO56_ADC23_NOT_INITIALIZED;
static uint32_t enabled_at, armed_at, capture_deadline;
static unsigned completed_mask;

static bool faulted(void) { return state >= MONO56_ADC23_BAD_CONFIG; }
static void close_channel(ADC_TypeDef *adc) {
    adc->CR1 = 0;
    adc->CR2 &= ~ADC_CR2_JEXTEN;
}
static mono56_adc23_status fail(mono56_adc23_status error) {
    ADC2->CR1 = ADC3->CR1 = 0;
    ADC2->CR2 = ADC3->CR2 = 0;
    __DSB();
    if (!faulted())
        state = error;
    return state;
}
static bool channel_valid(ADC_TypeDef *adc, unsigned channel, bool armed) {
    return adc->CR1 == (armed ? ADC_CR1_JEOCIE : 0u) &&
           adc->CR2 == (BASE_CR2 | (armed ? ADC_CR2_JEXTEN_0 : 0u)) &&
           adc->JSQR == (channel << 15) && adc->SMPR1 == (1u << (3 * (channel - 10))) &&
           adc->SMPR2 == 0 && adc->SQR1 == 0 && adc->SQR2 == 0 && adc->SQR3 == 0 &&
           adc->JOFR1 == 0 && adc->JOFR2 == 0 && adc->JOFR3 == 0 && adc->JOFR4 == 0;
}
static bool configuration_valid(void) {
    const bool pending = state == MONO56_ADC23_PENDING;
    return (RCC->APB2ENR & (RCC_APB2ENR_ADC2EN | RCC_APB2ENR_ADC3EN)) ==
               (RCC_APB2ENR_ADC2EN | RCC_APB2ENR_ADC3EN) &&
           (RCC->AHB1ENR & RCC_AHB1ENR_GPIOCEN) && (ADC->CCR & COMMON_MASK) == ADC_CCR_ADCPRE_0 &&
           (GPIOC->MODER & 15u) == 15u && (GPIOC->PUPDR & 15u) == 0 &&
           channel_valid(ADC2, 10, pending && !(completed_mask & 1u)) &&
           channel_valid(ADC3, 11, pending && !(completed_mask & 2u));
}
static void prepare_channel(ADC_TypeDef *adc, unsigned channel) {
    adc->CR1 = adc->CR2 = 0;
    adc->SMPR1 = 1u << (3 * (channel - 10)); // 15 cycles
    adc->SMPR2 = 0;
    adc->SQR1 = adc->SQR2 = adc->SQR3 = 0;
    adc->JSQR = channel << 15; // JL=0: first/only conversion uses JSQ4 -> JDR1.
    adc->JOFR1 = adc->JOFR2 = adc->JOFR3 = adc->JOFR4 = 0;
    adc->SR = 0;
    adc->CR2 = BASE_CR2; // Trigger remains disabled until arm.
}
mono56_adc23_status mono56_adc23_init(mono56_clock_us_fn clock_us, uint32_t pclk2_hz,
                                      uint32_t deadline_us, uint32_t min_trigger_spacing_us) {
    if (state != MONO56_ADC23_NOT_INITIALIZED)
        return MONO56_ADC23_BUSY;
    if (!clock_us || pclk2_hz != 84000000u || deadline_us < 3u ||
        min_trigger_spacing_us >= 0x80000000u ||
        (uint64_t)deadline_us + 1u >= min_trigger_spacing_us)
        return MONO56_ADC23_BAD_CONFIG;
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOCEN;
    (void)RCC->AHB1ENR;
    RCC->APB2ENR |= RCC_APB2ENR_ADC2EN | RCC_APB2ENR_ADC3EN;
    (void)RCC->APB2ENR;
    if (((ADC2->CR2 | ADC3->CR2) & ADC_CR2_ADON) || ((ADC2->CR1 | ADC3->CR1) & IRQ_FLAGS) ||
        (ADC->CCR & (ADC_CCR_MULTI | ADC_CCR_DMA | ADC_CCR_DDS)))
        return MONO56_ADC23_BUSY;
    // Never retime a running ADC1 bus acquisition.
    if ((ADC1->CR2 & ADC_CR2_ADON) && (ADC->CCR & ADC_CCR_ADCPRE) != ADC_CCR_ADCPRE_0)
        return MONO56_ADC23_BUSY;
    ADC->CCR = (ADC->CCR & ~ADC_CCR_ADCPRE) | ADC_CCR_ADCPRE_0;
    GPIOC->MODER = (GPIOC->MODER & ~15u) | 15u;
    GPIOC->PUPDR &= ~15u;
    prepare_channel(ADC2, 10);
    prepare_channel(ADC3, 11);
    __DSB();
    time_us = clock_us;
    enabled_at = time_us(); // After both ADCs are enabled.
    capture_deadline = deadline_us;
    completed_mask = 0;
    state = MONO56_ADC23_WARMING;
    return state;
}
mono56_adc23_status mono56_adc23_arm(void) {
    if (state == MONO56_ADC23_NOT_INITIALIZED || faulted())
        return state;
    if (state == MONO56_ADC23_PENDING)
        return MONO56_ADC23_BUSY;
    if (!configuration_valid())
        return fail(MONO56_ADC23_CONFIG_CHANGED);
    if (state == MONO56_ADC23_WARMING) {
        const uint32_t age = time_us() - enabled_at;
        if (age >= 0x80000000u)
            return fail(MONO56_ADC23_TIMEOUT);
        if (age < 10u)
            return state;
    }
    // Stale flags while disarmed indicate unexpected conversion activity.
    if (ADC2->SR || ADC3->SR)
        return fail(MONO56_ADC23_UNEXPECTED_CONVERSION);
    const uint32_t primask = __get_PRIMASK();
    __disable_irq();
    completed_mask = 0;
    armed_at = time_us(); // Oldest bound, before either ADC can accept an edge.
    state = MONO56_ADC23_PENDING;
    ADC2->CR1 = ADC3->CR1 = ADC_CR1_JEOCIE;
    ADC2->CR2 = ADC3->CR2 = BASE_CR2 | ADC_CR2_JEXTEN_0;
    __DSB();
    // A preemption or stalled clock callback during setup cannot silently grant
    // a fresh deadline after the ADCs have already been armed.
    if ((uint32_t)(time_us() - armed_at) > capture_deadline)
        fail(MONO56_ADC23_TIMEOUT);
    __set_PRIMASK(primask);
    return state;
}
mono56_adc23_status mono56_adc23_take(mono56_adc23_frame *out) {
    if (!out) {
        if (state == MONO56_ADC23_NOT_INITIALIZED)
            return MONO56_ADC23_BAD_CONFIG;
        return fail(MONO56_ADC23_BAD_CONFIG);
    }
    out->valid = false;
    if (state != MONO56_ADC23_PENDING)
        return state;
    if (!configuration_valid())
        return fail(MONO56_ADC23_CONFIG_CHANGED);
    if ((uint32_t)(time_us() - armed_at) > capture_deadline)
        return fail(MONO56_ADC23_TIMEOUT);
    const uint32_t b_status = ADC2->SR, c_status = ADC3->SR;
    if ((b_status | c_status) & UNEXPECTED_FLAGS)
        return fail(MONO56_ADC23_UNEXPECTED_CONVERSION);
    if (((b_status & ADC_SR_JEOC) && !(b_status & ADC_SR_JSTRT)) ||
        ((c_status & ADC_SR_JEOC) && !(c_status & ADC_SR_JSTRT)))
        return fail(MONO56_ADC23_UNEXPECTED_CONVERSION);
    if ((b_status & COMPLETE_FLAGS) == COMPLETE_FLAGS) {
        close_channel(ADC2);
        completed_mask |= 1u;
    }
    if ((c_status & COMPLETE_FLAGS) == COMPLETE_FLAGS) {
        close_channel(ADC3);
        completed_mask |= 2u;
    }
    // Do not leave the first completed channel continually asserting the shared
    // IRQ while its partner finishes. Its JDR1 remains unread and JEOC retained.
    if (completed_mask != 3u)
        return state;
    __DSB();
    if ((ADC2->SR & COMPLETE_FLAGS) != COMPLETE_FLAGS ||
        (ADC3->SR & COMPLETE_FLAGS) != COMPLETE_FLAGS || ((ADC2->SR | ADC3->SR) & UNEXPECTED_FLAGS))
        return fail(MONO56_ADC23_UNEXPECTED_CONVERSION);
    const uint32_t b = ADC2->JDR1, c = ADC3->JDR1;
    const uint32_t observed = time_us();
    if ((uint32_t)(observed - armed_at) > capture_deadline)
        return fail(MONO56_ADC23_TIMEOUT);
    if (!configuration_valid())
        return fail(MONO56_ADC23_CONFIG_CHANGED);
    if (b > 4095u || c > 4095u)
        return fail(MONO56_ADC23_BAD_DATA);
    if (((ADC2->SR | ADC3->SR) & UNEXPECTED_FLAGS) ||
        (ADC2->SR & COMPLETE_FLAGS) != COMPLETE_FLAGS ||
        (ADC3->SR & COMPLETE_FLAGS) != COMPLETE_FLAGS)
        return fail(MONO56_ADC23_UNEXPECTED_CONVERSION);
    ADC2->SR = ADC3->SR = 0;
    out->b_raw = (uint16_t)b;
    out->c_raw = (uint16_t)c;
    out->armed_at_us = armed_at;
    out->observed_complete_at_us = observed;
    out->valid = true;
    state = MONO56_ADC23_IDLE;
    return MONO56_ADC23_FRAME_READY;
}
mono56_adc23_status mono56_adc23_shutdown(void) {
    if (state == MONO56_ADC23_NOT_INITIALIZED)
        return state;
    ADC2->CR1 = ADC3->CR1 = 0;
    ADC2->CR2 = ADC3->CR2 = 0;
    __DSB();
    ADC2->SR = ADC3->SR = 0;
    state = MONO56_ADC23_NOT_INITIALIZED;
    time_us = 0;
    completed_mask = 0;
    return state;
}
