#include "bus_supervision.hpp"
#include "diagnostic_test_registers.h"
#include "driver_io.h"
#include "driver_monitor.hpp"
#include "monitor.h"
#ifdef MONO56_MONITOR_CURRENT
#include "current_capture.h"
#include "current_monitor.hpp"
#include "monitor_current_config.h"
#include <cmath>
#endif
#include <array>
#include <cstdlib>
#include <iostream>
#include <string>
#ifdef MONO56_MONITOR_TIMING
#include "timing_monitor.hpp"
TIM_TypeDef mono56_test_tim10{};
#endif

ADC_TypeDef mono56_test_adc1{}, mono56_test_adc2{}, mono56_test_adc3{};
ADC_Common_TypeDef mono56_test_adc_common{};
DMA_TypeDef mono56_test_dma2{};
DMA_Stream_TypeDef mono56_test_dma_stream{};
GPIO_TypeDef mono56_test_gpioa{}, mono56_test_gpiob{}, mono56_test_gpioc{},
    mono56_test_driver_gpiod{};
TIM_TypeDef mono56_test_tim1{}, mono56_test_tim5{}, mono56_test_tim7{};
RCC_TypeDef mono56_test_rcc{};
SYSCFG_TypeDef mono56_test_syscfg{};
EXTI_TypeDef mono56_test_exti{};
SPI_TypeDef mono56_test_spi3{};
uint32_t mono56_test_primask = 1, mono56_test_irq_disable_calls = 0;
uint32_t mono56_test_driver_ipsr = 0;
uint32_t mono56_test_priority_group = 0, mono56_test_irq_priority[82]{};
bool mono56_test_irq_enabled[82]{}, mono56_test_irq_cleared[82]{};
volatile mono56_monitor_diagnostics mono56_monitor{};
extern "C" void mono56_monitor_panic(uint32_t) { std::abort(); }
namespace {
using namespace odrive::mono56;
unsigned checks = 0, clock_calls = 0, frames = 0, rises = 0;
uint32_t next_timer = 125, adc_started = 0, written_at = 0, selected_at = 0;
bool in_irq = false, adc_pending = false, timer_events = true, dma_events = true;
bool selected = false, spi_pending = false, rx_published = false, no_rx = false;
bool enable_request = false, hardware_armed = false;
uint16_t bus_raw = 3159, tx_word = 0, response = 0;
std::array<uint16_t, 8> chip{0, 0, 0, 0x3ff, 0x7ff, 0x15d, 0x283, 0};
#ifdef MONO56_MONITOR_TIMING
std::array<uint32_t, 4> shadow{};
uint32_t tim1_flags = 0, tim5_flags = 0, normal_remaining = 0;
unsigned normal_triggers = 0, physical_cycle = 0;
uint32_t normal_trigger_at = 0;
bool ref4 = false;
void internal_tick() {
    if (!(TIM1->CR1 & TIM_CR1_CEN))
        return;
    bool boundary = false;
    if (TIM1->CR1 & TIM_CR1_DIR) {
        if (--TIM1->CNT == 0) {
            TIM1->CR1 &= ~TIM_CR1_DIR;
            ++physical_cycle;
            boundary = true;
        }
    } else if (++TIM1->CNT == TIM1->ARR) {
        TIM1->CR1 |= TIM_CR1_DIR;
        boundary = true;
    }
    if (boundary && !(TIM1->CR1 & TIM_CR1_UDIS)) {
        shadow = {TIM1->CCR1, TIM1->CCR2, TIM1->CCR3, TIM1->CCR4};
        TIM1->SR = tim1_flags |= TIM_SR_UIF;
    }
    const bool next_ref = TIM1->CR1 & TIM_CR1_DIR ? TIM1->CNT > shadow[3] : TIM1->CNT >= shadow[3];
    if (next_ref && !ref4 && TIM1->CR2 == TIM_CR2_MMS) {
        ++normal_triggers;
        normal_trigger_at = TIM5->CNT;
        normal_remaining = 243;
        for (auto *adc : {ADC2, ADC3})
            if ((adc->CR2 & (ADC_CR2_ADON | ADC_CR2_JEXTEN | ADC_CR2_JEXTSEL)) ==
                (ADC_CR2_ADON | ADC_CR2_JEXTEN_0 | ADC_CR2_JEXTSEL_0))
                adc->SR |= ADC_SR_JSTRT;
    }
    ref4 = next_ref;
    if (normal_remaining && --normal_remaining == 0) {
        ADC2->JDR1 = 2052;
        ADC3->JDR1 = 2041;
        // Scenario-dependent completion flags are applied by tick().
    }
}
#endif
#ifdef MONO56_MONITOR_CURRENT
std::string current_scenario;
unsigned triggers = 0, current_irqs = 0, deadline_irqs = 0;
uint32_t trigger_at = 0, first_trigger_at = 0, calibration_written_at = 0;
bool current_pending = false, captured_before_foreground_fault = false;
uint16_t reference_raw = 1502;
#endif
void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << " at " << TIM5->CNT
                  << " us; driver fault=" << mono56_driver_monitor_fault
                  << " bus=" << mono56_monitor.bus_fault << '\n';
        std::exit(1);
    }
}
void input(GPIO_TypeDef *port, unsigned pin, bool value) {
    const uint32_t old = port->IDR;
    port->IDR = (old & ~(1u << pin)) | (static_cast<uint32_t>(value) << pin);
    if ((old & (1u << pin)) && !value && (EXTI->FTSR & EXTI->IMR & (1u << pin)))
        EXTI->PR |= 1u << pin;
}
void writes() {
#ifdef MONO56_MONITOR_TIMING
    tim1_flags &= TIM1->SR;
    tim5_flags &= TIM5->SR;
    TIM1->SR = tim1_flags;
    TIM5->SR = tim5_flags;
    if ((TIM1->EGR & TIM_EGR_UG) && TIM1->CR2 != TIM_CR2_MMS_1) {
        TIM1->EGR = 0;
        shadow = {TIM1->CCR1, TIM1->CCR2, TIM1->CCR3, TIM1->CCR4};
        TIM1->CNT = 0;
        TIM1->CR1 &= ~TIM_CR1_DIR;
        ref4 = false;
    }
#endif
    for (auto *port : {GPIOA, GPIOB, GPIOC}) {
        port->ODR = (port->ODR | (port->BSRR & 0xffff)) & ~(port->BSRR >> 16);
        port->BSRR = 0;
        for (unsigned pin = 0; pin < 16; ++pin)
            if ((port->MODER >> (2 * pin) & 3u) == 1u)
                port->IDR = (port->IDR & ~(1u << pin)) | (port->ODR & (1u << pin));
    }
    const bool requested = GPIOB->ODR & (1u << 12);
    if (requested && !enable_request) {
        ++rises;
        hardware_armed = GPIOC->IDR & (1u << 7);
        expect(!(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)), "ENABLE rises with PWM disabled");
    }
    enable_request = requested;
    if (!(GPIOC->IDR & (1u << 7)))
        hardware_armed = false;
    input(GPIOC, 6, requested && hardware_armed);
    DMA2->LISR &= ~DMA2->LIFCR;
    DMA2->LIFCR = 0;
    if ((ADC1->CR2 & ADC_CR2_SWSTART) && !adc_pending) {
        adc_pending = true;
        adc_started = TIM5->CNT;
    }
#ifdef MONO56_MONITOR_CURRENT
    if (TIM1->EGR & TIM_EGR_UG) {
        TIM1->EGR = 0;
        expect(!current_pending && TIM1->CR2 == TIM_CR2_MMS_1 && TIM1->CR1 == 0,
               "one stopped TIM1 update produces the common current trigger");
        expect((chip[6] & 0x1c) == 0x0c && chip[7] == 0 && (chip[2] & 4) && (chip[3] >> 8) == 6,
               "every sample uses verified manual B/C shorts with locked COAST");
        expect(GPIOB->ODR & (1u << 12), "driver remains enabled for calibration");
        if (triggers)
            expect(static_cast<uint32_t>(TIM5->CNT - trigger_at) >= 1000,
                   "actual triggers respect minimum spacing");
        else {
            first_trigger_at = TIM5->CNT;
            expect(static_cast<uint32_t>(TIM5->CNT - calibration_written_at) >= 100,
                   "first sample follows the explicit settling interval");
        }
        ++triggers;
        trigger_at = TIM5->CNT;
        current_pending = true;
        for (auto *adc : {ADC2, ADC3}) {
            expect((adc->CR2 & (ADC_CR2_ADON | ADC_CR2_JEXTEN | ADC_CR2_JEXTSEL)) ==
                       (ADC_CR2_ADON | ADC_CR2_JEXTEN_0 | ADC_CR2_JEXTSEL_0),
                   "both injected paths receive the same rising TRGO");
            adc->SR |= ADC_SR_JSTRT;
        }
    }
#endif
}
void tick() {
    ++TIM5->CNT;
    writes();
#ifdef MONO56_MONITOR_TIMING
    for (unsigned i = 0; i < 168; ++i) {
        const auto before = normal_remaining;
        internal_tick();
        if (before == 1 && !normal_remaining) {
            if (current_scenario != "missing_b")
                ADC2->SR |= ADC_SR_JEOC;
            if (current_scenario != "missing_c")
                ADC3->SR |= ADC_SR_JEOC;
        }
    }
    if (TIM5->CNT == TIM5->CCR2)
        TIM5->SR = tim5_flags |= TIM_SR_CC2IF;
#endif
    if (timer_events && TIM5->CNT >= next_timer) {
        next_timer += 125;
        TIM7->SR |= TIM_SR_UIF;
    }
    if (adc_pending && static_cast<uint32_t>(TIM5->CNT - adc_started) >= 25 && dma_events) {
        adc_pending = false;
        ADC1->CR2 &= ~ADC_CR2_SWSTART;
        DMA2_Stream0->CR &= ~DMA_SxCR_EN;
        DMA2_Stream0->NDTR = 0;
        mono56_adc_test_buffer()[0] = bus_raw;
        mono56_adc_test_buffer()[1] =
#ifdef MONO56_MONITOR_CURRENT
            reference_raw;
#else
            1502;
#endif
        DMA2->LISR |= DMA_LISR_TCIF0;
    }
    if (spi_pending) {
        auto age = static_cast<uint32_t>(TIM5->CNT - written_at);
        if (age >= 1)
            SPI3->SR |= SPI_SR_TXE;
        if (age >= 49 && !rx_published && !no_rx) {
            SPI3->DR = response;
            SPI3->SR |= SPI_SR_RXNE;
            rx_published = true;
        }
        if (age >= 54)
            SPI3->SR &= ~SPI_SR_BSY;
    }
#ifdef MONO56_MONITOR_CURRENT
    if (current_pending && static_cast<uint32_t>(TIM5->CNT - trigger_at) >= 2) {
        current_pending = false;
        if (current_scenario != "missing_b") {
            ADC2->JDR1 = 2050 + (current_scenario == "noise" && triggers % 2 == 0 ? 8 : 0);
            ADC2->SR |= ADC_SR_JEOC;
        }
        if (current_scenario != "missing_c") {
            ADC3->JDR1 = 2045;
            ADC3->SR |= ADC_SR_JEOC;
        }
        if (current_scenario == "csa_drift" && triggers == 2)
            chip[6] &= ~0xcu;
        if (current_scenario == "supply_drift" && triggers == 2)
            reference_raw = 1600;
    }
    if (TIM5->CNT == TIM5->CCR1)
#ifdef MONO56_MONITOR_TIMING
        TIM5->SR = tim5_flags |= TIM_SR_CC1IF;
#else
        TIM5->SR |= TIM_SR_CC1IF;
#endif
#endif
    if (!mono56_test_primask && !in_irq) {
        in_irq = true;
#ifdef MONO56_MONITOR_CURRENT
        if (mono56_test_irq_enabled[ADC_IRQn] && current_scenario != "adc_irq_loss" &&
            (((ADC2->CR1 & ADC_CR1_JEOCIE) && (ADC2->SR & ADC_SR_JEOC)) ||
             ((ADC3->CR1 & ADC_CR1_JEOCIE) && (ADC3->SR & ADC_SR_JEOC)))) {
            ++current_irqs;
#ifdef MONO56_MONITOR_TIMING
            const auto prior_samples = mono56_timing_monitor.samples;
#endif
            mono56_test_driver_ipsr = 34;
            ADC_IRQHandler();
            mono56_test_driver_ipsr = 0;
#ifdef MONO56_MONITOR_TIMING
            if (mono56_driver_monitor_timing_active() && mono56_timing_monitor.frame_valid &&
                mono56_timing_monitor.samples != prior_samples) {
                expect(mono56_timing_monitor.cycle == physical_cycle &&
                           mono56_timing_monitor.armed_at_us <= normal_trigger_at &&
                           mono56_timing_monitor.complete_at_us >= normal_trigger_at + 1 &&
                           mono56_timing_monitor.complete_at_us == TIM5->CNT,
                       "delivered frame keeps the actual hardware cycle and trigger/completion "
                       "bounds");
            }
#endif
            writes();
        }
#ifdef MONO56_MONITOR_TIMING
        if (current_scenario != "update_irq_loss" && mono56_test_irq_enabled[TIM1_UP_TIM10_IRQn] &&
            (TIM1->DIER & TIM_DIER_UIE) && (TIM1->SR & TIM_SR_UIF)) {
            mono56_test_driver_ipsr = 41;
            TIM1_UP_TIM10_IRQHandler();
            mono56_test_driver_ipsr = 0;
            writes();
        }
        if ((TIM5->DIER & TIM5->SR & (TIM_SR_CC1IF | TIM_SR_CC2IF)) &&
#else
        if ((TIM5->DIER & TIM_DIER_CC1IE) && (TIM5->SR & TIM_SR_CC1IF) &&
#endif
            mono56_test_irq_enabled[TIM5_IRQn]) {
            ++deadline_irqs;
            mono56_test_driver_ipsr = 66;
            TIM5_IRQHandler();
            mono56_test_driver_ipsr = 0;
            writes();
            if (mono56_driver_monitor_fault && !(GPIOB->ODR & (1u << 12)))
                captured_before_foreground_fault = true;
        }
#endif
        if ((TIM7->SR & TIM_SR_UIF) && mono56_test_irq_enabled[TIM7_IRQn]) {
            TIM7_IRQHandler();
            writes();
        }
        if ((DMA2->LISR & DMA_LISR_TCIF0) && mono56_test_irq_enabled[DMA2_Stream0_IRQn]) {
            DMA2_Stream0_IRQHandler();
            writes();
        }
        in_irq = false;
    }
}
void advance(uint32_t us) {
    while (us--)
        tick();
}
void service_until(uint32_t deadline) {
    while (TIM5->CNT < deadline && !mono56_driver_monitor_fault) {
        mono56_driver_monitor_step();
        advance(100);
    }
}
} // namespace
extern "C" uint32_t mono56_diagnostic_test_clock() {
#ifdef MONO56_MONITOR_TIMING
    if (in_irq || (mono56_test_primask && (TIM1->CR1 & TIM_CR1_CEN)))
        return TIM5->CNT;
#endif
    if (++clock_calls % 4 == 0)
        tick();
    return TIM5->CNT;
}
extern "C" void mono56_driver_test_sync() { writes(); }
extern "C" void mono56_driver_test_clear_pending(uint32_t mask) { EXTI->PR &= ~mask; }
extern "C" void mono56_spi_test_select(bool value) {
    expect(GPIOC->BSRR == (value ? GPIO_BSRR_BR13 : GPIO_BSRR_BS13),
           "SPI selection uses actual shared PC13");
    if (value)
        selected_at = TIM5->CNT;
    if (!value && spi_pending && !(SPI3->SR & SPI_SR_BSY) && !(tx_word & 0x8000)) {
        const auto address = (tx_word >> 11) & 15;
        const auto data = tx_word & 0x7ff;
        if ((chip[3] >> 8) != 6)
#ifdef MONO56_MONITOR_CURRENT
        {
            if (!(current_scenario == "exit_loss" && address == 6 && data == 0x280 &&
                  triggers == 8))
                chip[address] = data;
            if (address == 6 && data == 0x28c)
                calibration_written_at = TIM5->CNT;
        }
#else
            chip[address] = data;
#endif
        else if (address == 2)
            chip[address] = (chip[address] & ~7u) | (data & 7);
        else if (address == 3 && (data >> 8) == 3)
            chip[3] = (chip[3] & 0xff) | 0x300;
    }
    selected = value;
    if (!value)
        spi_pending = false;
}
extern "C" void mono56_spi_test_write(uint16_t word) {
    expect(!in_irq && mono56_test_primask == 0,
           "SPI writes occur in foreground with interrupts enabled");
    expect(selected && !spi_pending && static_cast<uint32_t>(TIM5->CNT - selected_at) >= 2,
           "one SPI frame after CS setup");
    expect((word >> 11 & 15) < chip.size(), "valid DRV8353 register address");
    ++frames;
    tx_word = word;
    written_at = TIM5->CNT;
    spi_pending = true;
    rx_published = false;
    response = 0xa800 | chip[word >> 11 & 15];
    SPI3->SR = (SPI3->SR & ~(SPI_SR_TXE | SPI_SR_RXNE)) | SPI_SR_BSY;
}
extern "C" uint16_t mono56_spi_test_read() {
    expect(SPI3->SR & SPI_SR_RXNE, "SPI data consumed only after receive completion");
    SPI3->SR &= ~SPI_SR_RXNE;
    return SPI3->DR;
}
extern "C" void mono56_spi_test_reset() {
    SPI3->CR1 = 0;
    SPI3->SR = SPI_SR_TXE;
}
int main(int argc, char **argv) {
    const std::string scenario = argc > 1 ? argv[1] : "healthy";
#ifdef MONO56_MONITOR_CURRENT
    current_scenario = scenario;
    if (scenario == "collection_timeout")
        monitor_current_config.zero.timeout_us = 8000;
    if (scenario == "stale_frame")
        monitor_current_config.current.max_age_us = 50;
    if (scenario == "stale_frame")
        monitor_current_config.current.max_supply_skew_us = 50;
    if (scenario == "supply_skew")
        monitor_current_config.current.max_supply_skew_us = 20;
    if (scenario == "invalid_config")
        monitor_current_config.current.shunt_b_ohm = 0.0005f;
    if (scenario == "uncertain_span")
        monitor_current_config.zero.min_span_us = 11382;
#endif
    GPIOC->IDR = 1u << 7;
    GPIOD->IDR = 1u << 2;
    SPI3->SR = SPI_SR_TXE;
    expect(mono56_monitor_begin(1502), "bus IRQ service initializes");
    expect(mono56_driver_monitor_begin(), "driver diagnostic initializes with explicit fixture");
    expect(rises == 0 && frames == 0, "no ENABLE or SPI before first valid bus frame");
    mono56_test_primask = 0;
#ifdef MONO56_MONITOR_TIMING
    current_scenario = "healthy";
    while (TIM5->CNT < 90000 && !mono56_driver_monitor_fault &&
           mono56_timing_monitor.samples < 120) {
        mono56_driver_monitor_step();
        advance(100);
    }
    expect(!mono56_driver_monitor_fault && mono56_timing_monitor.samples >= 120,
           "calibration transfers into continuous capture through real monitor owners");
    expect(triggers == 8 && rises == 1 &&
               mono56_current_capture_status() == MONO56_CAPTURE_UNINITIALIZED,
           "eight calibration triggers then released ownership with no new ENABLE edge");
    expect(mono56_timing_monitor.b_raw == 2052 && mono56_timing_monitor.c_raw == 2041 &&
               mono56_timing_monitor.b_zero_code == 2050 &&
               mono56_timing_monitor.c_zero_code == 2045,
           "normal B/C raw data remains distinct from preserved calibration offsets");
    expect(mono56_timing_monitor.zero_completed_at_us ==
                   mono56_current_monitor.zero_completed_at_us &&
               mono56_timing_monitor.driver_session == 1 && mono56_timing_monitor.frame_valid,
           "same calibration time and register session survive transfer");
    expect((TIM1->CR1 & TIM_CR1_CEN) && mono56_driver_io_read().pwm_inhibited &&
               !mono56_driver_io_read().quiet && chip[6] == 0x280 && chip[2] == 0x484,
           "normal CSA and internal counter run with locked COAST and GPIO PWM inhibited");
    expect(mono56_driver_monitor.checks_completed >= 2 && mono56_monitor.dma_interrupts > 80,
           "ADC frames and next commands survive foreground SPI and bus IRQ service");
    current_scenario = scenario;
    if (scenario == "nfault") {
        input(GPIOD, 2, false);
        input(GPIOD, 2, true);
    } else if (scenario == "brake") {
        input(GPIOC, 7, false);
        writes();
        input(GPIOC, 7, true);
    } else if (scenario == "bus_ov")
        bus_raw = 3500;
    else if (scenario == "csa_drift")
        chip[6] ^= 1u << 6;
    else if (scenario == "timing_supply_skew")
        monitor_current_config.current.max_supply_skew_us = 1;
    else if (scenario == "timing_zero_age")
        monitor_current_config.current.max_zero_age_us = 1;
    else if (scenario == "timing_supply_drift")
        reference_raw = 1600;
    else if (scenario == "timing_stale_bus") {
        mono56_test_irq_enabled[TIM7_IRQn] = mono56_test_irq_enabled[DMA2_Stream0_IRQn] = false;
    }
    const auto before_frames = mono56_timing_monitor.samples;
    if (scenario == "foreground_stall")
        advance(500);
    service_until(TIM5->CNT + 3000);
    if (scenario == "healthy") {
        expect(!mono56_driver_monitor_fault && mono56_timing_monitor.samples > before_frames + 50 &&
                   normal_triggers >= mono56_timing_monitor.samples && rises == 1,
               "sustained internal cycles keep capturing across register checks");
    } else {
        expect(mono56_driver_monitor_fault && !(GPIOB->ODR & (1u << 12)) &&
                   !(TIM1->CR1 & TIM_CR1_CEN),
               "injected timing fault inhibits both ENABLE and counter");
        expect(!mono56_test_irq_enabled[ADC_IRQn] && !mono56_test_irq_enabled[TIM5_IRQn] &&
                   !mono56_test_irq_enabled[TIM1_UP_TIM10_IRQn] && !ADC2->CR1 && !ADC3->CR1 &&
                   !(ADC2->CR2 & ADC_CR2_ADON) && !(ADC3->CR2 & ADC_CR2_ADON),
               "fault closes owned ADC/timer interrupts before foreground resumes");
        mono56_driver_monitor_step();
        expect(!mono56_timing_monitor.frame_valid && !mono56_current_monitor.calibration_completed,
               "retained fault withdraws diagnostic frame and calibration validity");
        const auto first = mono56_driver_monitor_fault;
        const auto retained_samples = mono56_timing_monitor.samples;
        current_scenario = "healthy";
        bus_raw = 3159;
        input(GPIOC, 7, true);
        input(GPIOD, 2, true);
        for (unsigned i = 0; i < 10; ++i) {
            advance(125);
            mono56_driver_monitor_step();
        }
        expect(mono56_driver_monitor_fault == first &&
                   mono56_timing_monitor.samples == retained_samples && rises == 1,
               "recovered conditions cannot restart the calibrated timing session");
    }
    std::cout << checks << " timing diagnostic integration checks passed (" << scenario
              << "); normal captures=" << mono56_timing_monitor.samples << ".\n";
#elif defined(MONO56_MONITOR_CURRENT)
    while (TIM5->CNT < 90000 && !mono56_driver_monitor_fault &&
           !mono56_current_monitor.calibration_completed) {
        mono56_driver_monitor_step();
        advance(scenario == "foreground_stall" && triggers ? 500 : 100);
    }
    if (scenario == "post_fault") {
        expect(mono56_current_monitor.calibration_completed && !mono56_driver_monitor_fault,
               "calibration completes before injecting a later bus fault");
        bus_raw = 3500;
        advance(125);
        expect(mono56_driver_monitor_fault && !(GPIOB->ODR & (1u << 12)),
               "live fault latch invalidates the old completion report before foreground service");
    }
    if (scenario == "healthy") {
        expect(!mono56_driver_monitor_fault && mono56_current_monitor.calibration_completed,
               "real monitor owners complete the full calibration sequence");
        expect(triggers == 8 && mono56_current_monitor.samples == 8 && current_irqs == 8 &&
                   !deadline_irqs,
               "eight paired ADC IRQ captures consumed exactly once");
        expect(chip[6] == 0x280 && chip[7] == 0 && chip[3] == 0x633 && chip[2] == 0x484,
               "normal inputs restored and locked without releasing COAST");
        expect(std::abs(mono56_current_monitor.b_zero_code - 2050) < 0.01f &&
                   std::abs(mono56_current_monitor.c_zero_code - 2045) < 0.01f,
               "distinct B/C offsets survive acquisition and estimation");
        expect(static_cast<uint32_t>(trigger_at - first_trigger_at) >= 6900 &&
                   mono56_current_monitor.armed_at_us <= trigger_at &&
                   mono56_current_monitor.observed_complete_at_us == trigger_at + 2,
               "calibration retains original capture bounds and physical sample span");
        expect(mono56_current_monitor.zero_completed_at_us < mono56_current_monitor.observed_at_us,
               "SPI exit does not refresh the calibration timestamp");
        service_until(TIM5->CNT + 5000);
        expect(!mono56_driver_monitor_fault && triggers == 8 &&
                   mono56_driver_monitor.checks_completed >= 2 &&
                   mono56_monitor.dma_interrupts > 80,
               "completed calibration leaves live bus and driver monitoring, with no recapture");
        expect(mono56_driver_io_read().quiet && rises == 1 && (GPIOB->ODR & (1u << 12)),
               "PWM remains GPIO LOW with one uninterrupted ENABLE session");
        expect(!(mono56_current_monitor.sequence & 1) && mono56_current_monitor.magic == 0x4d353643,
               "current SWD snapshot has a coherent versioned publication");
    } else {
        mono56_driver_monitor_step();
        expect(mono56_driver_monitor_fault && !(GPIOB->ODR & (1u << 12)) &&
                   !mono56_current_monitor.calibration_completed,
               "failed calibration inhibits ENABLE and never reports success");
        if (scenario == "missing_b" || scenario == "missing_c" || scenario == "adc_irq_loss") {
            expect(captured_before_foreground_fault && deadline_irqs == 1 && triggers == 1,
                   "capture deadline inhibits directly from IRQ before foreground returns");
            expect(mono56_current_capture_status() == MONO56_CAPTURE_TIMEOUT,
                   "incomplete/unserviced capture retains deadline fault");
        } else if (scenario == "noise")
            expect(mono56_current_monitor.estimator_error ==
                       static_cast<uint32_t>(CurrentError::zero_noise),
                   "unstable amplifier offset rejected");
        else if (scenario == "supply_drift")
            expect(mono56_current_monitor.estimator_error ==
                       static_cast<uint32_t>(CurrentError::calibration_supply_changed),
                   "otherwise valid live VDDA drift invalidates zero collection");
        else if (scenario == "stale_frame")
            expect(mono56_current_monitor.estimator_error ==
                       static_cast<uint32_t>(CurrentError::stale_frame),
                   "late consumption does not refresh current acquisition timestamps");
        else if (scenario == "supply_skew")
            expect(mono56_current_monitor.error ==
                       static_cast<uint32_t>(CurrentMonitorError::bounds),
                   "VDDA correlation includes the whole current capture interval");
        else if (scenario == "collection_timeout")
            expect(mono56_current_monitor.error ==
                           static_cast<uint32_t>(CurrentMonitorError::timeout) &&
                       triggers < 8,
                   "overall collection deadline stops otherwise healthy incomplete sampling");
        else if (scenario == "invalid_config")
            expect(mono56_current_monitor.error ==
                           static_cast<uint32_t>(CurrentMonitorError::invalid_config) &&
                       triggers == 0 && chip[6] == 0x280,
                   "wrong physical shunt scaling rejected before calibration entry");
        else if (scenario == "foreground_stall")
            expect(mono56_driver_monitor_fault ==
                       static_cast<uint32_t>(DriverMonitorError::foreground_late),
                   "current IRQs cannot feed the stalled foreground heartbeat");
        else if (scenario == "uncertain_span")
            expect(mono56_current_monitor.estimator_error ==
                           static_cast<uint32_t>(CurrentError::calibration_too_short) &&
                       trigger_at - first_trigger_at == monitor_current_config.zero.min_span_us,
                   "nominal timestamp span alone cannot establish the minimum physical span");
        else if (scenario == "post_fault")
            expect(mono56_driver_monitor_fault ==
                       static_cast<uint32_t>(DriverMonitorError::bus_permission),
                   "completed calibration does not override later bus inhibition");
        else if (scenario == "csa_drift" || scenario == "exit_loss")
            expect(mono56_current_monitor.error ==
                       static_cast<uint32_t>(CurrentMonitorError::registers),
                   "changed manual shorts or ignored restoration detected by SPI readback");
        else
            expect(false, "known current integration scenario");
        const auto old_frames = frames, old_triggers = triggers,
                   first_fault = mono56_driver_monitor_fault;
        current_scenario = "healthy";
        for (unsigned i = 0; i < 10; ++i) {
            advance(125);
            mono56_driver_monitor_step();
        }
        expect(frames == old_frames && triggers == old_triggers && rises == 1 &&
                   mono56_driver_monitor_fault == first_fault,
               "recovery cannot retry calibration/SPI or create another ENABLE edge");
    }
    std::cout << checks << " current diagnostic integration checks passed (" << scenario
              << "); triggers=" << triggers << ", span=" << trigger_at - first_trigger_at
              << " us.\n";
#else
    if (scenario == "bus_timeout")
        dma_events = false;
    service_until(10000);
    if (scenario != "bus_timeout") {
        expect(!mono56_driver_monitor_fault && mono56_driver_monitor.configured_coasted,
               "integrated startup reaches configured COAST");
        expect(rises == 1 && (GPIOB->ODR & (1u << 12)),
               "one ENABLE request survives healthy bus IRQs");
        expect(chip[2] == 0x484 && chip[3] == 0x633 &&
                   !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)),
               "verified locked COAST and no motor PWM");
        expect(mono56_driver_monitor.checks_completed && frames >= 41,
               "foreground periodically rechecks registers while bus IRQs run");
        expect(mono56_monitor.dma_interrupts > 40,
               "bus acquisition continued through blocking SPI configuration");
    }
    if (scenario == "healthy") {
        expect(mono56_monitor_bus_permitted(nullptr), "fresh original acquisition permits startup");
        expect((mono56_driver_monitor.sequence & 1) == 0,
               "foreground snapshot publication completes");
    } else {
        if (scenario == "bus_ov")
            bus_raw = 3500;
        else if (scenario == "spi_loss")
            no_rx = true;
        else if (scenario == "nfault") {
            input(GPIOD, 2, false);
            input(GPIOD, 2, true);
            advance(125); // Exercise IRQ detection before another foreground call.
        } else if (scenario == "brake") {
            input(GPIOC, 7, false);
            writes();
            input(GPIOC, 7, true);
        } else if (scenario == "coast_drift")
            chip[2] &= ~4u;
        else if (scenario == "foreground_stall")
            advance(500);
        else if (scenario == "stale_bus") {
            mono56_test_irq_enabled[TIM7_IRQn] = mono56_test_irq_enabled[DMA2_Stream0_IRQn] = false;
            advance(251);
            expect(!mono56_monitor_bus_permitted(nullptr),
                   "old published permission expires without fresh IRQ service");
        } else
            expect(scenario == "bus_timeout", "known integration scenario");
        service_until(TIM5->CNT + 3000);
        mono56_driver_monitor_step();
        expect(mono56_driver_monitor_fault && !(GPIOB->ODR & (1u << 12)), "fault inhibits ENABLE");
        expect(!mono56_driver_monitor.configured_coasted, "fault withdraws configured permission");
        expect(!mono56_driver_monitor.fault_registers_valid,
               "external/transport failure invalidates unrelated old healthy register pair");
        const auto first = mono56_driver_monitor_fault;
        const auto previous_frames = frames, previous_rises = rises;
        no_rx = false;
        bus_raw = 3159;
        input(GPIOD, 2, true);
        input(GPIOC, 7, true);
        for (unsigned i = 0; i < 10; ++i) {
            advance(125);
            mono56_driver_monitor_step();
        }
        expect(mono56_driver_monitor_fault == first && frames == previous_frames &&
                   rises == previous_rises,
               "recovered levels do not retry SPI or rearm");
        if (scenario == "foreground_stall")
            expect(first == static_cast<uint32_t>(DriverMonitorError::foreground_late),
                   "IRQ detects expired foreground heartbeat");
        if (scenario == "nfault")
            expect(first == static_cast<uint32_t>(DriverMonitorError::nfault),
                   "recovered nFAULT pulse retained by IRQ guard");
    }
    std::cout << checks << " driver diagnostic integration checks passed (" << scenario
              << ") with simulated IRQs, ADC, GPIO and SPI.\n";
#endif
}
