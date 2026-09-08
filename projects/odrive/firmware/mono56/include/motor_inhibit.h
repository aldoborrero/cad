#pragma once
#ifdef __cplusplus
extern "C" {
#endif

// STM32F405 mono board only: clear PB12 request and TIM1 MOE/AOE. This never
// enables a motor, changes brake PWM, or acknowledges/clears an axis fault.
// The board's arm path must share the same serialized fault/permission owner.
void mono56_motor_inhibit(void);

#ifdef __cplusplus
}
#endif
