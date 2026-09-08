#include "pwm_timer_test_model.hpp"

int main() {
    reset();
    start();
    advance(7000 * 12);
    expect(starts == 13 && frames == 12 && triggers == 12,
           "twelve hardware-triggered ADC pairs cross real preload transfers");
    expect(ADC1->CR1 == ADC_CR1_SCAN && ADC1->CR2 == (ADC_CR2_ADON | ADC_CR2_DMA) &&
               (ADC->CCR & ADC_CCR_TSVREFE),
           "cycle/ADC2/3 service preserves bus/reference ownership");
    expect(TIM1->CCER == 0 && !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) &&
               !(GPIOA->ODR & (7u << 8)) && !(GPIOB->ODR & (7u << 13)),
           "running internal timer never enables motor PWM outputs");
    reset();
    start();
    auto_queue = false;
    expect(pwm_cycle_queue(1, 2100, 2200, 2300), "upcount command waits in software for apex");
    expect(TIM1->CCR1 == 1750, "queued upcount command has not touched preloads");
    advance(3500);
    expect(TIM1->CCR1 == 2100 && shadow[0] == 1750,
           "apex transfer retained active values before committing next preloads");
    advance(3500);
    expect(shadow[0] == 2100 && last_start.cycle == 1 && frames == 1,
           "underflow alone activates staged values and publishes the next generation");
    reset();
    start();
    auto_queue = false;
    advance(7000);
    failed(PwmCycleError::command_missing);
    expect(physical_cycle == 0, "missing command watchdog stops before the next underflow");
    reset();
    start();
    updates_enabled = adc_enabled = false;
    advance(7000);
    failed(PwmCycleError::boundary_late);
    reset();
    start();
    TIM1->CR1 &= ~TIM_CR1_CEN;
    advance(7000);
    failed(PwmCycleError::boundary_late);
    reset();
    start();
    allowed = false;
    advance(3500);
    failed(PwmCycleError::permission);
    reset();
    start();
    expect(!pwm_cycle_queue(2, 1500, 1600, 1700), "wrong target generation rejected");
    failed(PwmCycleError::command_generation);
    reset();
    start();
    expect(pwm_cycle_queue(1, 1500, 1600, 1700), "first queued command accepted");
    expect(!pwm_cycle_queue(1, 1550, 1650, 1750), "duplicate cannot replace pending command");
    failed(PwmCycleError::command_busy);
    reset();
    start();
    auto_queue = false;
    advance(3650);
    commit_delay_ticks = 200;
    expect(!pwm_cycle_queue(1, 1500, 1600, 1700), "over-budget four-register commit rejected");
    failed(PwmCycleError::commit_late);
    reset();
    start();
    auto_queue = false;
    advance(3650);
    commit_delay_ticks = 4000;
    expect(!pwm_cycle_queue(1, 1500, 1600, 1700),
           "counter crossing during UDIS cannot create an epoch");
    failed(PwmCycleError::commit_late);
    expect(shadow[0] == 1750 && shadow[1] == 1800 && shadow[2] == 1900,
           "update suppression prevents invalid writes from transferring across the missed edge");
    reset();
    expect(pwm_cycle_init(fixture()), "late-arm fixture initializes");
    arm_delay_ticks = 400;
    expect(!pwm_cycle_start(1750, 1800, 1900), "callback cannot exceed the ADC-arm budget");
    failed(PwmCycleError::boundary_late);
    reset();
    start();
    TIM1->CCR2 = 123;
    PwmCycleObservation invalid;
    expect(!pwm_cycle_observe(&invalid), "foreign preload write invalidates cycle history");
    failed(PwmCycleError::timer_changed);
    reset();
    ADC2->CR2 |= ADC_CR2_JEXTEN_0;
    expect(!pwm_cycle_init(fixture()), "armed foreign ADC rejected before OC4 mode/UG changes");
    failed(PwmCycleError::ownership);
    reset();
    expect(pwm_cycle_init(fixture()), "full-cycle callback-delay fixture initializes");
    callback_delay_ticks = 7100;
    expect(!pwm_cycle_start(1750, 1800, 1900),
           "full-cycle callback delay cannot alias to a small upcount");
    failed(PwmCycleError::boundary_late);
    reset();
    auto tight_spacing = fixture();
    tight_spacing.min_trigger_spacing_us = 41;
    expect(pwm_cycle_init(tight_spacing) && pwm_cycle_start(3027, 3000, 2900),
           "late-trigger first plan is individually valid");
    expect(!pwm_cycle_queue(1, 1750, 1800, 1900),
           "earlier next CCR4 would shorten the actual trigger gap below the ADC contract");
    failed(PwmCycleError::trigger_spacing);
    reset();
    consumer_ok = false;
    expect(pwm_cycle_init(fixture()) && !pwm_cycle_start(1750, 1800, 1900),
           "consumer refusal inhibits cycle start");
    failed(PwmCycleError::consumer);
    reset();
    RCC->APB2ENR |= RCC_APB2ENR_TIM10EN;
    TIM10->DIER = TIM_DIER_UIE;
    expect(!pwm_cycle_init(fixture()), "active shared TIM10 vector ownership rejected");
    failed(PwmCycleError::ownership);
    reset();
    start();
    mono56_capture_irq_priority[TIM5_IRQn] = 2;
    expect(!pwm_cycle_observe(&invalid), "foreign watchdog priority change rejected");
    failed(PwmCycleError::timer_changed);
    reset();
    start();
    advance(1500);
    TIM1->CNT = 0;
    expect(!pwm_cycle_observe(&invalid),
           "counter reset without UIF fails independent clock correlation");
    failed(PwmCycleError::boundary_late);
    reset();
    start();
    adc_enabled = updates_enabled = false;
    advance(3550);
    expect(pwm_cycle_observe(&invalid) && invalid.cycle == 0 && invalid.phase_ticks == 3550,
           "consumer can service a pending apex within the boundary budget");
    reset();
    start();
    adc_enabled = updates_enabled = false;
    advance(3750);
    expect(!pwm_cycle_observe(&invalid), "late apex cannot publish an apparently current cycle");
    failed(PwmCycleError::boundary_late);
    reset();
    start();
    advance(3480);
    barrier_delay_ticks = 40;
    expect(!pwm_cycle_observe(&invalid), "boundary during observation cannot mix epoch and phase");
    failed(PwmCycleError::boundary_late);
    reset(0xfffffff0u);
    start();
    advance(7000 * 4);
    expect(TIM5->CNT < 1000 && frames == 4 && pwm_cycle_state() == PwmCycleState::running,
           "independent microsecond clock wrap preserves cycles and acquisition deadlines");
    std::cout << checks << " continuous PWM-cycle/preload/ADC integration checks passed.\n";
}
