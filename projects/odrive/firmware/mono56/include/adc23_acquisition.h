#pragma once
#include "adc1_acquisition.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    MONO56_ADC23_NOT_INITIALIZED,
    MONO56_ADC23_WARMING,
    MONO56_ADC23_IDLE,
    MONO56_ADC23_PENDING,
    MONO56_ADC23_FRAME_READY,
    MONO56_ADC23_BUSY,
    MONO56_ADC23_BAD_CONFIG,
    MONO56_ADC23_TIMEOUT,
    MONO56_ADC23_CONFIG_CHANGED,
    MONO56_ADC23_UNEXPECTED_CONVERSION,
    MONO56_ADC23_BAD_DATA,
} mono56_adc23_status;

typedef struct {
    uint16_t b_raw, c_raw;
    // Conservative acquisition interval, not fabricated per-channel timestamps.
    // The common TIM1_TRGO edge occurs AFTER armed_at_us and before completion.
    uint32_t armed_at_us, observed_complete_at_us;
    bool valid;
} mono56_adc23_frame;

// Exclusive ADC2/3 owner: PC0/channel 10 (B), PC1/channel 11 (C), injected rank 1,
// independent mode, PCLK2=84 MHz /4, 15 sampling cycles, no regular conversions.
// Preserves ADC1, its DMA, other GPIOs, reference enable and NVIC configuration.
// Init before motor operation; all calls require one serialized execution owner.
// TIM1/NVIC scheduling is external. Both ADCs use the rising TIM1_TRGO edge.
// The timer owner MUST guarantee the stated minimum spacing, including software
// update/reset events. deadline includes the lead from arm to trigger, conversion,
// IRQ latency and data reads. 3 <= deadline; deadline+1 < min spacing < 2^31 us.
// The extra microsecond accounts for clock quantization. This is a timing
// contract, NOT measurement of the actual trigger spacing by this component.
mono56_adc23_status mono56_adc23_init(mono56_clock_us_fn clock_us, uint32_t pclk2_hz,
                                      uint32_t deadline_us, uint32_t min_trigger_spacing_us);
// Arm before the next common event, after >=10 us ADC stabilization. Does not
// trigger conversion, start TIM1 or enable any motor output. An overlapping arm
// returns BUSY and leaves the first capture pending. No unbounded polling.
mono56_adc23_status mono56_adc23_arm(void);
// Call from the shared ADC IRQ dispatcher and a deadline service. A single JEOC
// masks that channel's IRQ/trigger while waiting for its partner; both must
// finish before the deadline. The dispatcher still owns ADC1 IRQ handling.
// Valid pair delivered once; out->valid is false on every other return.
// Missing/late/drifted capture faults latch; the axis owner must inhibit on them.
mono56_adc23_status mono56_adc23_take(mono56_adc23_frame *out);
mono56_adc23_status mono56_adc23_shutdown(void);

#ifdef __cplusplus
}
#endif
