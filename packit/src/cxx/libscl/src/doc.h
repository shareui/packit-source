#ifndef SCL_DOC_H
#define SCL_DOC_H

#include "scl.h"
#include "value.h"
#include "arena.h"
#include "ast.h"

// concrete definition of opaque scl_doc_t
struct SclDoc {
    Arena        arena;
    scl_value_t *root;    // SCL_TYPE_STRUCT  top-level key-value scope
};

/*
 * build a SclDoc from a type-checked AST document node.
 * resolves all field values into SclValue tree allocated in doc->arena.
 * src is the original source text (used for error context, may be NULL).
 * returns NULL and sets *errOut (heap-allocated) on failure.
 */
scl_doc_t *docFromAst(Arena *astArena, AstNode *astDoc,
                      const char *src, char **errOut);

#endif
