#ifndef SCL_LEXER_H
#define SCL_LEXER_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include "arena.h"

typedef enum {
    // literals
    TOK_STRING,        // ...
    TOK_MULTILINE,     // ...
    TOK_INT,           // 42 -7
    TOK_UINT,          // 42u
    TOK_FLOAT,         // 3.14 -0.5
    TOK_BYTES,         // b64...
    TOK_DATE,          // 2024-01-15
    TOK_DATETIME,      // 2024-01-15T10:00:00Z
    TOK_DURATION,      // 3h30m 90s
    TOK_BOOL,          // true false
    TOK_NULL,          // null

    // identifiers and keywords
    TOK_IDENT,         // general identifier
    TOK_STRUCT,        // struct
    TOK_OPEN,          // open
    TOK_AS,            // as

    // directives
    TOK_DIR_SCL,       // scl
    TOK_DIR_ENUM,      // enum
    TOK_DIR_CONST,     // const
    TOK_DIR_INCLUDE,   // include

    // schema annotations
    TOK_ANN_RANGE,        // range
    TOK_ANN_MINLEN,       // minlen
    TOK_ANN_MAXLEN,       // maxlen
    TOK_ANN_PATTERN,      // pattern
    TOK_ANN_DEPRECATED,   // deprecated

    // operators
    TOK_COLON,     // :
    TOK_EQ,       
    TOK_PIPE,     
    TOK_AMP,      
    TOK_QUESTION, 
    TOK_DOT,       // .
    TOK_DOLLAR,   
    TOK_LBRACKET, 
    TOK_RBRACKET, 
    TOK_LBRACE,   
    TOK_RBRACE,   
    TOK_LPAREN,   
    TOK_RPAREN,   
    TOK_COMMA,    

    // meta
    TOK_COMMENT,   // text
    TOK_EOF
} TokenType;

typedef struct {
    TokenType   type;
    int         line;
    int         col;

    // interned text in arena for ident string comment etc.
    const char *text;
    size_t      textLen;

    // parsed scalar values
    union {
        int64_t  asInt;
        uint64_t asUint;
        double   asFloat;
        bool     asBool;
        // bytes: text holds base64 raw string decoded separately
        // datedatetimeduration: text holds raw string
    } val;
} Token;

typedef struct {
    const char *src;
    size_t      srcLen;
    size_t      pos;
    int         line;
    int         col;
    Arena      *arena;
    char       *error;   // set on lex error heap-allocated
} Lexer;

// initialize lexer over src not copied must outlive lexer
void lexerInit(Lexer *l, const char *src, size_t srcLen, Arena *arena);

/*
 * advance to next token.
 * returns false and sets l->error on lex error.
 * tok->type == TOK_EOF means end of input.
 */
bool lexerNext(Lexer *l, Token *tok);

const char *tokenTypeName(TokenType t);

#ifdef __cplusplus
}
#endif

#endif
