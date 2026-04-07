#define _POSIX_C_SOURCE 200809L

#include "parser.h"
#include "error.h"

#include <string.h>
#include <stdlib.h>
#include <stdio.h>

//  helpers 

static AstNode *allocNode(Parser *p, AstNodeType t, int line, int col) {
    AstNode *n = arenaAlloc(p->arena, sizeof(AstNode));
    if (!n) return NULL;
    memset(n, 0, sizeof(AstNode));
    n->type = t;
    n->line = line;
    n->col  = col;
    return n;
}

static char *makeError(Parser *p, int line, int col, const char *field, const char *msg) {
    SclErrorCtx ctx = {
        .line    = line,
        .col     = col,
        .field   = field,
        .message = msg,
        .src     = p->lexer.src,
        .tokLen  = (int)p->cur.textLen > 0 ? (int)p->cur.textLen : 1
    };
    return sclErrorFormat(&ctx);
}

static char *makeErrorTok(Parser *p, const char *msg) {
    return makeError(p, p->cur.line, p->cur.col, NULL, msg);
}

// advance: move peek - cur lex new peek
static bool advance(Parser *p, char **errOut) {
    p->cur = p->peek;
    if (p->hasPeek) {
        p->hasPeek = false;
    }
    // skip comments but save them as pending
    while (true) {
        Token t;
        if (!lexerNext(&p->lexer, &t)) {
            *errOut = p->lexer.error ? strdup(p->lexer.error) : strdup("lex error");
            return false;
        }
        if (t.type == TOK_COMMENT) {
            // save most recent comment before next real token
            AstNode *cn = allocNode(p, NODE_COMMENT, t.line, t.col);
            if (!cn) { *errOut = strdup("out of memory"); return false; }
            cn->as.comment.text = t.text;
            p->pendingComment = cn;
            continue;
        }
        p->peek     = t;
        p->hasPeek  = true;
        break;
    }
    return true;
}

// look at next real token without consuming
static Token peekTok(Parser *p) {
    return p->peek;
}

// consume peek if it matches type
static bool check(Parser *p, TokenType t) {
    return p->peek.type == t;
}

static bool eat(Parser *p, TokenType t, char **errOut) {
    if (!check(p, t)) return false;
    return advance(p, errOut);
}

// consume peek error if wrong type
static bool expect(Parser *p, TokenType t, const char *msg, char **errOut) {
    if (!check(p, t)) {
        Token pk = peekTok(p);
        char buf[256];
        snprintf(buf, sizeof(buf), "%s (got %s)", msg, tokenTypeName(pk.type));
        *errOut = makeError(p, pk.line, pk.col, NULL, buf);
        return false;
    }
    return advance(p, errOut);
}

static bool depthCheck(Parser *p, char **errOut) {
    if (p->maxDepth > 0 && p->depth >= p->maxDepth) {
        *errOut = makeErrorTok(p, "maximum nesting depth exceeded");
        return false;
    }
    return true;
}

//  forward declarations 
static AstNode *parseType(Parser *p, char **errOut);
static AstNode *parseValue(Parser *p, char **errOut);
static AstNode *parseAnnotation(Parser *p, char **errOut);

//  type parsing 

static AstNode *parsePrimitiveType(Parser *p, char **errOut) {
    Token t = peekTok(p);
    if (t.type != TOK_IDENT && t.type != TOK_NULL && t.type != TOK_BOOL) {
        *errOut = makeError(p, t.line, t.col, NULL, "expected type name");
        return NULL;
    }
    PrimType prim;
    bool found = true;
    const char *name_str = t.text ? t.text : "";
    if      (t.type == TOK_NULL)                       prim = PRIM_NULL;
    else if (strcmp(name_str, "string")   == 0)  prim = PRIM_STRING;
    else if (strcmp(name_str, "int")      == 0)  prim = PRIM_INT;
    else if (strcmp(name_str, "uint")     == 0)  prim = PRIM_UINT;
    else if (strcmp(name_str, "float")    == 0)  prim = PRIM_FLOAT;
    else if (strcmp(name_str, "bool")     == 0)  prim = PRIM_BOOL;
    else if (strcmp(name_str, "bytes")    == 0)  prim = PRIM_BYTES;
    else if (strcmp(name_str, "date")     == 0)  prim = PRIM_DATE;
    else if (strcmp(name_str, "datetime") == 0)  prim = PRIM_DATETIME;
    else if (strcmp(name_str, "duration") == 0)  prim = PRIM_DURATION;
    else found = false;

    if (!found) {
        // treat as enum reference
        AstNode *n = allocNode(p, NODE_TYPE_REF, t.line, t.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        if (!advance(p, errOut)) return NULL;
        n->as.typeRef.name = p->cur.text;
        return n;
    }

    AstNode *n = allocNode(p, NODE_TYPE_PRIMITIVE, t.line, t.col);
    if (!n) { *errOut = strdup("out of memory"); return NULL; }
    if (!advance(p, errOut)) return NULL;
    n->as.primitive.prim = prim;
    return n;
}

static AstNode *parseStructType(Parser *p, char **errOut) {
    // cur is TOK_STRUCT  already consumed by caller
    int line = p->cur.line, col = p->cur.col;

    bool open = false;
    if (check(p, TOK_OPEN)) {
        if (!advance(p, errOut)) return NULL;
        open = true;
    }

    if (!expect(p, TOK_LBRACE, "expected '{' after struct", errOut)) return NULL;

    p->depth++;
    if (!depthCheck(p, errOut)) { p->depth--; return NULL; }

    AstStructField *head = NULL, *tail = NULL;
    size_t count = 0;

    while (!check(p, TOK_RBRACE) && !check(p, TOK_EOF)) {
        // skip any pending comments inside struct type
        p->pendingComment = NULL;

        Token nameTok = peekTok(p);
        if (nameTok.type != TOK_IDENT) {
            *errOut = makeError(p, nameTok.line, nameTok.col, NULL,
                                "expected field name in struct type");
            p->depth--;
            return NULL;
        }
        if (!advance(p, errOut)) { p->depth--; return NULL; }
        const char *fieldName = p->cur.text;

        if (!expect(p, TOK_COLON, "expected ':' after field name", errOut)) {
            p->depth--;
            return NULL;
        }

        AstNode *fieldType = parseType(p, errOut);
        if (!fieldType) { p->depth--; return NULL; }

        AstStructField *sf = arenaAlloc(p->arena, sizeof(AstStructField));
        if (!sf) { *errOut = strdup("out of memory"); p->depth--; return NULL; }
        sf->name = fieldName;
        sf->type = fieldType;
        sf->next = NULL;

        if (!tail) { head = tail = sf; }
        else       { tail->next = sf; tail = sf; }
        count++;
    }

    p->depth--;
    if (!expect(p, TOK_RBRACE, "expected '}' to close struct type", errOut)) return NULL;

    AstNode *n = allocNode(p, NODE_TYPE_STRUCT, line, col);
    if (!n) { *errOut = strdup("out of memory"); return NULL; }
    n->as.strct.fields = head;
    n->as.strct.open   = open;
    (void)count;
    return n;
}

// parse a single base type no union no optional
static AstNode *parseBaseType(Parser *p, char **errOut) {
    Token t = peekTok(p);

    if (t.type == TOK_LBRACKET) {
        // T
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;
        p->depth++;
        if (!depthCheck(p, errOut)) { p->depth--; return NULL; }
        AstNode *elem = parseType(p, errOut);
        p->depth--;
        if (!elem) return NULL;
        if (!expect(p, TOK_RBRACKET, "expected ']' to close list type", errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_TYPE_LIST, line, col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.list.elem = elem;
        return n;
    }

    if (t.type == TOK_LBRACE) {
        // K: V
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;
        p->depth++;
        if (!depthCheck(p, errOut)) { p->depth--; return NULL; }
        AstNode *keyType = parseType(p, errOut);
        if (!keyType) { p->depth--; return NULL; }
        if (!expect(p, TOK_COLON, "expected ':' in map type", errOut)) { p->depth--; return NULL; }
        AstNode *valType = parseType(p, errOut);
        p->depth--;
        if (!valType) return NULL;
        if (!expect(p, TOK_RBRACE, "expected '}' to close map type", errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_TYPE_MAP, line, col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.map.key   = keyType;
        n->as.map.value = valType;
        return n;
    }

    if (t.type == TOK_STRUCT) {
        if (!advance(p, errOut)) return NULL;
        return parseStructType(p, errOut);
    }

    if (t.type == TOK_IDENT || t.type == TOK_NULL || t.type == TOK_BOOL) {
        return parsePrimitiveType(p, errOut);
    }

    char buf[128];
    snprintf(buf, sizeof(buf), "expected type, got %s", tokenTypeName(t.type));
    *errOut = makeError(p, t.line, t.col, NULL, buf);
    return NULL;
}

// parse type including union A  B and optional T
static AstNode *parseType(Parser *p, char **errOut) {
    AstNode *first = parseBaseType(p, errOut);
    if (!first) return NULL;

    // optional
    if (check(p, TOK_QUESTION)) {
        int line = p->cur.line, col = p->cur.col;
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_TYPE_OPTIONAL, line, col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.optional.inner = first;
        first = n;
    }

    // union: A  B  C
    if (!check(p, TOK_PIPE)) return first;

    // collect variants into a dynamic array on heap copy to arena at end
    size_t cap = 4, count = 1;
    AstNode **variants = malloc(cap * sizeof(AstNode *));
    if (!variants) { *errOut = strdup("out of memory"); return NULL; }
    variants[0] = first;

    int line = first->line, col = first->col;

    while (check(p, TOK_PIPE)) {
        if (!advance(p, errOut)) { free(variants); return NULL; }
        AstNode *next = parseBaseType(p, errOut);
        if (!next) { free(variants); return NULL; }

        // optional after union variant
        if (check(p, TOK_QUESTION)) {
            int vl = p->cur.line, vc = p->cur.col;
            if (!advance(p, errOut)) { free(variants); return NULL; }
            AstNode *opt = allocNode(p, NODE_TYPE_OPTIONAL, vl, vc);
            if (!opt) { *errOut = strdup("out of memory"); free(variants); return NULL; }
            opt->as.optional.inner = next;
            next = opt;
        }

        if (count >= cap) {
            cap *= 2;
            AstNode **tmp = realloc(variants, cap * sizeof(AstNode *));
            if (!tmp) { free(variants); *errOut = strdup("out of memory"); return NULL; }
            variants = tmp;
        }
        variants[count++] = next;
    }

    AstNode *n = allocNode(p, NODE_TYPE_UNION, line, col);
    if (!n) { free(variants); *errOut = strdup("out of memory"); return NULL; }

    AstNode **arenaVariants = arenaAlloc(p->arena, count * sizeof(AstNode *));
    if (!arenaVariants) { free(variants); *errOut = strdup("out of memory"); return NULL; }
    memcpy(arenaVariants, variants, count * sizeof(AstNode *));
    free(variants);

    n->as.unionType.variants = arenaVariants;
    n->as.unionType.count    = count;
    return n;
}

//  annotation parsing 

static AstNode *parseAnnotation(Parser *p, char **errOut) {
    Token t = peekTok(p);

    if (t.type == TOK_ANN_DEPRECATED) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_ANN_DEPRECATED, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        return n;
    }

    if (t.type == TOK_ANN_RANGE) {
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;
        if (!expect(p, TOK_LPAREN, "expected '(' after @range", errOut)) return NULL;

        // min: int or float
        Token minTok = peekTok(p);
        double minVal = 0;
        if (minTok.type == TOK_INT)        { minVal = (double)minTok.val.asInt;  if (!advance(p, errOut)) return NULL; }
        else if (minTok.type == TOK_UINT)  { minVal = (double)minTok.val.asUint; if (!advance(p, errOut)) return NULL; }
        else if (minTok.type == TOK_FLOAT) { minVal = minTok.val.asFloat;        if (!advance(p, errOut)) return NULL; }
        else {
            *errOut = makeError(p, minTok.line, minTok.col, NULL, "expected number for @range min");
            return NULL;
        }

        if (!expect(p, TOK_COMMA, "expected ',' in @range", errOut)) return NULL;

        Token maxTok = peekTok(p);
        double maxVal = 0;
        if (maxTok.type == TOK_INT)        { maxVal = (double)maxTok.val.asInt;  if (!advance(p, errOut)) return NULL; }
        else if (maxTok.type == TOK_UINT)  { maxVal = (double)maxTok.val.asUint; if (!advance(p, errOut)) return NULL; }
        else if (maxTok.type == TOK_FLOAT) { maxVal = maxTok.val.asFloat;        if (!advance(p, errOut)) return NULL; }
        else {
            *errOut = makeError(p, maxTok.line, maxTok.col, NULL, "expected number for @range max");
            return NULL;
        }

        if (!expect(p, TOK_RPAREN, "expected ')' after @range", errOut)) return NULL;

        AstNode *n = allocNode(p, NODE_ANN_RANGE, line, col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.range.min = minVal;
        n->as.range.max = maxVal;
        return n;
    }

    if (t.type == TOK_ANN_MINLEN || t.type == TOK_ANN_MAXLEN) {
        AstNodeType annType = (t.type == TOK_ANN_MINLEN) ? NODE_ANN_MINLEN : NODE_ANN_MAXLEN;
        const char *annName = (t.type == TOK_ANN_MINLEN) ? "@minlen" : "@maxlen";
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;
        if (!expect(p, TOK_LPAREN, "expected '(' after annotation", errOut)) return NULL;

        Token nTok = peekTok(p);
        size_t n_val = 0;
        if (nTok.type == TOK_INT && nTok.val.asInt >= 0) {
            n_val = (size_t)nTok.val.asInt;
            if (!advance(p, errOut)) return NULL;
        } else if (nTok.type == TOK_UINT) {
            n_val = (size_t)nTok.val.asUint;
            if (!advance(p, errOut)) return NULL;
        } else {
            char buf[128];
            snprintf(buf, sizeof(buf), "expected non-negative integer for %s", annName);
            *errOut = makeError(p, nTok.line, nTok.col, NULL, buf);
            return NULL;
        }

        if (!expect(p, TOK_RPAREN, "expected ')' after annotation", errOut)) return NULL;

        AstNode *node = allocNode(p, annType, line, col);
        if (!node) { *errOut = strdup("out of memory"); return NULL; }
        node->as.lenBound.n = n_val;
        return node;
    }

    if (t.type == TOK_ANN_PATTERN) {
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;
        if (!expect(p, TOK_LPAREN, "expected '(' after @pattern", errOut)) return NULL;

        Token strTok = peekTok(p);
        if (strTok.type != TOK_STRING) {
            *errOut = makeError(p, strTok.line, strTok.col, NULL,
                                "expected string literal for @pattern");
            return NULL;
        }
        if (!advance(p, errOut)) return NULL;
        const char *pat = p->cur.text;
        if (!expect(p, TOK_RPAREN, "expected ')' after @pattern", errOut)) return NULL;

        AstNode *n = allocNode(p, NODE_ANN_PATTERN, line, col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.pattern.pattern = pat;
        return n;
    }

    char buf[128];
    snprintf(buf, sizeof(buf), "unknown annotation: %s", tokenTypeName(t.type));
    *errOut = makeError(p, t.line, t.col, NULL, buf);
    return NULL;
}

static bool isAnnotationToken(TokenType t) {
    return t == TOK_ANN_RANGE || t == TOK_ANN_MINLEN || t == TOK_ANN_MAXLEN ||
           t == TOK_ANN_PATTERN || t == TOK_ANN_DEPRECATED;
}

//  value parsing 

static AstKV *parseKVPairs(Parser *p, char **errOut) {
    // parse key  value pairs until   used for map and struct values
    AstKV *head = NULL, *tail = NULL;

    while (!check(p, TOK_RBRACE) && !check(p, TOK_EOF)) {
        Token keyTok = peekTok(p);
        const char *key = NULL;

        if (keyTok.type == TOK_STRING) {
            if (!advance(p, errOut)) return NULL;
            key = p->cur.text;
        } else if (keyTok.type == TOK_IDENT) {
            if (!advance(p, errOut)) return NULL;
            key = p->cur.text;
        } else {
            *errOut = makeError(p, keyTok.line, keyTok.col, NULL,
                                "expected key (string or identifier)");
            return NULL;
        }

        if (!expect(p, TOK_EQ, "expected '=' after key", errOut)) return NULL;

        AstNode *val = parseValue(p, errOut);
        if (!val) return NULL;

        AstKV *kv = arenaAlloc(p->arena, sizeof(AstKV));
        if (!kv) { *errOut = strdup("out of memory"); return NULL; }
        kv->key   = key;
        kv->value = val;
        kv->next  = NULL;

        if (!tail) { head = tail = kv; }
        else       { tail->next = kv; tail = kv; }

        // trailing comma allowed
        eat(p, TOK_COMMA, errOut);
    }

    return head;
}

static AstNode *parseValue(Parser *p, char **errOut) {
    Token t = peekTok(p);

    // name or name   ...
    if (t.type == TOK_DOLLAR) {
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;

        Token nameTok = peekTok(p);
        if (nameTok.type != TOK_IDENT) {
            *errOut = makeError(p, nameTok.line, nameTok.col, NULL,
                                "expected identifier after '$'");
            return NULL;
        }
        if (!advance(p, errOut)) return NULL;
        const char *name = p->cur.text;

        // merge: name   ...
        if (check(p, TOK_AMP)) {
            if (!advance(p, errOut)) return NULL;
            if (!expect(p, TOK_LBRACE, "expected '{' after '&' in merge", errOut)) return NULL;
            p->depth++;
            if (!depthCheck(p, errOut)) { p->depth--; return NULL; }
            AstKV *overrides = parseKVPairs(p, errOut);
            p->depth--;
            if (!overrides && *errOut) return NULL;
            if (!expect(p, TOK_RBRACE, "expected '}' to close merge", errOut)) return NULL;

            AstNode *n = allocNode(p, NODE_VAL_MERGE, line, col);
            if (!n) { *errOut = strdup("out of memory"); return NULL; }
            n->as.merge.baseName  = name;
            n->as.merge.overrides = overrides;
            return n;
        }

        AstNode *n = allocNode(p, NODE_VAL_REF, line, col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.valRef.name = name;
        return n;
    }

    if (t.type == TOK_STRING || t.type == TOK_MULTILINE) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_STRING, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.strVal.str = p->cur.text;
        n->as.strVal.len = p->cur.textLen;
        return n;
    }

    if (t.type == TOK_INT) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_INT, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.intVal.v = p->cur.val.asInt;
        return n;
    }

    if (t.type == TOK_UINT) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_UINT, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.uintVal.v = p->cur.val.asUint;
        return n;
    }

    if (t.type == TOK_FLOAT) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_FLOAT, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.floatVal.v = p->cur.val.asFloat;
        return n;
    }

    if (t.type == TOK_BOOL) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_BOOL, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.boolVal.v = p->cur.val.asBool;
        return n;
    }

    if (t.type == TOK_NULL) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_NULL, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        return n;
    }

    if (t.type == TOK_BYTES) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_BYTES, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.strVal.str = p->cur.text;
        n->as.strVal.len = p->cur.textLen;
        return n;
    }

    if (t.type == TOK_DATE) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_DATE, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.strVal.str = p->cur.text;
        n->as.strVal.len = p->cur.textLen;
        return n;
    }

    if (t.type == TOK_DATETIME) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_DATETIME, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.strVal.str = p->cur.text;
        n->as.strVal.len = p->cur.textLen;
        return n;
    }

    if (t.type == TOK_DURATION) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_DURATION, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.strVal.str = p->cur.text;
        n->as.strVal.len = p->cur.textLen;
        return n;
    }

    // list value: v1 v2 ...
    if (t.type == TOK_LBRACKET) {
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;
        p->depth++;
        if (!depthCheck(p, errOut)) { p->depth--; return NULL; }

        size_t cap = 4, count = 0;
        AstNode **items = malloc(cap * sizeof(AstNode *));
        if (!items) { p->depth--; *errOut = strdup("out of memory"); return NULL; }

        while (!check(p, TOK_RBRACKET) && !check(p, TOK_EOF)) {
            AstNode *item = parseValue(p, errOut);
            if (!item) { free(items); p->depth--; return NULL; }
            if (count >= cap) {
                cap *= 2;
                AstNode **tmp = realloc(items, cap * sizeof(AstNode *));
                if (!tmp) { free(items); p->depth--; *errOut = strdup("out of memory"); return NULL; }
                items = tmp;
            }
            items[count++] = item;
            eat(p, TOK_COMMA, errOut);
        }
        p->depth--;
        if (!expect(p, TOK_RBRACKET, "expected ']' to close list value", errOut)) {
            free(items); return NULL;
        }

        AstNode *n = allocNode(p, NODE_VAL_LIST, line, col);
        if (!n) { free(items); *errOut = strdup("out of memory"); return NULL; }

        AstNode **arenaItems = arenaAlloc(p->arena, count * sizeof(AstNode *));
        if (!arenaItems) { free(items); *errOut = strdup("out of memory"); return NULL; }
        memcpy(arenaItems, items, count * sizeof(AstNode *));
        free(items);

        n->as.listVal.items = arenaItems;
        n->as.listVal.count = count;
        return n;
    }

    // structmap value:  key  value ...
    if (t.type == TOK_LBRACE) {
        if (!advance(p, errOut)) return NULL;
        int line = p->cur.line, col = p->cur.col;
        p->depth++;
        if (!depthCheck(p, errOut)) { p->depth--; return NULL; }

        AstKV *pairs = parseKVPairs(p, errOut);
        p->depth--;
        if (!pairs && *errOut) return NULL;

        if (!expect(p, TOK_RBRACE, "expected '}' to close struct/map value", errOut)) return NULL;

        /* we don't know at parse time if this is struct or map — use NODE_VAL_STRUCT
           (type checker will distinguish) */
        AstNode *n = allocNode(p, NODE_VAL_STRUCT, line, col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.kvVal.pairs = pairs;
        return n;
    }

    // identifier used as value  enum variant like INFO DEBUG
    if (t.type == TOK_IDENT) {
        if (!advance(p, errOut)) return NULL;
        AstNode *n = allocNode(p, NODE_VAL_REF, p->cur.line, p->cur.col);
        if (!n) { *errOut = strdup("out of memory"); return NULL; }
        n->as.valRef.name = p->cur.text;
        return n;
    }

    char buf[128];
    snprintf(buf, sizeof(buf), "expected value, got %s", tokenTypeName(t.type));
    *errOut = makeError(p, t.line, t.col, NULL, buf);
    return NULL;
}

//  top-level declarations 

static AstNode *parseField(Parser *p, char **errOut) {
    // cur is already at first token  caller ensures its an ident
    Token nameTok = peekTok(p);
    if (nameTok.type != TOK_IDENT) {
        *errOut = makeError(p, nameTok.line, nameTok.col, NULL, "expected field name");
        return NULL;
    }
    if (!advance(p, errOut)) return NULL;
    int line = p->cur.line, col = p->cur.col;
    const char *name = p->cur.text;

    if (!expect(p, TOK_COLON, "expected ':' after field name", errOut)) return NULL;

    AstNode *typeNode = parseType(p, errOut);
    if (!typeNode) return NULL;

    // annotations
    AstAnnotation *annHead = NULL, *annTail = NULL;
    while (isAnnotationToken(peekTok(p).type)) {
        AstNode *ann = parseAnnotation(p, errOut);
        if (!ann) return NULL;
        AstAnnotation *a = arenaAlloc(p->arena, sizeof(AstAnnotation));
        if (!a) { *errOut = strdup("out of memory"); return NULL; }
        a->node = ann;
        a->next = NULL;
        if (!annTail) { annHead = annTail = a; }
        else          { annTail->next = a; annTail = a; }
    }

    if (!expect(p, TOK_EQ, "expected '=' after type", errOut)) return NULL;

    AstNode *value = parseValue(p, errOut);
    if (!value) return NULL;

    AstNode *n = allocNode(p, NODE_FIELD, line, col);
    if (!n) { *errOut = strdup("out of memory"); return NULL; }
    n->as.field.name        = name;
    n->as.field.typeNode    = typeNode;
    n->as.field.annotations = annHead;
    n->as.field.value       = value;
    n->as.field.comment     = p->pendingComment;
    p->pendingComment       = NULL;
    return n;
}

static AstNode *parseEnumDirective(Parser *p, char **errOut) {
    // cur  enum
    int line = p->cur.line, col = p->cur.col;

    Token nameTok = peekTok(p);
    if (nameTok.type != TOK_IDENT) {
        *errOut = makeError(p, nameTok.line, nameTok.col, NULL,
                            "expected enum name after @enum");
        return NULL;
    }
    if (!advance(p, errOut)) return NULL;
    const char *enumName = p->cur.text;

    if (!expect(p, TOK_EQ, "expected '=' after enum name", errOut)) return NULL;

    AstEnumVariant *head = NULL, *tail = NULL;

    do {
        Token varTok = peekTok(p);
        if (varTok.type != TOK_IDENT) {
            *errOut = makeError(p, varTok.line, varTok.col, NULL,
                                "expected uppercase identifier for enum variant");
            return NULL;
        }
        if (!advance(p, errOut)) return NULL;

        AstEnumVariant *v = arenaAlloc(p->arena, sizeof(AstEnumVariant));
        if (!v) { *errOut = strdup("out of memory"); return NULL; }
        v->name = p->cur.text;
        v->next = NULL;

        if (!tail) { head = tail = v; }
        else       { tail->next = v; tail = v; }

    } while (check(p, TOK_PIPE) && advance(p, errOut));

    AstNode *n = allocNode(p, NODE_DIRECTIVE_ENUM, line, col);
    if (!n) { *errOut = strdup("out of memory"); return NULL; }
    n->as.enumDef.name     = enumName;
    n->as.enumDef.variants = head;
    return n;
}

static AstNode *parseConstDirective(Parser *p, char **errOut) {
    int line = p->cur.line, col = p->cur.col;

    Token nameTok = peekTok(p);
    if (nameTok.type != TOK_IDENT) {
        *errOut = makeError(p, nameTok.line, nameTok.col, NULL,
                            "expected const name after @const");
        return NULL;
    }
    if (!advance(p, errOut)) return NULL;
    const char *constName = p->cur.text;

    if (!expect(p, TOK_COLON, "expected ':' after const name", errOut)) return NULL;

    AstNode *typeNode = parseType(p, errOut);
    if (!typeNode) return NULL;

    if (!expect(p, TOK_EQ, "expected '=' after const type", errOut)) return NULL;

    AstNode *value = parseValue(p, errOut);
    if (!value) return NULL;

    AstNode *n = allocNode(p, NODE_DIRECTIVE_CONST, line, col);
    if (!n) { *errOut = strdup("out of memory"); return NULL; }
    n->as.constDef.name     = constName;
    n->as.constDef.typeNode = typeNode;
    n->as.constDef.value    = value;
    return n;
}

static AstNode *parseIncludeDirective(Parser *p, char **errOut) {
    int line = p->cur.line, col = p->cur.col;

    Token pathTok = peekTok(p);
    if (pathTok.type != TOK_STRING) {
        *errOut = makeError(p, pathTok.line, pathTok.col, NULL,
                            "expected string path after @include");
        return NULL;
    }
    if (!advance(p, errOut)) return NULL;
    const char *path = p->cur.text;
    const char *asName = NULL;

    if (check(p, TOK_AS)) {
        if (!advance(p, errOut)) return NULL;
        Token asTok = peekTok(p);
        if (asTok.type != TOK_IDENT) {
            *errOut = makeError(p, asTok.line, asTok.col, NULL,
                                "expected identifier after 'as'");
            return NULL;
        }
        if (!advance(p, errOut)) return NULL;
        asName = p->cur.text;
    }

    AstNode *n = allocNode(p, NODE_DIRECTIVE_INCLUDE, line, col);
    if (!n) { *errOut = strdup("out of memory"); return NULL; }
    n->as.include.path   = path;
    n->as.include.asName = asName;
    return n;
}

//  main entry 

ParseResult sclParse(const char *src, size_t srcLen, Arena *arena, int maxDepth) {
    ParseResult res;
    memset(&res, 0, sizeof(res));
    char *err = NULL;

    Parser p;
    memset(&p, 0, sizeof(p));
    p.arena    = arena;
    p.maxDepth = maxDepth;
    lexerInit(&p.lexer, src, srcLen, arena);

    /* prime the peek by doing an initial advance sequence:
       we need cur and peek both set. we call advance twice:
       first loads peek; we then shift to get cur = first real tok. */

    // load first real token into peek
    while (true) {
        Token t;
        if (!lexerNext(&p.lexer, &t)) {
            res.error = p.lexer.error ? strdup(p.lexer.error) : strdup("lex error");
            return res;
        }
        if (t.type == TOK_COMMENT) {
            AstNode *cn = allocNode(&p, NODE_COMMENT, t.line, t.col);
            if (cn) { cn->as.comment.text = t.text; p.pendingComment = cn; }
            continue;
        }
        p.peek    = t;
        p.hasPeek = true;
        break;
    }

    // require scl N as first token
    if (!check(&p, TOK_DIR_SCL)) {
        Token pk = peekTok(&p);
        SclErrorCtx ctx = {
            .line    = pk.line,
            .col     = pk.col,
            .message = "expected '@scl N' version directive as first line",
            .src     = src,
            .tokLen  = 1
        };
        res.error = sclErrorFormat(&ctx);
        return res;
    }
    if (!advance(&p, &err)) { res.error = err; return res; }

    int sclLine = p.cur.line, sclCol = p.cur.col;

    // next must be int version
    if (!check(&p, TOK_INT)) {
        Token pk = peekTok(&p);
        SclErrorCtx ctx = {
            .line    = pk.line,
            .col     = pk.col,
            .message = "expected version number after @scl",
            .src     = src,
            .tokLen  = 1
        };
        res.error = sclErrorFormat(&ctx);
        return res;
    }
    if (!advance(&p, &err)) { res.error = err; return res; }

    int version = (int)p.cur.val.asInt;
    if (version != 1) {
        char buf[64];
        snprintf(buf, sizeof(buf), "unsupported SCL version %d, only version 1 is supported", version);
        SclErrorCtx ctx = {
            .line    = p.cur.line,
            .col     = p.cur.col,
            .message = buf,
            .src     = src,
            .tokLen  = (int)p.cur.textLen
        };
        res.error = sclErrorFormat(&ctx);
        return res;
    }

    AstNode *sclDirective = allocNode(&p, NODE_DIRECTIVE_SCL, sclLine, sclCol);
    if (!sclDirective) { res.error = strdup("out of memory"); return res; }
    sclDirective->as.scl.version = version;

    // collect top-level declarations
    size_t cap = 16, count = 0;
    AstNode **decls = malloc(cap * sizeof(AstNode *));
    AstNode *doc = NULL;
    AstNode **arenaDecls = NULL;
    if (!decls) { res.error = strdup("out of memory"); return res; }
    decls[count++] = sclDirective;

    while (!check(&p, TOK_EOF)) {
        AstNode *decl = NULL;
        Token pk = peekTok(&p);

        if (pk.type == TOK_DIR_ENUM) {
            if (!advance(&p, &err)) goto fail;
            decl = parseEnumDirective(&p, &err);
        } else if (pk.type == TOK_DIR_CONST) {
            if (!advance(&p, &err)) goto fail;
            decl = parseConstDirective(&p, &err);
        } else if (pk.type == TOK_DIR_INCLUDE) {
            if (!advance(&p, &err)) goto fail;
            decl = parseIncludeDirective(&p, &err);
        } else if (pk.type == TOK_IDENT) {
            decl = parseField(&p, &err);
        } else {
            char buf[128];
            snprintf(buf, sizeof(buf), "unexpected token '%s' at top level",
                     tokenTypeName(pk.type));
            SclErrorCtx ctx = {
                .line    = pk.line,
                .col     = pk.col,
                .message = buf,
                .src     = src,
                .tokLen  = pk.textLen > 0 ? (int)pk.textLen : 1
            };
            err = sclErrorFormat(&ctx);
            goto fail;
        }

        if (!decl) goto fail;

        if (count >= cap) {
            cap *= 2;
            AstNode **tmp = realloc(decls, cap * sizeof(AstNode *));
            if (!tmp) { err = strdup("out of memory"); goto fail; }
            decls = tmp;
        }
        decls[count++] = decl;
    }

    doc = allocNode(&p, NODE_DOCUMENT, 1, 1);
    if (!doc) { err = strdup("out of memory"); goto fail; }

    arenaDecls = arenaAlloc(arena, count * sizeof(AstNode *));
    if (!arenaDecls) { err = strdup("out of memory"); goto fail; }
    memcpy(arenaDecls, decls, count * sizeof(AstNode *));
    free(decls);

    doc->as.document.decls = arenaDecls;
    doc->as.document.count = count;

    res.ok   = true;
    res.node = doc;
    return res;

fail:
    free(decls);
    res.error = err ? err : strdup("parse error");
    return res;
}
