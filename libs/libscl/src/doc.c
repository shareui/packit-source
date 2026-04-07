#define _POSIX_C_SOURCE 200809L
#include "doc.h"
#include "value.h"
#include "arena.h"
#include "ast.h"

#include <string.h>
#include <stdlib.h>
#include <stdio.h>

// forward declaration for recursion
static scl_value_t *valueFromAst(AstNode *node, AstNode *typeNode,
                                  Arena *arena, char **errOut);

static scl_value_t *valueFromKVList(AstKV *pairs, scl_type_t type,
                                     AstNode *elemTypeNode,
                                     Arena *arena, char **errOut) {
    scl_value_t *v = valueAlloc(arena, type);
    for (AstKV *kv = pairs; kv; kv = kv->next) {
        scl_value_t *child = valueFromAst(kv->value, elemTypeNode, arena, errOut);
        if (!child) return NULL;
        const char *key = arenaStrdup(arena, kv->key);
        valueKVSet(v, key, child, arena);
    }
    return v;
}

/*
 * resolve the innermost non-optional type node.
 * needed so struct/map fields inside optionals still get the right type.
 */
static AstNode *unwrapOptional(AstNode *t) {
    while (t && t->type == NODE_TYPE_OPTIONAL) t = t->as.optional.inner;
    return t;
}

static scl_value_t *valueFromAst(AstNode *node, AstNode *typeNode,
                                  Arena *arena, char **errOut) {
    switch (node->type) {
        case NODE_VAL_NULL:
            return valueAlloc(arena, SCL_TYPE_NULL);

        case NODE_VAL_BOOL: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_BOOL);
            v->as.b = node->as.boolVal.v;
            return v;
        }

        case NODE_VAL_INT: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_INT);
            v->as.i = node->as.intVal.v;
            return v;
        }

        case NODE_VAL_UINT: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_UINT);
            v->as.u = node->as.uintVal.v;
            return v;
        }

        case NODE_VAL_FLOAT: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_FLOAT);
            v->as.f = node->as.floatVal.v;
            return v;
        }

        case NODE_VAL_STRING: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_STRING);
            v->as.str.ptr = arenaStrndup(arena, node->as.strVal.str, node->as.strVal.len);
            v->as.str.len = node->as.strVal.len;
            return v;
        }

        case NODE_VAL_BYTES: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_BYTES);
            char *copy = arenaStrndup(arena, node->as.strVal.str, node->as.strVal.len);
            v->as.bytes.ptr = (const uint8_t *)copy;
            v->as.bytes.len = node->as.strVal.len;
            return v;
        }

        case NODE_VAL_DATE: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_DATE);
            v->as.str.ptr = arenaStrndup(arena, node->as.strVal.str, node->as.strVal.len);
            v->as.str.len = node->as.strVal.len;
            return v;
        }

        case NODE_VAL_DATETIME: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_DATETIME);
            v->as.str.ptr = arenaStrndup(arena, node->as.strVal.str, node->as.strVal.len);
            v->as.str.len = node->as.strVal.len;
            return v;
        }

        case NODE_VAL_DURATION: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_DURATION);
            v->as.str.ptr = arenaStrndup(arena, node->as.strVal.str, node->as.strVal.len);
            v->as.str.len = node->as.strVal.len;
            return v;
        }

        case NODE_VAL_LIST: {
            scl_value_t *v = valueAlloc(arena, SCL_TYPE_LIST);
            // pass list element type down so nested structsmaps resolve correctly
            AstNode *elemType = NULL;
            AstNode *inner = unwrapOptional(typeNode);
            if (inner && inner->type == NODE_TYPE_LIST) elemType = inner->as.list.elem;
            for (size_t i = 0; i < node->as.listVal.count; i++) {
                scl_value_t *item = valueFromAst(node->as.listVal.items[i],
                                                  elemType, arena, errOut);
                if (!item) return NULL;
                valueListPush(v, item, arena);
            }
            return v;
        }

        /*
         * parser always emits NODE_VAL_STRUCT for both struct and map literals.
         * use the fields typeNode to distinguish: NODE_TYPE_MAP → SCL_TYPE_MAP.
         */
        case NODE_VAL_STRUCT: {
            AstNode *inner = unwrapOptional(typeNode);
            if (inner && inner->type == NODE_TYPE_MAP) {
                // pass the map value type for nested resolution
                return valueFromKVList(node->as.kvVal.pairs, SCL_TYPE_MAP,
                                       inner->as.map.value, arena, errOut);
            }
            // struct: pass NULL typeNode for fields  structs carry their own schema
            return valueFromKVList(node->as.kvVal.pairs, SCL_TYPE_STRUCT,
                                   NULL, arena, errOut);
        }

        // NODE_VAL_MAP is never emitted by the parser but handle defensively
        case NODE_VAL_MAP:
            return valueFromKVList(node->as.kvVal.pairs, SCL_TYPE_MAP,
                                   NULL, arena, errOut);

        // ref and base  ... are resolved by the type checker before this runs
        case NODE_VAL_REF:
        case NODE_VAL_MERGE: {
            char buf[256];
            snprintf(buf, sizeof(buf),
                     "unresolved value node type %d at line %d — type checker must run first",
                     node->type, node->line);
            *errOut = strdup(buf);
            return NULL;
        }

        default: {
            char buf[256];
            snprintf(buf, sizeof(buf), "unexpected AST node type %d at line %d",
                     node->type, node->line);
            *errOut = strdup(buf);
            return NULL;
        }
    }
}

scl_doc_t *docFromAst(Arena *astArena, AstNode *astDoc,
                      const char *src, char **errOut) {
    (void)astArena;
    (void)src;

    scl_doc_t *doc = malloc(sizeof(scl_doc_t));
    if (!doc) {
        *errOut = strdup("out of memory");
        return NULL;
    }
    arenaInit(&doc->arena);
    doc->root = valueAlloc(&doc->arena, SCL_TYPE_STRUCT);

    for (size_t i = 0; i < astDoc->as.document.count; i++) {
        AstNode *decl = astDoc->as.document.decls[i];
        if (!decl || decl->type != NODE_FIELD) continue;

        scl_value_t *val = valueFromAst(decl->as.field.value,
                                         decl->as.field.typeNode,
                                         &doc->arena, errOut);
        if (!val) {
            arenaFree(&doc->arena);
            free(doc);
            return NULL;
        }

        const char *key = arenaStrdup(&doc->arena, decl->as.field.name);
        valueKVSet(doc->root, key, val, &doc->arena);
    }

    return doc;
}
