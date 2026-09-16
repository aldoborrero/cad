#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_MOTOR_TEST
#include "adc1_test_registers.h"
#elif defined(MONO56_DRIVER_IO_TEST)
#include "driver_io_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif
#ifdef MONO56_PWM_CYCLE_TEST
#include "pwm_cycle_test_registers.h"
#endif

void mono56_motor_inhibit(void) {
    const uint32_t interrupt_mask = __get_PRIMASK();
    __disable_irq();
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOBEN;
    (void)RCC->AHB1ENR;
    GPIOB->BSRR = GPIO_BSRR_BR12; // Preload LOW before selecting output mode.
    GPIOB->OTYPER &= ~(1u << 12);
    GPIOB->MODER = (GPIOB->MODER & ~(3u << 24)) | (1u << 24);
    RCC->APB2ENR |= RCC_APB2ENR_TIM1EN;
    (void)RCC->APB2ENR;
    // AOE must stay clear: otherwise an update can re-enable PWM (ES0182 2.7.1).
    TIM1->BDTR &= ~(TIM_BDTR_MOE | TIM_BDTR_AOE);
    __DSB();
    __set_PRIMASK(interrupt_mask);
}
