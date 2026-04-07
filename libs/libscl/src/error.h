#ifndef SCL_ERROR_H
#define SCL_ERROR_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// error context for building formatted messages
typedef struct {
    int         line;
    int         col;
    const char *field;     // nullable
    const char *message;
    const char *src;       // full source text nullable
    int         tokLen;    // length of offending token for caret
} SclErrorCtx;

/*
 * builds heap-allocated error string in spec format:
 *   scl error at line N, col M
 *     field "x": message
 *     |  source line
 *     |  ^^^^^^
 *
 * caller must free() the returned string.
 */
char *sclErrorFormat(const SclErrorCtx *ctx);

/*
 * warning: same format but prefixed with "scl warning".
 * caller must free().
 */
char *sclWarningFormat(const SclErrorCtx *ctx);

#ifdef __cplusplus
}
#endif

#endif
