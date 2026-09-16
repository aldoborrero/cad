#pragma once
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    MONO56_SPI_UNINITIALIZED,
    MONO56_SPI_READY,
    MONO56_SPI_BUSY,
    MONO56_SPI_BAD_CONFIG,
    MONO56_SPI_PERIPHERAL_BUSY,
    MONO56_SPI_TIMEOUT,
    MONO56_SPI_CLOCK_ERROR,
    MONO56_SPI_POLL_LIMIT,
    MONO56_SPI_ERROR,
    MONO56_SPI_STALE_RX,
    MONO56_SPI_CONFIG_CHANGED
} mono56_spi_status;

// Exclusive SPI3 / PC10..13 owner. Caller must first hold motor outputs quiet.
// PCLK1 must remain 42 MHz; the transport uses /128 = 328125 Hz, mode 1, 16 bits.
// clock_us must be a nonblocking monotonic wrapping microsecond counter.
// Deadline (60..1000 us) includes CS spacing/setup/hold and completion observation;
// no production latency or signal-integrity qualification is implied.
mono56_spi_status mono56_spi3_init(uint32_t (*clock_us)(void), uint32_t pclk1_hz,
                                   uint32_t deadline_us);
// Bounded polling, interrupts left enabled. Single serialized execution context;
// do not call from an ISR that would starve required safety/acquisition service.
// Only READY publishes a received word; all other outcomes clear *received.
mono56_spi_status mono56_spi3_transfer(uint16_t word, uint16_t *received);
mono56_spi_status mono56_spi3_status(void);
// Reset the owned SPI peripheral and release the session; never actuate ENABLE.
// An active/reentrant caller gets BUSY. Latched errors require shutdown + init.
mono56_spi_status mono56_spi3_shutdown(void);

// Drv8353Io.exchange-compatible adapter; board permission/quiet/inhibit callbacks
// remain separately required. The context argument is deliberately unused.
bool mono56_drv8353_spi3_exchange(void *context, uint16_t word, uint16_t *received);
#ifdef __cplusplus
}
#endif
