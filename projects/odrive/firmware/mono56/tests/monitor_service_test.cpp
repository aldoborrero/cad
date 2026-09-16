#include "bus_supervision.hpp"
#include "monitor.h"
#include "monitor_test_registers.h"
#include <cmath>
#include <cstdlib>
#include <iostream>

ADC_TypeDef mono56_test_adc1{}, mono56_test_adc2{}, mono56_test_adc3{};
ADC_Common_TypeDef mono56_test_adc_common{};
DMA_TypeDef mono56_test_dma2{};
DMA_Stream_TypeDef mono56_test_dma_stream{};
GPIO_TypeDef mono56_test_gpioa{}, mono56_test_gpiob{}, mono56_test_gpioc{};
TIM_TypeDef mono56_test_tim1{}, mono56_test_tim5{}, mono56_test_tim7{};
RCC_TypeDef mono56_test_rcc{};
uint32_t mono56_test_primask = 1, mono56_test_irq_disable_calls = 0;
uint32_t mono56_test_priority_group = 0, mono56_test_irq_priority[82]{};
bool mono56_test_irq_enabled[82]{}, mono56_test_irq_cleared[82]{};
volatile mono56_monitor_diagnostics mono56_monitor{};
extern "C" void mono56_monitor_panic(uint32_t) { std::abort(); }
namespace {
unsigned checks = 0;
unsigned deferred_preemptions = 0;
void expect(bool ok, const char *text) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << text << '\n';
        std::exit(1);
    }
}
void flags_cleared() {
    DMA2->LISR &= ~DMA2->LIFCR;
    DMA2->LIFCR = 0;
}
void complete(uint32_t now) {
    TIM5->CNT = now;
    mono56_adc_test_buffer()[0] = 3159; // Approximately 56 V at nominal VDDA.
    mono56_adc_test_buffer()[1] = 1502;
    DMA2_Stream0->NDTR = 0;
    DMA2_Stream0->CR &= ~DMA_SxCR_EN;
    DMA2->LISR = DMA_LISR_TCIF0;
    ADC1->CR2 &= ~ADC_CR2_SWSTART;
    DMA2_Stream0_IRQHandler();
    flags_cleared();
}
} // namespace
extern "C" void mono56_test_bus_publication_preempt() {
    // A higher-priority ADC IRQ can otherwise interrupt a bus IRQ between the
    // readiness store and the matching timestamp/VDDA stores.
    if (mono56_test_primask) {
        ++deferred_preemptions;
        return;
    }
    float voltage;
    uint32_t stamp;
    const bool valid = mono56_monitor_supply(&voltage, &stamp);
    expect(!valid || std::isfinite(voltage),
           "priority-1 reader must not see new readiness with the old invalid VDDA");
}
int main() {
    using namespace odrive::mono56;
    expect(mono56_monitor_begin(1502), "diagnostic service initializes with IRQs masked");
    expect(mono56_test_primask == 1, "initialization preserves its caller's IRQ mask");
    mono56_test_primask = 0; // Normal IRQ service runs with global interrupts enabled.
    expect(!mono56_monitor.bus_ready, "startup cannot publish ready without a frame");
    float supply = 0;
    uint32_t sampled_at = 99;
    expect(!mono56_monitor_supply(&supply, &sampled_at) && std::isnan(supply) && sampled_at == 0,
           "current calibration cannot get a fabricated startup reference");
    expect(TIM5->PSC == 83 && TIM5->ARR == 0xffffffffu && TIM5->CR1 == TIM_CR1_CEN,
           "microsecond counter uses full 32-bit range");
    expect(TIM7->PSC == 83 && TIM7->ARR == 124 && TIM7->DIER == TIM_DIER_UIE,
           "periodic service configured for 125 us");
    expect(mono56_test_irq_enabled[TIM7_IRQn] && mono56_test_irq_enabled[DMA2_Stream0_IRQn],
           "timer and DMA handlers enabled");
    expect(mono56_test_priority_group == 3 && mono56_test_irq_priority[TIM7_IRQn] == 2 &&
               mono56_test_irq_priority[DMA2_Stream0_IRQn] == 2,
           "handlers cannot preempt each other");
    expect(mono56_test_irq_cleared[TIM7_IRQn] && mono56_test_irq_cleared[DMA2_Stream0_IRQn],
           "old NVIC pending state cleared before enabling");
    const auto irq_bits = DMA_SxCR_TCIE | DMA_SxCR_TEIE | DMA_SxCR_DMEIE;
    expect((DMA2_Stream0->CR & irq_bits) == irq_bits && !(DMA2_Stream0->CR & DMA_SxCR_HTIE),
           "completion/error DMA interrupts without half transfer");
    expect(DMA2_Stream0->FCR & DMA_SxFCR_FEIE, "FIFO error observation enabled");
    expect((GPIOB->MODER >> 22 & 3) == 1 && !(GPIOB->OTYPER & (1u << 11)),
           "MCU brake request initialized as low push-pull GPIO");
    expect(!(GPIOC->MODER & 0xf000) && !(GPIOC->PUPDR & 0xf000), "PC6/7 passive feedback inputs");
    GPIOC->IDR = 1u << 7;
    for (uint32_t period = 1; period <= 3; ++period) {
        TIM1->BDTR |= TIM_BDTR_MOE | TIM_BDTR_AOE;
        GPIOB->BSRR = 0;
        TIM5->CNT = period * 125;
        TIM7->SR = TIM_SR_UIF;
        TIM7_IRQHandler();
        expect(TIM7->SR == 0 && DMA2_Stream0->NDTR == 2,
               "timer acknowledges tick and dispatches capture");
        expect((DMA2_Stream0->CR & irq_bits) == irq_bits, "capture restart preserves IRQ enables");
        expect(mono56_test_irq_enabled[DMA2_Stream0_IRQn],
               "DMA completion remains enabled after dispatch");
        flags_cleared();
        complete(period * 125 + 25);
        expect(mono56_test_irq_enabled[DMA2_Stream0_IRQn],
               "healthy completion leaves DMA IRQ enabled");
        expect(mono56_monitor.bus_ready && std::abs(mono56_monitor.bus_v - 56) < 0.02f,
               "DMA handler publishes compensated complete measurement");
        expect(mono56_monitor_supply(&supply, &sampled_at) && std::abs(supply - 3.3f) < 0.001f &&
                   sampled_at == period * 125,
               "VDDA accessor carries the original acquisition time, not the IRQ time");
        expect(mono56_monitor.timer_interrupts == period && mono56_monitor.dma_interrupts == period,
               "one completion and one timer event recorded per capture");
        expect(mono56_monitor.brake_permission_feedback == 1 &&
                   mono56_monitor.driver_enable_feedback == 0,
               "feedback recorded independently of bus readiness");
        expect(!(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) && GPIOB->BSRR == GPIO_BSRR_BR12,
               "healthy diagnostic acquisition never arms motor");
        expect((mono56_monitor.sequence & 1) == 0, "published snapshot has an even sequence");
    }
    // No DMA completion: next periodic call catches timeout and retains shutdown.
    TIM5->CNT = 500;
    TIM7_IRQHandler();
    flags_cleared();
    expect(mono56_monitor_supply(&supply, &sampled_at) && sampled_at == 375,
           "new capture dispatch does not retimestamp the last measured VDDA");
    TIM5->CNT = 625;
    TIM7_IRQHandler();
    expect(!mono56_monitor.bus_ready &&
               mono56_monitor.bus_fault == static_cast<uint32_t>(BusFault::acquisition),
           "missing completion becomes a retained bus fault");
    expect(!mono56_monitor_supply(&supply, &sampled_at) && std::isnan(supply) && sampled_at == 0,
           "bus acquisition fault invalidates the current calibration reference");
    expect(mono56_monitor.acquisition_status == MONO56_ADC_TIMEOUT &&
               std::isnan(mono56_monitor.bus_v),
           "timeout diagnostic cannot masquerade as fresh measurement");
    expect(!mono56_test_irq_enabled[DMA2_Stream0_IRQn] && mono56_test_irq_enabled[TIM7_IRQn],
           "fault masks DMA IRQ while periodic inhibition continues");
    TIM1->BDTR |= TIM_BDTR_MOE | TIM_BDTR_AOE;
    TIM5->CNT = 750;
    TIM7_IRQHandler();
    expect(!mono56_monitor.bus_ready && !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)),
           "later service preserves fault and forces inhibition");
    expect(mono56_test_primask == 0, "service and supply reads restore the caller's IRQ mask");
    expect(deferred_preemptions > 1,
           "higher-priority reads are deferred during private publication");
    std::cout << checks << " monitor IRQ-service checks passed with simulated peripherals.\n";
}
