#include <stddef.h>

// Compiler-generated aggregate initialization can call memset even with
// -fno-builtin. Supply the freestanding byte fill without a libc/CRT dependency.
// Volatile byte stores prevent loop recognition from recursively calling memset
// and work on unaligned normal RAM. This is not a peripheral-register API.
void *memset(void *destination, int value, size_t length) {
    volatile unsigned char *cursor = destination;
    const unsigned char byte = (unsigned char)value;
    while (length--) {
        *cursor = byte;
        ++cursor;
    }
    return destination;
}

// Aggregate copies can also lower to memcpy. Source/destination must be valid,
// nonoverlapping normal RAM for length bytes, as required by the C interface.
// Volatile byte accesses prevent recursive compiler loop recognition and avoid
// alignment assumptions. This is not memmove or a peripheral-register API.
void *memcpy(void *destination, const void *source, size_t length) {
    volatile unsigned char *out = destination;
    const volatile unsigned char *in = source;
    while (length--) {
        *out = *in;
        ++out;
        ++in;
    }
    return destination;
}
