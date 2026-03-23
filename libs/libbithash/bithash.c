#include "bithash.h"

#include <string.h>
#include <stdio.h>

#if defined(__GNUC__) || defined(__clang__)
#   define BH_INLINE   static inline __attribute__((always_inline))
#   define BH_LIKELY(x)   __builtin_expect(!!(x), 1)
#   define BH_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#   define BH_INLINE   static inline
#   define BH_LIKELY(x)   (x)
#   define BH_UNLIKELY(x) (x)
#endif

#define P0  UINT64_C(0x9e3779b97f4a7c15)
#define P1  UINT64_C(0x6c62272e07bb0142)
#define P2  UINT64_C(0x94d049bb133111eb)
#define P3  UINT64_C(0xbf58476d1ce4e5b9)

#define BULK_STEP  32u

BH_INLINE uint64_t load64(const void *p) {
    uint64_t v;
    memcpy(&v, p, 8);
    return v;
}

BH_INLINE uint64_t load32(const void *p) {
    uint32_t v;
    memcpy(&v, p, 4);
    return (uint64_t)v;
}

BH_INLINE uint64_t mum(uint64_t a, uint64_t b) {
#if defined(__SIZEOF_INT128__)
    __uint128_t r = (__uint128_t)a * b;
    return (uint64_t)(r >> 64) ^ (uint64_t)r;
#else
    uint64_t a0 = (uint32_t)a, a1 = a >> 32;
    uint64_t b0 = (uint32_t)b, b1 = b >> 32;
    uint64_t lo = a * b;
    uint64_t hi = a1 * b1 + ((a0 * b1 + a1 * b0) >> 32);
    return hi ^ lo;
#endif
}

BH_INLINE uint64_t mix(uint64_t a, uint64_t b) {
    return mum(a ^ P0, b ^ P1);
}

BH_INLINE uint64_t tail(const uint8_t *p, size_t len, uint64_t state) {
    if (len >= 16) {
        state = mum(state ^ load64(p),     P2);
        state = mum(state ^ load64(p + 8), P3);
        p += 16; len -= 16;
    }
    if (len >= 8) {
        state = mum(state ^ load64(p), P0);
        p += 8; len -= 8;
    }
    if (len >= 4) {
        state ^= load32(p) | (load32(p + len - 4) << 32);
        state  = mum(state, P1);
        p += 4; len -= 4;
    }
    if (len > 0) {
        uint64_t v = ((uint64_t)p[0])
                   | ((uint64_t)p[len >> 1] << 8)
                   | ((uint64_t)p[len - 1]  << 16);
        state = mum(state ^ v, P2);
    }
    return state;
}

BH_INLINE uint64_t finalize(uint64_t s0, uint64_t s1,
                             uint64_t s2, uint64_t s3, uint64_t len) {
    uint64_t h = mix(s0, s1) ^ mix(s2, s3);
    h = mum(h ^ len, P3);
    h ^= h >> 33;
    h *= P0;
    h ^= h >> 29;
    h *= P2;
    h ^= h >> 32;
    return h;
}

BH_INLINE void bulkProcess(uint64_t *s0, uint64_t *s1,
                            uint64_t *s2, uint64_t *s3,
                            const uint8_t *p, size_t blocks) {
    for (size_t i = 0; i < blocks; i++, p += BULK_STEP) {
        *s0 = mum(*s0 ^ load64(p),      P1);
        *s1 = mum(*s1 ^ load64(p + 8),  P2);
        *s2 = mum(*s2 ^ load64(p + 16), P3);
        *s3 = mum(*s3 ^ load64(p + 24), P0);
    }
}

uint64_t bitHash_oneshot(const void *data, size_t len, uint64_t seed) {
    const uint8_t *p = (const uint8_t *)data;

    uint64_t s0 = seed ^ P0;
    uint64_t s1 = seed ^ P1;
    uint64_t s2 = seed ^ P2;
    uint64_t s3 = seed ^ P3;

    size_t blocks    = len / BULK_STEP;
    size_t remaining = len % BULK_STEP;

    bulkProcess(&s0, &s1, &s2, &s3, p, blocks);

    uint64_t t = tail(p + blocks * BULK_STEP, remaining, s0 ^ s1 ^ s2 ^ s3);
    return finalize(s0, s1, s2, s3, t ^ (uint64_t)len);
}

void bitHash_init(BitHashState *state, uint64_t seed) {
    state->s0       = seed ^ P0;
    state->s1       = seed ^ P1;
    state->s2       = seed ^ P2;
    state->s3       = seed ^ P3;
    state->totalLen = 0;
    state->bufLen   = 0;
}

void bitHash_update(BitHashState *state, const void *data, size_t len) {
    const uint8_t *p = (const uint8_t *)data;
    state->totalLen += len;

    if (state->bufLen > 0) {
        uint32_t need = BULK_STEP - state->bufLen;
        if (len < need) {
            memcpy(state->buf + state->bufLen, p, len);
            state->bufLen += (uint32_t)len;
            return;
        }
        memcpy(state->buf + state->bufLen, p, need);
        bulkProcess(&state->s0, &state->s1, &state->s2, &state->s3,
                    state->buf, 1);
        p         += need;
        len       -= need;
        state->bufLen = 0;
    }

    size_t blocks = len / BULK_STEP;
    bulkProcess(&state->s0, &state->s1, &state->s2, &state->s3, p, blocks);
    p   += blocks * BULK_STEP;
    len -= blocks * BULK_STEP;

    if (len > 0) {
        memcpy(state->buf, p, len);
        state->bufLen = (uint32_t)len;
    }
}

uint64_t bitHash_finish(BitHashState *state) {
    uint64_t t = tail(state->buf, state->bufLen,
                      state->s0 ^ state->s1 ^ state->s2 ^ state->s3);
    return finalize(state->s0, state->s1, state->s2, state->s3,
                    t ^ state->totalLen);
}

int bitHash_file_fp(void *fp, void *io_buf, size_t io_buf_len,
                    uint64_t seed, uint64_t *out_hash) {
    BitHashState state;
    bitHash_init(&state, seed);

    size_t n;
    while ((n = fread(io_buf, 1, io_buf_len, (FILE *)fp)) > 0)
        bitHash_update(&state, io_buf, n);

    if (ferror((FILE *)fp))
        return -1;

    *out_hash = bitHash_finish(&state);
    return 0;
}

int bitHash_file(const char *path, void *io_buf, size_t io_buf_len,
                 uint64_t seed, uint64_t *out_hash) {
    FILE *fp = fopen(path, "rb");
    if (!fp)
        return -1;

    int rc = bitHash_file_fp(fp, io_buf, io_buf_len, seed, out_hash);
    fclose(fp);
    return rc;
}

int bitHash_files_equal(const char *path_a, const char *path_b,
                         void *io_buf, size_t io_buf_len) {
    uint64_t ha, hb;
    if (bitHash_file(path_a, io_buf, io_buf_len, BITHASH_SEED_DEFAULT, &ha) != 0)
        return -1;
    if (bitHash_file(path_b, io_buf, io_buf_len, BITHASH_SEED_DEFAULT, &hb) != 0)
        return -1;
    return (ha == hb) ? 1 : 0;
}

const char *bitHash_version(void) {
    return "1.0.0";
}
