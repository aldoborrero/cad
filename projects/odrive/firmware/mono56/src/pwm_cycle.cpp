#include "pwm_cycle.hpp"
#include "motor_inhibit.h"
#include "stm32f405xx.h"
#ifdef MONO56_PWM_CYCLE_TEST
#include "pwm_cycle_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

namespace odrive::mono56 {
namespace {
constexpr std::uint32_t base_cr1 = TIM_CR1_ARPE | TIM_CR1_URS | TIM_CR1_CMS_1;
constexpr std::uint32_t ccmr1 = TIM_CCMR1_OC1PE | TIM_CCMR1_OC1M_1 | TIM_CCMR1_OC1M_2 |
                                TIM_CCMR1_OC2PE | TIM_CCMR1_OC2M_1 | TIM_CCMR1_OC2M_2;
constexpr std::uint32_t ccmr2 =
    TIM_CCMR2_OC3PE | TIM_CCMR2_OC3M_1 | TIM_CCMR2_OC3M_2 | TIM_CCMR2_OC4PE | TIM_CCMR2_OC4M;
volatile PwmCycleState state = PwmCycleState::uninitialized;
volatile PwmCycleError error = PwmCycleError::none;
PwmCycleConfig config{};
PwmSamplePlan active, next;
bool owned = false, down_phase = false, queued = false, staged = false;
std::uint32_t cycle = 0, boundary_ticks = 0, commit_ticks = 0;
std::uint32_t began_lower = 0, began_upper = 0, last_boundary_at = 0, watchdog_at = 0;
bool waiting_for_command = false;
std::uint32_t clock_us() { return TIM5->CNT; }
std::uint32_t ceil_us(std::uint32_t timer_ticks) { return (timer_ticks + 167) / 168; }
std::uint32_t ticks(std::uint32_t ns) { return (ns * 168 + 999) / 1000; }
bool fail(PwmCycleError e) {
    if (error == PwmCycleError::none)
        error = e;
    state = PwmCycleState::fault;
    mono56_motor_inhibit();
    if (owned) {
        TIM1->CR1 &= ~TIM_CR1_CEN;
        TIM1->DIER = 0;
        TIM5->DIER &= ~TIM_DIER_CC2IE;
        NVIC_DisableIRQ(TIM1_UP_TIM10_IRQn);
    }
    return false;
}
bool gpio_quiet() {
    return (RCC->AHB1ENR & (RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN)) ==
               (RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN) &&
           (GPIOA->MODER & (0x3fu << 16)) == (0x15u << 16) &&
           (GPIOB->MODER & (0x3fu << 26)) == (0x15u << 26) && !(GPIOA->OTYPER & (7u << 8)) &&
           !(GPIOB->OTYPER & (7u << 13)) && !(GPIOA->PUPDR & (0x3fu << 16)) &&
           !(GPIOB->PUPDR & (0x3fu << 26)) && !((GPIOA->ODR | GPIOA->IDR) & (7u << 8)) &&
           !((GPIOB->ODR | GPIOB->IDR) & (7u << 13));
}
bool adc_unarmed() {
    return !((ADC2->CR2 | ADC3->CR2) & (ADC_CR2_JEXTEN | ADC_CR2_JSWSTART)) &&
           !(ADC1->CR2 & (ADC_CR2_JEXTEN | ADC_CR2_EXTEN));
}
bool register_plan(const PwmSamplePlan &p) {
    return TIM1->CCR1 == p.ccr_a && TIM1->CCR2 == p.ccr_b && TIM1->CCR3 == p.ccr_c &&
           TIM1->CCR4 == p.ccr4 && TIM1->BDTR == p.dead_time_code;
}
bool configuration_valid() {
    const bool running = state == PwmCycleState::running;
    return (RCC->APB2ENR & RCC_APB2ENR_TIM1EN) && (RCC->APB1ENR & RCC_APB1ENR_TIM5EN) &&
           (TIM1->CR1 & ~TIM_CR1_DIR) == (base_cr1 | (running ? TIM_CR1_CEN : 0u)) &&
           TIM1->CR2 == TIM_CR2_MMS && TIM1->SMCR == 0 && TIM1->PSC == 0 && TIM1->RCR == 0 &&
           TIM1->ARR == config.sampling.half_period_ticks && TIM1->CCER == 0 &&
           TIM1->CCMR1 == ccmr1 && TIM1->CCMR2 == ccmr2 &&
           TIM1->DIER == (running ? TIM_DIER_UIE : 0u) &&
           !(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) && gpio_quiet() &&
           TIM5->CR1 == TIM_CR1_CEN && TIM5->PSC == 83 && TIM5->ARR == 0xffffffffu &&
           TIM5->SMCR == 0 && TIM5->CCMR1 == 0 && TIM5->CCER == 0 &&
           !(TIM5->DIER & ~(TIM_DIER_CC1IE | TIM_DIER_CC2IE)) &&
           (!running || ((TIM5->DIER & TIM_DIER_CC2IE) && TIM5->CCR2 == watchdog_at)) &&
           NVIC_GetPriorityGrouping() == 3 && NVIC_GetPriority(TIM1_UP_TIM10_IRQn) == 1 &&
           NVIC_GetPriority(TIM5_IRQn) == 1 && NVIC_GetEnableIRQ(TIM1_UP_TIM10_IRQn) &&
           NVIC_GetEnableIRQ(TIM5_IRQn) &&
           (!(RCC->APB2ENR & RCC_APB2ENR_TIM10EN) || (TIM10->CR1 == 0 && TIM10->DIER == 0)) &&
           register_plan(staged ? next : active);
}
void set_watchdog(std::uint32_t deadline, bool command) {
    watchdog_at = deadline;
    waiting_for_command = command;
    TIM5->CCR2 = deadline;
    TIM5->SR = ~TIM_SR_CC2IF;
    TIM5->DIER |= TIM_DIER_CC2IE;
    __DSB();
}
bool watchdog_valid() {
    if (state == PwmCycleState::running &&
        static_cast<std::uint32_t>(clock_us() - watchdog_at) < 0x80000000u)
        return fail(waiting_for_command ? PwmCycleError::command_missing
                                        : PwmCycleError::boundary_late);
    return true;
}
bool permitted() {
    if (state == PwmCycleState::fault)
        return false;
    if (!config.permitted(config.context))
        return fail(PwmCycleError::permission);
    if (!configuration_valid())
        return fail(PwmCycleError::timer_changed);
    return watchdog_valid();
}
bool valid_plan(const PwmSamplePlan &p) {
    // Require time to submit the next command before underflow. This stage's
    // independent command watchdog expires conservatively ahead of that edge.
    const auto reserved_us = ceil_us(commit_ticks) + 3u;
    return p.valid() && p.min_trigger_spacing_us > reserved_us &&
           p.capture_deadline_us < p.min_trigger_spacing_us - reserved_us &&
           p.capture_deadline_us <= config.adc_deadline_us;
}
void write_compares(const PwmSamplePlan &p) {
    TIM1->CCR1 = p.ccr_a;
    TIM1->CCR2 = p.ccr_b;
    TIM1->CCR3 = p.ccr_c;
    TIM1->CCR4 = p.ccr4;
    __DSB();
}
bool observation(PwmCycleObservation *out) {
    out->valid = false;
    out->plan = active;
    out->cycle = cycle;
    const auto before = clock_us();
    const auto count = TIM1->CNT;
    out->phase_ticks = down_phase ? active.period_ticks - count : count;
    out->began_lower_us = began_lower;
    out->began_upper_us = began_upper;
    out->min_trigger_spacing_us = config.min_trigger_spacing_us;
    out->adc_deadline_us = config.adc_deadline_us;
    __DSB();
    const auto after = clock_us();
    // Intersect the independent clock interval with the elapsed phase derived
    // from CNT. A stopped/reset counter must not publish a plausible old phase
    // merely because its direction and update flag still look unchanged.
    const auto elapsed_lower = static_cast<std::uint32_t>(before - began_lower);
    const auto elapsed_upper = static_cast<std::uint32_t>(after - began_lower) + 1;
    const auto phase_upper =
        static_cast<std::uint32_t>(began_upper - began_lower) + ceil_us(out->phase_ticks);
    if (count > config.sampling.half_period_ticks ||
        static_cast<std::uint32_t>(after - before) > ceil_us(boundary_ticks) ||
        elapsed_upper < out->phase_ticks / 168 || elapsed_lower > phase_upper ||
        ((TIM1->CR1 & TIM_CR1_DIR) != 0) != down_phase || (TIM1->SR & TIM_SR_UIF))
        return fail(PwmCycleError::boundary_late);
    out->valid = true;
    return true;
}
bool notify_cycle() {
    PwmCycleObservation frame;
    if (!observation(&frame))
        return false;
    if (!config.cycle_started(config.context, &frame))
        return fail(PwmCycleError::consumer);
    // The callback's own work is included in underflow-to-ADC-arm latency.
    if ((TIM1->CR1 & TIM_CR1_DIR) || (TIM1->SR & TIM_SR_UIF) ||
        TIM1->CNT > ticks(config.sampling.arm_budget_ns) ||
        static_cast<std::uint32_t>(clock_us() - began_lower) >
            ceil_us(ticks(config.sampling.arm_budget_ns)) + 2)
        return fail(PwmCycleError::boundary_late);
    return permitted();
}
bool commit() {
    if (!queued || staged)
        return true;
    if (!down_phase || !(TIM1->CR1 & TIM_CR1_DIR))
        return fail(PwmCycleError::wrong_phase);
    const auto count_before = TIM1->CNT;
    const auto began = clock_us();
    if (count_before <= commit_ticks || !watchdog_valid())
        return fail(PwmCycleError::commit_late);
    // IRQ masking alone cannot stop a hardware preload transfer. UDIS protects
    // all four writes; the following phase/elapsed checks detect crossing an
    // update boundary while suppressed, instead of accepting a mixed cycle.
    TIM1->CR1 |= TIM_CR1_UDIS;
    write_compares(next);
    const auto count_after = TIM1->CNT;
    if (!(TIM1->CR1 & TIM_CR1_DIR) || count_after > count_before ||
        count_before - count_after > commit_ticks ||
        static_cast<std::uint32_t>(clock_us() - began) > ceil_us(commit_ticks) ||
        !register_plan(next))
        return fail(PwmCycleError::commit_late);
    TIM1->CR1 &= ~TIM_CR1_UDIS;
    __DSB();
    if (!(TIM1->CR1 & TIM_CR1_DIR) || TIM1->CNT == 0)
        return fail(PwmCycleError::commit_late);
    staged = true;
    set_watchdog(began_upper + ceil_us(active.period_ticks) + ceil_us(boundary_ticks) + 2, false);
    return watchdog_valid();
}
bool boundary() {
    if (!(TIM1->SR & TIM_SR_UIF))
        return true;
    const auto now = clock_us();
    const bool down = TIM1->CR1 & TIM_CR1_DIR;
    const auto count = TIM1->CNT;
    const auto arr = config.sampling.half_period_ticks;
    if (count > arr || down == down_phase)
        return fail(PwmCycleError::wrong_phase);
    const auto distance = down ? arr - count : count;
    const auto gap = static_cast<std::uint32_t>(now - last_boundary_at);
    const auto half_us = arr / 168;
    const auto jitter = 2 * ceil_us(boundary_ticks) + 2;
    if (distance > boundary_ticks || gap > ceil_us(arr) + jitter ||
        (half_us > jitter && gap < half_us - jitter))
        return fail(PwmCycleError::boundary_late);
    TIM1->SR = ~TIM_SR_UIF;
    down_phase = down;
    last_boundary_at = now;
    if (down) {
        set_watchdog(began_lower + active.min_trigger_spacing_us - ceil_us(commit_ticks) - 2, true);
        if (!watchdog_valid())
            return false;
        return commit();
    }
    if (!staged || cycle == 0xffffffffu)
        return fail(PwmCycleError::command_missing);
    active = next; // The observed underflow transferred exactly these preloads.
    ++cycle;
    queued = staged = false;
    began_lower = now - ceil_us(distance) - 1;
    began_upper = now + 1;
    set_watchdog(began_upper + ceil_us(arr) + ceil_us(boundary_ticks) + 2, false);
    return notify_cycle();
}
bool service() {
    if (state != PwmCycleState::running)
        return false;
    if (!permitted() || !boundary())
        return false;
    const bool down = TIM1->CR1 & TIM_CR1_DIR;
    // If another boundary occurs during service, do not return a stale epoch.
    if (down != down_phase || (TIM1->SR & TIM_SR_UIF))
        return fail(PwmCycleError::boundary_late);
    return true;
}
} // namespace
bool pwm_cycle_init(const PwmCycleConfig &c) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (state != PwmCycleState::uninitialized) {
        fail(PwmCycleError::invalid_state);
        __set_PRIMASK(mask);
        return false;
    }
    // Validate numeric ranges before converting ns or programming peripherals.
    if (!c.permitted || !c.cycle_started || !c.boundary_budget_ns || !c.commit_budget_ns ||
        c.boundary_budget_ns > 1000000 || c.commit_budget_ns > 1000000 ||
        c.boundary_budget_ns > c.sampling.arm_budget_ns || c.sampling.half_period_ticks < 2 ||
        c.sampling.half_period_ticks > 65535 || c.adc_deadline_us < 3 ||
        c.min_trigger_spacing_us > 2 * c.sampling.half_period_ticks / 168 ||
        static_cast<std::uint64_t>(c.adc_deadline_us) + 1 >= c.min_trigger_spacing_us) {
        fail(PwmCycleError::invalid_config);
        __set_PRIMASK(mask);
        return false;
    }
    config = c;
    boundary_ticks = ticks(c.boundary_budget_ns);
    commit_ticks = ticks(c.commit_budget_ns);
    const auto probe =
        make_pwm_sample_plan(c.sampling, c.sampling.half_period_ticks / 2,
                             c.sampling.half_period_ticks / 2, c.sampling.half_period_ticks / 2);
    if (!valid_plan(probe) || boundary_ticks >= c.sampling.half_period_ticks / 4 ||
        commit_ticks >= c.sampling.half_period_ticks / 4)
        fail(PwmCycleError::invalid_config);
    else if (!c.permitted(c.context))
        fail(PwmCycleError::permission);
    else if (!(RCC->APB2ENR & RCC_APB2ENR_TIM1EN) || !(RCC->APB1ENR & RCC_APB1ENR_TIM5EN) ||
             TIM1->CR1 || TIM1->CR2 || TIM1->DIER || TIM1->CCER ||
             (TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)) || !gpio_quiet() || !adc_unarmed() ||
             TIM5->CR1 != TIM_CR1_CEN || TIM5->PSC != 83 || TIM5->ARR != 0xffffffffu ||
             TIM5->DIER || TIM5->SMCR || TIM5->CCMR1 || TIM5->CCER ||
             NVIC_GetPriorityGrouping() != 3 || NVIC_GetEnableIRQ(TIM1_UP_TIM10_IRQn) ||
             NVIC_GetEnableIRQ(TIM5_IRQn) ||
             ((RCC->APB2ENR & RCC_APB2ENR_TIM10EN) && (TIM10->CR1 || TIM10->DIER)))
        fail(PwmCycleError::ownership);
    else {
        owned = true;
        active = probe;
        TIM1->CR1 = base_cr1;
        TIM1->CR2 = TIM_CR2_MMS; // OC4REF before any UG; never use update TRGO.
        TIM1->SMCR = 0;
        TIM1->PSC = 0;
        TIM1->RCR = 0; // Observe both apex and underflow, no repetition-phase assumption.
        TIM1->ARR = c.sampling.half_period_ticks;
        TIM1->CCMR1 = TIM1->CCMR2 = 0;
        write_compares(probe);
        TIM1->CCMR1 = ccmr1;
        TIM1->CCMR2 = ccmr2;
        TIM1->BDTR = probe.dead_time_code;
        TIM1->SR = 0;
        TIM1->CNT = 0;
        NVIC_SetPriority(TIM1_UP_TIM10_IRQn, 1);
        NVIC_SetPriority(TIM5_IRQn, 1);
        NVIC_ClearPendingIRQ(TIM1_UP_TIM10_IRQn);
        NVIC_ClearPendingIRQ(TIM5_IRQn);
        NVIC_EnableIRQ(TIM1_UP_TIM10_IRQn);
        NVIC_EnableIRQ(TIM5_IRQn);
        state = PwmCycleState::ready;
    }
    __DSB();
    __set_PRIMASK(mask);
    return state == PwmCycleState::ready;
}
bool pwm_cycle_start(std::uint32_t a, std::uint32_t b, std::uint32_t c) {
    const auto plan = make_pwm_sample_plan(config.sampling, a, b, c);
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (state != PwmCycleState::ready)
        fail(PwmCycleError::invalid_state);
    else if (!valid_plan(plan))
        fail(PwmCycleError::bad_plan);
    else if (!adc_unarmed())
        fail(PwmCycleError::ownership);
    else if (permitted()) {
        active = plan;
        write_compares(active);
        TIM1->EGR = TIM_EGR_UG; // Initial preload transfer while counter/ADC trigger is idle.
        __DSB();
        TIM1->SR = 0;
        cycle = 0;
        queued = staged = down_phase = false;
        began_lower = last_boundary_at = clock_us();
        TIM1->DIER = TIM_DIER_UIE;
        state = PwmCycleState::running;
        TIM1->CR1 |= TIM_CR1_CEN;
        __DSB();
        began_upper = clock_us() + 1;
        set_watchdog(began_upper + ceil_us(config.sampling.half_period_ticks) +
                         ceil_us(boundary_ticks) + 2,
                     false);
        if (!register_plan(active))
            fail(PwmCycleError::timer_changed);
        else if ((TIM1->SR & TIM_SR_UIF) || (TIM1->CR1 & TIM_CR1_DIR) ||
                 TIM1->CNT > boundary_ticks ||
                 static_cast<std::uint32_t>(clock_us() - began_lower) > ceil_us(boundary_ticks))
            fail(PwmCycleError::boundary_late);
        else
            notify_cycle();
    }
    __set_PRIMASK(mask);
    return state == PwmCycleState::running;
}
bool pwm_cycle_queue(std::uint32_t target, std::uint32_t a, std::uint32_t b, std::uint32_t c) {
    const auto plan = make_pwm_sample_plan(config.sampling, a, b, c);
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (service()) {
        if (cycle == 0xffffffffu || target != cycle + 1)
            fail(PwmCycleError::command_generation);
        else if (queued)
            fail(PwmCycleError::command_busy);
        else if (!valid_plan(plan))
            fail(PwmCycleError::bad_plan);
        else if ((active.period_ticks + plan.ccr4 - active.ccr4) / 168 <
                 config.min_trigger_spacing_us)
            fail(PwmCycleError::trigger_spacing);
        else {
            next = plan;
            queued = true;
            ok = !down_phase || commit();
        }
    }
    __set_PRIMASK(mask);
    return ok;
}
bool pwm_cycle_observe(PwmCycleObservation *out) {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    bool ok = false;
    if (!out)
        fail(PwmCycleError::invalid_state);
    else {
        out->valid = false;
        if (service()) {
            ok = observation(out);
        }
    }
    __set_PRIMASK(mask);
    return ok;
}
PwmCycleState pwm_cycle_state() { return state; }
PwmCycleError pwm_cycle_error() { return error; }
void pwm_cycle_update_irq() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (state == PwmCycleState::running)
        service();
    __set_PRIMASK(mask);
}
void pwm_cycle_watchdog_irq() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    if (TIM5->SR & TIM_SR_CC2IF) {
        TIM5->SR = ~TIM_SR_CC2IF;
        if (state == PwmCycleState::running)
            watchdog_valid();
    }
    __set_PRIMASK(mask);
}
void pwm_cycle_abort() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    fail(PwmCycleError::consumer);
    __set_PRIMASK(mask);
}
void pwm_cycle_shutdown() {
    const auto mask = __get_PRIMASK();
    __disable_irq();
    mono56_motor_inhibit();
    if (owned) {
        TIM1->CR1 = TIM1->CR2 = TIM1->DIER = TIM1->CCER = 0;
        TIM5->DIER &= ~TIM_DIER_CC2IE;
        TIM5->SR = ~TIM_SR_CC2IF;
        NVIC_DisableIRQ(TIM1_UP_TIM10_IRQn);
        if (TIM5->DIER == 0)
            NVIC_DisableIRQ(TIM5_IRQn);
    }
    owned = queued = staged = false;
    state = PwmCycleState::uninitialized;
    error = PwmCycleError::none;
    __set_PRIMASK(mask);
}
} // namespace odrive::mono56
