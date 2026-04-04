#include "pl_common.h"
// localuse library written entirely by @shareui

static const char* KT_KEYWORDS[] = {
    "as", "break", "class", "continue", "do", "else", "false", "for",
    "fun", "if", "in", "interface", "is", "null", "object", "package",
    "return", "super", "this", "throw", "true", "try", "typealias",
    "typeof", "val", "var", "when", "while",
    // soft keywords (context-sensitive, still highlight)
    "abstract", "actual", "annotation", "by", "catch", "companion",
    "constructor", "crossinline", "data", "dynamic", "enum", "expect",
    "external", "field", "file", "final", "finally", "get", "import",
    "infix", "init", "inline", "inner", "internal", "lateinit", "noinline",
    "open", "operator", "out", "override", "private", "protected", "public",
    "reified", "sealed", "set", "suspend", "tailrec", "vararg",
    nullptr
};

static const char* KT_CONSTANTS[] = {
    "true", "false", "null", nullptr
};

static const char* KT_BUILTINS[] = {
    "Any", "Unit", "Nothing", "Boolean", "Byte", "Short", "Int", "Long",
    "Float", "Double", "Char", "String", "Array", "IntArray", "LongArray",
    "FloatArray", "DoubleArray", "BooleanArray", "ByteArray", "CharArray",
    "ShortArray", "List", "MutableList", "Set", "MutableSet", "Map",
    "MutableMap", "Collection", "MutableCollection", "Iterable", "Iterator",
    "Sequence", "Pair", "Triple", "Result", "Lazy",
    "println", "print", "readLine", "error", "TODO", "require", "check",
    "requireNotNull", "checkNotNull", "assert", "run", "let", "also",
    "apply", "with", "takeIf", "takeUnless", "repeat",
    "listOf", "mutableListOf", "setOf", "mutableSetOf", "mapOf", "mutableMapOf",
    "arrayOf", "emptyList", "emptySet", "emptyMap",
    "Exception", "RuntimeException", "IllegalArgumentException",
    "IllegalStateException", "UnsupportedOperationException", "NullPointerException",
    nullptr
};

static uint32_t skipKtStr(const char* src, uint32_t len, uint32_t i) {
    i++; // skip opening "
    while (i < len) {
        if (src[i] == '\\') { i += 2; continue; }
        if (src[i] == '$') {
            // skip template expression (simplified: just skip the char)
            i++; continue;
        }
        if (src[i] == '"') return i + 1;
        if (src[i] == '\n') return i;
        i++;
    }
    return len;
}

static uint32_t skipRawStr(const char* src, uint32_t len, uint32_t i) {
    // raw string: """ ... """
    i += 3;
    while (i + 2 < len) {
        if (src[i] == '"' && src[i+1] == '"' && src[i+2] == '"') return i + 3;
        i++;
    }
    return len;
}

static uint32_t skipLineComment(const char* src, uint32_t len, uint32_t i) {
    while (i < len && src[i] != '\n') i++;
    return i;
}

static uint32_t skipBlockComment(const char* src, uint32_t len, uint32_t i) {
    // kotlin supports nested block comments
    i += 2;
    int depth = 1;
    while (i + 1 < len && depth > 0) {
        if (src[i] == '/' && src[i+1] == '*') { depth++; i += 2; continue; }
        if (src[i] == '*' && src[i+1] == '/') { depth--; i += 2; continue; }
        i++;
    }
    return i;
}

uint32_t pl_tokenize_kotlin(
    const char* src, uint32_t src_len,
    Token* out, uint32_t out_cap
) {
    uint32_t cnt = 0, i = 0;
    bool afterFun = false;
    bool afterClass = false;

    while (i < src_len && cnt < out_cap) {
        char c = src[i];

        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') { i++; continue; }

        // line comment
        if (c == '/' && i + 1 < src_len && src[i+1] == '/') {
            uint32_t s = i;
            i = skipLineComment(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_COMMENT);
            afterFun = afterClass = false; continue;
        }

        // block comment (nested)
        if (c == '/' && i + 1 < src_len && src[i+1] == '*') {
            uint32_t s = i;
            i = skipBlockComment(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_COMMENT);
            afterFun = afterClass = false; continue;
        }

        // annotation
        if (c == '@') {
            uint32_t s = i; i++;
            // optional use-site target: @file:, @get:, etc.
            while (i < src_len && (plIsAlNum(src[i]) || src[i] == ':')) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_DECORATOR);
            afterFun = afterClass = false; continue;
        }

        // raw string """
        if (c == '"' && i + 2 < src_len && src[i+1] == '"' && src[i+2] == '"') {
            uint32_t s = i;
            i = skipRawStr(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_STRING);
            afterFun = afterClass = false; continue;
        }

        // regular string
        if (c == '"') {
            uint32_t s = i;
            i = skipKtStr(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_STRING);
            afterFun = afterClass = false; continue;
        }

        // char literal
        if (c == '\'') {
            uint32_t s = i; i++;
            if (i < src_len && src[i] == '\\') i++;
            while (i < src_len && src[i] != '\'') i++;
            if (i < src_len) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_STRING);
            afterFun = afterClass = false; continue;
        }

        // number
        if (plIsDigit(c) || (c == '.' && i + 1 < src_len && plIsDigit(src[i+1]))) {
            uint32_t s = i;
            if (src[i] == '0' && i + 1 < src_len && (src[i+1] == 'x' || src[i+1] == 'X')) {
                i += 2;
                while (i < src_len && (plIsHex(src[i]) || src[i] == '_')) i++;
                if (i < src_len && (src[i] == 'L' || src[i] == 'u' || src[i] == 'U')) i++;
            } else if (src[i] == '0' && i + 1 < src_len && (src[i+1] == 'b' || src[i+1] == 'B')) {
                i += 2;
                while (i < src_len && (src[i] == '0' || src[i] == '1' || src[i] == '_')) i++;
                if (i < src_len && (src[i] == 'L' || src[i] == 'u' || src[i] == 'U')) i++;
            } else {
                while (i < src_len && (plIsDigit(src[i]) || src[i] == '_')) i++;
                if (i < src_len && src[i] == '.') {
                    i++;
                    while (i < src_len && (plIsDigit(src[i]) || src[i] == '_')) i++;
                }
                if (i < src_len && (src[i] == 'e' || src[i] == 'E')) {
                    i++;
                    if (i < src_len && (src[i] == '+' || src[i] == '-')) i++;
                    while (i < src_len && plIsDigit(src[i])) i++;
                }
                if (i < src_len && (src[i] == 'f' || src[i] == 'F' || src[i] == 'L')) i++;
            }
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_NUMBER);
            afterFun = afterClass = false; continue;
        }

        // operators (including elvis ?:, safe call ?., not-null !!)
        if (c == '+' || c == '-' || c == '*' || c == '/' || c == '%' || c == '=' ||
            c == '!' || c == '<' || c == '>' || c == '&' || c == '|' || c == '^' ||
            c == '~' || c == '?' || c == ':') {
            uint32_t s = i; i++;
            if (i < src_len && (src[i] == '=' || src[i] == '>' || src[i] == ':' || src[i] == c)) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_OPERATOR);
            afterFun = afterClass = false; continue;
        }

        // backtick-quoted identifier
        if (c == '`') {
            uint32_t s = i; i++;
            while (i < src_len && src[i] != '`') i++;
            if (i < src_len) i++;
            // check if followed by (
            uint32_t j = i;
            while (j < src_len && (src[j] == ' ' || src[j] == '\t')) j++;
            uint8_t t = (j < src_len && src[j] == '(') ? (uint8_t)TK_CALL : 0;
            if (t) plEmit(out, out_cap, &cnt, s, i - s, t);
            afterFun = afterClass = false; continue;
        }

        // identifier / keyword / builtin / call
        if (plIsAlpha(c)) {
            uint32_t s = i;
            while (i < src_len && plIsAlNum(src[i])) i++;
            uint32_t wlen = i - s;

            if (afterFun || afterClass) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_FUNCTION);
                afterFun = afterClass = false; continue;
            }

            if (plInTable(KT_CONSTANTS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_CONSTANT); continue;
            }
            if (plInTable(KT_KEYWORDS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_KEYWORD);
                if (plMatchWord(src, src_len, s, "fun",       3)) afterFun   = true;
                if (plMatchWord(src, src_len, s, "class",     5) ||
                    plMatchWord(src, src_len, s, "object",    6) ||
                    plMatchWord(src, src_len, s, "interface", 9) ||
                    plMatchWord(src, src_len, s, "typealias", 9)) afterClass = true;
                continue;
            }
            if (plInTable(KT_BUILTINS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_BUILTIN); continue;
            }
            // function call: ident followed by ( or { (kotlin trailing lambda)
            uint32_t j = i;
            while (j < src_len && (src[j] == ' ' || src[j] == '\t')) j++;
            if (j < src_len && (src[j] == '(' || src[j] == '{')) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_CALL);
            }
            continue;
        }

        i++;
    }
    return cnt;
}
