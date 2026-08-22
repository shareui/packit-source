#ifndef SCL_TYPES_H
#define SCL_TYPES_H

#ifdef __cplusplus
extern "C" {
#endif

#include "ast.h"
#include "arena.h"

typedef struct {
    bool  ok;
    char *error;    // heap-allocated caller must free if ok
    char **warnings;  // heap-allocated array of heap-allocated strings
    size_t warningCount;
} TypeResult;

/*
 * run type-checking pass on a parsed document.
 * resolves @enum and @const, validates field types, checks merge compatibility.
 * arena is used for any extra nodes needed (none currently).
 * caller must free result.error and each result.warnings[i] + result.warnings.
 */
TypeResult sclTypeCheck(AstNode *doc, const char *src, Arena *arena);

void typeResultFree(TypeResult *r);

#ifdef __cplusplus
}
#endif

#endif
