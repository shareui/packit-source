#include "annotations.h"
#include "error.h"

#include <regex>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <cstdint>

static char *annErr(const char *src, int line, int col,
                    const char *field, const char *msg) {
    SclErrorCtx ctx = {};
    ctx.line    = line;
    ctx.col     = col;
    ctx.field   = field;
    ctx.message = msg;
    ctx.src     = src;
    ctx.tokLen  = 1;
    return sclErrorFormat(&ctx);
}

static char *checkRange(AstNode *ann, AstNode *val,
                        const char *field, const char *src) {
    double mn = ann->as.range.min;
    double mx = ann->as.range.max;
    double v  = 0;

    if (val->type == NODE_VAL_INT)       v = (double)val->as.intVal.v;
    else if (val->type == NODE_VAL_UINT) v = (double)val->as.uintVal.v;
    else if (val->type == NODE_VAL_FLOAT) v = val->as.floatVal.v;
    else return nullptr;  // wrong type  type checker handles that

    if (v < mn || v > mx) {
        char buf[256];
        snprintf(buf, sizeof(buf),
                 "value %g is out of range [%g, %g]", v, mn, mx);
        return annErr(src, val->line, val->col, field, buf);
    }
    return nullptr;
}

static char *checkMinLen(AstNode *ann, AstNode *val,
                         const char *field, const char *src) {
    size_t n = ann->as.lenBound.n;
    size_t actual = 0;

    if (val->type == NODE_VAL_STRING)     actual = val->as.strVal.len;
    else if (val->type == NODE_VAL_LIST)  actual = val->as.listVal.count;
    else return nullptr;

    if (actual < n) {
        char buf[256];
        snprintf(buf, sizeof(buf),
                 "length %zu is less than minimum %zu", actual, n);
        return annErr(src, val->line, val->col, field, buf);
    }
    return nullptr;
}

static char *checkMaxLen(AstNode *ann, AstNode *val,
                         const char *field, const char *src) {
    size_t n = ann->as.lenBound.n;
    size_t actual = 0;

    if (val->type == NODE_VAL_STRING)     actual = val->as.strVal.len;
    else if (val->type == NODE_VAL_LIST)  actual = val->as.listVal.count;
    else return nullptr;

    if (actual > n) {
        char buf[256];
        snprintf(buf, sizeof(buf),
                 "length %zu exceeds maximum %zu", actual, n);
        return annErr(src, val->line, val->col, field, buf);
    }
    return nullptr;
}

static char *checkPattern(AstNode *ann, AstNode *val,
                          const char *field, const char *src) {
    if (val->type != NODE_VAL_STRING) return nullptr;

    const char *pat = ann->as.pattern.pattern;
    if (!pat) return nullptr;

    std::regex re;
    try {
        re = std::regex(pat, std::regex::ECMAScript);
    } catch (const std::regex_error &e) {
        char buf[512];
        snprintf(buf, sizeof(buf), "invalid @pattern regex '%s': %s", pat, e.what());
        return annErr(src, ann->line, ann->col, field, buf);
    }

    const char *str = val->as.strVal.str ? val->as.strVal.str : "";
    if (!std::regex_search(str, re)) {
        char buf[512];
        snprintf(buf, sizeof(buf),
                 "value \"%s\" does not match @pattern \"%s\"", str, pat);
        return annErr(src, val->line, val->col, field, buf);
    }
    return nullptr;
}

char *sclCheckAnnotations(AstAnnotation *annotations, AstNode *val,
                          const char *fieldName, const char *src) {
    for (AstAnnotation *ann = annotations; ann; ann = ann->next) {
        AstNode *node = ann->node;
        char *err = nullptr;

        switch (node->type) {
            case NODE_ANN_RANGE:      err = checkRange(node, val, fieldName, src);   break;
            case NODE_ANN_MINLEN:     err = checkMinLen(node, val, fieldName, src);  break;
            case NODE_ANN_MAXLEN:     err = checkMaxLen(node, val, fieldName, src);  break;
            case NODE_ANN_PATTERN:    err = checkPattern(node, val, fieldName, src); break;
            case NODE_ANN_DEPRECATED: break;  // warning emitted by type checker
            default:                  break;
        }

        if (err) return err;
    }
    return nullptr;
}
