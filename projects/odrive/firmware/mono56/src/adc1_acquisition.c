#include "adc1_acquisition.h"
#include "stm32f405xx.h"

#ifdef MONO56_ADC_TEST
#include "adc1_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

#define DMA_CLEAR_FLAGS (DMA_LIFCR_CFEIF0 | DMA_LIFCR_CDMEIF0 | DMA_LIFCR_CTEIF0 | \
                         DMA_LIFCR_CHTIF0 | DMA_LIFCR_CTCIF0)
#define DMA_ERROR_FLAGS (DMA_LISR_FEIF0 | DMA_LISR_DMEIF0 | DMA_LISR_TEIF0)

static mono56_clock_us_fn time_us;
static mono56_adc_status state = MONO56_ADC_NOT_INITIALIZED;
static uint32_t enabled_at_us, started_at_us, frame_deadline_us;
static volatile uint16_t frame_buffer[2] __attribute__((aligned(4)));

#ifdef MONO56_ADC_TEST
volatile uint16_t* mono56_adc_test_buffer(void) { return frame_buffer; }
#endif

static bool faulted(void) {
    return state == MONO56_ADC_TIMEOUT || state == MONO56_ADC_DMA_ERROR ||
           state == MONO56_ADC_OVERRUN || state == MONO56_ADC_BAD_TRANSFER;
}

static mono56_adc_status fail(mono56_adc_status error) {
    // Stop new requests/conversions before asking DMA to disable. Do not reuse
    // its storage until EN has actually cleared in shutdown/init.
    ADC1->CR2 &= ~(ADC_CR2_ADON | ADC_CR2_DMA | ADC_CR2_SWSTART);
    DMA2_Stream0->CR &= ~DMA_SxCR_EN;
    state = error;
    return state;
}

mono56_adc_status mono56_adc1_init(mono56_clock_us_fn clock_us,
                                  uint32_t pclk2_hz, uint32_t deadline_us) {
    if (state != MONO56_ADC_NOT_INITIALIZED) {
        return MONO56_ADC_PERIPHERAL_BUSY;
    }
    if (!clock_us || pclk2_hz != 84000000u || deadline_us < 25u ||
        deadline_us >= 0x80000000u) {
        return MONO56_ADC_BAD_CONFIG;
    }
#ifndef MONO56_ADC_TEST
    // STM32F405 DMA cannot access CCM RAM. Reject an unsuitable linker placement.
    const uintptr_t buffer_address = (uintptr_t)frame_buffer;
    if (buffer_address < 0x20000000u || buffer_address + sizeof(frame_buffer) > 0x20020000u) {
        return MONO56_ADC_BAD_DMA_MEMORY;
    }
#endif
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_DMA2EN;
    (void)RCC->AHB1ENR; // ES0182: read back after enabling the peripheral clock.
    RCC->APB2ENR |= RCC_APB2ENR_ADC1EN;
    (void)RCC->APB2ENR;
    if ((ADC1->CR2 & ADC_CR2_ADON) || (DMA2_Stream0->CR & DMA_SxCR_EN) ||
        (ADC->CCR & ADC_CCR_MULTI)) {
        return MONO56_ADC_PERIPHERAL_BUSY;
    }
    // Do not change the shared prescaler under an active current-sense ADC.
    if (((ADC2->CR2 | ADC3->CR2) & ADC_CR2_ADON) &&
        (ADC->CCR & ADC_CCR_ADCPRE) != ADC_CCR_ADCPRE_0) {
        return MONO56_ADC_PERIPHERAL_BUSY;
    }
    ADC->CCR = (ADC->CCR & ~ADC_CCR_ADCPRE) | ADC_CCR_ADCPRE_0 | ADC_CCR_TSVREFE;
    GPIOA->MODER = (GPIOA->MODER & ~(3u << 12)) | (3u << 12); // PA6 analog
    GPIOA->PUPDR &= ~(3u << 12);
    ADC1->CR1 = ADC_CR1_SCAN;
    ADC1->CR2 = 0; // No injected/continuous/external-trigger conversions.
    ADC1->SMPR1 = 7u << 21; // Channel 17, 480 cycles.
    ADC1->SMPR2 = 1u << 18; // Channel 6, 15 cycles.
    ADC1->SQR1 = 1u << 20;  // Two ranks, 12-bit right aligned.
    ADC1->SQR2 = 0;
    ADC1->SQR3 = 6u | (17u << 5);
    ADC1->JSQR = 0;
    ADC1->SR = 0;
    DMA2_Stream0->CR = DMA_SxCR_MINC | DMA_SxCR_PSIZE_0 | DMA_SxCR_MSIZE_0 |
                       DMA_SxCR_PL_1; // Channel 0, normal mode, halfwords, high priority.
    DMA2_Stream0->FCR = 0; // Direct mode; no DMA IRQ enabled by this component.
    DMA2_Stream0->PAR = (uint32_t)(uintptr_t)&ADC1->DR;
    DMA2_Stream0->M0AR = (uint32_t)(uintptr_t)frame_buffer;
    DMA2_Stream0->NDTR = 0;
    DMA2->LIFCR = DMA_CLEAR_FLAGS;
    time_us = clock_us;
    frame_deadline_us = deadline_us;
    ADC1->CR2 = ADC_CR2_ADON;
    enabled_at_us = time_us();
    state = MONO56_ADC_WARMING;
    return state;
}

mono56_adc_status mono56_adc1_start(void) {
    if (state == MONO56_ADC_NOT_INITIALIZED || faulted()) {
        return state;
    }
    if (state == MONO56_ADC_PENDING) {
        return MONO56_ADC_PERIPHERAL_BUSY;
    }
    if (state == MONO56_ADC_WARMING) {
        const uint32_t age = time_us() - enabled_at_us;
        if (age >= 0x80000000u) return fail(MONO56_ADC_TIMEOUT);
        if (age < 10u) return MONO56_ADC_WARMING;
    }
    if (DMA2_Stream0->CR & DMA_SxCR_EN) return fail(MONO56_ADC_BAD_TRANSFER);
    ADC1->CR2 &= ~ADC_CR2_DMA; // Re-arm finite-sequence DMA requests.
    ADC1->SR = 0;
    DMA2->LIFCR = DMA_CLEAR_FLAGS;
    DMA2_Stream0->NDTR = 2;
    __DMB();
    DMA2_Stream0->CR |= DMA_SxCR_EN;
    ADC1->CR2 |= ADC_CR2_DMA;
    started_at_us = time_us(); // Conservative oldest bound, before SWSTART.
    state = MONO56_ADC_PENDING;
    ADC1->CR2 |= ADC_CR2_SWSTART;
    return state;
}

mono56_adc_status mono56_adc1_take(mono56_adc_frame* out) {
    if (!out) return MONO56_ADC_BAD_CONFIG;
    out->valid = false;
    if (state != MONO56_ADC_PENDING) return state;
    if (ADC1->SR & ADC_SR_OVR) return fail(MONO56_ADC_OVERRUN);
    const uint32_t flags = DMA2->LISR;
    if (flags & DMA_ERROR_FLAGS) return fail(MONO56_ADC_DMA_ERROR);
    if ((uint32_t)(time_us() - started_at_us) > frame_deadline_us) {
        return fail(MONO56_ADC_TIMEOUT);
    }
    if (!(flags & DMA_LISR_TCIF0)) return MONO56_ADC_PENDING;
    if (DMA2_Stream0->NDTR != 0) return fail(MONO56_ADC_BAD_TRANSFER);
    if (DMA2_Stream0->CR & DMA_SxCR_EN) return MONO56_ADC_PENDING;
    __DMB();
    const uint16_t bus = frame_buffer[0], reference = frame_buffer[1];
    const uint32_t completed = time_us(); // Read after completion and data observation.
    if ((uint32_t)(completed - started_at_us) > frame_deadline_us) {
        return fail(MONO56_ADC_TIMEOUT);
    }
    if (ADC1->SR & ADC_SR_OVR) return fail(MONO56_ADC_OVERRUN);
    ADC1->CR2 &= ~ADC_CR2_DMA;
    DMA2->LIFCR = DMA_CLEAR_FLAGS;
    out->bus_raw = bus;
    out->reference_raw = reference;
    out->started_at_us = started_at_us;
    out->observed_complete_at_us = completed;
    out->valid = true;
    state = MONO56_ADC_IDLE;
    return MONO56_ADC_FRAME_READY;
}

mono56_adc_status mono56_adc1_shutdown(void) {
    if (state == MONO56_ADC_NOT_INITIALIZED) return state;
    ADC1->CR2 &= ~(ADC_CR2_ADON | ADC_CR2_DMA | ADC_CR2_SWSTART);
    DMA2_Stream0->CR &= ~DMA_SxCR_EN;
    if (DMA2_Stream0->CR & DMA_SxCR_EN) {
        state = MONO56_ADC_BAD_TRANSFER;
        return MONO56_ADC_PERIPHERAL_BUSY;
    }
    DMA2->LIFCR = DMA_CLEAR_FLAGS;
    state = MONO56_ADC_NOT_INITIALIZED;
    time_us = 0;
    return state;
}
