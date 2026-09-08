#pragma once
#include "stm32f405xx.h"
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
extern SPI_TypeDef mono56_test_spi3;
extern GPIO_TypeDef mono56_test_spi_gpioc;
extern RCC_TypeDef mono56_test_spi_rcc;
void mono56_spi_test_select(bool selected);
void mono56_spi_test_write(uint16_t word);
uint16_t mono56_spi_test_read(void);
void mono56_spi_test_reset(void);
#ifdef __cplusplus
}
#endif
#undef SPI3
#undef GPIOC
#undef RCC
#undef __DSB
#define SPI3 (&mono56_test_spi3)
#define GPIOC (&mono56_test_spi_gpioc)
#define RCC (&mono56_test_spi_rcc)
#define __DSB() __atomic_thread_fence(__ATOMIC_SEQ_CST)
