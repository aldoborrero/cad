#include "current_capture.h"
#include "pwm_timer_test_model.hpp"

namespace {
void capture_failed(PwmCaptureError expected) {
    PwmCaptureFrame invalid;
    expect(pwm_capture_state() == PwmCaptureState::fault && pwm_capture_error() == expected,
           "specific first capture failure is retained");
    expect(!pwm_capture_take(&invalid) && !invalid.valid && !(GPIOB->ODR & (1u << 12)) &&
               !(TIM1->CR1 & TIM_CR1_CEN) && !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) &&
               !(ADC2->CR2 & ADC_CR2_ADON) && !(ADC3->CR2 & ADC_CR2_ADON),
           "capture failure inhibits timer/ENABLE/ADC and invalidates delivery");
    allowed = true;
    expect(!pwm_capture_start(1750, 1800, 1900) && pwm_capture_error() == expected,
           "permission recovery cannot restart capture or replace its first error");
}
} // namespace
int main() {
    reset();
    start();
    advance(7000 * 12);
    expect(frames == 12 && triggers == 12 && physical_cycle == 12 &&
               pwm_capture_state() == PwmCaptureState::pending,
           "production owner captures and commands twelve complete cycles");
    expect(ADC1->CR1 == ADC_CR1_SCAN && ADC1->CR2 == (ADC_CR2_ADON | ADC_CR2_DMA) &&
               (ADC->CCR & ADC_CCR_TSVREFE),
           "shared ADC bus/reference configuration preserved");
    expect(TIM1->CCER == 0 && !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)),
           "continuous raw capture does not enable motor outputs");
    for (unsigned missing : {1u, 2u, 3u}) {
        reset();
        start();
        missing_mask = missing;
        advance(5300);
        capture_failed(PwmCaptureError::timeout);
        expect(triggers == 1 && physical_cycle == 0 && frames == 0,
               "missing ADC data stops before a second cycle without delivering a partial pair");
    }
    reset();
    start();
    adc_enabled = false;
    advance(5300);
    capture_failed(PwmCaptureError::timeout);
    expect(frames == 0, "ADC IRQ loss cannot be repaired by accepting JEOC after the deadline");
    reset();
    start();
    auto_take = false;
    auto_queue = false;
    expect(pwm_capture_queue(1, 1500, 1600, 1700),
           "queue future command before withholding delivery");
    advance(3700);
    expect(pwm_capture_state() == PwmCaptureState::ready && !(TIM5->DIER & TIM_DIER_CC1IE) &&
               (TIM5->DIER & TIM_DIER_CC2IE),
           "completed pair cancels only its own deadline");
    advance(3300);
    capture_failed(PwmCaptureError::unconsumed);
    expect(triggers == 1, "unconsumed pair is not overwritten or rearmed at the next cycle");
    reset();
    start();
    auto_take = false;
    auto_queue = false;
    advance(3700);
    PwmCaptureFrame pair;
    expect(pwm_capture_take(&pair) && pair.valid && pair.cycle.cycle == 0,
           "foreground can take the bounded completed frame once");
    expect(!pwm_capture_take(&pair) && !pair.valid && pwm_capture_state() == PwmCaptureState::idle,
           "second take cannot synthesize a fresh frame");
    reset();
    start();
    allowed = false;
    advance(3500);
    capture_failed(PwmCaptureError::permission);
    reset();
    start();
    TIM5->CCR1 += 1;
    expect(!pwm_capture_take(&pair), "capture deadline register drift is detected before delivery");
    capture_failed(PwmCaptureError::timer_changed);
    reset();
    start();
    ADC2->JOFR1 = 1;
    advance(3700);
    capture_failed(PwmCaptureError::adc);
    expect(pwm_capture_adc_status() == MONO56_ADC23_CONFIG_CHANGED,
           "ADC fault detail survives ADC shutdown");
    reset();
    start();
    expect(!pwm_capture_queue(2, 1500, 1600, 1700),
           "wrong cycle command propagates the timer fault");
    capture_failed(PwmCaptureError::cycle);
    reset();
    start();
    auto_take = false;
    ADC2->SR = ADC3->SR = ADC_SR_JSTRT | ADC_SR_JEOC;
    pwm_capture_adc_irq();
    capture_failed(PwmCaptureError::unexpected_phase);
    reset();
    auto bad = capture_fixture();
    bad.sampling.half_period_ticks = 0;
    expect(!pwm_capture_init(bad), "invalid timer configuration rejected");
    pwm_capture_shutdown();
    expect(pwm_cycle_state() == PwmCycleState::uninitialized && pwm_capture_init(capture_fixture()),
           "explicit shutdown also resets a failed timer initialization attempt");
    reset();
    start();
    auto_take = false;
    auto_queue = false;
    expect(pwm_capture_queue(1, 1500, 1600, 1700),
           "staged command permits late-delivery boundary test");
    advance(6990);
    barrier_delay_skip = 1;
    barrier_delay_ticks = 20;
    expect(!pwm_capture_take(&pair) && !pair.valid,
           "underflow during mailbox copy invalidates the caller's partially copied frame");
    capture_failed(PwmCaptureError::unconsumed);
    reset();
    start();
    adc_enabled = false;
    watchdog_enabled = false;
    advance(5300);
    expect(!pwm_capture_take(&pair),
           "polling enforces expiry when both ADC and deadline IRQs are lost");
    capture_failed(PwmCaptureError::timeout);
    reset();
    start();
    adc_enabled = false;
    advance(5100);
    barrier_delay_skip = 2;
    barrier_delay_ticks = 150;
    expect(!pwm_capture_take(&pair) && !pair.valid,
           "expiry during post-read cycle verification cannot publish a late pair");
    capture_failed(PwmCaptureError::timeout);
    reset();
    start();
    adc_enabled = false;
    advance(3700);
    mono56_test_primask = 1;
    expect(pwm_capture_take(&pair) && mono56_test_primask == 1,
           "nested masked caller retains its original interrupt mask on delivery");
    mono56_test_primask = 0;
    reset();
    start();
    TIM1->CR1 &= ~TIM_CR1_CEN;
    advance(5300);
    capture_failed(PwmCaptureError::cycle);
    reset();
    mono56_capture_irq_enabled[ADC_IRQn] = 1;
    expect(!pwm_capture_init(capture_fixture()) &&
               pwm_capture_error() == PwmCaptureError::ownership,
           "foreign shared ADC vector is rejected before timer initialization");
    pwm_capture_shutdown();
    expect(mono56_capture_irq_enabled[ADC_IRQn] == 1 &&
               pwm_cycle_state() == PwmCycleState::uninitialized,
           "shutdown does not release a foreign interrupt or timer state");
    reset();
    start();
    adc_enabled = watchdog_enabled = false;
    advance(5300);
    expect(!pwm_capture_queue(1, 1500, 1600, 1700),
           "command submission cannot bypass an expired capture when IRQ delivery is lost");
    capture_failed(PwmCaptureError::timeout);
    reset(0xfffffff0u);
    start();
    advance(7000 * 4);
    expect(frames == 4 && TIM5->CNT < 1000 && pwm_capture_state() == PwmCaptureState::pending,
           "capture deadlines and original timestamps survive microsecond-clock wrap");
    pwm_capture_shutdown();
    expect(TIM5->CR1 == TIM_CR1_CEN && TIM5->DIER == 0 && !mono56_capture_irq_enabled[ADC_IRQn] &&
               !mono56_capture_irq_enabled[TIM5_IRQn],
           "explicit shutdown releases both dispatchers while preserving the bus clock");
    reset();
    const mono56_capture_config stopped{permission, nullptr, 1000, 10};
    expect(mono56_current_capture_init(&stopped) == MONO56_CAPTURE_IDLE,
           "stopped capture first owns ADCs and the shared deadline vector");
    advance(1680);
    expect(mono56_current_capture_release() && (GPIOB->ODR & (1u << 12)),
           "idle transfer releases the old peripheral owner without dropping ENABLE");
    expect(pwm_capture_init(capture_fixture()),
           "continuous owner acquires the released TIM1/ADC/TIM5 resources");
    advance(1680);
    expect(pwm_capture_start(1750, 1800, 1900),
           "continuous capture starts in the retained ENABLE session");
    advance(7000 * 3);
    expect(frames == 3 && (GPIOB->ODR & (1u << 12)) &&
               mono56_current_capture_status() == MONO56_CAPTURE_UNINITIALIZED,
           "new owner produces three pairs while the stopped owner remains released");
    std::cout << checks << " continuous PWM capture/deadline/delivery checks passed.\n";
}
