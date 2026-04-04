#include "pl_common.h"
// localuse library written entirely by @shareui

static const char* JAVA_KEYWORDS[] = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "var", "void", "volatile", "while", nullptr
};

static const char* JAVA_CONSTANTS[] = {
    "true", "false", "null", nullptr
};

static const char* JAVA_BUILTINS[] = {
    "String", "Integer", "Long", "Double", "Float", "Boolean", "Byte",
    "Short", "Character", "Object", "Number", "Math", "System", "Runtime",
    "StringBuilder", "StringBuffer", "Iterable", "Comparable", "Cloneable",
    "Runnable", "Thread", "Exception", "RuntimeException", "Error",
    "Throwable", "NullPointerException", "IllegalArgumentException",
    "IllegalStateException", "UnsupportedOperationException", "IndexOutOfBoundsException",
    "ClassCastException", "ArithmeticException", "ArrayIndexOutOfBoundsException",
    "Override", "Deprecated", "SuppressWarnings", "FunctionalInterface",
    "Iterable", "Comparable", "AutoCloseable",
    nullptr
};

static uint32_t skipJavaStr(const char* src, uint32_t len, uint32_t i) {
    i++; // skip opening "
    while (i < len) {
        if (src[i] == '\\') { i += 2; continue; }
        if (src[i] == '"') return i + 1;
        if (src[i] == '\n') return i; // unterminated
        i++;
    }
    return len;
}

static uint32_t skipTextBlock(const char* src, uint32_t len, uint32_t i) {
    // text blocks: """ ... """ (java 15+)
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
    i += 2;
    while (i + 1 < len) {
        if (src[i] == '*' && src[i+1] == '/') return i + 2;
        i++;
    }
    return len;
}

uint32_t pl_tokenize_java(
    const char* src, uint32_t src_len,
    Token* out, uint32_t out_cap
) {
    uint32_t cnt = 0, i = 0;
    bool afterNew = false;

    while (i < src_len && cnt < out_cap) {
        char c = src[i];

        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') { i++; continue; }

        // line comment
        if (c == '/' && i + 1 < src_len && src[i+1] == '/') {
            uint32_t s = i;
            i = skipLineComment(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_COMMENT);
            afterNew = false; continue;
        }

        // block comment (including javadoc)
        if (c == '/' && i + 1 < src_len && src[i+1] == '*') {
            uint32_t s = i;
            i = skipBlockComment(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_COMMENT);
            afterNew = false; continue;
        }

        // annotation
        if (c == '@') {
            uint32_t s = i; i++;
            while (i < src_len && plIsAlNum(src[i])) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_DECORATOR);
            afterNew = false; continue;
        }

        // text block """
        if (c == '"' && i + 2 < src_len && src[i+1] == '"' && src[i+2] == '"') {
            uint32_t s = i;
            i = skipTextBlock(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_STRING);
            afterNew = false; continue;
        }

        // string
        if (c == '"') {
            uint32_t s = i;
            i = skipJavaStr(src, src_len, i);
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_STRING);
            afterNew = false; continue;
        }

        // char literal
        if (c == '\'') {
            uint32_t s = i; i++;
            if (i < src_len && src[i] == '\\') i++;
            while (i < src_len && src[i] != '\'') i++;
            if (i < src_len) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_STRING);
            afterNew = false; continue;
        }

        // number
        if (plIsDigit(c) || (c == '.' && i + 1 < src_len && plIsDigit(src[i+1]))) {
            uint32_t s = i;
            if (src[i] == '0' && i + 1 < src_len && (src[i+1] == 'x' || src[i+1] == 'X')) {
                i += 2;
                while (i < src_len && (plIsHex(src[i]) || src[i] == '_')) i++;
                if (i < src_len && (src[i] == 'l' || src[i] == 'L')) i++;
            } else if (src[i] == '0' && i + 1 < src_len && (src[i+1] == 'b' || src[i+1] == 'B')) {
                i += 2;
                while (i < src_len && (src[i] == '0' || src[i] == '1' || src[i] == '_')) i++;
                if (i < src_len && (src[i] == 'l' || src[i] == 'L')) i++;
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
                if (i < src_len && (src[i] == 'f' || src[i] == 'F' || src[i] == 'd' || src[i] == 'D' || src[i] == 'l' || src[i] == 'L')) i++;
            }
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_NUMBER);
            afterNew = false; continue;
        }

        // operators
        if (c == '+' || c == '-' || c == '*' || c == '/' || c == '%' || c == '=' ||
            c == '!' || c == '<' || c == '>' || c == '&' || c == '|' || c == '^' ||
            c == '~' || c == '?') {
            uint32_t s = i; i++;
            if (i < src_len && (src[i] == '=' || src[i] == '>' || src[i] == c)) i++;
            plEmit(out, out_cap, &cnt, s, i - s, (uint8_t)TK_OPERATOR);
            afterNew = false; continue;
        }

        // identifier / keyword / builtin / call
        if (plIsAlpha(c)) {
            uint32_t s = i;
            while (i < src_len && plIsAlNum(src[i])) i++;
            uint32_t wlen = i - s;

            // class name after 'new'
            if (afterNew) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_FUNCTION);
                afterNew = false; continue;
            }

            if (plInTable(JAVA_CONSTANTS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_CONSTANT);
                continue;
            }
            if (plInTable(JAVA_KEYWORDS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_KEYWORD);
                if (plMatchWord(src, src_len, s, "class",     5) ||
                    plMatchWord(src, src_len, s, "interface", 9) ||
                    plMatchWord(src, src_len, s, "enum",      4) ||
                    plMatchWord(src, src_len, s, "record",    6))
                    afterNew = true; // class name follows
                if (plMatchWord(src, src_len, s, "new", 3))
                    afterNew = true;
                continue;
            }
            if (plInTable(JAVA_BUILTINS, src, s, wlen)) {
                plEmit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_BUILTIN); continue;
            }
            // function call
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
