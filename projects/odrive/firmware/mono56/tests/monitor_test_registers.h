#pragma once
#include "adc1_test_registers.h"
extern GPIO_TypeDef mono56_test_gpioc;
extern TIM_TypeDef mono56_test_tim5, mono56_test_tim7;
extern uint32_t mono56_test_priority_group, mono56_test_irq_priority[82];
extern bool mono56_test_irq_enabled[82], mono56_test_irq_cleared[82];
#undef GPIOC
#undef TIM5
#undef TIM7
#define GPIOC (&mono56_test_gpioc)
#define TIM5 (&mono56_test_tim5)
#define TIM7 (&mono56_test_tim7)
#undef NVIC_SetPriorityGrouping
#undef NVIC_SetPriority
#undef NVIC_ClearPendingIRQ
#undef NVIC_EnableIRQ
#undef NVIC_DisableIRQ
#define NVIC_SetPriorityGrouping(group) (mono56_test_priority_group = (group))
#define NVIC_SetPriority(irq, value) (mono56_test_irq_priority[(irq)] = (value))
#define NVIC_ClearPendingIRQ(irq) (mono56_test_irq_cleared[(irq)] = true)
#define NVIC_EnableIRQ(irq) (mono56_test_irq_enabled[(irq)] = true)
#define NVIC_DisableIRQ(irq) (mono56_test_irq_enabled[(irq)] = false)
#define __enable_irq() (mono56_test_primask = 0)
#undef __WFI
#define __WFI() __builtin_trap()
