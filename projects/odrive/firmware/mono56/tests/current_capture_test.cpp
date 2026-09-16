#include "current_capture.h"
#include "current_capture_test_registers.h"
#include <cstdlib>
#include <cstring>
#include <iostream>

ADC_TypeDef mono56_test_adc1{}, mono56_test_adc2{}, mono56_test_adc3{};
ADC_Common_TypeDef mono56_test_adc_common{};
DMA_TypeDef mono56_test_dma2{};
DMA_Stream_TypeDef mono56_test_dma_stream{};
GPIO_TypeDef mono56_test_gpioa{}, mono56_test_gpiob{}, mono56_test_adc23_gpioc{};
TIM_TypeDef mono56_test_tim1{}, mono56_test_capture_tim5{};
RCC_TypeDef mono56_test_rcc{};
uint32_t mono56_test_primask = 0, mono56_test_irq_disable_calls = 0;
uint32_t mono56_capture_irq_enabled[82]{}, mono56_capture_irq_priority[82]{};
uint32_t mono56_capture_irq_group = 3;
namespace {
unsigned checks = 0, triggers = 0;
uint32_t complete_at = 0, previous_trigger = 0;
bool allowed = true, missing_b = false, missing_c = false;
bool adc_irq_delivery = true, deadline_irq_delivery = true;
bool event_pending = false, delay_trigger = false;
bool lose_permission_during_arm = false, lose_permission_during_release = false;
void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
bool permission(void *) { return allowed; }
const mono56_capture_config config{permission, nullptr, 1000, 10};
void advance(unsigned us) {
    for (unsigned i = 0; i < us; ++i) {
        ++TIM5->CNT;
        if (event_pending && TIM5->CNT == complete_at) {
            if (!missing_b && (ADC2->SR & ADC_SR_JSTRT)) {
                ADC2->JDR1 = 2050;
                ADC2->SR |= ADC_SR_JEOC;
            }
            if (!missing_c && (ADC3->SR & ADC_SR_JSTRT)) {
                ADC3->JDR1 = 2045;
                ADC3->SR |= ADC_SR_JEOC;
            }
            event_pending = false;
        }
        if (TIM5->CNT == TIM5->CCR1)
            TIM5->SR |= TIM_SR_CC1IF;
        if (!mono56_test_primask && adc_irq_delivery && mono56_capture_irq_enabled[ADC_IRQn] &&
            (((ADC2->CR1 & ADC_CR1_JEOCIE) && (ADC2->SR & ADC_SR_JEOC)) ||
             ((ADC3->CR1 & ADC_CR1_JEOCIE) && (ADC3->SR & ADC_SR_JEOC))))
            mono56_current_capture_adc_irq();
        if (!mono56_test_primask && deadline_irq_delivery &&
            mono56_capture_irq_enabled[TIM5_IRQn] && (TIM5->DIER & TIM_DIER_CC1IE) &&
            (TIM5->SR & TIM_SR_CC1IF))
            mono56_current_capture_deadline_irq();
    }
}
void reset(uint32_t now = 0) {
    mono56_current_capture_shutdown();
    mono56_test_adc1 = {};
    mono56_test_adc2 = {};
    mono56_test_adc3 = {};
    mono56_test_adc_common = {};
    mono56_test_dma2 = {};
    mono56_test_dma_stream = {};
    mono56_test_gpioa = {};
    mono56_test_gpiob = {};
    mono56_test_adc23_gpioc = {};
    mono56_test_tim1 = {};
    mono56_test_capture_tim5 = {};
    mono56_test_rcc = {};
    std::memset(mono56_capture_irq_enabled, 0, sizeof mono56_capture_irq_enabled);
    std::memset(mono56_capture_irq_priority, 0, sizeof mono56_capture_irq_priority);
    mono56_capture_irq_group = 3;
    mono56_test_primask = 0;
    TIM5->CR1 = TIM_CR1_CEN;
    TIM5->PSC = 83;
    TIM5->ARR = 0xffffffff;
    TIM5->CNT = now;
    RCC->APB1ENR = RCC_APB1ENR_TIM5EN;
    RCC->APB2ENR = RCC_APB2ENR_TIM1EN | RCC_APB2ENR_ADC1EN;
    ADC1->CR1 = ADC_CR1_SCAN;
    ADC1->CR2 = ADC_CR2_ADON | ADC_CR2_DMA;
    ADC->CCR = ADC_CCR_ADCPRE_0 | ADC_CCR_TSVREFE;
    DMA2_Stream0->CR = DMA_SxCR_EN | DMA_SxCR_TCIE;
    GPIOB->ODR = 1u << 12;
    triggers = 0;
    event_pending = delay_trigger = false;
    lose_permission_during_arm = lose_permission_during_release = false;
    missing_b = missing_c = false;
    adc_irq_delivery = deadline_irq_delivery = allowed = true;
}
void init() {
    expect(mono56_current_capture_init(&config) == MONO56_CAPTURE_IDLE,
           "stopped TIM1 and free TIM5 compare become explicit capture owners");
}
void start() {
    expect(mono56_current_capture_start() == MONO56_CAPTURE_PENDING,
           "one guarded TIM1 event arms a bounded capture");
}
void failed(mono56_capture_status error) {
    mono56_adc23_frame frame{};
    frame.valid = true;
    expect(mono56_current_capture_take(&frame) == error && !frame.valid,
           "failed owner cannot publish a capture");
    expect(mono56_current_capture_status() == error && mono56_current_capture_start() == error,
           "first error is retained and does not rearm");
    expect(!(TIM1->BDTR & TIM_BDTR_MOE) && GPIOB->BSRR == GPIO_BSRR_BR12,
           "capture fault directly inhibits PWM/ENABLE");
}
} // namespace
extern "C" void mono56_capture_test_barrier() {
    if (lose_permission_during_release && !(ADC2->CR2 & ADC_CR2_ADON) &&
        !(ADC3->CR2 & ADC_CR2_ADON)) {
        lose_permission_during_release = false;
        allowed = false;
    }
    if (lose_permission_during_arm && (ADC2->CR2 & ADC_CR2_JEXTEN)) {
        lose_permission_during_arm = false;
        allowed = false;
    }
    if (TIM1->EGR == TIM_EGR_UG && TIM1->CR2 == TIM_CR2_MMS_1) {
        TIM1->EGR = 0; // Model the write-only event register.
        if (triggers)
            expect(static_cast<uint32_t>(TIM5->CNT - previous_trigger) >= 1000,
                   "real trigger events respect the configured minimum interval");
        previous_trigger = TIM5->CNT;
        ++triggers;
        for (auto adc : {ADC2, ADC3})
            if ((adc->CR2 & (ADC_CR2_ADON | ADC_CR2_JEXTSEL | ADC_CR2_JEXTEN)) ==
                (ADC_CR2_ADON | ADC_CR2_JEXTSEL_0 | ADC_CR2_JEXTEN_0))
                adc->SR |= ADC_SR_JSTRT;
        complete_at = TIM5->CNT + 2;
        event_pending = true;
        if (delay_trigger) {
            TIM5->CNT += 20;
            delay_trigger = false;
        }
    }
}
extern "C" void mono56_adc23_test_barrier() {}
int main() {
    reset();
    init();
    expect(mono56_current_capture_start() == MONO56_CAPTURE_WARMING && triggers == 0,
           "warm-up never generates a premature event");
    advance(10);
    const auto bus = *ADC1;
    const auto dma = *DMA2_Stream0;
    start();
    expect(triggers == 1 && TIM1->CR1 == 0 && TIM1->CCER == 0 && TIM1->DIER == 0,
           "UG triggers both ADCs without running TIM1 or enabling PWM outputs");
    expect(TIM5->CCR1 == 21 && TIM5->DIER == TIM_DIER_CC1IE,
           "compare deadline includes quantization margin and starts before UG");
    expect(mono56_current_capture_start() == MONO56_CAPTURE_BUSY, "pending capture not replaced");
    advance(2);
    expect(mono56_current_capture_status() == MONO56_CAPTURE_READY && TIM5->DIER == 0,
           "ADC completion IRQ publishes once and cancels deadline IRQ");
    mono56_adc23_frame frame{};
    expect(mono56_current_capture_take(&frame) == MONO56_CAPTURE_READY && frame.valid &&
               frame.b_raw == 2050 && frame.c_raw == 2045 && frame.armed_at_us == 10 &&
               frame.observed_complete_at_us == 12,
           "IRQ mailbox preserves the actual acquisition bounds");
    expect(mono56_current_capture_take(&frame) == MONO56_CAPTURE_IDLE && !frame.valid,
           "foreground consumes the mailbox once");
    expect(mono56_current_capture_start() == MONO56_CAPTURE_BUSY && triggers == 1,
           "requests cannot create a faster trigger stream");
    advance(998);
    start();
    advance(2);
    expect(mono56_current_capture_take(&frame) == MONO56_CAPTURE_READY && frame.valid &&
               triggers == 2,
           "next permitted trigger yields a new complete pair");
    expect(std::memcmp(&bus, ADC1, sizeof bus) == 0 &&
               std::memcmp(&dma, DMA2_Stream0, sizeof dma) == 0 && TIM5->CR1 == TIM_CR1_CEN &&
               TIM5->PSC == 83,
           "capture IRQs preserve ADC1/DMA and the running system clock");
    for (unsigned failure = 0; failure < 5; ++failure) {
        reset();
        init();
        advance(10);
        if (failure == 0)
            missing_b = true;
        if (failure == 1)
            missing_c = true;
        if (failure == 2)
            adc_irq_delivery = false;
        if (failure == 3) {
            adc_irq_delivery = false;
            deadline_irq_delivery = false;
        }
        if (failure == 4)
            delay_trigger = true;
        if (failure == 4)
            expect(mono56_current_capture_start() == MONO56_CAPTURE_TIMEOUT,
                   "delayed event write cannot reset the deadline");
        else {
            start();
            advance(11);
            if (failure < 3)
                expect(mono56_current_capture_status() == MONO56_CAPTURE_TIMEOUT,
                       "deadline IRQ inhibits before foreground can poll");
        }
        failed(MONO56_CAPTURE_TIMEOUT);
        expect(ADC1->CR2 == (ADC_CR2_ADON | ADC_CR2_DMA) && (DMA2_Stream0->CR & DMA_SxCR_EN),
               "capture fault does not abort bus measurement");
    }
    for (unsigned phase = 0; phase < 3; ++phase) {
        reset();
        init();
        advance(10);
        if (phase)
            start();
        if (phase == 2)
            advance(2);
        allowed = false;
        if (!phase)
            expect(mono56_current_capture_start() == MONO56_CAPTURE_PERMISSION && triggers == 0,
                   "lost permission blocks trigger creation");
        failed(MONO56_CAPTURE_PERMISSION);
    }
    reset();
    init();
    advance(10);
    lose_permission_during_arm = true;
    expect(mono56_current_capture_start() == MONO56_CAPTURE_PERMISSION && triggers == 0,
           "permission loss during ADC arming blocks the later UG event");
    failed(MONO56_CAPTURE_PERMISSION);
    for (unsigned field = 0; field < 10; ++field) {
        reset();
        init();
        advance(10);
        start();
        if (field == 0)
            TIM1->CR1 = TIM_CR1_CEN;
        if (field == 1)
            TIM1->CR2 = 0;
        if (field == 2)
            TIM1->SMCR = 1;
        if (field == 3)
            TIM1->RCR = 1;
        if (field == 4)
            TIM5->PSC = 42;
        if (field == 5)
            TIM5->CCR1 += 1;
        if (field == 6)
            TIM5->DIER |= TIM_DIER_UIE;
        if (field == 7)
            ADC1->CR1 |= ADC_CR1_JEOCIE;
        if (field == 8)
            mono56_capture_irq_priority[ADC_IRQn] = 2;
        if (field == 9)
            mono56_capture_irq_group = 4;
        failed(MONO56_CAPTURE_TIMER_CHANGED);
    }
    for (unsigned conflict = 0; conflict < 5; ++conflict) {
        reset();
        if (conflict == 0)
            mono56_capture_irq_enabled[TIM5_IRQn] = 1;
        if (conflict == 1)
            mono56_capture_irq_enabled[ADC_IRQn] = 1;
        if (conflict == 2)
            TIM5->CCMR1 = 1;
        if (conflict == 3)
            TIM1->CR2 = 1;
        if (conflict == 4)
            ADC1->CR1 |= ADC_CR1_EOCIE;
        expect(mono56_current_capture_init(&config) == MONO56_CAPTURE_OWNERSHIP,
               "existing IRQ/timer ownership is rejected");
        failed(MONO56_CAPTURE_OWNERSHIP);
    }
    reset(0xfffffff4);
    init();
    advance(10);
    start();
    advance(2);
    expect(mono56_current_capture_take(&frame) == MONO56_CAPTURE_READY && frame.valid,
           "capture source and deadline handle a normal clock wrap");
    reset();
    init();
    advance(10);
    mono56_test_primask = 1;
    start();
    expect(mono56_test_primask == 1, "trigger setup preserves IRQ masking");
    mono56_test_primask = 0;
    advance(2);
    mono56_current_capture_shutdown();
    expect(TIM5->CR1 == TIM_CR1_CEN && TIM5->DIER == 0 && TIM1->CR2 == 0 &&
               mono56_current_capture_status() == MONO56_CAPTURE_UNINITIALIZED,
           "explicit shutdown releases trigger/IRQ ownership but preserves time");
    reset();
    init();
    advance(10);
    start();
    advance(2);
    expect(mono56_current_capture_take(&frame) == MONO56_CAPTURE_READY && frame.valid,
           "consume final calibration capture before ownership transfer");
    const auto release_time = TIM5->CNT;
    mono56_test_primask = 1;
    expect(mono56_current_capture_release() && mono56_test_primask == 1,
           "idle release preserves caller IRQ masking");
    mono56_test_primask = 0;
    expect(mono56_current_capture_status() == MONO56_CAPTURE_UNINITIALIZED &&
               mono56_current_capture_adc_status() == MONO56_ADC23_NOT_INITIALIZED &&
               GPIOB->ODR == (1u << 12) && GPIOB->BSRR == 0 && TIM1->CR2 == 0 &&
               TIM5->CNT == release_time && TIM5->CR1 == TIM_CR1_CEN && TIM5->DIER == 0 &&
               !mono56_capture_irq_enabled[ADC_IRQn] && !mono56_capture_irq_enabled[TIM5_IRQn] &&
               ADC2->CR2 == 0 && ADC3->CR2 == 0,
           "handoff releases capture resources without an ENABLE drop or timebase reset");
    expect(ADC1->CR2 == (ADC_CR2_ADON | ADC_CR2_DMA) && (DMA2_Stream0->CR & DMA_SxCR_EN),
           "idle release preserves continuous bus/reference acquisition");
    expect(!mono56_current_capture_release(),
           "duplicate release cannot create another successful handoff");
    failed(MONO56_CAPTURE_OWNERSHIP);
    for (unsigned phase = 0; phase < 3; ++phase) {
        reset();
        init();
        advance(10);
        if (phase < 2)
            start();
        if (phase == 1)
            advance(2);
        if (phase == 2)
            allowed = false;
        expect(!mono56_current_capture_release(),
               "pending/unread/unpermitted capture cannot be released");
        failed(phase == 2 ? MONO56_CAPTURE_PERMISSION : MONO56_CAPTURE_OWNERSHIP);
    }
    reset();
    init();
    lose_permission_during_release = true;
    expect(!mono56_current_capture_release(),
           "permission loss during resource release still inhibits");
    failed(MONO56_CAPTURE_PERMISSION);
    std::cout << checks
              << " stopped-TIM1 capture/IRQ/deadline checks passed with simulated peripherals.\n";
}
