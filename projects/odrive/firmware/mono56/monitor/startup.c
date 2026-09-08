// Reset-only diagnostic image startup, authored for this board (no vendor CRT).
#include "monitor.h"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_MONITOR_CURRENT
void ADC_IRQHandler(void);
void TIM5_IRQHandler(void);
#endif
#ifdef MONO56_MONITOR_TIMING
void TIM1_UP_TIM10_IRQHandler(void);
#endif

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _stack_top;
extern const uintptr_t mono56_vectors[];
volatile mono56_monitor_diagnostics mono56_monitor;

void mono56_monitor_panic(uint32_t code) {
    __disable_irq();
    mono56_motor_inhibit();
    mono56_monitor.fatal_code = code;
    mono56_monitor.exception_number = __get_IPSR();
    mono56_monitor.bus_ready = 0;
    // End a possibly interrupted diagnostic write with an even sequence number.
    mono56_monitor.sequence = (mono56_monitor.sequence + 2u) & ~1u;
    RCC->CIR = RCC_CIR_CSSC;
    __DSB();
    for (;;)
        __WFI();
}

void Default_Handler(void) { mono56_monitor_panic(1); }

static void wait_bits(volatile uint32_t *reg, uint32_t mask, uint32_t expected, uint32_t error) {
    // Finite iteration bound, not a calibrated millisecond timeout.
    for (uint32_t remaining = 1600000; remaining; --remaining) {
        if ((*reg & mask) == expected)
            return;
    }
    mono56_monitor_panic(error);
}

static void clock_init(void) {
    // Only hardware-reset entry is supported; no bootloader clock handoff.
    if ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_HSI || (RCC->CR & RCC_CR_PLLON))
        mono56_monitor_panic(2);
    RCC->APB1ENR |= RCC_APB1ENR_PWREN;
    (void)RCC->APB1ENR;
    PWR->CR |= PWR_CR_VOS;
    (void)PWR->CR;
    wait_bits(&PWR->CSR, PWR_CSR_VOSRDY, PWR_CSR_VOSRDY, 3);
    RCC->CR &= ~RCC_CR_HSEBYP;
    RCC->CR |= RCC_CR_HSEON;
    wait_bits(&RCC->CR, RCC_CR_HSERDY, RCC_CR_HSERDY, 4);
    // 8 MHz HSE / 4 * 168 / 2 = 168 MHz; PLLQ=7 gives 48 MHz.
    RCC->PLLCFGR = 4u | (168u << 6) | RCC_PLLCFGR_PLLSRC_HSE | (7u << 24);
    RCC->CR |= RCC_CR_PLLON;
    wait_bits(&RCC->CR, RCC_CR_PLLRDY, RCC_CR_PLLRDY, 5);
    // 3.3 V board; 5 WS requires VDD >= 2.7 V. Keep prefetch off (ES0182 ADC noise).
    FLASH->ACR = FLASH_ACR_LATENCY_5WS | FLASH_ACR_ICEN | FLASH_ACR_DCEN;
    wait_bits(&FLASH->ACR, FLASH_ACR_LATENCY, FLASH_ACR_LATENCY_5WS, 6);
    RCC->CFGR = (RCC->CFGR & ~(RCC_CFGR_HPRE | RCC_CFGR_PPRE1 | RCC_CFGR_PPRE2 | RCC_CFGR_SW)) |
                RCC_CFGR_PPRE1_DIV4 | RCC_CFGR_PPRE2_DIV2;
    RCC->CFGR |= RCC_CFGR_SW_PLL;
    wait_bits(&RCC->CFGR, RCC_CFGR_SWS, RCC_CFGR_SWS_PLL, 7);
    RCC->CR |= RCC_CR_CSSON; // HSE failure reaches the inhibiting NMI/default handler.
    __DSB();
    __ISB();
}

void Reset_Handler(void) {
    __disable_irq();
    mono56_motor_inhibit(); // Does not require .data/.bss or an FPU.
    for (uint32_t *p = &_sdata, *from = &_sidata; p < &_edata;)
        *p++ = *from++;
    for (uint32_t *p = &_sbss; p < &_ebss;)
        *p++ = 0;
    SCB->VTOR = (uint32_t)(uintptr_t)mono56_vectors;
    SCB->CPACR |= (0xfu << 20); // Enable CP10/CP11 before entering C++/float code.
    __DSB();
    __ISB();
    mono56_monitor.magic = 0x4d353644; // M56D
    mono56_monitor.version = 1;
    clock_init();
    mono56_monitor_main();
}

__attribute__((section(".isr_vector"), used, aligned(512))) const uintptr_t mono56_vectors[98] = {
    (uintptr_t)&_stack_top,     // vector 0
    (uintptr_t)Reset_Handler,   // vector 1
    (uintptr_t)Default_Handler, // vector 2
    (uintptr_t)Default_Handler, // vector 3
    (uintptr_t)Default_Handler, // vector 4
    (uintptr_t)Default_Handler, // vector 5
    (uintptr_t)Default_Handler, // vector 6
    0,                          // vector 7
    0,                          // vector 8
    0,                          // vector 9
    0,                          // vector 10
    (uintptr_t)Default_Handler, // vector 11
    (uintptr_t)Default_Handler, // vector 12
    0,                          // vector 13
    (uintptr_t)Default_Handler, // vector 14
    (uintptr_t)Default_Handler, // vector 15
    (uintptr_t)Default_Handler, // vector 16
    (uintptr_t)Default_Handler, // vector 17
    (uintptr_t)Default_Handler, // vector 18
    (uintptr_t)Default_Handler, // vector 19
    (uintptr_t)Default_Handler, // vector 20
    (uintptr_t)Default_Handler, // vector 21
    (uintptr_t)Default_Handler, // vector 22
    (uintptr_t)Default_Handler, // vector 23
    (uintptr_t)Default_Handler, // vector 24
    (uintptr_t)Default_Handler, // vector 25
    (uintptr_t)Default_Handler, // vector 26
    (uintptr_t)Default_Handler, // vector 27
    (uintptr_t)Default_Handler, // vector 28
    (uintptr_t)Default_Handler, // vector 29
    (uintptr_t)Default_Handler, // vector 30
    (uintptr_t)Default_Handler, // vector 31
    (uintptr_t)Default_Handler, // vector 32
    (uintptr_t)Default_Handler, // vector 33
#ifdef MONO56_MONITOR_CURRENT
    (uintptr_t)ADC_IRQHandler, // vector 34
#else
    (uintptr_t)Default_Handler, // vector 34
#endif
    (uintptr_t)Default_Handler, // vector 35
    (uintptr_t)Default_Handler, // vector 36
    (uintptr_t)Default_Handler, // vector 37
    (uintptr_t)Default_Handler, // vector 38
    (uintptr_t)Default_Handler, // vector 39
    (uintptr_t)Default_Handler, // vector 40
#ifdef MONO56_MONITOR_TIMING
    (uintptr_t)TIM1_UP_TIM10_IRQHandler, // vector 41
#else
    (uintptr_t)Default_Handler, // vector 41
#endif
    (uintptr_t)Default_Handler, // vector 42
    (uintptr_t)Default_Handler, // vector 43
    (uintptr_t)Default_Handler, // vector 44
    (uintptr_t)Default_Handler, // vector 45
    (uintptr_t)Default_Handler, // vector 46
    (uintptr_t)Default_Handler, // vector 47
    (uintptr_t)Default_Handler, // vector 48
    (uintptr_t)Default_Handler, // vector 49
    (uintptr_t)Default_Handler, // vector 50
    (uintptr_t)Default_Handler, // vector 51
    (uintptr_t)Default_Handler, // vector 52
    (uintptr_t)Default_Handler, // vector 53
    (uintptr_t)Default_Handler, // vector 54
    (uintptr_t)Default_Handler, // vector 55
    (uintptr_t)Default_Handler, // vector 56
    (uintptr_t)Default_Handler, // vector 57
    (uintptr_t)Default_Handler, // vector 58
    (uintptr_t)Default_Handler, // vector 59
    (uintptr_t)Default_Handler, // vector 60
    (uintptr_t)Default_Handler, // vector 61
    (uintptr_t)Default_Handler, // vector 62
    (uintptr_t)Default_Handler, // vector 63
    (uintptr_t)Default_Handler, // vector 64
    (uintptr_t)Default_Handler, // vector 65
#ifdef MONO56_MONITOR_CURRENT
    (uintptr_t)TIM5_IRQHandler, // vector 66
#else
    (uintptr_t)Default_Handler, // vector 66
#endif
    (uintptr_t)Default_Handler,         // vector 67
    (uintptr_t)Default_Handler,         // vector 68
    (uintptr_t)Default_Handler,         // vector 69
    (uintptr_t)Default_Handler,         // vector 70
    (uintptr_t)TIM7_IRQHandler,         // vector 71
    (uintptr_t)DMA2_Stream0_IRQHandler, // vector 72
    (uintptr_t)Default_Handler,         // vector 73
    (uintptr_t)Default_Handler,         // vector 74
    (uintptr_t)Default_Handler,         // vector 75
    (uintptr_t)Default_Handler,         // vector 76
    0,                                  // vector 77
    0,                                  // vector 78
    (uintptr_t)Default_Handler,         // vector 79
    (uintptr_t)Default_Handler,         // vector 80
    (uintptr_t)Default_Handler,         // vector 81
    (uintptr_t)Default_Handler,         // vector 82
    (uintptr_t)Default_Handler,         // vector 83
    (uintptr_t)Default_Handler,         // vector 84
    (uintptr_t)Default_Handler,         // vector 85
    (uintptr_t)Default_Handler,         // vector 86
    (uintptr_t)Default_Handler,         // vector 87
    (uintptr_t)Default_Handler,         // vector 88
    (uintptr_t)Default_Handler,         // vector 89
    (uintptr_t)Default_Handler,         // vector 90
    (uintptr_t)Default_Handler,         // vector 91
    (uintptr_t)Default_Handler,         // vector 92
    (uintptr_t)Default_Handler,         // vector 93
    0,                                  // vector 94
    0,                                  // vector 95
    (uintptr_t)Default_Handler,         // vector 96
    (uintptr_t)Default_Handler,         // vector 97
};
