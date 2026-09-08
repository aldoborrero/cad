#pragma once
#include "adc1_test_registers.h"
#ifdef __cplusplus
extern "C" {
#endif
extern GPIO_TypeDef mono56_test_adc23_gpioc;
void mono56_adc23_test_barrier(void);
#ifdef __cplusplus
}
#endif
#undef GPIOC
#define GPIOC (&mono56_test_adc23_gpioc)
#undef __DSB
#define __DSB() mono56_adc23_test_barrier()
