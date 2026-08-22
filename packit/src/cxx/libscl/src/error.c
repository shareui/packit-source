#include "error.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// extract the Nth line 1-based from src into buf return length
static size_t extractLine(const char *src, int lineNum, char *buf, size_t bufSize) {
    if (!src || lineNum < 1) {
        buf[0] = '\0';
        return 0;
    }

    int cur = 1;
    const char *p = src;

    while (*p && cur < lineNum) {
        if (*p == '\n') cur++;
        p++;
    }

    const char *lineStart = p;
    while (*p && *p != '\n') p++;

    size_t len = (size_t)(p - lineStart);
    if (len >= bufSize) len = bufSize - 1;

    memcpy(buf, lineStart, len);
    buf[len] = '\0';
    return len;
}

static char *buildMessage(const char *prefix, const SclErrorCtx *ctx) {
    char lineBuf[1024];
    size_t lineLen = 0;

    if (ctx->src) {
        lineLen = extractLine(ctx->src, ctx->line, lineBuf, sizeof(lineBuf));
    }

    // build caret string: spaces up to col-1 then carets
    char caretBuf[1024] = {0};
    if (lineLen > 0 && ctx->col >= 1) {
        int spaces = ctx->col - 1;
        int carets = ctx->tokLen > 0 ? ctx->tokLen : 1;

        if (spaces < 0) spaces = 0;
        if (spaces >= (int)sizeof(caretBuf) - 1) spaces = (int)sizeof(caretBuf) - 2;
        if (spaces + carets >= (int)sizeof(caretBuf)) carets = (int)sizeof(caretBuf) - spaces - 1;

        memset(caretBuf, ' ', spaces);
        memset(caretBuf + spaces, '^', carets);
        caretBuf[spaces + carets] = '\0';
    }

    // estimate buffer size
    size_t sz = 256 + strlen(ctx->message) + lineLen + sizeof(caretBuf);
    if (ctx->field) sz += strlen(ctx->field) + 32;

    char *out = malloc(sz);
    if (!out) return NULL;

    int written = 0;

    written += snprintf(out + written, sz - written,
        "%s at line %d, col %d\n", prefix, ctx->line, ctx->col);

    if (ctx->field) {
        written += snprintf(out + written, sz - written,
            "  field \"%s\": %s\n", ctx->field, ctx->message);
    } else {
        written += snprintf(out + written, sz - written,
            "  %s\n", ctx->message);
    }

    if (lineLen > 0) {
        written += snprintf(out + written, sz - written,
            "  |  %s\n", lineBuf);
        if (caretBuf[0]) {
            written += snprintf(out + written, sz - written,
                "  |  %s\n", caretBuf);
        }
    }

    (void)written;
    return out;
}

char *sclErrorFormat(const SclErrorCtx *ctx) {
    return buildMessage("scl error", ctx);
}

char *sclWarningFormat(const SclErrorCtx *ctx) {
    return buildMessage("scl warning", ctx);
}
