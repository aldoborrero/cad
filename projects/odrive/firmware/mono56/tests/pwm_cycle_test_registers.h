#pragma once
#include "current_capture_test_registers.h"
extern TIM_TypeDef mono56_test_tim10;
#undef TIM10
#define TIM10 (&mono56_test_tim10)
