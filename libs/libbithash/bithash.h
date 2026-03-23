#ifndef BITHASH_H
#define BITHASH_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BITHASH_VERSION_MAJOR 1
#define BITHASH_VERSION_MINOR 0
#define BITHASH_VERSION_PATCH 0

#if defined(_WIN32)
#   ifdef BITHASH_BUILD
#       define BITHASH_API  __declspec(dllexport)
#   else
#       define BITHASH_API  __declspec(dllimport)
#   endif
#elif defined(__GNUC__) || defined(__clang__)
#   define BITHASH_API  __attribute__((visibility("default")))
#else
#   define BITHASH_API
#endif

#define BITHASH_SEED_DEFAULT  UINT64_C(0)

#define BITHASH_BUF_SIZE  32u

typedef struct {
    uint64_t s0, s1, s2, s3;
    uint64_t totalLen;
    uint8_t  buf[BITHASH_BUF_SIZE];
    uint32_t bufLen;
} BitHashState;

BITHASH_API uint64_t bitHash_oneshot(const void *data, size_t len, uint64_t seed);

BITHASH_API void bitHash_init(BitHashState *state, uint64_t seed);

BITHASH_API void bitHash_update(BitHashState *state, const void *data, size_t len);

BITHASH_API uint64_t bitHash_finish(BitHashState *state);

BITHASH_API int bitHash_file(const char   *path,
                              void         *io_buf,
                              size_t        io_buf_len,
                              uint64_t      seed,
                              uint64_t     *out_hash);

BITHASH_API int bitHash_file_fp(void     *fp,
                                 void     *io_buf,
                                 size_t    io_buf_len,
                                 uint64_t  seed,
                                 uint64_t *out_hash);

BITHASH_API int bitHash_files_equal(const char *path_a,
                                     const char *path_b,
                                     void       *io_buf,
                                     size_t      io_buf_len);

BITHASH_API const char *bitHash_version(void);

#ifdef __cplusplus
}
#endif

#endif
