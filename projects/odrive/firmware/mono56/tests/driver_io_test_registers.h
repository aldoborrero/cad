#pragma once
#include "adc1_test_registers.h"
#ifdef __cplusplus
extern "C" {
#endif
extern GPIO_TypeDef mono56_test_driver_gpioc, mono56_test_driver_gpiod;
extern SYSCFG_TypeDef mono56_test_syscfg;
extern EXTI_TypeDef mono56_test_exti;
extern uint32_t mono56_test_driver_nvic_enabled;
extern uint32_t mono56_test_driver_ipsr;
void mono56_driver_test_sync(void);
void mono56_driver_test_clear_pending(uint32_t mask);
#ifdef __cplusplus
}
#endif
#undef GPIOC
#undef GPIOD
#undef SYSCFG
#undef EXTI
#define GPIOC (&mono56_test_driver_gpioc)
#define GPIOD (&mono56_test_driver_gpiod)
#define SYSCFG (&mono56_test_syscfg)
#define EXTI (&mono56_test_exti)
#undef __DSB
#define __DSB() mono56_driver_test_sync()
#define __get_IPSR() (mono56_test_driver_ipsr)

#undef NVIC_GetEnableIRQ
#define NVIC_GetEnableIRQ(irq) ((mono56_test_driver_nvic_enabled >> (uint32_t)(irq)) & 1u)
