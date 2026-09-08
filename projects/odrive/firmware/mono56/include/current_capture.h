#pragma once
#include "adc23_acquisition.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    MONO56_CAPTURE_UNINITIALIZED,
    MONO56_CAPTURE_IDLE,
    MONO56_CAPTURE_PENDING,
    MONO56_CAPTURE_READY,
    MONO56_CAPTURE_WARMING,
    MONO56_CAPTURE_BUSY,
    MONO56_CAPTURE_BAD_CONFIG,
    MONO56_CAPTURE_OWNERSHIP,
    MONO56_CAPTURE_PERMISSION,
    MONO56_CAPTURE_TIMER_CHANGED,
    MONO56_CAPTURE_ADC_ERROR,
    MONO56_CAPTURE_TIMEOUT,
} mono56_capture_status;

typedef struct {
    // Must remain valid and callable with IRQs masked; no SPI or blocking work.
    // Checks fresh bus, quiet GPIO PWM, qualified ENABLE and fault history.
    bool (*permitted)(void *);
    void *context;
    uint32_t period_us, deadline_us;
} mono56_capture_config;

// Diagnostic/manual-calibration capture owner. TIM1 stays stopped, channels
// disabled, PWM pins remain under the GPIO/wake owner's LOW-output ownership.
// One software UG produces each common TIM1 update TRGO; it is NOT software
// starting the two ADCs separately. TIM5 remains the existing free 1 MHz clock;
// this owner reserves compare 1 + TIM5 IRQ as the capture deadline.
// Requires ADC/TIM5 vectors to dispatch to the two handlers below, priority
// grouping 3, PCLK2=84 MHz and APB1 timer clock=84 MHz. Rejects existing IRQ use.
// Init may run after wake/configuration; every error inhibits the motor. No
// automatic restart. The GPIO/PWM-running owner must replace this diagnostic
// trigger scheme before any motor control is attempted.
mono56_capture_status mono56_current_capture_init(const mono56_capture_config *config);
mono56_capture_status mono56_current_capture_start(void);
mono56_capture_status mono56_current_capture_take(mono56_adc23_frame *out);
mono56_capture_status mono56_current_capture_status(void);
mono56_adc23_status mono56_current_capture_adc_status(void);
// These handlers perform no SPI and never modify DriverWake/Drv8353 objects.
void mono56_current_capture_adc_irq(void);
void mono56_current_capture_deadline_irq(void);
// Explicit idle-only transfer to another timer/ADC owner. Releases ADC2/3,
// TIM1 TRGO and owned ADC/TIM5 vectors while preserving ENABLE and GPIO state.
// Requires fresh permission and no pending/unread capture; failures inhibit.
// Does not validate/transfer a current zero or grant motor/PWM permission. The
// caller must restore/verify normal CSA inputs and preserve its driver session.
// Success returns this owner to UNINITIALIZED; do not call its inhibiting
// shutdown afterward while another owner is running.
bool mono56_current_capture_release(void);
void mono56_current_capture_shutdown(void);

#ifdef __cplusplus
}
#endif
