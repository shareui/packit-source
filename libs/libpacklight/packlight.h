#pragma once
#include <stdint.h>

#define PL_API __attribute__((visibility("default")))

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TK_KEYWORD   = 1,   // keyword (if/for/def/...)     key_code_keyword
    TK_STRING    = 2,   // string literal               key_code_string
    TK_NUMBER    = 3,   // number literal               key_code_number
    TK_COMMENT   = 4,   // # comment                    key_code_comment
    TK_FUNCTION  = 5,   // def name / class name        key_code_function
    TK_CALL      = 6,   // function call name(          key_color_lightblue
    TK_BUILTIN   = 7,   // builtin type (int/str/...)   key_color_cyan
    TK_CONSTANT  = 8,   // True/False/None              key_code_constant
    TK_DECORATOR = 9,   // @decorator                   key_color_orange
    TK_OPERATOR  = 10,  // operator                     key_code_operator
    TK_JSON_KEY  = 11,  // json object key              key_code_keyword
} TokenType;

// byte offsets into utf-8 source
typedef struct {
    uint32_t start;   // byte offset
    uint32_t length;  // byte length
    uint8_t  type;    // TokenType
} Token;

// maps byte offset range [byte_start, byte_end) to char indices [char_start, char_end)
// returns 0 on success, -1 if any offset is out of range or misaligned
typedef struct {
    uint32_t byte_start;
    uint32_t byte_end;
    uint32_t char_start;
    uint32_t char_end;
} CharRange;

// tokenize full buffer
PL_API uint32_t packlight_json(
    const char* src, uint32_t src_len,
    Token* out_tokens, uint32_t out_cap
);

PL_API uint32_t packlight_python(
    const char* src, uint32_t src_len,
    Token* out_tokens, uint32_t out_cap
);

// convert a slice of tokens to char ranges in one pass over src
// src must be the full utf-8 source; tokens must be sorted by start offset
// writes out_cap entries into out_ranges, returns count written (== token_count on success)
PL_API uint32_t packlight_tokens_to_chars(
    const char* src, uint32_t src_len,
    const Token* tokens, uint32_t token_count,
    CharRange* out_ranges, uint32_t out_cap
);

#ifdef __cplusplus
}
#endif
