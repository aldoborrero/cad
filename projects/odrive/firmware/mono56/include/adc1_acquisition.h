#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef uint32_t (*mono56_clock_us_fn)(void);

typedef enum {
    MONO56_ADC_IDLE,
    MONO56_ADC_WARMING,
    MONO56_ADC_PENDING,
    MONO56_ADC_FRAME_READY,
    MONO56_ADC_NOT_INITIALIZED,
    MONO56_ADC_BAD_CONFIG,
    MONO56_ADC_PERIPHERAL_BUSY,
    MONO56_ADC_BAD_DMA_MEMORY,
    MONO56_ADC_TIMEOUT,
    MONO56_ADC_DMA_ERROR,
    MONO56_ADC_OVERRUN,
    MONO56_ADC_BAD_TRANSFER,
} mono56_adc_status;

typedef struct {
    uint16_t bus_raw;
    uint16_t reference_raw;
    // Samples were acquired within this interval, not at completion/ISR time.
    uint32_t started_at_us;
    uint32_t observed_complete_at_us;
    bool valid;
} mono56_adc_frame;

// Exclusive owner of ADC1 and DMA2 stream 0/channel 0. Call from one serialized
// execution context, only after the board has inhibited motor PWM/enable.
// The clock callback must be monotonic, wrap as uint32_t, and remain available.
// Requires PCLK2=84 MHz, stable throughout operation; ADC prescaler is /4.
// Deadline is required (25..2^31-1 us), not a qualified production default.
mono56_adc_status mono56_adc1_init(mono56_clock_us_fn clock_us,
                                  uint32_t pclk2_hz, uint32_t deadline_us);
mono56_adc_status mono56_adc1_start(void);
// Delivers each frame once. Clears out->valid on every other outcome. Does not
// start the next frame, poll in a loop, or service the motor-control fault policy.
mono56_adc_status mono56_adc1_take(mono56_adc_frame* out);
// Explicit shutdown is required before recovering a latched acquisition fault.
// A busy DMA disable is reported without an unbounded wait; call again later.
mono56_adc_status mono56_adc1_shutdown(void);

#ifdef __cplusplus
}
#endif
