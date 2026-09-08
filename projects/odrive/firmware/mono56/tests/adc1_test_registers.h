#pragma once
// Register layout and bit definitions come from the real STM32F405 CMSIS header.
// Only addresses and the CPU memory barrier are substituted on the host.
#include "stm32f405xx.h"
#ifdef __cplusplus
extern "C" {
#endif
extern ADC_TypeDef mono56_test_adc1, mono56_test_adc2, mono56_test_adc3;
extern ADC_Common_TypeDef mono56_test_adc_common;
extern DMA_TypeDef mono56_test_dma2;
extern DMA_Stream_TypeDef mono56_test_dma_stream;
extern GPIO_TypeDef mono56_test_gpioa;
extern GPIO_TypeDef mono56_test_gpiob;
extern TIM_TypeDef mono56_test_tim1;
extern uint32_t mono56_test_primask, mono56_test_irq_disable_calls;
extern RCC_TypeDef mono56_test_rcc;
volatile uint16_t* mono56_adc_test_buffer(void);
#ifdef __cplusplus
}
#endif
#undef ADC1
#undef ADC2
#undef ADC3
#undef ADC
#undef DMA2
#undef DMA2_Stream0
#undef GPIOA
#undef GPIOB
#undef TIM1
#undef RCC
#define ADC1 (&mono56_test_adc1)
#define ADC2 (&mono56_test_adc2)
#define ADC3 (&mono56_test_adc3)
#define ADC (&mono56_test_adc_common)
#define DMA2 (&mono56_test_dma2)
#define DMA2_Stream0 (&mono56_test_dma_stream)
#define GPIOA (&mono56_test_gpioa)
#define GPIOB (&mono56_test_gpiob)
#define TIM1 (&mono56_test_tim1)
#define RCC (&mono56_test_rcc)
#undef __DMB
#define __DMB() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#undef __DSB
#define __DSB() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#define __get_PRIMASK() (mono56_test_primask)
#define __disable_irq() do { mono56_test_primask = 1; ++mono56_test_irq_disable_calls; } while (0)
#define __set_PRIMASK(value) do { mono56_test_primask = (value); } while (0)
