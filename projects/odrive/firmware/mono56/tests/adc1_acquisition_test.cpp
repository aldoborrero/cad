#include "adc1_test_registers.h"
#include "acquired_bus.hpp"

#include <cmath>
#include <cstdlib>
#include <iostream>

ADC_TypeDef mono56_test_adc1{}, mono56_test_adc2{}, mono56_test_adc3{};
ADC_Common_TypeDef mono56_test_adc_common{};
DMA_TypeDef mono56_test_dma2{};
DMA_Stream_TypeDef mono56_test_dma_stream{};
GPIO_TypeDef mono56_test_gpioa{};
RCC_TypeDef mono56_test_rcc{};

namespace {
unsigned checks = 0;
uint32_t clock_value = 0, clock_step = 0;
uint32_t clock_us() { const auto value = clock_value; clock_value += clock_step; return value; }
void expect(bool condition, const char* message) {
    ++checks;
    if (!condition) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
void reset() {
    mono56_adc1_shutdown();
    mono56_test_adc1 = {}; mono56_test_adc2 = {}; mono56_test_adc3 = {};
    mono56_test_adc_common = {}; mono56_test_dma2 = {}; mono56_test_dma_stream = {};
    mono56_test_gpioa = {}; mono56_test_rcc = {};
    clock_value = 0; clock_step = 0;
}
void flags_clear_tick() {
    // Emulate DMA's documented write-one-to-clear side effect.
    DMA2->LISR &= ~DMA2->LIFCR;
    DMA2->LIFCR = 0;
}
void begin(uint32_t initial_time = 0) {
    reset(); clock_value = initial_time;
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_WARMING, "init warming");
    clock_value += 10;
    expect(mono56_adc1_start() == MONO56_ADC_PENDING, "start frame");
    flags_clear_tick();
}
void complete(uint16_t bus = 3000, uint16_t reference = 1502) {
    mono56_adc_test_buffer()[0] = bus;
    mono56_adc_test_buffer()[1] = reference;
    DMA2_Stream0->NDTR = 0;
    DMA2_Stream0->CR &= ~DMA_SxCR_EN;
    DMA2->LISR |= DMA_LISR_TCIF0;
    ADC1->CR2 &= ~ADC_CR2_SWSTART;
}
void expect_fault(mono56_adc_status error) {
    mono56_adc_frame frame{}; frame.valid = true;
    expect(mono56_adc1_take(&frame) == error && !frame.valid, "fault invalidates frame");
    expect(mono56_adc1_start() == error, "fault is retained across start");
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_PERIPHERAL_BUSY,
           "fault cannot be bypassed by init without shutdown");
    expect((ADC1->CR2 & (ADC_CR2_ADON | ADC_CR2_DMA)) == 0, "fault stops ADC requests");
}
} // namespace

int main() {
    using namespace odrive::mono56;
    const MeasurementLimits limits{1000, 100, 3.0f, 3.6f}; // Test fixtures only.
    mono56_adc_frame frame{}; frame.valid = true;
    expect(mono56_adc1_take(&frame) == MONO56_ADC_NOT_INITIALIZED && !frame.valid,
           "no power-up frame");
    expect(mono56_adc1_start() == MONO56_ADC_NOT_INITIALIZED, "start before init");
    expect(mono56_adc1_init(nullptr, 84000000, 100) == MONO56_ADC_BAD_CONFIG, "missing clock");
    expect(mono56_adc1_init(clock_us, 42000000, 100) == MONO56_ADC_BAD_CONFIG, "wrong APB clock");
    for (auto deadline : {0u, 24u, 0x80000000u, 0xffffffffu}) {
        expect(mono56_adc1_init(clock_us, 84000000, deadline) == MONO56_ADC_BAD_CONFIG,
               "invalid deadline");
    }
    ADC1->CR2 = ADC_CR2_ADON;
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_PERIPHERAL_BUSY,
           "does not take active ADC1");
    expect(ADC1->CR2 == ADC_CR2_ADON, "busy ADC untouched");
    ADC1->CR2 = 0; DMA2_Stream0->CR = DMA_SxCR_EN;
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_PERIPHERAL_BUSY,
           "does not take active DMA stream");
    DMA2_Stream0->CR = 0; ADC->CCR = 1;
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_PERIPHERAL_BUSY,
           "rejects multimode");
    ADC->CCR = 0; ADC2->CR2 = ADC_CR2_ADON;
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_PERIPHERAL_BUSY,
           "cannot change prescaler under active ADC2");
    ADC2->CR2 = 0; ADC3->CR2 = ADC_CR2_ADON;
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_PERIPHERAL_BUSY,
           "cannot change prescaler under active ADC3");
    ADC->CCR = ADC_CCR_ADCPRE_0 | ADC_CCR_VBATE;
    const auto other_adc_before = ADC3->CR2;
    GPIOA->MODER = 0x55555555; GPIOA->PUPDR = 0xaaaaaaaa;
    expect(mono56_adc1_init(clock_us, 84000000, 100) == MONO56_ADC_WARMING, "shared clock compatible");
    expect(ADC3->CR2 == other_adc_before && (ADC->CCR & ADC_CCR_VBATE), "other ADC configuration retained");
    expect((GPIOA->MODER & ~(3u << 12)) == (0x55555555u & ~(3u << 12)), "other pin modes retained");
    expect((GPIOA->MODER >> 12 & 3) == 3 && (GPIOA->PUPDR >> 12 & 3) == 0, "PA6 analog without pulls");
    expect(ADC1->SQR1 >> 20 == 1 && (ADC1->SQR3 & 31) == 6 &&
           (ADC1->SQR3 >> 5 & 31) == 17, "bus then reference ranks");
    expect((ADC1->SMPR1 >> 21 & 7) == 7 && (ADC1->SMPR2 >> 18 & 7) == 1,
           "480-cycle reference, 15-cycle bus");
    expect(ADC1->CR1 == ADC_CR1_SCAN && ADC1->CR2 == ADC_CR2_ADON,
           "12-bit independent one-shot acquisition");
    expect((DMA2_Stream0->CR & (DMA_SxCR_CIRC | DMA_SxCR_DBM | DMA_SxCR_CHSEL | DMA_SxCR_DIR)) == 0,
           "finite DMA peripheral-to-memory channel zero");
    expect((DMA2_Stream0->CR & (DMA_SxCR_MINC | DMA_SxCR_MSIZE | DMA_SxCR_PSIZE)) ==
           (DMA_SxCR_MINC | DMA_SxCR_MSIZE_0 | DMA_SxCR_PSIZE_0), "incrementing halfword DMA");
    expect(mono56_adc1_start() == MONO56_ADC_WARMING, "cannot start immediately");
    clock_value = 9; expect(mono56_adc1_start() == MONO56_ADC_WARMING, "warmup minimum");
    clock_value = 10; expect(mono56_adc1_start() == MONO56_ADC_PENDING, "warmup complete");
    flags_clear_tick();
    expect(DMA2_Stream0->NDTR == 2 && (DMA2_Stream0->CR & DMA_SxCR_EN), "two transfers armed");
    expect(mono56_adc1_start() == MONO56_ADC_PERIPHERAL_BUSY, "no overlapping frame");
    expect(mono56_adc1_take(nullptr) == MONO56_ADC_BAD_CONFIG, "null output rejected");
    clock_value = 20; DMA2_Stream0->NDTR = 1; DMA2->LISR = DMA_LISR_HTIF0;
    frame.valid = true;
    expect(mono56_adc1_take(&frame) == MONO56_ADC_PENDING && !frame.valid, "partial frame never published");
    clock_value = 40; complete();
    expect(mono56_adc1_take(&frame) == MONO56_ADC_FRAME_READY && frame.valid, "complete frame delivered");
    expect(frame.bus_raw == 3000 && frame.reference_raw == 1502 && frame.started_at_us == 10 &&
           frame.observed_complete_at_us == 40, "frame data and full acquisition interval");
    auto result = measure_acquired_bus(frame, 1502, 40, limits);
    expect(result.valid() && std::abs(result.bus_v - 53.173828125f) < 0.001f, "acquisition feeds calibrated converter");
    auto invalid_supply_limits = limits; invalid_supply_limits.vdda_min_v = 1.8f;
    expect(measure_acquired_bus(frame, 1502, 40, invalid_supply_limits).error == MeasurementError::invalid_limits,
           "21 MHz acquisition rejects low-VDDA operating range");
    auto old_frame = frame;
    expect(mono56_adc1_take(&frame) == MONO56_ADC_IDLE && !frame.valid, "frame consumed once");
    expect(!measure_acquired_bus(frame, 1502, 40, limits).valid(), "no old voltage from consumed frame");
    expect(mono56_adc1_start() == MONO56_ADC_PENDING, "next finite sequence starts");
    flags_clear_tick(); clock_value = 70; complete(3100);
    expect(mono56_adc1_take(&frame) == MONO56_ADC_FRAME_READY && frame.bus_raw == 3100 &&
           frame.started_at_us == 40, "next frame has fresh data and trigger");
    expect(measure_acquired_bus(old_frame, 1502, 1011, limits).error == MeasurementError::stale_or_future_sample,
           "age measured from trigger, not delayed observation");
    old_frame.observed_complete_at_us = 111;
    expect(measure_acquired_bus(old_frame, 1502, 111, limits).error == MeasurementError::excessive_pair_skew,
           "whole interval bounds skew even when nominal timestamps match");
    expect(measure_acquired_bus(old_frame, 1502, 110, limits).error == MeasurementError::stale_or_future_sample,
           "future completion rejected");
    old_frame.observed_complete_at_us = 9;
    expect(!measure_acquired_bus(old_frame, 1502, 40, limits).valid(), "reversed acquisition interval rejected");
    for (auto flags : {DMA_LISR_FEIF0, DMA_LISR_DMEIF0, DMA_LISR_TEIF0}) {
        begin(); clock_value = 40; complete(); DMA2->LISR |= flags;
        expect_fault(MONO56_ADC_DMA_ERROR);
    }
    begin(); clock_value = 40; complete(); ADC1->SR = ADC_SR_OVR;
    expect_fault(MONO56_ADC_OVERRUN);
    begin(); clock_value = 40; complete(); DMA2_Stream0->NDTR = 1;
    expect_fault(MONO56_ADC_BAD_TRANSFER);
    begin(); clock_value = 40; complete(); DMA2_Stream0->CR |= DMA_SxCR_EN;
    expect(mono56_adc1_take(&frame) == MONO56_ADC_PENDING && !frame.valid, "wait for DMA disable acknowledgement");
    clock_value = 111; expect_fault(MONO56_ADC_TIMEOUT);
    begin(); clock_value = 111; expect_fault(MONO56_ADC_TIMEOUT);
    begin(); clock_value = 111; complete(); expect_fault(MONO56_ADC_TIMEOUT);
    begin(); clock_value = 110; complete();
    expect(mono56_adc1_take(&frame) == MONO56_ADC_FRAME_READY, "exact deadline accepted");
    begin(); clock_value = 110; clock_step = 1; complete();
    expect_fault(MONO56_ADC_TIMEOUT); // Deadline crossed after data/TC observation.
    begin(0xfffffff0u); clock_value += 30; complete();
    expect(mono56_adc1_take(&frame) == MONO56_ADC_FRAME_READY, "acquisition over timestamp wrap");
    expect(measure_acquired_bus(frame, 1502, clock_value, limits).valid(), "wrapped interval converts");
    begin(); clock_value = 9; expect_fault(MONO56_ADC_TIMEOUT);
    reset();
    expect(mono56_adc1_start() == MONO56_ADC_NOT_INITIALIZED, "shutdown invalidates acquisition");
    std::cout << checks << " acquisition/measurement checks passed using simulated register events.\n";
}
