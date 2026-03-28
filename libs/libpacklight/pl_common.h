#pragma once
#include "packlight.h"
#include <string.h>
#include <stdint.h>
// localuse library written entirely by @shareui

static inline bool plIsAlpha(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}
static inline bool plIsDigit(char c) { return c >= '0' && c <= '9'; }
static inline bool plIsAlNum(char c) { return plIsAlpha(c) || plIsDigit(c); }
static inline bool plIsHex(char c) {
    return plIsDigit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

static inline void plEmit(Token* out, uint32_t cap, uint32_t* cnt,
                          uint32_t start, uint32_t len, uint8_t type) {
    if (*cnt < cap && len > 0) {
        out[*cnt] = {start, len, type};
        (*cnt)++;
    }
}

static inline bool plMatchWord(const char* src, uint32_t slen, uint32_t i,
                               const char* w, uint32_t wlen) {
    if (i + wlen > slen) return false;
    if (memcmp(src + i, w, wlen) != 0) return false;
    if (i + wlen < slen && plIsAlNum(src[i + wlen])) return false;
    return true;
}

static inline bool plInTable(const char** table, const char* src,
                             uint32_t pos, uint32_t len) {
    for (int k = 0; table[k]; k++) {
        uint32_t klen = (uint32_t)strlen(table[k]);
        if (klen == len && memcmp(src + pos, table[k], klen) == 0) return true;
    }
    return false;
}
