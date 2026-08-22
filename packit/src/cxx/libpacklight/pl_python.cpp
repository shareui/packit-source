#include "pl_common.h"
// localuse library written entirely by @shareui

static const char* PY_KEYWORDS[] = {
    "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from",
    "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
    "or", "pass", "raise", "return", "try", "while", "with", "yield", nullptr
};

static const char* PY_CONSTANTS[] = {
    "True", "False", "None", "NotImplemented", "Ellipsis", nullptr
};

static const char* PY_BUILTINS[] = {
    // types
    "int", "str", "float", "bool", "bytes", "list", "dict", "set", "tuple",
    "type", "object", "complex", "bytearray", "memoryview", "frozenset",
    // common builtins
    "len", "range", "print", "input", "open", "super", "isinstance", "issubclass",
    "hasattr", "getattr", "setattr", "delattr", "callable", "iter", "next",
    "enumerate", "zip", "map", "filter", "sorted", "reversed", "any", "all",
    "min", "max", "sum", "abs", "round", "pow", "divmod", "hash", "id", "repr",
    "format", "vars", "dir", "staticmethod", "classmethod", "property",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
    nullptr
};

static uint32_t skipPyStr(const char* src, uint32_t len, uint32_t i,
                          char q, bool triple) {
    while (i < len) {
        if (src[i] == '\\') { i += 2; continue; }
        if (triple) {
            if (i + 2 < len && src[i] == q && src[i+1] == q && src[i+2] == q)
                return i + 3;
        } else {
            if (src[i] == q)    return i + 1;
            if (src[i] == '\n') return i; // unterminated single-line string
        }
        i++;
    }
    return len;
}

static inline bool isStrPrefix(char c) {
    return c == 'r' || c == 'b' || c == 'f' || c == 'u' ||
           c == 'R' || c == 'B' || c == 'F' || c == 'U';
}

uint32_t pl_tokenize_python(
    const char* src, uint32_t src_len,
    Token* out, uint32_t out_cap
) {
    uint32_t cnt = 0, i = 0;
    bool afterDef = false;

    while (i < src_len && cnt < out_cap) {
        char c = src[i];

        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') { i++; continue; }

        // comment
        if (c == '#') {
            uint32_t s = i;
            while (i < src_len && src[i] != '\n') i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_COMMENT);
            afterDef = false; continue;
        }

        // decorator
        if (c == '@') {
            uint32_t s = i; i++;
            while (i < src_len && plIsAlNum(src[i])) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_DECORATOR);
            afterDef = false; continue;
        }

        // string with optional prefix (r/b/f/u)
        if (isStrPrefix(c)) {
            uint32_t pfx = i;
            if (i + 1 < src_len && isStrPrefix(src[i+1]) &&
                i + 2 < src_len && (src[i+2] == '\'' || src[i+2] == '"')) {
                i += 2;
            } else if (i + 1 < src_len && (src[i+1] == '\'' || src[i+1] == '"')) {
                i += 1;
            } else {
                goto do_ident;
            }
            c = src[i];
            // fall through to quote handling
            (void)pfx;
        }

        // quoted string
        if (c == '\'' || c == '"') {
            uint32_t tokenStart = i;
            if (tokenStart >= 1 && isStrPrefix(src[tokenStart - 1])) tokenStart--;
            if (tokenStart >= 1 && isStrPrefix(src[tokenStart - 1])) tokenStart--;

            char q = src[i]; i++;
            bool triple = (i + 1 < src_len && src[i] == q && src[i+1] == q);
            if (triple) i += 2;
            uint32_t end = skipPyStr(src, src_len, i, q, triple);
            plEmit(out, out_cap, &cnt, tokenStart, end - tokenStart, (uint8_t)TK_STRING);
            i = end; afterDef = false; continue;
        }

        // number
        if (plIsDigit(c)) {
            uint32_t s = i;
            if (src[i] == '0' && i + 1 < src_len && (src[i+1] == 'x' || src[i+1] == 'X')) {
                i += 2; while (i < src_len && plIsHex(src[i])) i++;
            } else if (src[i] == '0' && i + 1 < src_len && (src[i+1] == 'b' || src[i+1] == 'B')) {
                i += 2; while (i < src_len && (src[i] == '0' || src[i] == '1')) i++;
            } else if (src[i] == '0' && i + 1 < src_len && (src[i+1] == 'o' || src[i+1] == 'O')) {
                i += 2; while (i < src_len && src[i] >= '0' && src[i] <= '7') i++;
            } else {
                while (i < src_len && plIsDigit(src[i])) i++;
                if (i < src_len && src[i] == '.') { i++; while (i < src_len && plIsDigit(src[i])) i++; }
                if (i < src_len && (src[i] == 'e' || src[i] == 'E')) {
                    i++;
                    if (i < src_len && (src[i] == '+' || src[i] == '-')) i++;
                    while (i < src_len && plIsDigit(src[i])) i++;
                }
                if (i < src_len && (src[i] == 'j' || src[i] == 'J')) i++;
            }
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_NUMBER);
            afterDef = false; continue;
        }

        // operators
        if (c == '+' || c == '-' || c == '*' || c == '/' || c == '%' || c == '=' ||
            c == '!' || c == '<' || c == '>' || c == '&' || c == '|' || c == '^' || c == '~') {
            uint32_t s = i; i++;
            if (i < src_len && (src[i] == '=' || src[i] == '>' || src[i] == c)) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_OPERATOR);
            afterDef = false; continue;
        }

        // identifier / keyword / builtin / call
        if (plIsAlpha(c)) {
            do_ident:;
            uint32_t s = i;
            while (i < src_len && plIsAlNum(src[i])) i++;
            uint32_t wlen = i - s;

            if (afterDef) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_FUNCTION);
                afterDef = false; continue;
            }
            if (plInTable(PY_CONSTANTS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_CONSTANT); continue;
            }
            if (plInTable(PY_KEYWORDS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_KEYWORD);
                if (plMatchWord(src, src_len, s, "def",   3) ||
                    plMatchWord(src, src_len, s, "class", 5))
                    afterDef = true;
                continue;
            }
            if (plInTable(PY_BUILTINS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_BUILTIN); continue;
            }
            // function call: ident followed by (
            uint32_t j = i;
            while (j < src_len && (src[j] == ' ' || src[j] == '\t')) j++;
            if (j < src_len && src[j] == '(') {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_CALL);
            }
            continue;
        }

        i++;
    }
    return cnt;
}
