#include "pl_common.h"

static inline void skipWs(const char* src, uint32_t len, uint32_t* i) {
    while (*i < len) {
        char c = src[*i];
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') (*i)++;
        else break;
    }
}

static uint32_t skipJsonStr(const char* src, uint32_t len, uint32_t i) {
    i++; // skip opening "
    while (i < len) {
        if (src[i] == '\\') { i += 2; continue; }
        if (src[i] == '"')  return i + 1;
        i++;
    }
    return len;
}

uint32_t pl_tokenize_json(
    const char* src, uint32_t src_len,
    Token* out, uint32_t out_cap
) {
    uint32_t cnt = 0, i = 0;
    uint64_t objMask = 0;
    int depth = 0;
    bool expectKey = false;

    while (i < src_len && cnt < out_cap) {
        skipWs(src, src_len, &i);
        if (i >= src_len) break;
        char c = src[i];

        if (c == '{') {
            depth++;
            if (depth <= 64) objMask |= (1ULL << (depth - 1));
            expectKey = true; i++; continue;
        }
        if (c == '}') {
            if (depth > 0) {
                if (depth <= 64) objMask &= ~(1ULL << (depth - 1));
                depth--;
            }
            expectKey = false; i++; continue;
        }
        if (c == '[') {
            depth++;
            if (depth <= 64) objMask &= ~(1ULL << (depth - 1));
            expectKey = false; i++; continue;
        }
        if (c == ']') {
            if (depth > 0) {
                if (depth <= 64) objMask &= ~(1ULL << (depth - 1));
                depth--;
            }
            i++; continue;
        }
        if (c == ',') {
            if (depth > 0 && depth <= 64 && (objMask >> (depth - 1)) & 1)
                expectKey = true;
            i++; continue;
        }
        if (c == ':') { expectKey = false; i++; continue; }

        if (c == '"') {
            uint32_t s = i, e = skipJsonStr(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, e - s,
                   expectKey ? (uint8_t)TK_JSON_KEY : (uint8_t)TK_STRING);
            expectKey = false; i = e; continue;
        }

        if (c == '-' || (c >= '0' && c <= '9')) {
            uint32_t s = i;
            if (src[i] == '-') i++;
            while (i < src_len && src[i] >= '0' && src[i] <= '9') i++;
            if (i < src_len && src[i] == '.') {
                i++;
                while (i < src_len && src[i] >= '0' && src[i] <= '9') i++;
            }
            if (i < src_len && (src[i] == 'e' || src[i] == 'E')) {
                i++;
                if (i < src_len && (src[i] == '+' || src[i] == '-')) i++;
                while (i < src_len && src[i] >= '0' && src[i] <= '9') i++;
            }
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_NUMBER);
            continue;
        }

        if (plMatchWord(src, src_len, i, "true",  4)) { plEmit(out, out_cap, &cnt, i, 4, (uint8_t)TK_CONSTANT); i += 4; continue; }
        if (plMatchWord(src, src_len, i, "false", 5)) { plEmit(out, out_cap, &cnt, i, 5, (uint8_t)TK_CONSTANT); i += 5; continue; }
        if (plMatchWord(src, src_len, i, "null",  4)) { plEmit(out, out_cap, &cnt, i, 4, (uint8_t)TK_CONSTANT); i += 4; continue; }
        i++;
    }
    return cnt;
}
