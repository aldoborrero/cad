#pragma once
#include "driver_io_test_registers.h"
#include "monitor_test_registers.h"
#include "spi3_test_registers.h"
// The integration test shares ONE peripheral instance across all modules.
#undef GPIOC
#undef RCC
#undef __DSB
#undef NVIC_GetEnableIRQ
#define GPIOC (&mono56_test_gpioc)
#define RCC (&mono56_test_rcc)
#define __DSB() mono56_driver_test_sync()
#define NVIC_GetEnableIRQ(irq) (mono56_test_irq_enabled[(irq)])
#undef NVIC_GetPriorityGrouping
#undef NVIC_GetPriority
#define NVIC_GetPriorityGrouping() (mono56_test_priority_group)
#define NVIC_GetPriority(irq) (mono56_test_irq_priority[(irq)])
#ifdef __cplusplus
extern "C" {
#endif
uint32_t mono56_diagnostic_test_clock(void);
#ifdef __cplusplus
}
#endif

#ifdef MONO56_MONITOR_TIMING
extern TIM_TypeDef mono56_test_tim10;
#undef TIM10
#define TIM10 (&mono56_test_tim10)
#endif
