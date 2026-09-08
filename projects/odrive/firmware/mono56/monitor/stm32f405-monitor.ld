/* Board-specific diagnostic layout; reserve the upstream last 256 KiB for NVM.
   All data/DMA buffers use the 128 KiB SRAM window, never CCM. No heap/runtime. */
ENTRY(Reset_Handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 768K
    RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}
_stack_top = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS {
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH
    .ARM.extab : { *(.ARM.extab*) } > FLASH
    .ARM.exidx : { *(.ARM.exidx*) } > FLASH
    .data : {
        . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .;
    } > RAM AT> FLASH
    _sidata = LOADADDR(.data);
    .bss (NOLOAD) : {
        . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .;
    } > RAM
    .init_array : { KEEP(*(.init_array*)) KEEP(*(.ctors*)) } > FLASH
    /DISCARD/ : { *(.comment) *(.note*) }
}
ASSERT(SIZEOF(.isr_vector) == 392, "F405 vector table must contain 98 words")
ASSERT(SIZEOF(.init_array) == 0, "Static constructors are not supported by this startup")
ASSERT(_ebss <= _stack_top - 8192, "Reserve at least 8 KiB stack")
ASSERT((ADDR(.isr_vector) & 511) == 0, "Vector table must be 512-byte aligned")
