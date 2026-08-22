#include "lexer.h"
#include "error.h"

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>

void lexerInit(Lexer *l, const char *src, size_t srcLen, Arena *arena) {
    l->src    = src;
    l->srcLen = srcLen;
    l->pos    = 0;
    l->line   = 1;
    l->col    = 1;
    l->arena  = arena;
    l->error  = NULL;
}

static char peek(const Lexer *l) {
    if (l->pos >= l->srcLen) return '\0';
    return l->src[l->pos];
}

static char peekAt(const Lexer *l, size_t offset) {
    if (l->pos + offset >= l->srcLen) return '\0';
    return l->src[l->pos + offset];
}

static char advance(Lexer *l) {
    char c = l->src[l->pos++];
    if (c == '\n') {
        l->line++;
        l->col = 1;
    } else {
        l->col++;
    }
    return c;
}

static void setError(Lexer *l, int line, int col, const char *msg) {
    SclErrorCtx ctx = {
        .line    = line,
        .col     = col,
        .field   = NULL,
        .message = msg,
        .src     = l->src,
        .tokLen  = 1
    };
    free(l->error);
    l->error = sclErrorFormat(&ctx);
}

static void skipWhitespace(Lexer *l) {
    while (l->pos < l->srcLen) {
        char c = peek(l);
        if (c == ' ' || c == '\t' || c == '\r' || c == '\n') {
            advance(l);
        } else {
            break;
        }
    }
}

static bool isIdentStart(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}

static bool isIdentCont(char c) {
    return isIdentStart(c) || (c >= '0' && c <= '9') || c == '-';
}

static bool isDigit(char c) {
    return c >= '0' && c <= '9';
}

// decode a single uXXXXXX escape write UTF-8 into buf return byte count or -1 on error
static int decodeUnicodeEscape(Lexer *l, char *buf) {
    // expects pos at first char after u
    size_t start = l->pos;
    while (l->pos < l->srcLen && peek(l) != '}') {
        char c = peek(l);
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) {
            setError(l, l->line, l->col, "invalid character in unicode escape");
            return -1;
        }
        advance(l);
    }
    if (peek(l) != '}') {
        setError(l, l->line, l->col, "unterminated unicode escape, expected '}'");
        return -1;
    }

    size_t hexLen = l->pos - start;
    advance(l);  // consume

    if (hexLen == 0 || hexLen > 6) {
        setError(l, l->line, l->col, "unicode escape must be 1-6 hex digits");
        return -1;
    }

    char hexStr[7] = {0};
    memcpy(hexStr, l->src + start, hexLen);
    uint32_t cp = (uint32_t)strtoul(hexStr, NULL, 16);

    // encode as UTF-8
    if (cp <= 0x7F) {
        buf[0] = (char)cp;
        return 1;
    } else if (cp <= 0x7FF) {
        buf[0] = (char)(0xC0 | (cp >> 6));
        buf[1] = (char)(0x80 | (cp & 0x3F));
        return 2;
    } else if (cp <= 0xFFFF) {
        buf[0] = (char)(0xE0 | (cp >> 12));
        buf[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
        buf[2] = (char)(0x80 | (cp & 0x3F));
        return 3;
    } else if (cp <= 0x10FFFF) {
        buf[0] = (char)(0xF0 | (cp >> 18));
        buf[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
        buf[2] = (char)(0x80 | ((cp >> 6) & 0x3F));
        buf[3] = (char)(0x80 | (cp & 0x3F));
        return 4;
    }

    setError(l, l->line, l->col, "unicode codepoint out of range");
    return -1;
}

// parse a regular ... string process escapes intern into arena
static bool lexString(Lexer *l, Token *tok) {
    int startLine = l->line;
    int startCol  = l->col - 1;  // already consumed the

    // temp buffer on heap grow as needed
    size_t cap = 256;
    size_t len = 0;
    char *buf  = malloc(cap);
    if (!buf) {
        setError(l, startLine, startCol, "out of memory");
        return false;
    }

#define PUSH(c) do { \
    if (len + 1 >= cap) { cap *= 2; char *tmp = realloc(buf, cap); if (!tmp) { free(buf); setError(l, startLine, startCol, "out of memory"); return false; } buf = tmp; } \
    buf[len++] = (c); \
} while(0)

#define PUSH_UTF8(bytes, n) do { \
    for (int _i = 0; _i < (n); _i++) PUSH((bytes)[_i]); \
} while(0)

    while (l->pos < l->srcLen) {
        char c = advance(l);

        if (c == '"') {
            buf[len] = '\0';
            tok->type    = TOK_STRING;
            tok->text    = arenaStrndup(l->arena, buf, len);
            tok->textLen = len;
            free(buf);
            return true;
        }

        if (c == '\n') {
            setError(l, startLine, startCol, "unterminated string literal");
            free(buf);
            return false;
        }

        if (c == '\\') {
            char esc = advance(l);
            switch (esc) {
                case 'n':  PUSH('\n'); break;
                case 't':  PUSH('\t'); break;
                case 'r':  PUSH('\r'); break;
                case '\\': PUSH('\\'); break;
                case '"':  PUSH('"');  break;
                case 'u': {
                    if (peek(l) != '{') {
                        setError(l, l->line, l->col, "expected '{' after \\u");
                        free(buf);
                        return false;
                    }
                    advance(l);  // consume
                    char utf8[4];
                    int n = decodeUnicodeEscape(l, utf8);
                    if (n < 0) { free(buf); return false; }
                    PUSH_UTF8(utf8, n);
                    break;
                }
                default:
                    setError(l, l->line, l->col, "unknown escape sequence");
                    free(buf);
                    return false;
            }
        } else {
            PUSH(c);
        }
    }

    setError(l, startLine, startCol, "unterminated string literal");
    free(buf);
    return false;

#undef PUSH
#undef PUSH_UTF8
}

// compute dedent amount: leading spaces of first non-empty line
static int computeDedent(const char *s, size_t len) {
    size_t i = 0;
    while (i < len) {
        // skip empty lines
        size_t lineStart = i;
        while (i < len && s[i] != '\n') i++;
        size_t lineEnd = i;
        if (i < len) i++;  // skip n

        // check if line is non-empty not just whitespace
        size_t j = lineStart;
        while (j < lineEnd && (s[j] == ' ' || s[j] == '\t')) j++;
        if (j < lineEnd) {
            // first non-empty line: count leading spaces
            int spaces = 0;
            for (size_t k = lineStart; k < lineEnd && (s[k] == ' ' || s[k] == '\t'); k++) {
                spaces++;
            }
            return spaces;
        }
    }
    return 0;
}

// parse ... multiline string
static bool lexMultiline(Lexer *l, Token *tok) {
    int startLine = l->line;
    int startCol  = l->col - 3;

    size_t rawCap = 512;
    size_t rawLen = 0;
    char *raw     = malloc(rawCap);
    if (!raw) {
        setError(l, startLine, startCol, "out of memory");
        return false;
    }

#define RPUSH(c) do { \
    if (rawLen + 1 >= rawCap) { rawCap *= 2; char *tmp = realloc(raw, rawCap); if (!tmp) { free(raw); setError(l, startLine, startCol, "out of memory"); return false; } raw = tmp; } \
    raw[rawLen++] = (c); \
} while(0)

    while (l->pos + 2 < l->srcLen || l->pos < l->srcLen) {
        if (l->pos + 2 <= l->srcLen &&
            l->src[l->pos] == '"' && l->src[l->pos+1] == '"' && l->src[l->pos+2] == '"') {
            // found closing
            advance(l); advance(l); advance(l);
            break;
        }
        if (l->pos >= l->srcLen) {
            setError(l, startLine, startCol, "unterminated multiline string");
            free(raw);
            return false;
        }
        RPUSH(advance(l));
    }

    raw[rawLen] = '\0';

    // strip leading newline
    const char *content = raw;
    size_t contentLen   = rawLen;
    if (contentLen > 0 && content[0] == '\n') {
        content++;
        contentLen--;
    }

    // compute dedent
    int dedent = computeDedent(content, contentLen);

    // apply dedent: remove up to dedent leading spaces per line
    size_t outCap = contentLen + 1;
    char *out     = malloc(outCap);
    if (!out) {
        free(raw);
        setError(l, startLine, startCol, "out of memory");
        return false;
    }

    size_t outLen = 0;
    size_t i = 0;
    while (i <= contentLen) {
        // skip dedent spaces at line start
        int skipped = 0;
        while (skipped < dedent && i < contentLen &&
               (content[i] == ' ' || content[i] == '\t')) {
            i++;
            skipped++;
        }
        // copy until newline or end
        while (i < contentLen && content[i] != '\n') {
            out[outLen++] = content[i++];
        }
        if (i < contentLen) {
            out[outLen++] = '\n';
            i++;
        } else {
            break;
        }
    }
    out[outLen] = '\0';

    tok->type    = TOK_MULTILINE;
    tok->text    = arenaStrndup(l->arena, out, outLen);
    tok->textLen = outLen;

    free(raw);
    free(out);
    return true;

#undef RPUSH
}

/* lex a number: int, uint, or float.
   called when pos is at first digit (or after consumed '-') */
static bool lexNumber(Lexer *l, Token *tok, bool negative, int startLine, int startCol) {
    size_t numStart = l->pos;
    bool isFloat    = false;

    while (l->pos < l->srcLen && isDigit(peek(l))) advance(l);

    if (peek(l) == '.') {
        isFloat = true;
        advance(l);
        while (l->pos < l->srcLen && isDigit(peek(l))) advance(l);
    }

    // optional exponent
    if (peek(l) == 'e' || peek(l) == 'E') {
        isFloat = true;
        advance(l);
        if (peek(l) == '+' || peek(l) == '-') advance(l);
        while (l->pos < l->srcLen && isDigit(peek(l))) advance(l);
    }

    // uint suffix
    bool isUint = false;
    if (!isFloat && peek(l) == 'u') {
        isUint = true;
        advance(l);
    }

    size_t numLen = l->pos - numStart;
    char numBuf[64];
    if (numLen >= sizeof(numBuf)) {
        setError(l, startLine, startCol, "number literal too long");
        return false;
    }
    memcpy(numBuf, l->src + numStart, numLen);
    numBuf[numLen] = '\0';

    if (isFloat) {
        char *end;
        double v;
        if (negative) {
            char signed_buf[65];
            signed_buf[0] = '-';
            memcpy(signed_buf + 1, numBuf, numLen + 1);
            v = strtod(signed_buf, &end);
        } else {
            v = strtod(numBuf, &end);
        }
        tok->type      = TOK_FLOAT;
        tok->val.asFloat = v;
        tok->text      = arenaStrndup(l->arena, numBuf, numLen);
        tok->textLen   = numLen;
    } else if (isUint) {
        if (negative) {
            setError(l, startLine, startCol, "unsigned integer cannot be negative");
            return false;
        }
        char *end;
        uint64_t v       = strtoull(numBuf, &end, 10);
        tok->type        = TOK_UINT;
        tok->val.asUint  = v;
        tok->text        = arenaStrndup(l->arena, numBuf, numLen);
        tok->textLen     = numLen;
    } else {
        char *end;
        int64_t v;
        if (negative) {
            char signed_buf[65];
            signed_buf[0] = '-';
            memcpy(signed_buf + 1, numBuf, numLen + 1);
            v = strtoll(signed_buf, &end, 10);
        } else {
            v = strtoll(numBuf, &end, 10);
        }
        tok->type       = TOK_INT;
        tok->val.asInt  = v;
        tok->text       = arenaStrndup(l->arena, numBuf, numLen);
        tok->textLen    = numLen;
    }

    return true;
}

// check if current position starts a datedatetime: YYYY-MM-DDT...
static bool looksLikeDatetime(const Lexer *l, size_t start) {
    // need at least YYYY-MM-DD  10 chars
    if (start + 9 >= l->srcLen) return false;
    const char *s = l->src + start;
    return isDigit(s[0]) && isDigit(s[1]) && isDigit(s[2]) && isDigit(s[3]) &&
           s[4] == '-' &&
           isDigit(s[5]) && isDigit(s[6]) &&
           s[7] == '-' &&
           isDigit(s[8]) && isDigit(s[9]);
}

static bool lexDateOrDatetime(Lexer *l, Token *tok, size_t start, int startLine, int startCol) {
    // already consumed YYYY-MM-DD 10 chars from start
    // advance past the 10 chars we peeked
    for (int i = 0; i < 10; i++) advance(l);

    bool isDatetime = false;
    if (peek(l) == 'T') {
        isDatetime = true;
        advance(l);  // T
        // consume hh:mm:ss
        while (l->pos < l->srcLen && (isDigit(peek(l)) || peek(l) == ':')) advance(l);
        // timezone: Z or +HH:MM or -HH:MM
        if (peek(l) == 'Z') {
            advance(l);
        } else if (peek(l) == '+' || peek(l) == '-') {
            advance(l);
            while (l->pos < l->srcLen && (isDigit(peek(l)) || peek(l) == ':')) advance(l);
        }
    }

    size_t len = l->pos - start;
    tok->type    = isDatetime ? TOK_DATETIME : TOK_DATE;
    tok->text    = arenaStrndup(l->arena, l->src + start, len);
    tok->textLen = len;
    (void)startLine; (void)startCol;
    return true;
}

// parse duration: e.g. 3h30m 90s 1h 500ms
static bool lexDuration(Lexer *l, Token *tok, size_t start, int startLine, int startCol) {
    // consume units: digits followed by hmsms
    while (l->pos < l->srcLen) {
        if (!isDigit(peek(l))) break;
        while (l->pos < l->srcLen && isDigit(peek(l))) advance(l);

        // unit
        if (l->pos + 1 < l->srcLen && peek(l) == 'm' && peekAt(l, 1) == 's') {
            advance(l); advance(l);  // ms
        } else if (peek(l) == 'h' || peek(l) == 'm' || peek(l) == 's') {
            advance(l);
        } else {
            setError(l, l->line, l->col, "invalid duration unit, expected h/m/s/ms");
            return false;
        }
    }

    size_t len = l->pos - start;
    if (len == 0) {
        setError(l, startLine, startCol, "empty duration literal");
        return false;
    }
    tok->type    = TOK_DURATION;
    tok->text    = arenaStrndup(l->arena, l->src + start, len);
    tok->textLen = len;
    return true;
}

// lex b64... bytes literal called after b 6 4 are confirmed
static bool lexBytes(Lexer *l, Token *tok, int startLine, int startCol) {
    // consume b64
    advance(l); advance(l); advance(l);

    if (peek(l) != '"') {
        setError(l, l->line, l->col, "expected '\"' after b64");
        return false;
    }
    advance(l);  // opening

    size_t contentStart = l->pos;
    while (l->pos < l->srcLen && peek(l) != '"') {
        advance(l);
    }
    if (peek(l) != '"') {
        setError(l, startLine, startCol, "unterminated bytes literal");
        return false;
    }
    size_t contentLen = l->pos - contentStart;
    tok->text    = arenaStrndup(l->arena, l->src + contentStart, contentLen);
    tok->textLen = contentLen;
    tok->type    = TOK_BYTES;
    advance(l);  // closing
    return true;
}

static TokenType directiveType(const char *name) {
    if (strcmp(name, "@scl")        == 0) return TOK_DIR_SCL;
    if (strcmp(name, "@enum")       == 0) return TOK_DIR_ENUM;
    if (strcmp(name, "@const")      == 0) return TOK_DIR_CONST;
    if (strcmp(name, "@include")    == 0) return TOK_DIR_INCLUDE;
    if (strcmp(name, "@range")      == 0) return TOK_ANN_RANGE;
    if (strcmp(name, "@minlen")     == 0) return TOK_ANN_MINLEN;
    if (strcmp(name, "@maxlen")     == 0) return TOK_ANN_MAXLEN;
    if (strcmp(name, "@pattern")    == 0) return TOK_ANN_PATTERN;
    if (strcmp(name, "@deprecated") == 0) return TOK_ANN_DEPRECATED;
    return TOK_EOF;  // unknown
}

bool lexerNext(Lexer *l, Token *tok) {
    skipWhitespace(l);

    tok->line    = l->line;
    tok->col     = l->col;
    tok->text    = NULL;
    tok->textLen = 0;

    if (l->pos >= l->srcLen) {
        tok->type = TOK_EOF;
        return true;
    }

    char c = peek(l);

    // comment
    if (c == '/' && peekAt(l, 1) == '/') {
        advance(l); advance(l);  // consume
        size_t start = l->pos;
        while (l->pos < l->srcLen && peek(l) != '\n') advance(l);
        size_t len = l->pos - start;
        // trim leading space
        const char *text = l->src + start;
        while (len > 0 && (*text == ' ' || *text == '\t')) { text++; len--; }
        tok->type    = TOK_COMMENT;
        tok->text    = arenaStrndup(l->arena, text, len);
        tok->textLen = len;
        return true;
    }

    // directive: name
    if (c == '@') {
        size_t start = l->pos;
        advance(l); 
        while (l->pos < l->srcLen && isIdentCont(peek(l))) advance(l);
        size_t len = l->pos - start;
        char name[64];
        if (len >= sizeof(name)) {
            setError(l, tok->line, tok->col, "directive name too long");
            return false;
        }
        memcpy(name, l->src + start, len);
        name[len] = '\0';
        TokenType dt = directiveType(name);
        if (dt == TOK_EOF) {
            setError(l, tok->line, tok->col, "unknown directive");
            return false;
        }
        tok->type    = dt;
        tok->text    = arenaStrndup(l->arena, name, len);
        tok->textLen = len;
        return true;
    }

    // multiline string
    if (c == '"' && peekAt(l, 1) == '"' && peekAt(l, 2) == '"') {
        advance(l); advance(l); advance(l);
        return lexMultiline(l, tok);
    }

    // regular string
    if (c == '"') {
        advance(l);
        return lexString(l, tok);
    }

    // bytes literal b64...
    if (c == 'b' && peekAt(l, 1) == '6' && peekAt(l, 2) == '4' && peekAt(l, 3) == '"') {
        return lexBytes(l, tok, tok->line, tok->col);
    }

    // negative number
    if (c == '-' && isDigit(peekAt(l, 1))) {
        advance(l);  // consume -
        return lexNumber(l, tok, true, tok->line, tok->col);
    }

    // positive number or datedatetimeduration
    if (isDigit(c)) {
        size_t start = l->pos;
        int startLine = l->line;
        int startCol  = l->col;

        if (looksLikeDatetime(l, start)) {
            return lexDateOrDatetime(l, tok, start, startLine, startCol);
        }

        // peek ahead: if digits followed by hms its a duration
        size_t i = l->pos;
        while (i < l->srcLen && isDigit(l->src[i])) i++;
        bool isDuration = false;
        if (i < l->srcLen) {
            char u = l->src[i];
            if (u == 'h' || u == 'm' || u == 's') isDuration = true;
            if (u == 'm' && i + 1 < l->srcLen && l->src[i+1] == 's') isDuration = true;
        }
        if (isDuration) return lexDuration(l, tok, start, startLine, startCol);

        return lexNumber(l, tok, false, startLine, startCol);
    }

    // identifier  keyword
    if (isIdentStart(c)) {
        size_t start = l->pos;
        while (l->pos < l->srcLen && isIdentCont(peek(l))) advance(l);
        size_t len = l->pos - start;
        const char *text = arenaStrndup(l->arena, l->src + start, len);

        if (len == 4 && memcmp(l->src + start, "true", 4) == 0) {
            tok->type       = TOK_BOOL;
            tok->val.asBool = true;
            tok->text       = text;
            tok->textLen    = len;
        } else if (len == 5 && memcmp(l->src + start, "false", 5) == 0) {
            tok->type       = TOK_BOOL;
            tok->val.asBool = false;
            tok->text       = text;
            tok->textLen    = len;
        } else if (len == 4 && memcmp(l->src + start, "null", 4) == 0) {
            tok->type    = TOK_NULL;
            tok->text    = text;
            tok->textLen = len;
        } else if (len == 6 && memcmp(l->src + start, "struct", 6) == 0) {
            tok->type    = TOK_STRUCT;
            tok->text    = text;
            tok->textLen = len;
        } else if (len == 4 && memcmp(l->src + start, "open", 4) == 0) {
            tok->type    = TOK_OPEN;
            tok->text    = text;
            tok->textLen = len;
        } else if (len == 2 && memcmp(l->src + start, "as", 2) == 0) {
            tok->type    = TOK_AS;
            tok->text    = text;
            tok->textLen = len;
        } else {
            tok->type    = TOK_IDENT;
            tok->text    = text;
            tok->textLen = len;
        }
        return true;
    }

    // single-char operators
    advance(l);
    switch (c) {
        case ':': tok->type = TOK_COLON;    return true;
        case '=': tok->type = TOK_EQ;       return true;
        case '|': tok->type = TOK_PIPE;     return true;
        case '&': tok->type = TOK_AMP;      return true;
        case '?': tok->type = TOK_QUESTION; return true;
        case '.': tok->type = TOK_DOT;      return true;
        case '$': tok->type = TOK_DOLLAR;   return true;
        case '[': tok->type = TOK_LBRACKET; return true;
        case ']': tok->type = TOK_RBRACKET; return true;
        case '{': tok->type = TOK_LBRACE;   return true;
        case '}': tok->type = TOK_RBRACE;   return true;
        case '(': tok->type = TOK_LPAREN;   return true;
        case ')': tok->type = TOK_RPAREN;   return true;
        case ',': tok->type = TOK_COMMA;    return true;
        default:
            setError(l, tok->line, tok->col, "unexpected character");
            return false;
    }
}

const char *tokenTypeName(TokenType t) {
    switch (t) {
        case TOK_STRING:       return "string";
        case TOK_MULTILINE:    return "multiline string";
        case TOK_INT:          return "int";
        case TOK_UINT:         return "uint";
        case TOK_FLOAT:        return "float";
        case TOK_BYTES:        return "bytes";
        case TOK_DATE:         return "date";
        case TOK_DATETIME:     return "datetime";
        case TOK_DURATION:     return "duration";
        case TOK_BOOL:         return "bool";
        case TOK_NULL:         return "null";
        case TOK_IDENT:        return "identifier";
        case TOK_STRUCT:       return "struct";
        case TOK_OPEN:         return "open";
        case TOK_AS:           return "as";
        case TOK_DIR_SCL:      return "@scl";
        case TOK_DIR_ENUM:     return "@enum";
        case TOK_DIR_CONST:    return "@const";
        case TOK_DIR_INCLUDE:  return "@include";
        case TOK_ANN_RANGE:    return "@range";
        case TOK_ANN_MINLEN:   return "@minlen";
        case TOK_ANN_MAXLEN:   return "@maxlen";
        case TOK_ANN_PATTERN:  return "@pattern";
        case TOK_ANN_DEPRECATED: return "@deprecated";
        case TOK_COLON:        return ":";
        case TOK_EQ:           return "=";
        case TOK_PIPE:         return "|";
        case TOK_AMP:          return "&";
        case TOK_QUESTION:     return "?";
        case TOK_DOT:          return ".";
        case TOK_DOLLAR:       return "$";
        case TOK_LBRACKET:     return "[";
        case TOK_RBRACKET:     return "]";
        case TOK_LBRACE:       return "{";
        case TOK_RBRACE:       return "}";
        case TOK_LPAREN:       return "(";
        case TOK_RPAREN:       return ")";
        case TOK_COMMA:        return ",";
        case TOK_COMMENT:      return "comment";
        case TOK_EOF:          return "EOF";
        default:               return "unknown";
    }
}
