#pragma once
#include <stdint.h>
#include <stddef.h>
// localuse library written entirely by @shareui

// number of bytes in a utf-8 sequence starting with byte b
static inline uint32_t utf8SeqLen(uint8_t b) {
    if (b < 0x80) return 1;
    if (b < 0xE0) return 2;
    if (b < 0xF0) return 3;
    return 4;
}

// walk src once, converting byte offsets from a sorted list to char indices
// offsets[] must be sorted ascending, length offsets_count
// out_chars[] receives the char index for each byte offset
// any offset that falls on a continuation byte or past end gets UINT32_MAX
static inline void utf8MapOffsets(
    const char* src, uint32_t src_len,
    const uint32_t* offsets, uint32_t offsets_count,
    uint32_t* out_chars
) {
    uint32_t charIdx = 0;
    uint32_t byteIdx = 0;
    uint32_t oi = 0;

    while (oi < offsets_count && offsets[oi] < byteIdx) {
        out_chars[oi++] = UINT32_MAX; // offset before start (shouldn't happen)
    }

    while (byteIdx <= src_len && oi < offsets_count) {
        while (oi < offsets_count && offsets[oi] == byteIdx) {
            out_chars[oi++] = charIdx;
        }
        if (byteIdx == src_len) break;
        byteIdx += utf8SeqLen((uint8_t)src[byteIdx]);
        charIdx++;
    }

    // any remaining offsets are past end
    while (oi < offsets_count) {
        out_chars[oi++] = UINT32_MAX;
    }
}
