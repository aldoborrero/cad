#include <limits.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

// The production source is compiled under this name in the host test so its
// implementation cannot replace the host C runtime used by the harness itself.
void *mono56_test_memset(void *, int, size_t);
void *mono56_test_memcpy(void *, const void *, size_t);
static unsigned checks;
static void expect(int ok, const char *message) {
    ++checks;
    if (!ok) {
        fprintf(stderr, "FAIL: %s\n", message);
        exit(1);
    }
}
int main(void) {
    const int values[] = {0, 1, 127, 255, 256, 257, -1, -257, INT_MIN, INT_MAX};
    unsigned char guarded[300];
    for (size_t offset = 0; offset < 16; ++offset)
        for (size_t length = 0; length <= 256; ++length)
            for (size_t v = 0; v < sizeof(values) / sizeof(values[0]); ++v) {
                for (size_t i = 0; i < sizeof(guarded); ++i)
                    guarded[i] = 0xa5;
                void *const start = &guarded[8 + offset];
                void *const result = mono56_test_memset(start, values[v], length);
                int valid = result == start;
                for (size_t i = 0; i < sizeof(guarded); ++i) {
                    const unsigned char expected = i >= 8 + offset && i < 8 + offset + length
                                                       ? (unsigned char)values[v]
                                                       : 0xa5;
                    valid = valid && guarded[i] == expected;
                }
                expect(valid, "byte fill returns original pointer and preserves both guards");
            }
    unsigned char source[300];
    for (size_t src_offset = 0; src_offset < 16; ++src_offset)
        for (size_t dst_offset = 0; dst_offset < 16; ++dst_offset)
            for (size_t length = 0; length <= 256; ++length) {
                for (size_t i = 0; i < sizeof(source); ++i) {
                    source[i] = (unsigned char)(i * 37 + length);
                    guarded[i] = 0xa5;
                }
                void *const start = &guarded[8 + dst_offset];
                void *const result = mono56_test_memcpy(start, &source[8 + src_offset], length);
                int valid = result == start;
                for (size_t i = 0; i < sizeof(source); ++i) {
                    const unsigned char expected =
                        i >= 8 + dst_offset && i < 8 + dst_offset + length
                            ? (unsigned char)((i - dst_offset + src_offset) * 37 + length)
                            : 0xa5;
                    valid = valid && guarded[i] == expected &&
                            source[i] == (unsigned char)(i * 37 + length);
                }
                expect(valid,
                       "copy preserves source and guards for independently unaligned buffers");
            }
    printf(
        "%u freestanding memory fill/copy checks passed across lengths, values and alignments.\n",
        checks);
}
