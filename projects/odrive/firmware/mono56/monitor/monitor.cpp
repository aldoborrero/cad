#include "monitor.h"
#include "bus_supervision.hpp"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_MONITOR_DRIVER
#include "driver_monitor.hpp"
#endif
#ifdef MONO56_MONITOR_TEST
#include "monitor_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif
#ifdef MONO56_BUS_PUBLICATION_TEST
extern "C" void mono56_test_bus_publication_preempt();
#endif

#ifndef MONO56_MONITOR_UV
#error "Explicit diagnostic undervoltage setting required"
#endif
#ifndef MONO56_MONITOR_OV
#error "Explicit diagnostic overvoltage setting required"
#endif

namespace {
using namespace odrive::mono56;
BusSupervisor supervisor;
struct BusPermission {
    std::uint32_t ready, fault, sampled_at, serviced_at;
    float vdda_v;
};
volatile BusPermission permission{};
enum class Event { startup, timer, dma };
uint32_t clock_us() { return TIM5->CNT; }

void publish(const BusSupervisionResult &result, Event event = Event::startup) {
    // A priority-1 current-capture IRQ can preempt this priority-2 bus service.
    // Mask only the short private-state commit so that its permission callback
    // cannot observe new readiness with an old timestamp or VDDA value.
    const auto mask = __get_PRIMASK();
    __disable_irq();
    permission.ready = result.bus_ready();
    permission.fault = result.fault != BusFault::none;
#ifdef MONO56_BUS_PUBLICATION_TEST
    mono56_test_bus_publication_preempt();
#endif
    permission.sampled_at = result.sampled_at_us;
    permission.serviced_at = clock_us();
    permission.vdda_v = result.measurement.vdda_v;
    __DMB();
    __set_PRIMASK(mask);
    ++mono56_monitor.sequence;
    __DMB();
    if (event == Event::timer)
        ++mono56_monitor.timer_interrupts;
    if (event == Event::dma)
        ++mono56_monitor.dma_interrupts;
    mono56_monitor.observed_at_us = clock_us();
    mono56_monitor.bus_ready = result.bus_ready();
    mono56_monitor.bus_fault = static_cast<uint32_t>(result.fault);
    mono56_monitor.acquisition_status = static_cast<uint32_t>(result.acquisition);
    mono56_monitor.measurement_error = static_cast<uint32_t>(result.measurement.error);
    mono56_monitor.bus_v = result.measurement.bus_v;
    mono56_monitor.vdda_v = result.measurement.vdda_v;
    const uint32_t feedback = GPIOC->IDR;
    mono56_monitor.driver_enable_feedback = (feedback >> 6) & 1;
    mono56_monitor.brake_permission_feedback = (feedback >> 7) & 1;
    __DMB();
    ++mono56_monitor.sequence;
}

void service(Event event) {
    // The bus-only image stays inhibited; the optional driver diagnostic may
    // wake the driver with GPIO inputs LOW and COAST retained.
#ifndef MONO56_MONITOR_DRIVER
    mono56_motor_inhibit();
#endif
    const auto result = supervisor.update();
    publish(result, event);
#ifdef MONO56_MONITOR_DRIVER
    mono56_driver_monitor_irq_guard();
#endif
    if (result.fault != BusFault::none) {
        // The periodic caller retains diagnostics/inhibition. No implicit recovery.
        NVIC_DisableIRQ(DMA2_Stream0_IRQn);
    }
}
} // namespace

extern "C" bool mono56_monitor_bus_permitted(void *) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    const bool ready = permission.ready && !permission.fault;
    const auto sampled_at = permission.sampled_at;
    const auto serviced_at = permission.serviced_at;
    const auto now = clock_us();
    const bool valid = ready && static_cast<uint32_t>(now - sampled_at) <= 250 &&
                       static_cast<uint32_t>(now - serviced_at) <= 125;
    __set_PRIMASK(mask);
    return valid;
}
extern "C" bool mono56_monitor_bus_faulted(void) { return permission.fault != 0; }
extern "C" bool mono56_monitor_supply(float *vdda, uint32_t *sampled_at) {
    if (!vdda || !sampled_at)
        return false;
    const auto mask = __get_PRIMASK();
    __disable_irq();
    const bool valid = mono56_monitor_bus_permitted(nullptr);
    *vdda = valid ? permission.vdda_v : std::numeric_limits<float>::quiet_NaN();
    *sampled_at = valid ? permission.sampled_at : 0;
    __set_PRIMASK(mask);
    return valid;
}

extern "C" void TIM7_IRQHandler(void) {
    TIM7->SR = 0;
    service(Event::timer);
}
extern "C" void DMA2_Stream0_IRQHandler(void) {
    service(Event::dma); // Acquisition owns DMA flag acknowledgement and frame delivery.
}

extern "C" bool mono56_monitor_begin(uint16_t calibration) {
    mono56_motor_inhibit();
    if (__get_PRIMASK() == 0)
        return false;
    // MCU brake request LOW; the hardware OV brake path remains independent.
    GPIOB->BSRR = GPIO_BSRR_BR11;
    GPIOB->OTYPER &= ~(1u << 11);
    GPIOB->MODER = (GPIOB->MODER & ~(3u << 22)) | (1u << 22);
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOCEN;
    (void)RCC->AHB1ENR;
    GPIOC->MODER &= ~((3u << 12) | (3u << 14));
    GPIOC->PUPDR &= ~((3u << 12) | (3u << 14)); // PC6/7 feedback, no internal pulls.

    RCC->APB1ENR |= RCC_APB1ENR_TIM5EN | RCC_APB1ENR_TIM7EN;
    (void)RCC->APB1ENR;
    // APB1=42 MHz with /4 bus divider: timer clock=84 MHz.
    TIM5->CR1 = 0;
    TIM5->PSC = 83;
    TIM5->ARR = 0xffffffffu;
    TIM5->EGR = TIM_EGR_UG;
    TIM5->SR = 0;
    TIM5->CR1 = TIM_CR1_CEN;

    const BusSupervisionConfig config{
        clock_us,          calibration,      125, 50, 300, {250, 50, 3.0f, 3.6f},
        MONO56_MONITOR_UV, MONO56_MONITOR_OV};
    if (!supervisor.begin(config)) {
        publish(supervisor.update());
        return false;
    }
    publish(supervisor.update());
    // Normal-mode DMA interrupt bits persist across starts; acquisition writes
    // them only at initialization. No half-transfer IRQ is enabled.
    DMA2_Stream0->CR |= DMA_SxCR_TCIE | DMA_SxCR_TEIE | DMA_SxCR_DMEIE;
    DMA2_Stream0->FCR |= DMA_SxFCR_FEIE;

    TIM7->CR1 = 0;
    TIM7->PSC = 83;
    TIM7->ARR = 124;
    TIM7->EGR = TIM_EGR_UG;
    TIM7->SR = 0;
    TIM7->DIER = TIM_DIER_UIE;
    // Same preemption priority: a single serialized supervisor/ADC owner.
    NVIC_SetPriorityGrouping(3);
    NVIC_SetPriority(TIM7_IRQn, 2);
    NVIC_SetPriority(DMA2_Stream0_IRQn, 2);
    NVIC_ClearPendingIRQ(TIM7_IRQn);
    NVIC_ClearPendingIRQ(DMA2_Stream0_IRQn);
    NVIC_EnableIRQ(TIM7_IRQn);
    NVIC_EnableIRQ(DMA2_Stream0_IRQn);
    TIM7->CR1 = TIM_CR1_CEN;
    __DSB();
    return true;
}

extern "C" void mono56_monitor_main(void) {
    const auto calibration =
        *reinterpret_cast<const volatile uint16_t *>(odrive::mono56::vrefint_cal_address);
    if (!mono56_monitor_begin(calibration))
        mono56_monitor_panic(8);
#ifdef MONO56_MONITOR_DRIVER
    if (!mono56_driver_monitor_begin())
        mono56_monitor_panic(9);
#endif
    __enable_irq();
    for (;;) {
#ifdef MONO56_MONITOR_DRIVER
        mono56_driver_monitor_step();
#endif
        __WFI();
    }
}
