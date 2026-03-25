#include "packlight.h"
#include <string.h>
#include <stdint.h>

static inline bool isAlpha(char c) {
    return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='_';
}
static inline bool isDigit(char c) { return c>='0'&&c<='9'; }
static inline bool isAlNum(char c) { return isAlpha(c)||isDigit(c); }
static inline bool isHex(char c) {
    return isDigit(c)||(c>='a'&&c<='f')||(c>='A'&&c<='F');
}

static inline void emit(Token* out, uint32_t cap, uint32_t* cnt,
                         uint32_t start, uint32_t len, uint8_t type) {
    if (*cnt < cap && len > 0) {
        out[*cnt] = {start, len, type};
        (*cnt)++;
    }
}

static inline bool matchWord(const char* src, uint32_t slen, uint32_t i,
                               const char* w, uint32_t wlen) {
    if (i + wlen > slen) return false;
    if (memcmp(src + i, w, wlen) != 0) return false;
    if (i + wlen < slen && isAlNum(src[i + wlen])) return false;
    return true;
}

static bool inTable(const char** table, const char* src, uint32_t pos, uint32_t len) {
    for (int k = 0; table[k]; k++) {
        uint32_t klen = (uint32_t)strlen(table[k]);
        if (klen == len && memcmp(src + pos, table[k], klen) == 0) return true;
    }
    return false;
}

// json 

static inline void skipWs(const char* src, uint32_t len, uint32_t* i) {
    while (*i < len) {
        char c = src[*i];
        if (c==' '||c=='\t'||c=='\n'||c=='\r') (*i)++; else break;
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

extern "C" PL_API uint32_t packlight_json(
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
            depth++; if(depth<=64) objMask|=(1ULL<<(depth-1));
            expectKey=true; i++; continue;
        }
        if (c == '}') {
            if(depth>0){if(depth<=64)objMask&=~(1ULL<<(depth-1));depth--;}
            expectKey=false; i++; continue;
        }
        if (c == '[') {
            depth++; if(depth<=64) objMask&=~(1ULL<<(depth-1));
            expectKey=false; i++; continue;
        }
        if (c == ']') {
            if(depth>0){if(depth<=64)objMask&=~(1ULL<<(depth-1));depth--;}
            i++; continue;
        }
        if (c == ',') {
            if(depth>0&&depth<=64&&(objMask>>(depth-1))&1) expectKey=true;
            i++; continue;
        }
        if (c == ':') { expectKey=false; i++; continue; }

        if (c == '"') {
            uint32_t s = i, e = skipJsonStr(src, src_len, i);
            emit(out, out_cap, &cnt, s, e-s, expectKey?(uint8_t)TK_JSON_KEY:(uint8_t)TK_STRING);
            expectKey=false; i=e; continue;
        }
        if (c=='-'||(c>='0'&&c<='9')) {
            uint32_t s = i;
            if (src[i]=='-') i++;
            while(i<src_len&&src[i]>='0'&&src[i]<='9') i++;
            if(i<src_len&&src[i]=='.'){i++;while(i<src_len&&src[i]>='0'&&src[i]<='9')i++;}
            if(i<src_len&&(src[i]=='e'||src[i]=='E')){i++;if(i<src_len&&(src[i]=='+'||src[i]=='-'))i++;while(i<src_len&&src[i]>='0'&&src[i]<='9')i++;}
            emit(out, out_cap, &cnt, s, i-s, (uint8_t)TK_NUMBER); continue;
        }
        if (matchWord(src,src_len,i,"true", 4)){emit(out,out_cap,&cnt,i,4,(uint8_t)TK_CONSTANT);i+=4;continue;}
        if (matchWord(src,src_len,i,"false",5)){emit(out,out_cap,&cnt,i,5,(uint8_t)TK_CONSTANT);i+=5;continue;}
        if (matchWord(src,src_len,i,"null", 4)){emit(out,out_cap,&cnt,i,4,(uint8_t)TK_CONSTANT);i+=4;continue;}
        i++;
    }
    return cnt;
}

// python 

static const char* PY_KEYWORDS[] = {
    "and","as","assert","async","await","break","class","continue",
    "def","del","elif","else","except","finally","for","from",
    "global","if","import","in","is","lambda","nonlocal","not",
    "or","pass","raise","return","try","while","with","yield", nullptr
};

static const char* PY_CONSTANTS[] = {
    "True","False","None","NotImplemented","Ellipsis", nullptr
};

static const char* PY_BUILTINS[] = {
    // types
    "int","str","float","bool","bytes","list","dict","set","tuple",
    "type","object","complex","bytearray","memoryview","frozenset",
    // common builtins
    "len","range","print","input","open","super","isinstance","issubclass",
    "hasattr","getattr","setattr","delattr","callable","iter","next",
    "enumerate","zip","map","filter","sorted","reversed","any","all",
    "min","max","sum","abs","round","pow","divmod","hash","id","repr",
    "format","vars","dir","staticmethod","classmethod","property",
    "Exception","ValueError","TypeError","KeyError","IndexError",
    "AttributeError","RuntimeError","StopIteration","NotImplementedError",
    nullptr
};

// skip python string body, i points after opening quotes
static uint32_t skipPyStr(const char* src, uint32_t len, uint32_t i,
                            char q, bool triple) {
    while (i < len) {
        if (src[i] == '\\') { i += 2; continue; }
        if (triple) {
            if (i+2 < len && src[i]==q && src[i+1]==q && src[i+2]==q) return i+3;
        } else {
            if (src[i] == q)    return i+1;
            if (src[i] == '\n') return i;   // unterminated
        }
        i++;
    }
    return len;
}

// check if char is a string prefix letter
static inline bool isStrPrefix(char c) {
    return c=='r'||c=='b'||c=='f'||c=='u'||c=='R'||c=='B'||c=='F'||c=='U';
}

extern "C" PL_API uint32_t packlight_python(
    const char* src, uint32_t src_len,
    Token* out, uint32_t out_cap
) {
    uint32_t cnt = 0, i = 0;
    bool afterDef = false;

    while (i < src_len && cnt < out_cap) {
        char c = src[i];

        // whitespace
        if (c==' '||c=='\t'||c=='\n'||c=='\r') { i++; continue; }

        // comment
        if (c == '#') {
            uint32_t s = i;
            while (i < src_len && src[i] != '\n') i++;
            emit(out, out_cap, &cnt, s, i-s, (uint8_t)TK_COMMENT);
            afterDef = false; continue;
        }

        // decorator @ident
        if (c == '@') {
            uint32_t s = i; i++;
            while (i < src_len && isAlNum(src[i])) i++;
            emit(out, out_cap, &cnt, s, i-s, (uint8_t)TK_DECORATOR);
            afterDef = false; continue;
        }

        // string with optional prefix: r/b/f/u + quote
        if (isStrPrefix(c)) {
            uint32_t pfx = i;
            if (i+1 < src_len && isStrPrefix(src[i+1]) &&
                i+2 < src_len && (src[i+2]=='\''||src[i+2]=='"')) {
                i += 2; // two-char prefix
            } else if (i+1 < src_len && (src[i+1]=='\''||src[i+1]=='"')) {
                i += 1; // one-char prefix
            } else {
                goto do_ident; // not a str prefix, treat as identifier
            }
            // fall through to quote handling
            c = src[i];
        }

        // quoted string (handles '' "" ''' """)
        if (c=='\''||c=='"') {
            uint32_t s = (i > 0 && isStrPrefix(src[i-1])) ?
                         // find actual prefix start
                         i-1 : i; // approximation; start tracked via pfx var
            // simpler: just use current i as token start if no prefix was consumed
            // we already moved i past prefix above, so token start = pfx (saved before goto)
            // to avoid complexity, just start token at last nonquote char before i
            // actually simplest: record s before any prefix logic
            uint32_t tokenStart = i;
            // walk back to find prefix start (at most 2)
            if (tokenStart >= 1 && isStrPrefix(src[tokenStart-1])) tokenStart--;
            if (tokenStart >= 1 && isStrPrefix(src[tokenStart-1])) tokenStart--;

            char q = src[i]; i++;
            bool triple = (i+1 < src_len && src[i]==q && src[i+1]==q);
            if (triple) i += 2;
            uint32_t end = skipPyStr(src, src_len, i, q, triple);
            emit(out, out_cap, &cnt, tokenStart, end-tokenStart, (uint8_t)TK_STRING);
            i = end; afterDef = false; continue;
        }

        // number
        if (isDigit(c)) {
            uint32_t s = i;
            if (src[i]=='0' && i+1<src_len && (src[i+1]=='x'||src[i+1]=='X')) {
                i+=2; while(i<src_len&&isHex(src[i]))i++;
            } else if (src[i]=='0' && i+1<src_len && (src[i+1]=='b'||src[i+1]=='B')) {
                i+=2; while(i<src_len&&(src[i]=='0'||src[i]=='1'))i++;
            } else if (src[i]=='0' && i+1<src_len && (src[i+1]=='o'||src[i+1]=='O')) {
                i+=2; while(i<src_len&&src[i]>='0'&&src[i]<='7')i++;
            } else {
                while(i<src_len&&isDigit(src[i]))i++;
                if(i<src_len&&src[i]=='.'){i++;while(i<src_len&&isDigit(src[i]))i++;}
                if(i<src_len&&(src[i]=='e'||src[i]=='E')){i++;if(i<src_len&&(src[i]=='+'||src[i]=='-'))i++;while(i<src_len&&isDigit(src[i]))i++;}
                if(i<src_len&&(src[i]=='j'||src[i]=='J'))i++;
            }
            emit(out, out_cap, &cnt, s, i-s, (uint8_t)TK_NUMBER);
            afterDef = false; continue;
        }

        // operators
        if (c=='+'||c=='-'||c=='*'||c=='/'||c=='%'||c=='='||c=='!'||
            c=='<'||c=='>'||c=='&'||c=='|'||c=='^'||c=='~') {
            uint32_t s = i; i++;
            if (i<src_len && (src[i]=='='||src[i]=='>'||src[i]==c)) i++;
            emit(out, out_cap, &cnt, s, i-s, (uint8_t)TK_OPERATOR);
            afterDef = false; continue;
        }

        // identifier / keyword / builtin
        if (isAlpha(c)) {
            do_ident:;
            uint32_t s = i;
            while (i < src_len && isAlNum(src[i])) i++;
            uint32_t wlen = i - s;

            if (afterDef) {
                emit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_FUNCTION);
                afterDef = false; continue;
            }

            if (inTable(PY_CONSTANTS, src, s, wlen)) {
                emit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_CONSTANT);
                continue;
            }
            if (inTable(PY_KEYWORDS, src, s, wlen)) {
                emit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_KEYWORD);
                if (matchWord(src, src_len, s, "def",  3) ||
                    matchWord(src, src_len, s, "class",5))
                    afterDef = true;
                continue;
            }
            if (inTable(PY_BUILTINS, src, s, wlen)) {
                emit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_BUILTIN);
                continue;
            }

            // function call: ident(
            uint32_t j = i;
            while (j < src_len && (src[j]==' '||src[j]=='\t')) j++;
            if (j < src_len && src[j] == '(') {
                emit(out, out_cap, &cnt, s, wlen, (uint8_t)TK_CALL);
                continue;
            }
            continue;
        }

        i++;
    }
    return cnt;
}
