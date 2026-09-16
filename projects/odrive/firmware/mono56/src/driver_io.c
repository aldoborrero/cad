#include "driver_io.h"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_DRIVER_IO_TEST
#include "driver_io_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

#define PWM_A (7u << 8)
#define PWM_B (7u << 13)
#define MODE_A (0x3fu << 16)
#define MODE_B (0x3fu << 26)
#define FB_MODE ((3u << 12) | (3u << 14))
#define EDGES (MONO56_DRIVER_FAULT_EDGE | MONO56_DRIVER_ENABLE_EDGE | MONO56_DRIVER_BRAKE_EDGE)
static bool owned, requested_once, fault_qualified, failed;

static void clear_pending(uint32_t mask) {
    // EXTI PR is write-one-to-clear. Never read-modify-write another line's PR.
#ifdef MONO56_DRIVER_IO_TEST
    mono56_driver_test_clear_pending(mask);
#else
    EXTI->PR = mask;
#endif
    __DSB();
}
static bool valid_configuration(void) {
    const uint32_t ports =
        RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN | RCC_AHB1ENR_GPIOCEN | RCC_AHB1ENR_GPIODEN;
    const uint32_t apb = RCC_APB2ENR_SYSCFGEN | RCC_APB2ENR_TIM1EN;
    return owned && !failed && (RCC->AHB1ENR & ports) == ports && (RCC->APB2ENR & apb) == apb &&
           !(GPIOC->MODER & FB_MODE) && !(GPIOC->PUPDR & FB_MODE) && !(GPIOD->MODER & (3u << 4)) &&
           !(GPIOD->PUPDR & (3u << 4)) && (GPIOB->MODER & (3u << 24)) == (1u << 24) &&
           !(GPIOB->OTYPER & (1u << 12)) && !(GPIOB->PUPDR & (3u << 24)) &&
           !((GPIOB->ODR ^ GPIOB->IDR) & (1u << 12)) &&
           (SYSCFG->EXTICR[0] & (15u << 8)) == (3u << 8) &&
           (SYSCFG->EXTICR[1] & (255u << 8)) == (0x22u << 8) && (EXTI->FTSR & EDGES) == EDGES &&
           (EXTI->IMR & EDGES) == EDGES && !((EXTI->RTSR | EXTI->EMR) & EDGES) &&
           !NVIC_GetEnableIRQ(EXTI2_IRQn) && !NVIC_GetEnableIRQ(EXTI9_5_IRQn);
}
static bool inhibited_outputs(void) {
    return (GPIOA->MODER & MODE_A) == (0x15u << 16) && (GPIOB->MODER & MODE_B) == (0x15u << 26) &&
           !(GPIOA->OTYPER & PWM_A) && !(GPIOB->OTYPER & PWM_B) && !(GPIOA->PUPDR & MODE_A) &&
           !(GPIOB->PUPDR & MODE_B) && !((GPIOA->ODR | GPIOA->IDR) & PWM_A) &&
           !((GPIOB->ODR | GPIOB->IDR) & PWM_B) && !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) &&
           TIM1->CCER == 0;
}
mono56_driver_inputs mono56_driver_io_read(void) {
    mono56_driver_inputs r = {0};
    if (!owned)
        return r;
    r.valid = valid_configuration();
    r.pwm_inhibited = inhibited_outputs();
    r.quiet = r.pwm_inhibited && !(TIM1->CR1 & TIM_CR1_CEN) && TIM1->DIER == 0;
    r.requested = (GPIOB->ODR & GPIOB->IDR & (1u << 12)) != 0;
    const uint32_t feedback = GPIOC->IDR;
    r.enable_feedback = (feedback & (1u << 6)) != 0;
    r.brake_ok = (feedback & (1u << 7)) != 0;
    r.nfault_high = (GPIOD->IDR & (1u << 2)) != 0;
    // Read pending LAST so a pulse during the level reads is also retained.
    r.falling_edges = EXTI->PR & EDGES;
    return r;
}
static bool reject(void) {
    failed = true;
    mono56_motor_inhibit();
    return false;
}
bool mono56_driver_io_prepare(void) {
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    mono56_motor_inhibit();
    if (owned) {
        reject();
        __set_PRIMASK(mask);
        return false;
    }
    if (((EXTI->IMR | EXTI->EMR | EXTI->RTSR | EXTI->FTSR) & EDGES) ||
        NVIC_GetEnableIRQ(EXTI2_IRQn) || NVIC_GetEnableIRQ(EXTI9_5_IRQn)) {
        __set_PRIMASK(mask);
        return false;
    }
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOCEN | RCC_AHB1ENR_GPIODEN;
    (void)RCC->AHB1ENR;
    RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;
    (void)RCC->APB2ENR;
    TIM1->CR1 &= ~TIM_CR1_CEN;
    TIM1->DIER = 0;
    TIM1->CCER = 0;
    GPIOA->BSRR = PWM_A << 16;
    GPIOB->BSRR = PWM_B << 16;
    GPIOA->OTYPER &= ~PWM_A;
    GPIOB->OTYPER &= ~PWM_B;
    GPIOA->PUPDR &= ~MODE_A;
    GPIOB->PUPDR &= ~(MODE_B | (3u << 24));
    GPIOA->OSPEEDR &= ~MODE_A;
    GPIOB->OSPEEDR &= ~(MODE_B | (3u << 24));
    GPIOA->MODER = (GPIOA->MODER & ~MODE_A) | (0x15u << 16);
    GPIOB->MODER = (GPIOB->MODER & ~MODE_B) | (0x15u << 26);
    GPIOC->MODER &= ~FB_MODE;
    GPIOC->PUPDR &= ~FB_MODE;
    GPIOD->MODER &= ~(3u << 4);
    GPIOD->PUPDR &= ~(3u << 4);
    SYSCFG->EXTICR[0] = (SYSCFG->EXTICR[0] & ~(15u << 8)) | (3u << 8);
    SYSCFG->EXTICR[1] = (SYSCFG->EXTICR[1] & ~(255u << 8)) | (0x22u << 8);
    EXTI->FTSR |= EDGES;
    // Arm EXTI capture; CPU delivery stays disabled in NVIC. Do not rely on
    // an interrupt-masked EXTI line to latch a pulse in PR.
    EXTI->IMR |= EDGES;
    // New session starts here. Expected previous ENABLE shutdown may have
    // caused an edge. All subsequent enable/brake edges are retained.
    clear_pending(EDGES);
    owned = true;
    failed = requested_once = fault_qualified = false;
    __DSB();
    __set_PRIMASK(mask);
    return true;
}
bool mono56_driver_io_request_enable(bool (*bus_permitted)(void *), void *context) {
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    const bool bus_ok = bus_permitted && bus_permitted(context);
    const mono56_driver_inputs r = mono56_driver_io_read();
    bool ok = bus_ok && r.valid && r.quiet && !requested_once && !r.requested &&
              !r.enable_feedback && r.brake_ok &&
              !(r.falling_edges & (MONO56_DRIVER_ENABLE_EDGE | MONO56_DRIVER_BRAKE_EDGE));
    if (ok) {
        requested_once = true;
        GPIOB->BSRR = GPIO_BSRR_BS12;
        __DSB();
        // Hardware interlock handles an asynchronous brake/rail/OV loss. The
        // owner must still observe actual ENABLE and qualify the wake duration.
    } else {
        reject();
    }
    __set_PRIMASK(mask);
    return ok;
}
bool mono56_driver_io_qualify_nfault(void) {
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    bool ok = owned && !failed && requested_once && !fault_qualified;
    if (ok) {
        fault_qualified = true;
        clear_pending(MONO56_DRIVER_FAULT_EDGE);
        const mono56_driver_inputs r = mono56_driver_io_read();
        ok = r.valid && r.quiet && r.requested && r.enable_feedback && r.brake_ok &&
             r.nfault_high && !r.falling_edges;
    }
    if (!ok)
        reject();
    __set_PRIMASK(mask);
    return ok;
}
void mono56_driver_io_shutdown(void) {
    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    mono56_motor_inhibit();
    if (owned) {
        EXTI->IMR &= ~EDGES;
        EXTI->FTSR &= ~EDGES;
        // Teardown ends capture history; software diagnostics belong to the
        // wake owner. Changing edge sensitivity may clear hardware PR bits.
        owned = false;
    }
    __DSB();
    __set_PRIMASK(mask);
}
