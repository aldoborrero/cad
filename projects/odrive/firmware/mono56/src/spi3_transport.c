#include "spi3_transport.h"
#include "stm32f405xx.h"
#ifdef MONO56_SPI_TEST
#include "spi3_test_registers.h"
#endif
#ifdef MONO56_DIAGNOSTIC_TEST
#include "diagnostic_test_registers.h"
#endif

#define EXPECTED_CR1                                                                               \
    (SPI_CR1_MSTR | SPI_CR1_SSM | SPI_CR1_SSI | SPI_CR1_CPHA | SPI_CR1_DFF | SPI_CR1_BR_1 |        \
     SPI_CR1_BR_2 | SPI_CR1_SPE)
#define ERROR_FLAGS (SPI_SR_MODF | SPI_SR_OVR | SPI_SR_CRCERR | SPI_SR_FRE)
#define POLL_BUDGET 200000u
static mono56_spi_status state = MONO56_SPI_UNINITIALIZED;
static uint32_t (*time_us)(void);
static uint32_t deadline, started, last_observed, polls;

static void select_chip(bool selected) {
    GPIOC->BSRR = selected ? GPIO_BSRR_BR13 : GPIO_BSRR_BS13;
#ifdef MONO56_SPI_TEST
    mono56_spi_test_select(selected);
#endif
    __DSB();
}
static void write_data(uint16_t value) {
#ifdef MONO56_SPI_TEST
    mono56_spi_test_write(value);
#else
    *(volatile uint16_t *)&SPI3->DR = value;
#endif
}
static uint16_t read_data(void) {
#ifdef MONO56_SPI_TEST
    return mono56_spi_test_read();
#else
    return *(volatile uint16_t *)&SPI3->DR;
#endif
}
static mono56_spi_status fail(mono56_spi_status reason) {
    select_chip(false);
    SPI3->CR1 &= ~SPI_CR1_SPE;
    __DSB();
    state = reason;
    return state;
}
static bool poll(uint32_t *now) {
    if (polls-- == 0) {
        fail(MONO56_SPI_POLL_LIMIT);
        return false;
    }
    *now = time_us();
    if ((uint32_t)(*now - last_observed) >= 0x80000000u) {
        fail(MONO56_SPI_CLOCK_ERROR);
        return false;
    }
    last_observed = *now;
    if ((uint32_t)(*now - started) > deadline) {
        fail(MONO56_SPI_TIMEOUT);
        return false;
    }
    if (SPI3->SR & ERROR_FLAGS) {
        fail(MONO56_SPI_ERROR);
        return false;
    }
    if (SPI3->CR1 != EXPECTED_CR1 || SPI3->CR2 != 0 || (SPI3->I2SCFGR & SPI_I2SCFGR_I2SMOD)) {
        fail(MONO56_SPI_CONFIG_CHANGED);
        return false;
    }
    return true;
}
static bool wait_delay(uint32_t since) {
    uint32_t now;
    do {
        if (!poll(&now))
            return false;
        if ((uint32_t)(now - since) >= 0x80000000u) {
            fail(MONO56_SPI_CLOCK_ERROR);
            return false;
        }
    } while ((uint32_t)(now - since) < 2u);
    return true;
}
static bool wait_flags(uint32_t mask, uint32_t value) {
    uint32_t now;
    do {
        if (!poll(&now))
            return false;
    } while ((SPI3->SR & mask) != value);
    return true;
}

mono56_spi_status mono56_spi3_init(uint32_t (*clock_us)(void), uint32_t pclk1_hz,
                                   uint32_t deadline_us) {
    if (state != MONO56_SPI_UNINITIALIZED)
        return MONO56_SPI_BUSY;
    if (!clock_us || pclk1_hz != 42000000u || deadline_us < 60u || deadline_us > 1000u)
        return MONO56_SPI_BAD_CONFIG;
    RCC->APB1ENR |= RCC_APB1ENR_SPI3EN;
    (void)RCC->APB1ENR;
    if ((SPI3->CR1 & SPI_CR1_SPE) || (SPI3->I2SCFGR & SPI_I2SCFGR_I2SE) ||
        (SPI3->SR & (SPI_SR_BSY | SPI_SR_RXNE)))
        return MONO56_SPI_PERIPHERAL_BUSY;
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOCEN;
    (void)RCC->AHB1ENR;
    // nCS high before changing its mode. PC13 uses low output speed.
    select_chip(false);
    GPIOC->OTYPER &= ~(0xfu << 10);
    GPIOC->OSPEEDR = (GPIOC->OSPEEDR & ~(0xffu << 20)) | (1u << 20) | (1u << 24);
    GPIOC->PUPDR &= ~(0xffu << 20);
    GPIOC->AFR[1] = (GPIOC->AFR[1] & ~(0xfffu << 8)) | (6u << 8) | (6u << 12) | (6u << 16);
    GPIOC->MODER =
        (GPIOC->MODER & ~(0xffu << 20)) | (2u << 20) | (2u << 22) | (2u << 24) | (1u << 26);
    SPI3->I2SCFGR = 0;
    SPI3->CR2 = 0;
    SPI3->CR1 = EXPECTED_CR1;
    time_us = clock_us;
    deadline = deadline_us;
    state = MONO56_SPI_READY;
    return state;
}

mono56_spi_status mono56_spi3_transfer(uint16_t word, uint16_t *received) {
    if (!received)
        return MONO56_SPI_BAD_CONFIG;
    *received = 0;
    if (state != MONO56_SPI_READY)
        return state;
    state = MONO56_SPI_BUSY;
    polls = POLL_BUDGET;
    started = last_observed = time_us();
    uint32_t now;
    if (!poll(&now))
        return state;
    if (SPI3->SR & (SPI_SR_RXNE | SPI_SR_BSY))
        return fail(MONO56_SPI_STALE_RX);
    // An unconditional high interval avoids relying on timestamps across long idles.
    if (!wait_delay(started))
        return state;
    select_chip(true);
    if (!poll(&now))
        return state;
    const uint32_t selected_at = now;
    if (!wait_delay(selected_at) || !wait_flags(SPI_SR_TXE, SPI_SR_TXE))
        return state;
    write_data(word);
    if (!wait_flags(SPI_SR_RXNE, SPI_SR_RXNE))
        return state;
    const uint16_t response = read_data();
    // RXNE alone does not establish that the final clock edge has completed.
    if (!wait_flags(SPI_SR_TXE | SPI_SR_BSY, SPI_SR_TXE))
        return state;
    if (!poll(&now))
        return state;
    const uint32_t completed_at = now;
    if (!wait_delay(completed_at))
        return state;
    select_chip(false);
    if (!poll(&now))
        return state; // Include final observation/CS write in deadline.
    *received = response;
    state = MONO56_SPI_READY;
    return state;
}

mono56_spi_status mono56_spi3_status(void) { return state; }
mono56_spi_status mono56_spi3_shutdown(void) {
    if (state == MONO56_SPI_UNINITIALIZED || state == MONO56_SPI_BUSY)
        return state;
    select_chip(false);
    SPI3->CR1 &= ~SPI_CR1_SPE;
    RCC->APB1RSTR |= RCC_APB1RSTR_SPI3RST;
    (void)RCC->APB1RSTR;
#ifdef MONO56_SPI_TEST
    mono56_spi_test_reset();
#endif
    RCC->APB1RSTR &= ~RCC_APB1RSTR_SPI3RST;
    (void)RCC->APB1RSTR;
    state = MONO56_SPI_UNINITIALIZED;
    time_us = 0;
    return state;
}
bool mono56_drv8353_spi3_exchange(void *context, uint16_t word, uint16_t *received) {
    (void)context;
    return mono56_spi3_transfer(word, received) == MONO56_SPI_READY;
}
