#include "driver_io.h"
#include "driver_io_test_registers.h"
#include "driver_wake.hpp"
#include <array>
#include <cstdlib>
#include <iostream>

GPIO_TypeDef mono56_test_gpioa{}, mono56_test_gpiob{};
GPIO_TypeDef mono56_test_driver_gpioc{}, mono56_test_driver_gpiod{};
TIM_TypeDef mono56_test_tim1{};
RCC_TypeDef mono56_test_rcc{};
SYSCFG_TypeDef mono56_test_syscfg{};
EXTI_TypeDef mono56_test_exti{};
uint32_t mono56_test_primask = 0, mono56_test_irq_disable_calls = 0;
uint32_t mono56_test_driver_nvic_enabled = 0;
uint32_t mono56_test_driver_ipsr = 0;
namespace {
unsigned checks = 0, rising_requests = 0;
uint32_t inject_after_clear = 0;
uint32_t virtual_time = 0;
bool bus_ok = true, withdraw_during_request = false;
unsigned spi_frames = 0, spi_fail_frame = 0, edge_frame = 0;
std::array<uint16_t, 8> chip{};
uint32_t wake_clock() { return virtual_time; }
bool bus_permission(void *) {
    if (withdraw_during_request && mono56_test_primask)
        bus_ok = false;
    return bus_ok;
}
bool register_exchange(void *, uint16_t word, uint16_t *received) {
    ++spi_frames;
    virtual_time += 60;
    if (spi_frames == spi_fail_frame)
        return false;
    if (spi_frames == edge_frame)
        EXTI->PR |= MONO56_DRIVER_ENABLE_EDGE;
    const unsigned address = (word >> 11) & 15;
    if (address >= chip.size())
        return false;
    *received = chip[address] | 0xa800;
    if (!(word & 0x8000)) {
        const uint16_t data = word & 0x7ff;
        const bool locked = (chip[3] >> 8) == 6;
        if (!locked)
            chip[address] = data;
        else if (address == 2)
            chip[address] = (chip[address] & ~7u) | (data & 7);
        else if (address == 3 && (data >> 8) == 3)
            chip[3] = (chip[3] & 0xff) | 0x300;
    }
    return true;
}

void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
void reset() {
    mono56_driver_io_shutdown();
    mono56_test_gpioa = {};
    mono56_test_gpiob = {};
    mono56_test_driver_gpioc = {};
    mono56_test_driver_gpiod = {};
    mono56_test_tim1 = {};
    mono56_test_rcc = {};
    mono56_test_syscfg = {};
    mono56_test_exti = {};
    rising_requests = inject_after_clear = 0;
    mono56_test_primask = mono56_test_driver_nvic_enabled = 0;
    mono56_test_driver_ipsr = 0;
    GPIOC->IDR = 1u << 7;
    GPIOD->IDR = 1u << 2;
}
void prepare() {
    expect(mono56_driver_io_prepare(), "exclusive GPIO preparation succeeds");
    auto r = mono56_driver_io_read();
    expect(r.valid && r.quiet && !r.requested && r.brake_ok && r.nfault_high,
           "prepared motor inputs low, feedback valid, request low");
}
void request() {
    expect(mono56_driver_io_request_enable([](void *) { return true; }, nullptr),
           "one request allowed after caller sleep qualification");
    GPIOC->IDR |= 1u << 6;
}
void expect_retained_rejection() {
    expect(!mono56_driver_io_request_enable([](void *) { return true; }, nullptr) &&
               !mono56_driver_io_read().requested,
           "unsafe enable attempt rejected and inhibited");
    GPIOC->IDR = 1u << 7;
    EXTI->PR = 0;
    expect(!mono56_driver_io_request_enable([](void *) { return true; }, nullptr),
           "recovered conditions cannot clear local failure");
}
} // namespace
extern "C" void mono56_driver_test_sync(void) {
    for (auto *port : {GPIOA, GPIOB}) {
        auto old = port->ODR;
        const auto write = port->BSRR;
        port->ODR = (old | (write & 0xffff)) & ~(write >> 16);
        if (port == GPIOB && !(old & (1u << 12)) && (port->ODR & (1u << 12))) {
            ++rising_requests;
            expect(mono56_test_primask == 1, "enable transition protected against CPU IRQ race");
            expect(!(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) && !(GPIOA->ODR & (7u << 8)) &&
                       !(GPIOB->ODR & (7u << 13)),
                   "enable rises only with PWM disabled and all six output latches low");
        }
        port->BSRR = 0;
        for (unsigned pin = 0; pin < 16; ++pin)
            if ((port->MODER >> (2 * pin) & 3u) == 1u)
                port->IDR = (port->IDR & ~(1u << pin)) | (port->ODR & (1u << pin));
    }
}
extern "C" void mono56_driver_test_clear_pending(uint32_t mask) {
    expect(!(mask & ~0xc4u), "clear only owned EXTI pending bits");
    EXTI->PR = (EXTI->PR & ~mask) | inject_after_clear;
    inject_after_clear = 0;
}
int main() {
    reset();
    GPIOA->MODER = GPIOA->OTYPER = GPIOA->PUPDR = GPIOA->OSPEEDR = 0xffffffff;
    GPIOB->MODER = GPIOB->OTYPER = GPIOB->PUPDR = GPIOB->OSPEEDR = 0xffffffff;
    GPIOC->MODER = GPIOC->PUPDR = GPIOD->MODER = GPIOD->PUPDR = 0xffffffff;
    GPIOA->ODR = 7u << 8;
    GPIOB->ODR = (15u << 12) | (1u << 11);
    GPIOB->IDR = GPIOB->ODR;
    TIM1->CR1 = TIM_CR1_CEN;
    TIM1->BDTR = TIM_BDTR_MOE | TIM_BDTR_AOE;
    TIM1->CCER = TIM1->DIER = 0xffff;
    EXTI->PR = 0xffff;
    SYSCFG->EXTICR[0] = SYSCFG->EXTICR[1] = 0xffff;
    prepare();
    expect(rising_requests == 0, "prepare never raises enable");
    expect((GPIOB->ODR & (1u << 11)) && (GPIOB->MODER & (3u << 22)) == (3u << 22),
           "independent PB11 brake output and mode preserved");
    expect((GPIOA->MODER & ~(0x3fu << 16)) == (0xffffffffu & ~(0x3fu << 16)),
           "other GPIOA modes preserved");
    expect((GPIOC->MODER & ~(15u << 12)) == (0xffffffffu & ~(15u << 12)),
           "SPI and other GPIOC modes preserved");
    expect((SYSCFG->EXTICR[0] & 0xf0ffu) == 0xf0ffu && (SYSCFG->EXTICR[1] & 0xffu) == 0xffu &&
               EXTI->PR == (0xffffu & ~0xc4u),
           "other EXTI mappings and pending history preserved");
    expect(!mono56_test_primask, "initially enabled IRQ mask restored");
    mono56_test_primask = 1;
    request();
    expect(mono56_test_primask == 1 && rising_requests == 1, "masked caller stays masked");
    EXTI->PR |= MONO56_DRIVER_FAULT_EDGE;
    expect(mono56_driver_io_qualify_nfault(), "initial wake fault history cleared once");
    expect(!(EXTI->PR & 0xc4u) && (EXTI->PR & (1u << 9)),
           "fault qualification preserves unrelated PR");
    EXTI->PR |= MONO56_DRIVER_FAULT_EDGE;
    expect(mono56_driver_io_read().falling_edges == MONO56_DRIVER_FAULT_EDGE,
           "recovered fault level retains falling edge");
    expect(!mono56_driver_io_qualify_nfault() && !mono56_driver_io_read().requested &&
               (EXTI->PR & MONO56_DRIVER_FAULT_EDGE),
           "repeat qualification cannot erase a later fault");
    for (auto edge : {MONO56_DRIVER_ENABLE_EDGE, MONO56_DRIVER_BRAKE_EDGE}) {
        reset();
        prepare();
        EXTI->PR |= edge;
        expect_retained_rejection();
    }
    reset();
    prepare();
    GPIOC->IDR = 0;
    expect_retained_rejection();
    reset();
    prepare();
    GPIOC->IDR |= 1u << 6;
    expect_retained_rejection();
    for (unsigned pin = 0; pin < 6; ++pin) {
        reset();
        prepare();
        if (pin < 3)
            GPIOA->IDR |= 1u << (8 + pin);
        else
            GPIOB->IDR |= 1u << (10 + pin);
        expect_retained_rejection();
    }
    for (auto bit : {TIM_BDTR_MOE, TIM_BDTR_AOE}) {
        reset();
        prepare();
        TIM1->BDTR |= bit;
        expect_retained_rejection();
    }
    reset();
    prepare();
    TIM1->DIER = TIM_DIER_UDE;
    expect_retained_rejection();
    reset();
    prepare();
    GPIOC->PUPDR = 1u << 12;
    expect_retained_rejection();
    reset();
    prepare();
    SYSCFG->EXTICR[0] = 0;
    expect_retained_rejection();
    reset();
    prepare();
    EXTI->FTSR &= ~MONO56_DRIVER_BRAKE_EDGE;
    expect_retained_rejection();
    reset();
    prepare();
    request();
    expect_retained_rejection();
    expect(rising_requests == 1, "duplicate requests never produce another rising edge");
    for (auto edge :
         {MONO56_DRIVER_FAULT_EDGE, MONO56_DRIVER_ENABLE_EDGE, MONO56_DRIVER_BRAKE_EDGE}) {
        reset();
        prepare();
        request();
        inject_after_clear = edge;
        expect(!mono56_driver_io_qualify_nfault() && !mono56_driver_io_read().requested,
               "edge arriving after qualification acknowledgement inhibits");
    }
    reset();
    prepare();
    request();
    GPIOD->IDR = 0;
    expect(!mono56_driver_io_qualify_nfault(), "live nFAULT rejects qualification");
    reset();
    prepare();
    expect(!mono56_driver_io_prepare() && !mono56_driver_io_read().valid,
           "duplicate prepare cannot silently reset history");
    reset();
    EXTI->IMR = MONO56_DRIVER_ENABLE_EDGE;
    expect(!mono56_driver_io_prepare() && EXTI->IMR == MONO56_DRIVER_ENABLE_EDGE,
           "foreign active EXTI ownership rejected");
    mono56_driver_io_shutdown();
    expect(EXTI->IMR == MONO56_DRIVER_ENABLE_EDGE, "nonowner teardown preserves foreign EXTI");
    for (auto irq : {EXTI2_IRQn, EXTI9_5_IRQn}) {
        reset();
        mono56_test_driver_nvic_enabled = 1u << static_cast<unsigned>(irq);
        expect(!mono56_driver_io_prepare(), "enabled foreign EXTI vector rejected");
    }
    reset();
    prepare();
    EXTI->IMR &= ~MONO56_DRIVER_ENABLE_EDGE;
    expect_retained_rejection();
    reset();
    prepare();
    expect((EXTI->IMR & 0xc4u) == 0xc4u, "EXTI capture armed while NVIC delivery remains disabled");
    reset();
    prepare();
    request();
    mono56_driver_io_shutdown();
    expect(!mono56_driver_io_read().valid && !(GPIOB->ODR & (1u << 12)) && !(EXTI->FTSR & 0xc4u),
           "explicit shutdown inhibits and releases detection");
    using namespace odrive::mono56;
    DriverWake wake;
    const DriverWakeConfig config{wake_clock, nullptr, bus_permission, 2000, 2000, 250, 250};
    auto fresh = [&] {
        wake.reset();
        reset();
        virtual_time = 0;
        bus_ok = true;
        withdraw_during_request = false;
        spi_frames = spi_fail_frame = edge_frame = 0;
        chip = {0, 0, 0, 0x3ff, 0x7ff, 0x15d, 0x283, 0};
    };
    auto advance = [&](uint32_t duration) {
        while (duration) {
            const uint32_t step = duration > 125 ? 125 : duration;
            duration -= step;
            virtual_time += step;
            wake.update();
        }
    };
    auto ready = [&] {
        expect(wake.begin(config), "wake begins inhibited");
        expect(wake.state() == DriverWakeState::sleeping && !wake.permitted(),
               "awake permission unavailable in full sleep");
        advance(1999);
        expect(!mono56_driver_io_read().requested, "no ENABLE before full sleep duration");
        advance(1);
        expect(wake.state() == DriverWakeState::waiting_on && rising_requests == 1,
               "full sleep gives exactly one ENABLE request");
        virtual_time += 20;
        wake.update();
        expect(wake.state() == DriverWakeState::waiting_on,
               "request is not actual ENABLE feedback");
        GPIOC->IDR |= 1u << 6;
        wake.update();
        expect(wake.state() == DriverWakeState::waking, "wake interval starts at observed HIGH");
        advance(1999);
        expect(!wake.permitted(), "not awake before full observed wake duration");
        advance(1);
        expect(wake.permitted() && rising_requests == 1 && mono56_driver_io_read().quiet,
               "qualified wake leaves all six PWM inputs LOW");
    };
    auto retained = [&](DriverWakeError reason) {
        expect(wake.state() == DriverWakeState::fault && wake.error() == reason &&
                   !mono56_driver_io_read().requested,
               "wake fault retains reason and inhibits");
        const unsigned requests_before = rising_requests;
        bus_ok = true;
        GPIOC->IDR = (1u << 7);
        GPIOD->IDR = 1u << 2;
        EXTI->PR = 0;
        expect(!wake.begin(config) && wake.error() == reason,
               "begin cannot bypass retained wake fault");
        advance(5000);
        expect(!wake.permitted() && rising_requests == requests_before,
               "recovered conditions and elapsed time never rearm");
    };
    fresh();
    ready();
    const Drv8353Config gate_config{150, 300, 150, 300, 2000, 200, 200, 2, 20, 250};
    Drv8353 driver(wake.io(register_exchange));
    expect(driver.configure_coasted(gate_config) && driver.coasted() && spi_frames == 31,
           "real wake owner provides board callbacks for complete coasted register configuration");
    expect(wake.permitted() && mono56_driver_io_read().quiet && chip[2] == 0x484,
           "register configuration does not switch gates");
    edge_frame = spi_frames + 1;
    expect(!driver.check() && driver.error() == Drv8353Error::permission_lost,
           "falling edge inside SPI frame reaches register-session inhibition");
    retained(DriverWakeError::enable_history);

    for (auto edge :
         {MONO56_DRIVER_FAULT_EDGE, MONO56_DRIVER_ENABLE_EDGE, MONO56_DRIVER_BRAKE_EDGE}) {
        fresh();
        ready();
        EXTI->PR |= edge;
        wake.update();
        retained(edge == MONO56_DRIVER_FAULT_EDGE    ? DriverWakeError::nfault
                 : edge == MONO56_DRIVER_ENABLE_EDGE ? DriverWakeError::enable_history
                                                     : DriverWakeError::brake_permission);
    }
    fresh();
    ready();
    GPIOD->IDR = 0;
    wake.update();
    retained(DriverWakeError::nfault);
    fresh();
    ready();
    bus_ok = false;
    wake.update();
    retained(DriverWakeError::bus_permission);
    fresh();
    ready();
    GPIOC->IDR &= ~(1u << 6);
    wake.update();
    retained(DriverWakeError::enable_history);
    fresh();
    ready();
    GPIOA->IDR |= 1u << 8;
    wake.update();
    retained(DriverWakeError::outputs_not_quiet);
    fresh();
    ready();
    --virtual_time;
    wake.update();
    retained(DriverWakeError::clock_error);
    fresh();
    ready();
    virtual_time += 251;
    wake.update();
    retained(DriverWakeError::service_late);
    fresh();
    ready();
    GPIOB->ODR &= ~(1u << 12);
    GPIOB->IDR &= ~(1u << 12);
    wake.update();
    retained(DriverWakeError::request_mismatch);

    fresh();
    expect(wake.begin(config), "begin before bus/IRQ race test");
    advance(1999);
    withdraw_during_request = true;
    advance(1);
    expect(rising_requests == 0 && wake.state() == DriverWakeState::fault,
           "bus withdrawal immediately before atomic request prevents ENABLE edge");
    fresh();
    GPIOC->IDR |= 1u << 6;
    expect(wake.begin(config) && wake.state() == DriverWakeState::waiting_off,
           "initial HIGH feedback must first go LOW");
    advance(251);
    retained(DriverWakeError::feedback_timeout);
    fresh();
    expect(wake.begin(config), "begin before missing HIGH test");
    advance(2000);
    advance(251);
    retained(DriverWakeError::feedback_timeout);
    fresh();
    expect(wake.begin(config), "begin before sleep glitch test");
    GPIOC->IDR |= 1u << 6;
    wake.update();
    retained(DriverWakeError::enable_history);
    fresh();
    expect(wake.begin(config), "begin before wake nFAULT test");
    advance(2000);
    GPIOC->IDR |= 1u << 6;
    wake.update();
    GPIOD->IDR = 0;
    advance(2000);
    retained(DriverWakeError::nfault);
    fresh();
    expect(wake.begin(config), "begin before expected wake fault recovery");
    advance(2000);
    GPIOC->IDR |= 1u << 6;
    wake.update();
    EXTI->PR |= MONO56_DRIVER_FAULT_EDGE;
    advance(2000);
    expect(wake.permitted(), "recovered initial wake fault is qualified once after full delay");

    for (bool waiting_high : {false, true}) {
        fresh();
        if (!waiting_high)
            GPIOC->IDR |= 1u << 6;
        expect(wake.begin(config), "begin before late-but-recovered feedback");
        if (waiting_high)
            advance(2000);
        advance(125);
        if (waiting_high)
            GPIOC->IDR |= 1u << 6;
        else
            GPIOC->IDR &= ~(1u << 6);
        virtual_time += 126;
        wake.update();
        retained(DriverWakeError::feedback_timeout);
    }
    fresh();
    virtual_time = 0xfffffff0;
    ready();
    expect(virtual_time < 10000, "wake handles normal microsecond-counter wrap");
    for (unsigned field = 0; field < 6; ++field) {
        fresh();
        auto bad = config;
        if (field == 0)
            bad.sleep_us = 1000;
        if (field == 1)
            bad.wake_us = 1000;
        if (field == 2)
            bad.clock_us = nullptr;
        if (field == 3)
            bad.bus_permitted = nullptr;
        if (field == 4)
            bad.feedback_timeout_us = 0;
        if (field == 5)
            bad.max_service_gap_us = 0;
        expect(!wake.begin(bad) && rising_requests == 0,
               "invalid wake qualification rejected before ENABLE");
        retained(DriverWakeError::invalid_config);
    }
    fresh();
    ready();
    Drv8353 failed_driver(wake.io(register_exchange));
    spi_fail_frame = 3;
    expect(!failed_driver.configure_coasted(gate_config) &&
               failed_driver.error() == Drv8353Error::transport,
           "register transport failure reaches real wake-owner inhibit callback");
    retained(DriverWakeError::register_session);
    wake.reset();
    const DriverTimingPermission timing{
        nullptr, [](void *) {
            expect(mono56_test_primask == 1, "timing permission is checked under an IRQ mask");
            return bus_ok;
        }};
    fresh();
    ready();
    Drv8353 timing_driver(wake.io(register_exchange));
    expect(timing_driver.configure_coasted(gate_config) &&
               timing_driver.begin_current_calibration() && timing_driver.end_current_calibration(),
           "normal CSA inputs restored before timing handoff");
    const auto before_timing = chip;
    const auto before_frames = spi_frames;
    expect(wake.begin_timing(timing_driver, timing) && wake.state() == DriverWakeState::timing &&
               chip == before_timing && spi_frames == before_frames + 10 && rising_requests == 1,
           "handoff verifies and preserves register/ENABLE session without a new edge");
    TIM1->CR1 = TIM_CR1_CEN;
    TIM1->DIER = TIM_DIER_UIE;
    expect(mono56_driver_io_read().pwm_inhibited && !mono56_driver_io_read().quiet &&
               wake.timing_permitted(),
           "internal TIM1 interrupts are allowed with GPIO PWM inhibited");
    expect(
        timing_driver.check() && timing_driver.coasted() && !timing_driver.calibrating(),
        "same driver IO callbacks continue verified foreground SPI service during internal timing");
    const auto lease_began = virtual_time;
    for (unsigned i = 1; i <= 50; ++i) {
        virtual_time = lease_began + i * 5;
        expect(wake.timing_permitted(), "IRQ checks within foreground lease remain permitted");
    }
    ++virtual_time;
    expect(!wake.timing_permitted(), "frequent IRQ checks cannot renew a stalled foreground lease");
    retained(DriverWakeError::service_late);
    for (unsigned fault = 0; fault < 7; ++fault) {
        fresh();
        ready();
        Drv8353 candidate(wake.io(register_exchange));
        expect(candidate.configure_coasted(gate_config) && wake.begin_timing(candidate, timing),
               "timing fault fixture retains a verified coasted driver");
        TIM1->CR1 = TIM_CR1_CEN;
        TIM1->DIER = TIM_DIER_UIE;
        DriverWakeError reason = DriverWakeError::outputs_not_quiet;
        if (fault == 0)
            TIM1->BDTR |= TIM_BDTR_MOE;
        if (fault == 1)
            TIM1->CCER = TIM_CCER_CC1E;
        if (fault == 2)
            GPIOA->IDR |= 1u << 8;
        if (fault == 3) {
            EXTI->PR |= MONO56_DRIVER_ENABLE_EDGE;
            reason = DriverWakeError::enable_history;
        }
        if (fault == 4) {
            EXTI->PR |= MONO56_DRIVER_BRAKE_EDGE;
            reason = DriverWakeError::brake_permission;
        }
        if (fault == 5) {
            EXTI->PR |= MONO56_DRIVER_FAULT_EDGE;
            reason = DriverWakeError::nfault;
        }
        if (fault == 6) {
            bus_ok = false;
            reason = DriverWakeError::bus_permission;
        }
        expect(!wake.timing_permitted(),
               "timing permission rejects output or fault-history changes");
        retained(reason);
    }
    fresh();
    ready();
    Drv8353 calibrating(wake.io(register_exchange));
    expect(calibrating.configure_coasted(gate_config) && calibrating.begin_current_calibration(),
           "active manual-short fixture establishes a driver session");
    expect(!wake.begin_timing(calibrating, timing),
           "manual CSA shorts cannot enter normal timing mode");
    retained(DriverWakeError::register_session);
    fresh();
    ready();
    Drv8353 drifted(wake.io(register_exchange));
    expect(drifted.configure_coasted(gate_config), "register drift fixture configures");
    chip[6] ^= 1u << 6;
    expect(!wake.begin_timing(drifted, timing),
           "timing handoff rejects hardware CSA gain drift despite cached configuration");
    retained(DriverWakeError::register_session);
    fresh();
    ready();
    auto detached_io = wake.io(register_exchange);
    detached_io.awake_and_permitted = [](void *) { return true; };
    Drv8353 detached(detached_io);
    expect(detached.configure_coasted(gate_config), "alternate IO fixture configures");
    expect(!wake.begin_timing(detached, timing),
           "timing handoff rejects a session that bypasses the wake owner's permission");
    retained(DriverWakeError::register_session);
    fresh();
    ready();
    Drv8353 captured_driver(wake.io(register_exchange));
    expect(captured_driver.configure_coasted(gate_config),
           "stopped capture release fixture configures");
    TIM1->CR2 = TIM_CR2_MMS_1;
    expect(!wake.begin_timing(captured_driver, timing),
           "old stopped-capture TRGO must be released first");
    retained(DriverWakeError::outputs_not_quiet);
    fresh();
    ready();
    Drv8353 refreshed(wake.io(register_exchange));
    expect(refreshed.configure_coasted(gate_config) && wake.begin_timing(refreshed, timing),
           "foreground lease renewal fixture initializes");
    TIM1->CR1 = TIM_CR1_CEN;
    TIM1->DIER = TIM_DIER_UIE;
    for (unsigned i = 0; i < 20; ++i) {
        virtual_time += 200;
        expect(wake.update() == DriverWakeState::timing && wake.timing_permitted(),
               "explicit foreground service renews a healthy timing lease");
    }
    mono56_test_primask = 1;
    expect(wake.timing_permitted() && mono56_test_primask == 1,
           "timing guard preserves a nested caller mask");
    mono56_test_primask = 0;
    wake.reset();
    for (unsigned operation = 0; operation < 3; ++operation) {
        fresh();
        ready();
        Drv8353 irq_driver(wake.io(register_exchange));
        expect(irq_driver.configure_coasted(gate_config), "ISR misuse fixture configures");
        if (operation != 0)
            expect(wake.begin_timing(irq_driver, timing), "ISR guard fixture enters timing");
        mono56_test_driver_ipsr = 41; // TIM1 update exception, with PRIMASK still clear.
        const auto frames_before_irq = spi_frames;
        if (operation == 0)
            expect(!wake.begin_timing(irq_driver, timing), "handoff refuses interrupt context");
        else if (operation == 1)
            expect(wake.update() == DriverWakeState::fault,
                   "IRQ cannot renew foreground progress by calling update");
        else {
            expect(wake.timing_permitted(), "IRQ uses the nonrenewing timing guard");
            expect(!wake.permitted(), "IRQ cannot renew progress through the SPI callback path");
        }
        expect(spi_frames == frames_before_irq, "ISR rejection occurs without a SPI transaction");
        mono56_test_driver_ipsr = 0;
        retained(DriverWakeError::invalid_state);
    }
    wake.reset();
    std::cout << checks << " driver GPIO/wake checks passed with simulated registers and SPI.\n";
}
