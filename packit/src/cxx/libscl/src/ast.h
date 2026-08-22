#ifndef SCL_AST_H
#define SCL_AST_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

// forward declaration
typedef struct AstNode AstNode;

typedef enum {
    // type nodes
    NODE_TYPE_PRIMITIVE,
    NODE_TYPE_OPTIONAL,
    NODE_TYPE_LIST,
    NODE_TYPE_MAP,
    NODE_TYPE_STRUCT,
    NODE_TYPE_UNION,
    NODE_TYPE_REF,       // reference to enum by name

    // value nodes
    NODE_VAL_STRING,
    NODE_VAL_INT,
    NODE_VAL_UINT,
    NODE_VAL_FLOAT,
    NODE_VAL_BOOL,
    NODE_VAL_NULL,
    NODE_VAL_BYTES,
    NODE_VAL_DATE,
    NODE_VAL_DATETIME,
    NODE_VAL_DURATION,
    NODE_VAL_LIST,
    NODE_VAL_MAP,
    NODE_VAL_STRUCT,
    NODE_VAL_REF,        // name
    NODE_VAL_MERGE,      // base   ...

    // annotation nodes
    NODE_ANN_RANGE,
    NODE_ANN_MINLEN,
    NODE_ANN_MAXLEN,
    NODE_ANN_PATTERN,
    NODE_ANN_DEPRECATED,

    // declaration nodes
    NODE_FIELD,
    NODE_COMMENT,
    NODE_DIRECTIVE_SCL,
    NODE_DIRECTIVE_ENUM,
    NODE_DIRECTIVE_CONST,
    NODE_DIRECTIVE_INCLUDE,

    // document root
    NODE_DOCUMENT
} AstNodeType;

typedef enum {
    PRIM_STRING,
    PRIM_INT,
    PRIM_UINT,
    PRIM_FLOAT,
    PRIM_BOOL,
    PRIM_BYTES,
    PRIM_DATE,
    PRIM_DATETIME,
    PRIM_DURATION,
    PRIM_NULL
} PrimType;

// key-value pair for structmap value nodes
typedef struct AstKV {
    const char *key;
    AstNode    *value;
    struct AstKV *next;
} AstKV;

// struct field declaration inside NODE_TYPE_STRUCT
typedef struct AstStructField {
    const char          *name;
    AstNode             *type;    // type node
    struct AstStructField *next;
} AstStructField;

// enum variant list
typedef struct AstEnumVariant {
    const char            *name;
    struct AstEnumVariant *next;
} AstEnumVariant;

// annotation list node linked
typedef struct AstAnnotation {
    AstNode              *node;  // NODE_ANN_*
    struct AstAnnotation *next;
} AstAnnotation;

struct AstNode {
    AstNodeType type;
    int         line;
    int         col;

    union {
        // NODE_TYPE_PRIMITIVE
        struct { PrimType prim; } primitive;

        // NODE_TYPE_OPTIONAL
        struct { AstNode *inner; } optional;

        // NODE_TYPE_LIST
        struct { AstNode *elem; } list;

        // NODE_TYPE_MAP
        struct { AstNode *key; AstNode *value; } map;

        // NODE_TYPE_STRUCT
        struct {
            AstStructField *fields;
            bool            open;
        } strct;

        // NODE_TYPE_UNION
        struct {
            AstNode **variants;
            size_t    count;
        } unionType;

        // NODE_TYPE_REF
        struct { const char *name; } typeRef;

        /* NODE_VAL_STRING / NODE_VAL_BYTES / NODE_VAL_DATE /
           NODE_VAL_DATETIME / NODE_VAL_DURATION */
        struct { const char *str; size_t len; } strVal;

        // NODE_VAL_INT
        struct { int64_t v; } intVal;

        // NODE_VAL_UINT
        struct { uint64_t v; } uintVal;

        // NODE_VAL_FLOAT
        struct { double v; } floatVal;

        // NODE_VAL_BOOL
        struct { bool v; } boolVal;

        // NODE_VAL_LIST
        struct {
            AstNode **items;
            size_t    count;
        } listVal;

        // NODE_VAL_MAP  NODE_VAL_STRUCT
        struct { AstKV *pairs; } kvVal;

        // NODE_VAL_REF
        struct { const char *name; } valRef;

        // NODE_VAL_MERGE: base   ...
        struct {
            const char *baseName;
            AstKV      *overrides;
        } merge;

        // NODE_ANN_RANGE
        struct { double min; double max; } range;

        // NODE_ANN_MINLEN  NODE_ANN_MAXLEN
        struct { size_t n; } lenBound;

        // NODE_ANN_PATTERN
        struct { const char *pattern; } pattern;

        // NODE_FIELD
        struct {
            const char    *name;
            AstNode       *typeNode;
            AstAnnotation *annotations;
            AstNode       *value;
            AstNode       *comment;   // preceding comment nullable
        } field;

        // NODE_COMMENT
        struct { const char *text; } comment;

        // NODE_DIRECTIVE_SCL
        struct { int version; } scl;

        // NODE_DIRECTIVE_ENUM
        struct {
            const char      *name;
            AstEnumVariant  *variants;
        } enumDef;

        // NODE_DIRECTIVE_CONST
        struct {
            const char *name;
            AstNode    *typeNode;
            AstNode    *value;
        } constDef;

        // NODE_DIRECTIVE_INCLUDE
        struct {
            const char *path;
            const char *asName;   // nullable  no alias
        } include;

        // NODE_DOCUMENT
        struct {
            AstNode **decls;
            size_t    count;
        } document;
    } as;
};

#ifdef __cplusplus
}
#endif

#endif
