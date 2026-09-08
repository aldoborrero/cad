#include "drv8353.hpp"
#include "phase_current.hpp"
#include "spi3_test_registers.h"
#include "spi3_transport.h"
#include <array>
#include <cstdlib>
#include <iostream>
#include <vector>

SPI_TypeDef mono56_test_spi3{};
GPIO_TypeDef mono56_test_spi_gpioc{};
RCC_TypeDef mono56_test_spi_rcc{};
namespace {
unsigned checks = 0;
void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
struct Edge {
    uint32_t time;
    bool selected;
};
std::vector<Edge> edges;
std::vector<uint16_t> sent;
std::array<uint16_t, 8> chip{0, 0, 0, 0x3ff, 0x7ff, 0x15d, 0x283, 0};
uint32_t now = 0, written_at = 0, finished_at = 0, error_flags = 0;
unsigned reads = 0, resets = 0, inhibited = 0, clock_reads = 0;
bool selected = false, pending = false, published = false, chip_model = false;
bool no_rx = false, stuck_busy = false, frozen = false, backwards = false;
bool reenter = false, reentered = false, permitted = true, quiet = true;
uint16_t response = 0x5a3c, tx_word = 0;
uint32_t clock_us() {
    if (reenter && !reentered) {
        reentered = true;
        uint16_t nested = 0xffff;
        expect(mono56_spi3_transfer(0x1234, &nested) == MONO56_SPI_BUSY && nested == 0,
               "reentrant transaction is rejected without publishing data");
        expect(mono56_spi3_shutdown() == MONO56_SPI_BUSY,
               "active owner cannot be shut down reentrantly");
    }
    if (backwards)
        --now;
    // Polling is faster than the 1 us timer: repeated reads must not silently
    // provide the setup/hold delay that production code is required to request.
    else if (!frozen && ++clock_reads % 4 == 0)
        ++now;
    if (pending) {
        const auto age = static_cast<uint32_t>(now - written_at);
        if (age >= 1)
            SPI3->SR |= SPI_SR_TXE;
        if (age >= 49 && !published && !no_rx) {
            SPI3->DR = response;
            SPI3->SR |= SPI_SR_RXNE;
            published = true;
        }
        // Deliberately separated from RXNE to exercise completion confirmation.
        if (age >= 54 && !stuck_busy)
            SPI3->SR &= ~SPI_SR_BSY;
        if (age >= 10)
            SPI3->SR |= error_flags;
    }
    return now;
}
void reset() {
    (void)mono56_spi3_shutdown();
    mono56_test_spi3 = {};
    SPI3->SR = SPI_SR_TXE;
    mono56_test_spi_gpioc = {};
    mono56_test_spi_rcc = {};
    edges.clear();
    sent.clear();
    chip = {0, 0, 0, 0x3ff, 0x7ff, 0x15d, 0x283, 0};
    now = written_at = finished_at = error_flags = 0;
    reads = resets = inhibited = clock_reads = 0;
    selected = pending = published = chip_model = no_rx = stuck_busy = frozen = backwards = false;
    reenter = reentered = false;
    permitted = quiet = true;
    response = 0x5a3c;
}
void begin() {
    expect(mono56_spi3_init(clock_us, 42000000, 200) == MONO56_SPI_READY, "SPI initialization");
}
void failed(mono56_spi_status error) {
    uint16_t rx = 0xffff;
    expect(mono56_spi3_transfer(0xa5c3, &rx) == error && rx == 0,
           "failure does not publish a receive word");
    expect(!selected && !(SPI3->CR1 & SPI_CR1_SPE), "failure releases nCS and disables SPI");
    expect(mono56_spi3_status() == error, "transport fault retained");
    const auto count = sent.size();
    expect(mono56_spi3_transfer(0x1234, &rx) == error && sent.size() == count,
           "fault cannot retry implicitly");
    expect(mono56_spi3_init(clock_us, 42000000, 200) == MONO56_SPI_BUSY,
           "init cannot bypass a fault");
}
} // namespace
extern "C" void mono56_spi_test_select(bool value) {
    expect(GPIOC->BSRR == (value ? GPIO_BSRR_BR13 : GPIO_BSRR_BS13),
           "production CS write targets PC13 with correct polarity");
    if (!value && selected && pending && !stuck_busy && !no_rx && !error_flags) {
        expect(!(SPI3->SR & SPI_SR_BSY), "normal nCS release waits for peripheral not busy");
        expect(static_cast<uint32_t>(now - finished_at) >= 2, "nCS hold after final completion");
    }
    if (!value && pending && chip_model && !(SPI3->SR & SPI_SR_BSY) && !(tx_word & 0x8000)) {
        const auto addr = (tx_word >> 11) & 15;
        const auto data = tx_word & 0x7ff;
        const bool locked = (chip[3] >> 8) == 6;
        if (!locked)
            chip[addr] = data;
        else if (addr == 2)
            chip[addr] = (chip[addr] & ~7u) | (data & 7);
        else if (addr == 3 && (data >> 8) == 3)
            chip[3] = (chip[3] & 0xff) | 0x300;
    }
    edges.push_back({now, value});
    selected = value;
    if (!value)
        pending = false;
}
extern "C" void mono56_spi_test_write(uint16_t word) {
    expect(selected && !pending, "exactly one transmit write under nCS");
    expect(edges.back().selected && static_cast<uint32_t>(now - edges.back().time) >= 2,
           "nCS setup before word starts");
    pending = true;
    published = false;
    written_at = now;
    finished_at = now + 54;
    tx_word = word;
    sent.push_back(word);
    if (chip_model) {
        const auto addr = (word >> 11) & 15;
        expect(addr < 8, "integrated register driver uses listed addresses");
        response = 0xa800 | chip[addr];
    }
    SPI3->DR = word;
    SPI3->SR = (SPI3->SR & ~(SPI_SR_TXE | SPI_SR_RXNE)) | SPI_SR_BSY;
}
extern "C" uint16_t mono56_spi_test_read(void) {
    expect(selected && (SPI3->SR & SPI_SR_RXNE), "receive read requires completed data");
    ++reads;
    SPI3->SR &= ~SPI_SR_RXNE;
    return SPI3->DR;
}
extern "C" void mono56_spi_test_reset(void) {
    expect(RCC->APB1RSTR & RCC_APB1RSTR_SPI3RST,
           "owned SPI3 reset asserted before acknowledgement");
    ++resets;
    mono56_test_spi3 = {};
    SPI3->SR = SPI_SR_TXE;
}

int main() {
    reset();
    GPIOC->MODER = GPIOC->PUPDR = GPIOC->OSPEEDR = 0xffffffff;
    GPIOC->AFR[1] = GPIOC->OTYPER = 0xffffffff;
    begin();
    expect((SPI3->CR1 & (SPI_CR1_DFF | SPI_CR1_CPHA | SPI_CR1_MSTR | SPI_CR1_SSM | SPI_CR1_SSI)) ==
               (SPI_CR1_DFF | SPI_CR1_CPHA | SPI_CR1_MSTR | SPI_CR1_SSM | SPI_CR1_SSI),
           "16-bit software-NSS mode-1 master");
    expect(!(SPI3->CR1 &
             (SPI_CR1_CPOL | SPI_CR1_LSBFIRST | SPI_CR1_CRCEN | SPI_CR1_RXONLY | SPI_CR1_BIDIMODE)),
           "idle-low MSB-first full duplex without CRC");
    expect((SPI3->CR1 & SPI_CR1_BR) == (SPI_CR1_BR_1 | SPI_CR1_BR_2) && SPI3->CR2 == 0,
           "42 MHz /128; no DMA or SPI IRQ ownership");
    expect((GPIOC->MODER >> 20 & 0xff) == 0x6a && (GPIOC->AFR[1] >> 8 & 0xfff) == 0x666,
           "PC10/11/12 AF6, PC13 GPIO output");
    expect(!(GPIOC->PUPDR & (0xffu << 20)) && !(GPIOC->OSPEEDR & (3u << 26)),
           "no internal pulls and low-speed PC13");
    expect((GPIOC->MODER & ~(0xffu << 20)) == (0xffffffffu & ~(0xffu << 20)),
           "other GPIO modes including feedback preserved");
    expect((GPIOC->AFR[1] & ~(0xfffu << 8)) == (0xffffffffu & ~(0xfffu << 8)),
           "other alternate functions preserved");
    uint16_t rx = 0;
    expect(mono56_spi3_transfer(0xa5c3, &rx) == MONO56_SPI_READY && rx == 0x5a3c,
           "one full-duplex word delivered");
    expect(sent.size() == 1 && sent[0] == 0xa5c3 && reads == 1,
           "one TX and one RX access per frame");
    expect(mono56_spi3_transfer(0xffff, &rx) == MONO56_SPI_READY, "back-to-back transfer");
    expect(static_cast<uint32_t>(edges[3].time - edges[2].time) >= 2,
           "nCS-high spacing between words");
    expect(mono56_spi3_shutdown() == MONO56_SPI_UNINITIALIZED && resets == 1,
           "explicit owned peripheral reset");
    reset();
    begin();
    now = 0xfffffff0;
    reenter = true;
    expect(mono56_spi3_transfer(0x1234, &rx) == MONO56_SPI_READY && reentered,
           "normal time wrap and nested-call rejection");
    for (auto error : {SPI_SR_OVR, SPI_SR_MODF, SPI_SR_CRCERR, SPI_SR_FRE}) {
        reset();
        begin();
        error_flags = error;
        failed(MONO56_SPI_ERROR);
    }
    reset();
    begin();
    no_rx = true;
    failed(MONO56_SPI_TIMEOUT);
    reset();
    begin();
    stuck_busy = true;
    failed(MONO56_SPI_TIMEOUT);
    reset();
    begin();
    SPI3->SR &= ~SPI_SR_TXE;
    failed(MONO56_SPI_TIMEOUT);
    reset();
    begin();
    frozen = true;
    failed(MONO56_SPI_POLL_LIMIT);
    reset();
    begin();
    backwards = true;
    failed(MONO56_SPI_CLOCK_ERROR);
    reset();
    begin();
    SPI3->SR |= SPI_SR_RXNE;
    failed(MONO56_SPI_STALE_RX);
    reset();
    begin();
    SPI3->CR1 ^= SPI_CR1_CPHA;
    failed(MONO56_SPI_CONFIG_CHANGED);
    reset();
    begin();
    SPI3->CR2 = SPI_CR2_RXDMAEN;
    failed(MONO56_SPI_CONFIG_CHANGED);
    reset();
    begin();
    SPI3->I2SCFGR = SPI_I2SCFGR_I2SMOD;
    failed(MONO56_SPI_CONFIG_CHANGED);
    reset();
    SPI3->CR1 = SPI_CR1_SPE;
    expect(mono56_spi3_init(clock_us, 42000000, 200) == MONO56_SPI_PERIPHERAL_BUSY,
           "foreign active SPI rejected");
    expect(mono56_spi3_shutdown() == MONO56_SPI_UNINITIALIZED && SPI3->CR1 == SPI_CR1_SPE,
           "non-owner shutdown leaves foreign SPI untouched");
    reset();
    expect(mono56_spi3_init(nullptr, 42000000, 200) == MONO56_SPI_BAD_CONFIG,
           "missing clock rejected");
    expect(mono56_spi3_init(clock_us, 84000000, 200) == MONO56_SPI_BAD_CONFIG,
           "wrong peripheral clock rejected");
    expect(mono56_spi3_init(clock_us, 42000000, 59) == MONO56_SPI_BAD_CONFIG,
           "insufficient deadline rejected");
    expect(mono56_spi3_init(clock_us, 42000000, 1001) == MONO56_SPI_BAD_CONFIG,
           "excessive polling deadline rejected");
    begin();
    expect(mono56_spi3_transfer(0, nullptr) == MONO56_SPI_BAD_CONFIG,
           "null receive pointer rejected");
    // Real register session -> real C transport -> simulated peripheral/device.
    reset();
    begin();
    chip_model = true;
    odrive::mono56::Drv8353 driver({nullptr, mono56_drv8353_spi3_exchange,
                                    [](void *) { return permitted; }, [](void *) { return quiet; },
                                    [](void *) { return true; },
                                    [](void *) {
                                        ++inhibited;
                                        permitted = false;
                                    }});
    const odrive::mono56::Drv8353Config config{150, 300, 150, 300, 2000, 200, 200, 2, 20, 250};
    expect(driver.configure_coasted(config) && driver.coasted(),
           "integrated configuration through SPI3 adapter");
    expect(sent.size() == 31 && chip[2] == 0x484 && chip[3] == 0x633,
           "all 31 register frames complete and lock");
    expect(driver.begin_current_calibration() && driver.calibrating() && chip[6] == 0x28c &&
               chip[7] == 0 && chip[3] == 0x633 && chip[2] == 0x484,
           "B/C manual input shorting through real transport retains COAST and lock");
    odrive::mono56::CurrentZeroEstimator estimator;
    const odrive::mono56::CurrentConfig current{
        0.001f, 0.001f, 20, 1, 1, 100, 5, 50, 1000000, 3.0f, 3.6f, 0.30f, 40.0f, 16.0f, 0.05f};
    const auto calibrated_at = now;
    expect(estimator.begin(current, {8, 10, 700, 2000, 4}, 1, calibrated_at),
           "zero collection starts after verified SPI calibration entry");
    for (unsigned i = 0; i < 8; ++i) {
        now = calibrated_at + 12 + 100 * i;
        // Synthetic analog samples respond to the simulated chip's input
        // switches. No ADC2/3 hardware or physical settling is modeled here.
        const uint16_t b = chip[6] & 0x08 ? 2050 : 2300;
        const uint16_t c = chip[6] & 0x04 ? 2045 : 2300;
        const odrive::mono56::CurrentFrame sample{
            {b, now - 2, true},  {c, now - 1, true}, {3.3f, now - 2, true}, 1, false,
            driver.calibrating()};
        estimator.add(sample, now);
    }
    const auto zero = estimator.zero();
    expect(zero.valid && zero.b_code == 2050 && zero.c_code == 2045,
           "register-controlled synthetic zero samples reach the real estimator");
    expect(driver.end_current_calibration() && !driver.calibrating() && driver.coasted() &&
               chip[6] == 0x280 && chip[3] == 0x633 && chip[2] == 0x484,
           "normal inputs restored through transport without releasing COAST");
    expect(driver.release_coast() && chip[2] == 0x480,
           "explicit COAST release through real transport");
    quiet = false;
    expect(driver.check(), "runtime readback through real transport");
    no_rx = true;
    expect(!driver.check() && inhibited &&
               driver.error() == odrive::mono56::Drv8353Error::transport,
           "transport timeout reaches required motor inhibition callback");
    expect(mono56_spi3_status() == MONO56_SPI_TIMEOUT && !driver.configured(),
           "both layers retain failure");
    std::cout << checks
              << " SPI3 transport/DRV8353 integration checks passed with simulated peripherals.\n";
}
