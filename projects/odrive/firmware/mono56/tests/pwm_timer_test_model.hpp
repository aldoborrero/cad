#pragma once
#include "adc23_acquisition.h"
#include "pwm_cycle.hpp"
#ifdef MONO56_PWM_CAPTURE_TEST
#include "pwm_capture.hpp"
#endif
#include "pwm_cycle_test_registers.h"
#include <array>
#include <cstdlib>
#include <iostream>

ADC_TypeDef mono56_test_adc1{}, mono56_test_adc2{}, mono56_test_adc3{};
ADC_Common_TypeDef mono56_test_adc_common{};
DMA_TypeDef mono56_test_dma2{};
DMA_Stream_TypeDef mono56_test_dma_stream{};
GPIO_TypeDef mono56_test_gpioa{}, mono56_test_gpiob{}, mono56_test_adc23_gpioc{};
TIM_TypeDef mono56_test_tim1{}, mono56_test_capture_tim5{}, mono56_test_tim10{};
RCC_TypeDef mono56_test_rcc{};
uint32_t mono56_test_primask = 0, mono56_test_irq_disable_calls = 0;
uint32_t mono56_capture_irq_enabled[82]{}, mono56_capture_irq_priority[82]{};
uint32_t mono56_capture_irq_group = 3;
using namespace odrive::mono56;
namespace {
unsigned checks = 0, triggers = 0, starts = 0, frames = 0;
std::uint64_t timer_ticks = 0, conversion_at = 0, previous_trigger = 0;
unsigned tim5_fraction = 0, physical_cycle = 0;
std::array<unsigned, 4> shadow{}, captured{};
bool allowed = true, consumer_ok = true, auto_queue = true;
bool updates_enabled = true, adc_enabled = true, watchdog_enabled = true;
bool in_irq = false, in_sync = false, ref4 = false, converting = false;
unsigned commit_delay_ticks = 0, arm_delay_ticks = 0, barrier_delay_ticks = 0;
unsigned callback_delay_ticks = 0, missing_mask = 0;
unsigned barrier_delay_skip = 0;
bool auto_take = true;
PwmCycleObservation last_start{};
[[maybe_unused]] uint32_t now_us() { return TIM5->CNT; }
void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << "; clock=" << TIM5->CNT << " counter=" << TIM1->CNT
                  << " error=" << static_cast<unsigned>(pwm_cycle_error()) << '\n';
        std::exit(1);
    }
}
bool permission(void *) { return allowed; }
void advance(unsigned count);
bool begin_cycle(void *, const PwmCycleObservation *event) {
    ++starts;
    expect(event->valid && event->cycle == physical_cycle,
           "callback generation matches actual hardware underflow");
    expect(shadow[0] == event->plan.ccr_a && shadow[1] == event->plan.ccr_b &&
               shadow[2] == event->plan.ccr_c && shadow[3] == event->plan.ccr4,
           "active shadow compares match this cycle, not queued/preload values");
    last_start = *event;
    if (!consumer_ok)
        return false;
    const bool armed = mono56_adc23_arm() == MONO56_ADC23_PENDING;
    const auto delay = callback_delay_ticks;
    callback_delay_ticks = 0;
    advance(delay);
    return armed;
}
PwmCycleConfig fixture() {
    return {{3500, 200, 2500, 100, 500, 2000, 2000},
            nullptr,
            permission,
            begin_cycle,
            1000,
            1000,
            30,
            32};
}
void transfer() { shadow = {TIM1->CCR1, TIM1->CCR2, TIM1->CCR3, TIM1->CCR4}; }
void sync();
void tick() {
    ++timer_ticks;
    if ((TIM5->CR1 & TIM_CR1_CEN) && (RCC->APB1ENR & RCC_APB1ENR_TIM5EN)) {
        if (++tim5_fraction == 168) {
            tim5_fraction = 0;
            ++TIM5->CNT;
            if (TIM5->CNT == TIM5->CCR2)
                TIM5->SR |= TIM_SR_CC2IF;
            if (TIM5->CNT == TIM5->CCR1)
                TIM5->SR |= TIM_SR_CC1IF;
        }
    }
    sync();
    if ((TIM1->CR1 & TIM_CR1_CEN) && (RCC->APB2ENR & RCC_APB2ENR_TIM1EN)) {
        bool boundary = false;
        if (TIM1->CR1 & TIM_CR1_DIR) {
            if (--TIM1->CNT == 0) {
                TIM1->CR1 &= ~TIM_CR1_DIR;
                ++physical_cycle;
                boundary = true;
            }
        } else if (++TIM1->CNT == TIM1->ARR) {
            TIM1->CR1 |= TIM_CR1_DIR;
            boundary = true;
        }
        if (boundary && !(TIM1->CR1 & TIM_CR1_UDIS)) {
            transfer();
            TIM1->SR |= TIM_SR_UIF;
        }
        const bool next_ref =
            TIM1->CR1 & TIM_CR1_DIR ? TIM1->CNT > shadow[3] : TIM1->CNT >= shadow[3];
        if (next_ref && !ref4 && TIM1->CR2 == TIM_CR2_MMS) {
            if (triggers)
                expect(timer_ticks - previous_trigger >=
#ifdef MONO56_PWM_CAPTURE_TEST
                           fixture().min_trigger_spacing_us * 168,
#else
                           last_start.min_trigger_spacing_us * 168,
#endif

                       "actual successive trigger spacing preserves the ADC contract");
            previous_trigger = timer_ticks;
            ++triggers;
            TIM1->SR |= TIM_SR_CC4IF;
            captured = shadow;
            bool both = true;
            for (auto *adc : {ADC2, ADC3}) {
                const bool armed = (adc->CR2 & (ADC_CR2_ADON | ADC_CR2_JEXTEN | ADC_CR2_JEXTSEL)) ==
                                   (ADC_CR2_ADON | ADC_CR2_JEXTEN_0 | ADC_CR2_JEXTSEL_0);
                both &= armed;
                if (armed)
                    adc->SR |= ADC_SR_JSTRT;
            }
            expect(both, "both real ADC2/3 paths armed before the common hardware edge");
            converting = true;
            conversion_at = timer_ticks + 242;
        }
        ref4 = next_ref;
    }
    if (!(ADC2->CR2 & ADC_CR2_ADON) && !(ADC3->CR2 & ADC_CR2_ADON))
        converting = false;
    if (converting) {
        expect(shadow == captured, "active compares never change inside a current conversion");
        if (timer_ticks >= conversion_at) {
            converting = false;
            ADC2->JDR1 = 1900 + captured[1] / 10;
            ADC3->JDR1 = 1900 + captured[2] / 10;
            if (!(missing_mask & 1))
                ADC2->SR |= ADC_SR_JEOC;
            if (!(missing_mask & 2))
                ADC3->SR |= ADC_SR_JEOC;
        }
    }
    if (!mono56_test_primask && !in_irq) {
        in_irq = true;
        // ADC can win arbitration when both same-priority vectors are pending.
        if (adc_enabled &&
            (((ADC2->CR1 & ADC_CR1_JEOCIE) && (ADC2->SR & ADC_SR_JEOC)) ||
             ((ADC3->CR1 & ADC_CR1_JEOCIE) && (ADC3->SR & ADC_SR_JEOC))) &&
            pwm_cycle_state() == PwmCycleState::running) {
#ifdef MONO56_PWM_CAPTURE_TEST
            pwm_capture_adc_irq();
            PwmCaptureFrame pair;
            if (auto_take && pwm_capture_take(&pair)) {
                ++frames;
                expect(pair.valid && pair.adc.valid && pair.cycle.valid &&
                           pair.cycle.cycle == physical_cycle &&
                           pair.adc.b_raw == 1900 + shadow[1] / 10 &&
                           pair.adc.c_raw == 1900 + shadow[2] / 10,
                       "production capture binds distinct B/C data to hardware-active cycle");
                expect(pair.cycle.plan.ccr_a == shadow[0] && pair.cycle.plan.ccr_b == shadow[1] &&
                           pair.cycle.plan.ccr_c == shadow[2] && pair.cycle.plan.ccr4 == shadow[3],
                       "delivered history matches all hardware-active compares");
                expect(static_cast<uint32_t>(pair.adc.armed_at_us - pair.cycle.began_lower_us) <=
                               3 &&
                           static_cast<uint32_t>(pair.adc.observed_complete_at_us -
                                                 pair.cycle.began_lower_us) <= 30,
                       "production delivery preserves underflow/arm/completion bounds");
                PwmCaptureFrame duplicate;
                expect(!pwm_capture_take(&duplicate) && !duplicate.valid,
                       "each production capture is delivered exactly once");
                if (auto_queue) {
                    const unsigned n = pair.cycle.cycle + 1;
                    expect(pwm_capture_queue(n, 1200 + n % 10 * 17, 1500 + n % 10 * 13,
                                             1900 + n % 10 * 11),
                           "delivered production capture can drive the next cycle command");
                }
            }
#else
            PwmCycleObservation event;
            if (pwm_cycle_observe(&event)) {
                mono56_adc23_frame raw;
                const auto result = mono56_adc23_take(&raw);
                if (result == MONO56_ADC23_FRAME_READY) {
                    ++frames;
                    expect(event.cycle == last_start.cycle && event.cycle == physical_cycle &&
                               raw.b_raw == 1900 + event.plan.ccr_b / 10 &&
                               raw.c_raw == 1900 + event.plan.ccr_c / 10,
                           "ADC data binds to the active cycle and distinct B/C compares");
                    expect(raw.armed_at_us == last_start.began_lower_us ||
                               static_cast<uint32_t>(raw.armed_at_us - last_start.began_lower_us) <=
                                   3,
                           "current capture retains original underflow/arming bounds");
                    if (auto_queue) {
                        const unsigned n = event.cycle + 1;
                        expect(pwm_cycle_queue(n, 1200 + n % 10 * 17, 1500 + n % 10 * 13,
                                               1900 + n % 10 * 11),
                               "new current result can commit the next cycle after apex");
                    }
                }
            }
#endif
        }
        if (updates_enabled && (TIM1->SR & TIM_SR_UIF) && (TIM1->DIER & TIM_DIER_UIE) &&
            mono56_capture_irq_enabled[TIM1_UP_TIM10_IRQn])
#ifdef MONO56_PWM_CAPTURE_TEST
            pwm_capture_update_irq();
#else
            pwm_cycle_update_irq();
#endif
        if (watchdog_enabled && (TIM5->SR & TIM5->DIER & (TIM_SR_CC1IF | TIM_SR_CC2IF)) &&
            mono56_capture_irq_enabled[TIM5_IRQn])
#ifdef MONO56_PWM_CAPTURE_TEST
            pwm_capture_deadline_irq();
#else
            pwm_cycle_watchdog_irq();
#endif
        in_irq = false;
    }
}
void advance(unsigned count) {
    while (count--)
        tick();
}
void sync() {
    if (in_sync)
        return;
    in_sync = true;
    for (auto *port : {GPIOA, GPIOB}) {
        port->ODR = (port->ODR | (port->BSRR & 0xffffu)) & ~(port->BSRR >> 16);
        port->BSRR = 0;
        port->IDR = port->ODR;
    }
    if (!(TIM1->CCMR1 & TIM_CCMR1_OC1PE))
        shadow[0] = TIM1->CCR1;
    if (!(TIM1->CCMR1 & TIM_CCMR1_OC2PE))
        shadow[1] = TIM1->CCR2;
    if (!(TIM1->CCMR2 & TIM_CCMR2_OC3PE))
        shadow[2] = TIM1->CCR3;
    if (!(TIM1->CCMR2 & TIM_CCMR2_OC4PE))
        shadow[3] = TIM1->CCR4;
    if (TIM1->EGR & TIM_EGR_UG) {
        TIM1->EGR = 0;
        transfer();
        TIM1->CNT = 0;
        TIM1->CR1 &= ~TIM_CR1_DIR;
        ref4 = false;
        if (!(TIM1->CR1 & TIM_CR1_URS))
            TIM1->SR |= TIM_SR_UIF;
    }
    if (commit_delay_ticks && (TIM1->CR1 & TIM_CR1_DIR) && TIM1->CCR1 != shadow[0]) {
        const auto delay = commit_delay_ticks;
        commit_delay_ticks = 0;
        advance(delay);
    }
    if (arm_delay_ticks && (ADC2->CR2 & ADC_CR2_JEXTEN)) {
        const auto delay = arm_delay_ticks;
        arm_delay_ticks = 0;
        advance(delay);
    }
    if (barrier_delay_ticks) {
        if (barrier_delay_skip)
            --barrier_delay_skip;
        else {
            const auto delay = barrier_delay_ticks;
            barrier_delay_ticks = 0;
            advance(delay);
        }
    }
    in_sync = false;
}
void reset(uint32_t time = 0) {
#ifdef MONO56_PWM_CAPTURE_TEST
    pwm_capture_shutdown();
#endif
    pwm_cycle_shutdown();
    mono56_adc23_shutdown();
    mono56_test_tim1 = {};
    mono56_test_capture_tim5 = {};
    mono56_test_tim10 = {};
    mono56_test_adc1 = {};
    mono56_test_adc2 = {};
    mono56_test_adc3 = {};
    mono56_test_adc_common = {};
    mono56_test_rcc = {};
    mono56_test_gpioa = {};
    mono56_test_gpiob = {};
    mono56_test_adc23_gpioc = {};
    for (auto &v : mono56_capture_irq_enabled)
        v = 0;
    for (auto &v : mono56_capture_irq_priority)
        v = 0;
    mono56_capture_irq_group = 3;
    mono56_test_primask = 0;
    timer_ticks = previous_trigger = 0;
    tim5_fraction = physical_cycle = 0;
    triggers = starts = frames = missing_mask = 0;
    auto_take = true;
    shadow = {};
    captured = {};
    last_start = {};
    ref4 = converting = in_irq = in_sync = false;
    allowed = consumer_ok = auto_queue = updates_enabled = adc_enabled = watchdog_enabled = true;
    arm_delay_ticks = commit_delay_ticks = barrier_delay_ticks = callback_delay_ticks = 0;
    barrier_delay_skip = 0;
    TIM5->CR1 = TIM_CR1_CEN;
    TIM5->PSC = 83;
    TIM5->ARR = 0xffffffff;
    TIM5->CNT = time;
    RCC->APB1ENR = RCC_APB1ENR_TIM5EN;
    RCC->APB2ENR = RCC_APB2ENR_TIM1EN | RCC_APB2ENR_ADC1EN;
    RCC->AHB1ENR = RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN;
    GPIOA->MODER = 0x15u << 16;
    GPIOB->MODER = (0x15u << 26) | (1u << 24);
    GPIOB->ODR = GPIOB->IDR = 1u << 12;
    ADC1->CR1 = ADC_CR1_SCAN;
    ADC1->CR2 = ADC_CR2_ADON | ADC_CR2_DMA;
    ADC->CCR = ADC_CCR_ADCPRE_0 | ADC_CCR_TSVREFE;
#ifndef MONO56_PWM_CAPTURE_TEST
    expect(mono56_adc23_init(now_us, 84000000, 30, 32) == MONO56_ADC23_WARMING,
           "companion ADC owner initializes with the same bounded trigger contract");
    advance(1680);
#endif
}
#ifdef MONO56_PWM_CAPTURE_TEST
PwmCaptureConfig capture_fixture() {
    const auto c = fixture();
    return {c.sampling,
            nullptr,
            permission,
            c.boundary_budget_ns,
            c.commit_budget_ns,
            c.adc_deadline_us,
            c.min_trigger_spacing_us};
}
#endif
void start() {
#ifdef MONO56_PWM_CAPTURE_TEST
    expect(pwm_capture_init(capture_fixture()), "production capture owner initializes");
    expect(!pwm_capture_start(1750, 1800, 1900) && pwm_capture_state() == PwmCaptureState::warming,
           "early start waits for ADC stabilization without arming or faulting");
    advance(1680);
    expect(pwm_capture_start(1750, 1800, 1900),
           "production continuous capture starts after warmup");
#else
    expect(pwm_cycle_init(fixture()), "exclusive cycle owner initializes without PWM outputs");
    expect(pwm_cycle_start(1750, 1800, 1900),
           "continuous TIM1 starts with ADC armed on cycle zero");
#endif
}
[[maybe_unused]] void failed(PwmCycleError expected) {
    PwmCycleObservation event;
    expect(pwm_cycle_state() == PwmCycleState::fault && pwm_cycle_error() == expected,
           "specific first cycle fault retained");
    expect(!pwm_cycle_observe(&event) && !event.valid && !(GPIOB->ODR & (1u << 12)) &&
               !(TIM1->CR1 & TIM_CR1_CEN) && !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)),
           "fault inhibits ENABLE/timer and cannot return a current-looking cycle");
    const auto old_starts = starts;
    allowed = true;
    expect(!pwm_cycle_start(1750, 1800, 1900) && starts == old_starts &&
               pwm_cycle_error() == expected,
           "recovery does not restart or overwrite the first failure");
}
} // namespace
extern "C" void mono56_capture_test_barrier() { sync(); }
