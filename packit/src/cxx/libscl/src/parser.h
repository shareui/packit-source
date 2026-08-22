#ifndef SCL_PARSER_H
#define SCL_PARSER_H

#ifdef __cplusplus
extern "C" {
#endif

#include "ast.h"
#include "lexer.h"
#include "arena.h"

typedef struct {
    Lexer  lexer;
    Token  cur;     // current token already consumed from lexer
    Token  peek;    // one token lookahead
    Arena *arena;
    bool   hasPeek;
    int    depth;   // current nesting depth
    int    maxDepth;  // 0  unlimited

    // pending comment to attach to next field
    AstNode *pendingComment;
} Parser;

typedef struct {
    bool     ok;
    AstNode *node;   // NODE_DOCUMENT on success
    char    *error;  // heap-allocated caller must free
} ParseResult;

/*
 * parse a full SCL document from null-terminated src.
 * maxDepth: max nesting depth, 0 = unlimited.
 * caller must free result.error if !result.ok.
 */
ParseResult sclParse(const char *src, size_t srcLen, Arena *arena, int maxDepth);

#ifdef __cplusplus
}
#endif

#endif
