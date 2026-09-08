#pragma once
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

// EXTI pending bits retained until explicit session teardown. Falling edges:
// PD2 nFAULT, PC6 actual ENABLE, PC7 brake permission.
#define MONO56_DRIVER_FAULT_EDGE (1u << 2)
#define MONO56_DRIVER_ENABLE_EDGE (1u << 6)
#define MONO56_DRIVER_BRAKE_EDGE (1u << 7)

typedef struct {
    bool valid, quiet, requested, enable_feedback, brake_ok, nfault_high;
    uint32_t falling_edges;
    // Six GPIO PWM inputs LOW and CCER/MOE/AOE clear, independently of CEN/DIER.
    // Allows internal timer/ADC operation, never physical PWM switching.
    bool pwm_inhibited;
} mono56_driver_inputs;

// Exclusive TIM1, PA8..10, PB12..15, PC6/7, PD2 and EXTI2/6/7 owner.
// The previous PWM/DMA owner must already be stopped. Never call on a running
// controller. Inhibits first, holds six PWM GPIOs LOW, configures feedback without
// pulls and falling-edge capture. Does not enable NVIC interrupts or the driver.
// EXTI IMR is armed, but NVIC EXTI2 and EXTI9_5 must remain disabled; this
// polled startup owner cannot share those vectors with active IRQ users.
// Active foreign EXTI ownership is rejected. False still inhibits the motor.
bool mono56_driver_io_prepare(void);
mono56_driver_inputs mono56_driver_io_read(void);
// Caller must FIRST establish full driver sleep, fresh bus permission and the
// qualified startup sequence. Atomic local checks do not establish those facts.
// bus_permitted is checked with IRQs masked immediately before local input checks;
// it must be nonblocking and validate freshness/retained bus faults without IRQs.
// This can raise PB12 once; duplicate requests fail and inhibit. Never starts PWM.
bool mono56_driver_io_request_enable(bool (*bus_permitted)(void *), void *context);
// After the qualified wake interval, establish nFAULT edge history. Initial
// wake UV faults may have asserted nFAULT. Clears ONLY PD2's prior pending bit,
// then requires live healthy feedback with no new pending fault. Call once per
// session; repeated calls fail/inhibit so they cannot erase a later fault.
bool mono56_driver_io_qualify_nfault(void);
// Inhibit and release owned EXTI detection. Leaves motor GPIOs LOW. This is the
// explicit teardown; read/request cannot recover a failed request implicitly.
void mono56_driver_io_shutdown(void);
#ifdef __cplusplus
}
#endif
