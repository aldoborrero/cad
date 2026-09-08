#include "adc1_test_registers.h"
#include "bus_supervision.hpp"
#include "motor_inhibit.h"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>

ADC_TypeDef mono56_test_adc1{}, mono56_test_adc2{}, mono56_test_adc3{};
ADC_Common_TypeDef mono56_test_adc_common{};
DMA_TypeDef mono56_test_dma2{};
DMA_Stream_TypeDef mono56_test_dma_stream{};
GPIO_TypeDef mono56_test_gpioa{}, mono56_test_gpiob{};
TIM_TypeDef mono56_test_tim1{};
RCC_TypeDef mono56_test_rcc{};
uint32_t mono56_test_primask = 0, mono56_test_irq_disable_calls = 0;

namespace {
using namespace odrive::mono56;
unsigned checks = 0;
uint32_t now_us = 0;
uint32_t clock_us() { return now_us; }
void expect(bool ok, const char* message) {
    ++checks;
    if (!ok) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
void reset() {
    mono56_adc1_shutdown();
    mono56_test_adc1 = {}; mono56_test_adc2 = {}; mono56_test_adc3 = {};
    mono56_test_adc_common = {}; mono56_test_dma2 = {}; mono56_test_dma_stream = {};
    mono56_test_gpioa = {}; mono56_test_gpiob = {}; mono56_test_tim1 = {}; mono56_test_rcc = {};
    mono56_test_primask = mono56_test_irq_disable_calls = 0;
    now_us = 0;
}
BusSupervisionConfig config() {
    // Arbitrary test limits, not selected/qualified production settings.
    return {clock_us, 1502, 125, 50, 300, {250, 50, 3.0f, 3.6f}, 10.0f, 58.0f};
}
void clear_dma_flags() { DMA2->LISR &= ~DMA2->LIFCR; DMA2->LIFCR = 0; }
void complete(double bus_v = 56.0, uint16_t reference = 1502) {
    mono56_adc_test_buffer()[0] = static_cast<uint16_t>(std::lround(bus_v * 4096 / (3.3 * 22)));
    mono56_adc_test_buffer()[1] = reference;
    DMA2_Stream0->NDTR = 0; DMA2_Stream0->CR &= ~DMA_SxCR_EN;
    DMA2->LISR |= DMA_LISR_TCIF0; ADC1->CR2 &= ~ADC_CR2_SWSTART;
}
void pretend_armed() { GPIOB->BSRR = 0; TIM1->BDTR |= TIM_BDTR_MOE | TIM_BDTR_AOE; }
void expect_inhibited() {
    expect(GPIOB->BSRR == GPIO_BSRR_BR12, "PB12 enable request forced low");
    expect((GPIOB->MODER >> 24 & 3) == 1 && !(GPIOB->OTYPER & (1u << 12)), "PB12 push-pull output");
    expect(!(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)), "PWM and automatic re-enable inhibited");
}
void healthy(BusSupervisor& supervisor) {
    expect(supervisor.begin(config()), "valid configuration begins inhibited");
    expect_inhibited();
    now_us = 9; expect(!supervisor.update().bus_ready(), "warmup not ready");
    now_us = 10; expect(!supervisor.update().bus_ready(), "first capture pending not ready");
    clear_dma_flags(); now_us = 40; complete();
    const auto result = supervisor.update();
    expect(result.bus_ready() && std::abs(result.measurement.bus_v - 56) < 0.02f, "first valid bus sample");
    expect_inhibited(); // Readiness does not arm the motor.
}
void expect_fault(BusSupervisor& supervisor, BusFault fault) {
    const auto result = supervisor.update();
    expect(result.fault == fault && !result.bus_ready() && std::isnan(result.measurement.bus_v),
           "fault removes bus readiness and voltage");
    expect_inhibited();
    // A later healthy-looking peripheral event is not an explicit recovery.
    now_us += 20; complete(); pretend_armed();
    expect(supervisor.update().fault == fault, "first fault remains latched");
    expect_inhibited();
    expect(!supervisor.begin(config()), "begin cannot silently recover a fault");
    expect(supervisor.update().fault == fault, "bad restart preserves original fault cause");
    expect(supervisor.stop(), "explicit shutdown succeeds");
}
} // namespace

int main() {
    using namespace odrive::mono56;
    // Test the real stop primitive's register writes and interrupt-mask restore.
    for (uint32_t mask : {0u, 1u}) {
        reset(); GPIOB->MODER = 0xaaaaaaaa; GPIOB->OTYPER = 0xffff;
        TIM1->BDTR = 0x1015 | TIM_BDTR_MOE | TIM_BDTR_AOE;
        mono56_test_primask = mask;
        mono56_motor_inhibit();
        expect_inhibited();
        expect(mono56_test_primask == mask && mono56_test_irq_disable_calls == 1, "interrupt mask restored exactly");
        expect((GPIOB->MODER & ~(3u << 24)) == (0xaaaaaaaau & ~(3u << 24)), "other pin modes including PB11 retained");
        expect((GPIOB->OTYPER & ~(1u << 12)) == (0xffffu & ~(1u << 12)), "other output types retained");
        expect(TIM1->BDTR == 0x1015, "other timer break/dead-time settings retained");
    }
    reset();
    {
        BusSupervisor supervisor;
        pretend_armed(); expect(!supervisor.update().bus_ready(), "unstarted service cannot permit running");
        expect_inhibited(); healthy(supervisor);
        pretend_armed(); now_us = 100;
        expect(supervisor.update().bus_ready(), "fresh cached frame allowed between acquisitions");
        expect(TIM1->BDTR & TIM_BDTR_MOE, "healthy update does not withdraw valid external arm");
        expect(GPIOB->BSRR == 0, "healthy update issues no enable GPIO write");
        now_us = 134; expect(supervisor.update().bus_ready() && DMA2_Stream0->NDTR == 0, "no early next trigger");
        now_us = 135; expect(supervisor.update().bus_ready() && DMA2_Stream0->NDTR == 2, "next frame scheduled at period");
        clear_dma_flags(); now_us = 155; DMA2_Stream0->NDTR = 1;
        expect(supervisor.update().bus_ready(), "partial new frame does not overwrite fresh complete frame");
        expect(supervisor.update().sampled_at_us == 10, "rereading retains original acquisition timestamp");
        now_us = 165; complete(55.0);
        expect(std::abs(supervisor.update().measurement.bus_v - 55) < 0.02f, "next frame replaces previous measurement");
        expect(supervisor.update().sampled_at_us == 135, "only a completed new acquisition advances timestamp");
        expect(supervisor.stop(), "normal shutdown"); expect_inhibited();
        expect(!supervisor.update().bus_ready(), "shutdown removes cached readiness");
    }
    // A service gap with an idle ADC must not refresh the old frame's timestamp.
    reset(); { BusSupervisor s; healthy(s); pretend_armed(); now_us = 261; expect_fault(s, BusFault::measurement); }
    // Pending DMA timeout wins even if a cached measurement is still nominally fresh.
    reset(); { BusSupervisor s; healthy(s); now_us = 135; (void)s.update(); clear_dma_flags();
        pretend_armed(); now_us = 186; expect_fault(s, BusFault::acquisition); }
    for (auto flag : {DMA_LISR_TEIF0, DMA_LISR_DMEIF0, DMA_LISR_FEIF0}) {
        reset(); BusSupervisor s; healthy(s); now_us = 135; (void)s.update(); clear_dma_flags();
        pretend_armed(); now_us = 150; DMA2->LISR = flag; expect_fault(s, BusFault::acquisition);
    }
    reset(); { BusSupervisor s; healthy(s); now_us = 135; (void)s.update(); clear_dma_flags();
        pretend_armed(); now_us = 165; complete(); ADC1->SR = ADC_SR_OVR; expect_fault(s, BusFault::acquisition); }
    for (auto voltage : {0.0, 9.0, 59.0, 65.0}) {
        reset(); BusSupervisor s; healthy(s); now_us = 135; (void)s.update(); clear_dma_flags();
        pretend_armed(); now_us = 165; complete(voltage);
        expect_fault(s, voltage < 10 ? BusFault::undervoltage : BusFault::overvoltage);
    }
    for (auto reference : {0, 4095, 65535, 2000}) {
        reset(); BusSupervisor s; healthy(s); now_us = 135; (void)s.update(); clear_dma_flags();
        pretend_armed(); now_us = 165; complete(56, reference); expect_fault(s, BusFault::measurement);
    }
    reset(); { BusSupervisor s; healthy(s); pretend_armed(); now_us = 39; expect_fault(s, BusFault::clock); }
    reset(); { BusSupervisor s; expect(s.begin(config()), "startup fixture begins");
        pretend_armed(); now_us = 301; expect_fault(s, BusFault::startup_timeout); }
    // A valid first frame delivered after startup deadline cannot skip that deadline.
    reset(); { BusSupervisor s; auto c = config(); c.startup_deadline_us = 60;
        expect(s.begin(c), "short startup deadline fixture"); now_us = 50; (void)s.update(); clear_dma_flags();
        pretend_armed(); now_us = 80; complete(); expect_fault(s, BusFault::startup_timeout); }
    // Explicit recovery resets acquisition, but never raises GPIO/PWM itself.
    reset(); { BusSupervisor s; healthy(s); now_us = 261;
        expect(s.update().fault == BusFault::measurement, "recovery fixture fault");
        expect(s.stop(), "recovery shutdown");
        expect(s.begin(config()), "explicit recovery begins");
        now_us += 10; expect(!s.update().bus_ready(), "recovery waits for fresh frame"); clear_dma_flags();
        now_us += 30; complete(); expect(s.update().bus_ready(), "fresh recovery frame accepted");
        expect_inhibited(); expect(s.stop(), "recovered shutdown"); }
    // Both the service clock and the acquisition can wrap normally.
    reset(); { BusSupervisor s; now_us = 0xffffffe0u; expect(s.begin(config()), "wrap startup");
        now_us += 10; (void)s.update(); clear_dma_flags(); now_us += 30; complete();
        expect(s.update().bus_ready(), "wrap frame valid"); now_us += 100; (void)s.update(); clear_dma_flags();
        now_us += 30; complete(); expect(s.update().bus_ready(), "wrap cadence maintained"); expect(s.stop(), "wrap shutdown"); }
    // Reject invalid configuration before granting readiness or taking the ADC.
    for (int mutation = 0; mutation < 14; ++mutation) {
        reset(); BusSupervisor s; auto c = config();
        switch (mutation) {
        case 0: c.clock_us = nullptr; break;
        case 1: c.capture_period_us = 0; break;
        case 2: c.acquisition_deadline_us = 24; break;
        case 3: c.acquisition_deadline_us = 126; break;
        case 4: c.startup_deadline_us = 50; break;
        case 5: c.measurement_limits.max_age_us = 174; break;
        case 6: c.measurement_limits.max_pair_skew_us = 49; break;
        case 7: c.measurement_limits.vdda_min_v = 1.8f; break;
        case 8: c.measurement_limits.vdda_max_v = 3.7f; break;
        case 9: c.undervoltage_v = 0; break;
        case 10: c.overvoltage_v = c.undervoltage_v; break;
        case 11: c.overvoltage_v = std::numeric_limits<float>::quiet_NaN(); break;
        case 12: c.measurement_limits.max_age_us = 0x80000000u; break;
        case 13: c.overvoltage_v = 70; break;
        }
        pretend_armed(); expect(!s.begin(c), "invalid config rejected");
        expect_fault(s, BusFault::invalid_config);
    }
    reset(); { BusSupervisor s; ADC1->CR2 = ADC_CR2_ADON;
        expect(!s.begin(config()), "foreign ADC owner rejected");
        expect(ADC1->CR2 == ADC_CR2_ADON, "foreign ADC not shut down on failed ownership");
        expect_inhibited(); expect(s.stop(), "non-owner shutdown"); }
    std::cout << checks << " bus supervision/motor-inhibit checks passed with simulated peripherals.\n";
}
