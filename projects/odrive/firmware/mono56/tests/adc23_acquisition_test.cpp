#include "adc23_acquisition.h"
#include "adc23_test_registers.h"
#include <array>
#include <cstdlib>
#include <cstring>
#include <iostream>

ADC_TypeDef mono56_test_adc1{}, mono56_test_adc2{}, mono56_test_adc3{};
ADC_Common_TypeDef mono56_test_adc_common{};
DMA_TypeDef mono56_test_dma2{};
DMA_Stream_TypeDef mono56_test_dma_stream{};
GPIO_TypeDef mono56_test_gpioa{}, mono56_test_gpiob{}, mono56_test_adc23_gpioc{};
TIM_TypeDef mono56_test_tim1{};
RCC_TypeDef mono56_test_rcc{};
uint32_t mono56_test_primask = 0, mono56_test_irq_disable_calls = 0;
namespace {
unsigned checks = 0;
uint32_t now = 0, clock_calls = 0, jump_call = 0, jump_amount = 0;
uint32_t error_on_clock = 0;
bool corrupt_after_close = false;
void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
uint32_t clock_us() {
    if (++clock_calls == jump_call)
        now += jump_amount;
    if (clock_calls == error_on_clock)
        ADC3->SR |= ADC_SR_OVR;
    return now;
}
void reset(uint32_t start = 0) {
    mono56_adc23_shutdown();
    mono56_adc1_shutdown();
    mono56_test_adc1 = {};
    mono56_test_adc2 = {};
    mono56_test_adc3 = {};
    mono56_test_adc_common = {};
    mono56_test_dma2 = {};
    mono56_test_dma_stream = {};
    mono56_test_gpioa = {};
    mono56_test_gpiob = {};
    mono56_test_adc23_gpioc = {};
    mono56_test_tim1 = {};
    mono56_test_rcc = {};
    mono56_test_primask = mono56_test_irq_disable_calls = 0;
    now = start;
    clock_calls = jump_call = jump_amount = 0;
    error_on_clock = 0;
    corrupt_after_close = false;
}
void init() {
    expect(mono56_adc23_init(clock_us, 84000000, 10, 40) == MONO56_ADC23_WARMING,
           "independent B/C owner initializes with explicit timing contract");
}
void arm() { expect(mono56_adc23_arm() == MONO56_ADC23_PENDING, "pair armed before shared event"); }
// The external timer owner supplies one update TRGO. Honor each ADC's real
// enable/mux/edge selection; do not fabricate a conversion for a missed edge.
void trigger() {
    TIM1->CR2 = TIM_CR2_MMS_1; // Update TRGO, supplied by the test's timer owner.
    TIM1->EGR = TIM_EGR_UG;
    for (auto adc : {ADC2, ADC3})
        if ((adc->CR2 & (ADC_CR2_ADON | ADC_CR2_JEXTSEL | ADC_CR2_JEXTEN)) ==
            (ADC_CR2_ADON | ADC_CR2_JEXTSEL_0 | ADC_CR2_JEXTEN_0))
            adc->SR |= ADC_SR_JSTRT;
}
void complete(ADC_TypeDef *adc) {
    if (!(adc->SR & ADC_SR_JSTRT))
        return;
    const unsigned channel = (adc->JSQR >> 15) & 31;
    adc->JDR1 = channel == 10 ? 2300 : channel == 11 ? 1900 : 17;
    adc->SR |= ADC_SR_JEOC;
}
void pair() {
    trigger();
    now += 2;
    complete(ADC2);
    complete(ADC3);
}
void failed(mono56_adc23_status error) {
    mono56_adc23_frame f{};
    f.valid = true;
    expect(mono56_adc23_take(&f) == error && !f.valid, "fault never publishes a pair");
    expect(ADC2->CR2 == 0 && ADC3->CR2 == 0 && ADC2->CR1 == 0 && ADC3->CR1 == 0,
           "fault stops only the owned ADCs and their interrupts");
    expect(mono56_adc23_arm() == error &&
               mono56_adc23_init(clock_us, 84000000, 10, 40) == MONO56_ADC23_BUSY,
           "fault retained until explicit shutdown");
}
} // namespace
extern "C" void mono56_adc23_test_barrier() {
    if (corrupt_after_close && !(ADC2->CR2 & ADC_CR2_JEXTEN) && !(ADC3->CR2 & ADC_CR2_JEXTEN)) {
        ADC3->JOFR1 = 1;
        corrupt_after_close = false;
    }
}
int main() {
    reset();
    mono56_adc23_frame f{};
    expect(mono56_adc23_take(&f) == MONO56_ADC23_NOT_INITIALIZED && !f.valid,
           "uninitialized acquisition is not a sample");
    for (auto args : {std::array<uint32_t, 3>{42000000, 10, 40},
                      {84000000, 2, 40},
                      {84000000, 10, 11},
                      {84000000, 10, 0x80000000},
                      {84000000, 0xffffffff, 40}}) {
        expect(mono56_adc23_init(clock_us, args[0], args[1], args[2]) == MONO56_ADC23_BAD_CONFIG,
               "clock, quantization and repeat-trigger timing constraints required");
    }
    expect(mono56_adc23_init(nullptr, 84000000, 10, 40) == MONO56_ADC23_BAD_CONFIG,
           "clock callback required");
    for (unsigned conflict = 0; conflict < 6; ++conflict) {
        reset();
        if (conflict == 0)
            ADC2->CR2 = ADC_CR2_ADON;
        if (conflict == 1)
            ADC3->CR1 = ADC_CR1_JEOCIE;
        if (conflict == 2)
            ADC->CCR = ADC_CCR_MULTI_0;
        if (conflict == 3)
            ADC->CCR = ADC_CCR_DMA_0;
        if (conflict == 4)
            ADC->CCR = ADC_CCR_DDS;
        if (conflict == 5)
            ADC1->CR2 = ADC_CR2_ADON; // Incompatible default /2 clock.
        const auto a = *ADC1, b = *ADC2, c = *ADC3;
        const uint32_t common = ADC->CCR;
        expect(mono56_adc23_init(clock_us, 84000000, 10, 40) == MONO56_ADC23_BUSY,
               "reject existing ADC ownership or incompatible shared clock");
        expect(std::memcmp(&a, ADC1, sizeof a) == 0 && std::memcmp(&b, ADC2, sizeof b) == 0 &&
                   std::memcmp(&c, ADC3, sizeof c) == 0 && ADC->CCR == common,
               "rejected init does not overwrite someone else's ADC state");
    }
    reset();
    GPIOC->MODER = 0xaaaaaaaa;
    GPIOC->PUPDR = 0x55555555;
    ADC->CCR = ADC_CCR_TSVREFE | ADC_CCR_VBATE;
    init();
    expect(GPIOC->MODER == 0xaaaaaaaf && GPIOC->PUPDR == 0x55555550,
           "only PC0/PC1 analog settings change");
    expect(ADC2->JSQR == 0x50000 && ADC3->JSQR == 0x58000 && ADC2->SMPR1 == 1 && ADC3->SMPR1 == 8 &&
               ADC2->JOFR1 == 0 && ADC3->JOFR1 == 0,
           "independent channel, rank, sample-time and zero-offset register oracle");
    expect(ADC->CCR == (ADC_CCR_ADCPRE_0 | ADC_CCR_TSVREFE | ADC_CCR_VBATE),
           "shared /4 clock preserves reference enables");
    now = 9;
    expect(mono56_adc23_arm() == MONO56_ADC23_WARMING, "both ADCs need stabilization");
    now = 10;
    mono56_test_primask = 1;
    arm();
    expect(mono56_test_primask == 1, "arm preserves a caller's masked IRQ state");
    expect(mono56_adc23_arm() == MONO56_ADC23_BUSY, "overlapping arm does not overwrite capture");
    expect(!(ADC2->CR2 & (ADC_CR2_JSWSTART | ADC_CR2_SWSTART)) && TIM1->EGR == 0,
           "arming never issues a software trigger or timer event");
    now = 11;
    pair();
    expect(mono56_adc23_take(&f) == MONO56_ADC23_FRAME_READY && f.valid && f.b_raw == 2300 &&
               f.c_raw == 1900 && f.armed_at_us == 10 && f.observed_complete_at_us == 13,
           "complete B/C pair retains original acquisition bounds");
    expect(!ADC2->SR && !ADC3->SR && !ADC2->CR1 && !ADC3->CR1 && !(ADC2->CR2 & ADC_CR2_JEXTEN) &&
               !(ADC3->CR2 & ADC_CR2_JEXTEN),
           "published frame closes triggers and clears only owned flags");
    expect(mono56_adc23_take(&f) == MONO56_ADC23_IDLE && !f.valid, "pair delivered only once");
    // Either ADC may be the first IRQ source. It must not cause an interrupt storm.
    for (bool c_first : {false, true}) {
        reset();
        init();
        now = 10;
        arm();
        trigger();
        now = 12;
        complete(c_first ? ADC3 : ADC2);
        expect(mono56_adc23_take(&f) == MONO56_ADC23_PENDING && !f.valid,
               "one completed ADC is not a coherent pair");
        expect((c_first ? ADC3 : ADC2)->CR1 == 0 && (c_first ? ADC2 : ADC3)->CR1 == ADC_CR1_JEOCIE,
               "mask completed channel IRQ while partner remains able to interrupt");
        now = 13;
        complete(c_first ? ADC2 : ADC3);
        expect(mono56_adc23_take(&f) == MONO56_ADC23_FRAME_READY && f.valid,
               "second channel completion publishes the pair");
    }
    for (bool partial : {false, true}) {
        reset();
        init();
        now = 10;
        arm();
        if (partial) {
            trigger();
            now = 12;
            complete(ADC2);
            mono56_adc23_take(&f);
        }
        now = 21;
        failed(MONO56_ADC23_TIMEOUT);
    }
    // Every class of configuration relevant to identity, timing or data format.
    for (unsigned mutation = 0; mutation < 15; ++mutation) {
        reset();
        init();
        now = 10;
        arm();
        if (mutation == 0)
            ADC2->JSQR = 11u << 15;
        if (mutation == 1)
            ADC3->SMPR1 = 0;
        if (mutation == 2)
            ADC->CCR &= ~ADC_CCR_ADCPRE;
        if (mutation == 3)
            ADC->CCR |= ADC_CCR_MULTI_0;
        if (mutation == 4)
            ADC2->CR2 |= ADC_CR2_ALIGN;
        if (mutation == 5)
            ADC3->CR2 |= ADC_CR2_JEXTSEL_1;
        if (mutation == 6)
            ADC2->JOFR1 = 1;
        if (mutation == 7)
            ADC3->CR1 |= ADC_CR1_JAUTO;
        if (mutation == 8)
            ADC2->SQR1 = 1u << 20;
        if (mutation == 9)
            GPIOC->PUPDR |= 1;
        if (mutation == 10)
            GPIOC->MODER &= ~3u;
        if (mutation == 11)
            RCC->APB2ENR &= ~RCC_APB2ENR_ADC2EN;
        if (mutation == 12)
            ADC3->CR1 = 0;
        if (mutation == 13)
            ADC->CCR |= ADC_CCR_DMA_0;
        if (mutation == 14)
            ADC3->CR2 |= ADC_CR2_SWSTART;
        failed(MONO56_ADC23_CONFIG_CHANGED);
    }
    for (auto flag : {ADC_SR_OVR, ADC_SR_STRT, ADC_SR_EOC, ADC_SR_AWD, ADC_SR_JEOC}) {
        reset();
        init();
        now = 10;
        arm();
        ADC2->SR = flag;
        failed(MONO56_ADC23_UNEXPECTED_CONVERSION);
    }
    reset();
    init();
    now = 10;
    ADC3->SR = ADC_SR_JSTRT;
    expect(mono56_adc23_arm() == MONO56_ADC23_UNEXPECTED_CONVERSION,
           "unexpected disarmed conversion cannot be erased and relabeled");
    reset();
    init();
    now = 10;
    arm();
    pair();
    ADC3->JDR1 = 0xffff;
    failed(MONO56_ADC23_BAD_DATA);
    reset();
    init();
    now = 10;
    arm();
    pair();
    jump_call = clock_calls + 2;
    jump_amount = 20;
    failed(MONO56_ADC23_TIMEOUT); // Delay after JDR reads must also invalidate data.
    reset();
    init();
    now = 10;
    arm();
    now = 9;
    failed(MONO56_ADC23_TIMEOUT);
    reset();
    init();
    now = 10;
    arm();
    pair();
    corrupt_after_close = true;
    failed(MONO56_ADC23_CONFIG_CHANGED);
    reset();
    init();
    now = 10;
    mono56_test_primask = 0;
    jump_call = clock_calls + 3;
    jump_amount = 20;
    expect(mono56_adc23_arm() == MONO56_ADC23_TIMEOUT && mono56_test_primask == 0,
           "delayed arm setup faults and restores interrupt state");
    reset();
    init();
    now = 10;
    arm();
    pair();
    error_on_clock = clock_calls + 2;
    failed(MONO56_ADC23_UNEXPECTED_CONVERSION);
    reset();
    init();
    now = 10;
    arm();
    trigger();
    now = 12;
    complete(ADC2);
    mono56_adc23_take(&f);
    // A later cycle cannot supply the missing partner, even when both JEOC
    // flags are now set. Its age exceeds this capture's deadline.
    now = 51;
    trigger();
    complete(ADC3);
    failed(MONO56_ADC23_TIMEOUT);
    expect(mono56_adc23_shutdown() == MONO56_ADC23_NOT_INITIALIZED,
           "explicit teardown clears retained acquisition failure");
    init();
    now += 10;
    arm();
    pair();
    expect(mono56_adc23_take(&f) == MONO56_ADC23_FRAME_READY && f.valid,
           "fresh initialization and stabilization permit a new capture");
    reset(0xfffffff8);
    init();
    now += 10;
    arm();
    now += 2;
    pair();
    expect(mono56_adc23_take(&f) == MONO56_ADC23_FRAME_READY && f.valid,
           "normal microsecond counter wrap is accepted");
    // ADC1 bus DMA and independent ADC2/3 can coexist, in either init order.
    for (bool bus_first : {false, true}) {
        reset();
        if (!bus_first)
            init();
        expect(mono56_adc1_init(clock_us, 84000000, 50) == MONO56_ADC_WARMING,
               "bus ADC initialized with shared /4 clock");
        if (bus_first)
            init();
        now = 10;
        arm();
        expect(mono56_adc1_start() == MONO56_ADC_PENDING, "bus DMA starts beside current capture");
        const auto bus = *ADC1;
        const auto dma = *DMA2_Stream0;
        pair();
        expect(mono56_adc23_take(&f) == MONO56_ADC23_FRAME_READY && f.valid,
               "current pair completes alongside bus DMA");
        expect(std::memcmp(&bus, ADC1, sizeof bus) == 0 &&
                   std::memcmp(&dma, DMA2_Stream0, sizeof dma) == 0,
               "current completion preserves every ADC1 and DMA stream register");
        mono56_adc23_shutdown();
        expect(std::memcmp(&bus, ADC1, sizeof bus) == 0 &&
                   std::memcmp(&dma, DMA2_Stream0, sizeof dma) == 0 && (ADC->CCR & ADC_CCR_TSVREFE),
               "current shutdown does not reset ADC1, DMA or the reference");
        now = 38;
        auto buffer = mono56_adc_test_buffer();
        buffer[0] = 3000;
        buffer[1] = 1500;
        DMA2_Stream0->CR &= ~DMA_SxCR_EN;
        DMA2_Stream0->NDTR = 0;
        DMA2->LISR = DMA_LISR_TCIF0;
        mono56_adc_frame voltage{};
        expect(mono56_adc1_take(&voltage) == MONO56_ADC_FRAME_READY && voltage.valid &&
                   voltage.bus_raw == 3000 && voltage.reference_raw == 1500,
               "bus acquisition still publishes its original pair");
    }
    std::cout << checks
              << " ADC2/ADC3 acquisition checks passed with simulated shared peripherals.\n";
}
