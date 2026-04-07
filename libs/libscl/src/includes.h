#ifndef SCL_INCLUDES_H
#define SCL_INCLUDES_H

#ifdef __cplusplus
extern "C" {
#endif

#include "ast.h"
#include "arena.h"

typedef struct {
    bool     ok;
    char    *error;         // heap-allocated caller must free if ok
    char   **warnings;      // heap-allocated array of heap-allocated strings
    size_t   warningCount;
} IncludeResult;

/*
 * resolve all @include directives in a parsed, type-checked document.
 * modifies doc in-place: merges declarations from included files.
 * path is used as the base directory for relative include paths.
 * maxDepth: max nesting depth passed through to sclParse, 0 = unlimited.
 * caller must free result.error and each result.warnings[i] + result.warnings.
 */
IncludeResult sclResolveIncludes(AstNode *doc, const char *basePath,
                                 Arena *arena, int maxDepth);

void includeResultFree(IncludeResult *r);

#ifdef __cplusplus
}
#endif

#endif
