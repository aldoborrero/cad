#pragma once
#include "adc23_test_registers.h"
#ifdef __cplusplus
extern "C" {
#endif
extern TIM_TypeDef mono56_test_capture_tim5;
extern uint32_t mono56_capture_irq_enabled[82], mono56_capture_irq_priority[82];
extern uint32_t mono56_capture_irq_group;
void mono56_capture_test_barrier(void);
#ifdef __cplusplus
}
#endif
#undef TIM5
#define TIM5 (&mono56_test_capture_tim5)
#undef __DSB
#define __DSB() mono56_capture_test_barrier()
#undef NVIC_GetPriorityGrouping
#undef NVIC_GetEnableIRQ
#undef NVIC_GetPriority
#undef NVIC_SetPriority
#undef NVIC_EnableIRQ
#undef NVIC_DisableIRQ
#undef NVIC_ClearPendingIRQ
#define NVIC_GetPriorityGrouping() (mono56_capture_irq_group)
#define NVIC_GetEnableIRQ(irq) (mono56_capture_irq_enabled[(irq)])
#define NVIC_GetPriority(irq) (mono56_capture_irq_priority[(irq)])
#define NVIC_SetPriority(irq, priority) (mono56_capture_irq_priority[(irq)] = (priority))
#define NVIC_EnableIRQ(irq) (mono56_capture_irq_enabled[(irq)] = 1)
#define NVIC_DisableIRQ(irq) (mono56_capture_irq_enabled[(irq)] = 0)
#define NVIC_ClearPendingIRQ(irq) ((void)(irq))
