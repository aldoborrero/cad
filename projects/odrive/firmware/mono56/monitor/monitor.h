#pragma once
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
// Read with SWD. For a coherent live snapshot, read sequence before/after and
// accept equal even values. A halted CPU does not freeze timers/DMA in this image.
typedef struct {
    uint32_t magic, version, sequence;
    uint32_t fatal_code, exception_number;
    uint32_t timer_interrupts, dma_interrupts, observed_at_us;
    uint32_t bus_ready, bus_fault, acquisition_status, measurement_error;
    float bus_v, vdda_v;
    uint32_t driver_enable_feedback, brake_permission_feedback;
} mono56_monitor_diagnostics;
extern volatile mono56_monitor_diagnostics mono56_monitor;
// Reset-only initialization, with IRQs masked and the 168/84/42 MHz clocks ready.
bool mono56_monitor_begin(uint16_t calibration);
// Coherent IRQ-published bus permission with original acquisition age checked.
// Nonblocking, saves/restores PRIMASK; safe inside the guarded ENABLE request.
bool mono56_monitor_bus_permitted(void *unused);
bool mono56_monitor_bus_faulted(void);
// Fresh coherent VDDA estimate for current acquisition/calibration. Preserves
// the original bus acquisition timestamp; false returns NaN and timestamp zero.
bool mono56_monitor_supply(float *vdda_v, uint32_t *sampled_at_us);
void mono56_monitor_main(void) __attribute__((noreturn));
void mono56_monitor_panic(uint32_t code) __attribute__((noreturn));
void TIM7_IRQHandler(void);
void DMA2_Stream0_IRQHandler(void);
#ifdef __cplusplus
}
#endif
