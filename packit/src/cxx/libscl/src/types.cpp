#include "types.h"
#include "error.h"
#include "annotations.h"

#include <unordered_map>
#include <unordered_set>
#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <cstdio>

// scope holds resolved enums and consts by name
struct Scope {
    std::unordered_map<std::string, AstNode *> enums;    // name - NODE_DIRECTIVE_ENUM
    std::unordered_map<std::string, AstNode *> consts;   // name - NODE_DIRECTIVE_CONST
};

struct Checker {
    const char *src;
    Scope       scope;
    std::vector<std::string> warnings;
    // tracks const names currently being resolved  detects cycles
    std::unordered_set<std::string> resolving;
};

static char *makeErr(const char *src, int line, int col, const char *field, const char *msg) {
    SclErrorCtx ctx = {};
    ctx.line    = line;
    ctx.col     = col;
    ctx.field   = field;
    ctx.message = msg;
    ctx.src     = src;
    ctx.tokLen  = 1;
    return sclErrorFormat(&ctx);
}

static char *makeWarn(const char *src, int line, int col, const char *field, const char *msg) {
    SclErrorCtx ctx = {};
    ctx.line    = line;
    ctx.col     = col;
    ctx.field   = field;
    ctx.message = msg;
    ctx.src     = src;
    ctx.tokLen  = 1;
    return sclWarningFormat(&ctx);
}

//  primitive compatibility 

static bool primCompatible(PrimType declared, AstNodeType valType) {
    switch (declared) {
        case PRIM_STRING:   return valType == NODE_VAL_STRING;
        case PRIM_INT:      return valType == NODE_VAL_INT;
        case PRIM_UINT:     return valType == NODE_VAL_UINT;
        case PRIM_FLOAT:    return valType == NODE_VAL_FLOAT || valType == NODE_VAL_INT;
        case PRIM_BOOL:     return valType == NODE_VAL_BOOL;
        case PRIM_BYTES:    return valType == NODE_VAL_BYTES;
        case PRIM_DATE:     return valType == NODE_VAL_DATE;
        case PRIM_DATETIME: return valType == NODE_VAL_DATETIME;
        case PRIM_DURATION: return valType == NODE_VAL_DURATION;
        case PRIM_NULL:     return valType == NODE_VAL_NULL;
    }
    return false;
}

static const char *primName(PrimType p) {
    switch (p) {
        case PRIM_STRING:   return "string";
        case PRIM_INT:      return "int";
        case PRIM_UINT:     return "uint";
        case PRIM_FLOAT:    return "float";
        case PRIM_BOOL:     return "bool";
        case PRIM_BYTES:    return "bytes";
        case PRIM_DATE:     return "date";
        case PRIM_DATETIME: return "datetime";
        case PRIM_DURATION: return "duration";
        case PRIM_NULL:     return "null";
    }
    return "unknown";
}

//  forward declarations 
static char *checkValue(Checker &c, AstNode *typeNode, AstNode *val,
                        const char *fieldName, bool inUnion);

//  resolve name reference 
static AstNode *resolveConst(Checker &c, const std::string &name,
                              int line, int col, char **errOut) {
    auto it = c.scope.consts.find(name);
    if (it == c.scope.consts.end()) {
        char buf[256];
        snprintf(buf, sizeof(buf), "undefined reference '$%s'", name.c_str());
        *errOut = makeErr(c.src, line, col, nullptr, buf);
        return nullptr;
    }
    if (c.resolving.count(name)) {
        char buf[256];
        snprintf(buf, sizeof(buf), "circular reference detected for '$%s'", name.c_str());
        *errOut = makeErr(c.src, line, col, nullptr, buf);
        return nullptr;
    }
    return it->second;
}

//  check value against type 

static char *checkValueList(Checker &c, AstNode *elemType, AstNode *val,
                            const char *fieldName) {
    if (val->type != NODE_VAL_LIST) {
        return makeErr(c.src, val->line, val->col, fieldName, "expected list value");
    }
    for (size_t i = 0; i < val->as.listVal.count; i++) {
        char *err = checkValue(c, elemType, val->as.listVal.items[i], fieldName, false);
        if (err) return err;
    }
    return nullptr;
}

static char *checkValueMap(Checker &c, AstNode *keyType, AstNode *valType,
                           AstNode *val, const char *fieldName) {
    if (val->type != NODE_VAL_STRUCT) {
        return makeErr(c.src, val->line, val->col, fieldName, "expected map value {}");
    }
    for (AstKV *kv = val->as.kvVal.pairs; kv; kv = kv->next) {
        char *err = checkValue(c, keyType, nullptr, fieldName, false);
        (void)err;
        // key is always a string literal in SCL map syntax  validate key type
        if (keyType->type == NODE_TYPE_PRIMITIVE &&
            keyType->as.primitive.prim != PRIM_STRING) {
            return makeErr(c.src, val->line, val->col, fieldName,
                           "only string keys are supported in map literals");
        }
        char *verr = checkValue(c, valType, kv->value, fieldName, false);
        if (verr) return verr;
    }
    return nullptr;
}

static char *checkValueStruct(Checker &c, AstNode *typeNode, AstNode *val,
                              const char *fieldName) {
    if (val->type == NODE_VAL_REF || val->type == NODE_VAL_MERGE) {
        // const refs and merges are validated after resolution  skip here
        return nullptr;
    }
    if (val->type != NODE_VAL_STRUCT) {
        return makeErr(c.src, val->line, val->col, fieldName, "expected struct value {}");
    }

    bool open = typeNode->as.strct.open;

    // check all declared fields are present and typed correctly
    for (AstStructField *sf = typeNode->as.strct.fields; sf; sf = sf->next) {
        // find matching kv in value
        AstKV *found = nullptr;
        for (AstKV *kv = val->as.kvVal.pairs; kv; kv = kv->next) {
            if (strcmp(kv->key, sf->name) == 0) { found = kv; break; }
        }
        if (!found) {
            // missing field  only error if not optional
            if (sf->type->type != NODE_TYPE_OPTIONAL) {
                char buf[256];
                snprintf(buf, sizeof(buf), "missing required field '%s' in struct value", sf->name);
                return makeErr(c.src, val->line, val->col, fieldName, buf);
            }
            continue;
        }
        char *err = checkValue(c, sf->type, found->value, sf->name, false);
        if (err) return err;
    }

    // check for extra fields in closed struct
    if (!open) {
        for (AstKV *kv = val->as.kvVal.pairs; kv; kv = kv->next) {
            bool declaredField = false;
            for (AstStructField *sf = typeNode->as.strct.fields; sf; sf = sf->next) {
                if (strcmp(kv->key, sf->name) == 0) { declaredField = true; break; }
            }
            if (!declaredField) {
                char buf[256];
                snprintf(buf, sizeof(buf), "unknown field '%s' in closed struct", kv->key);
                return makeErr(c.src, val->line, val->col, fieldName, buf);
            }
        }
    }
    return nullptr;
}

static char *checkValue(Checker &c, AstNode *typeNode, AstNode *val,
                        const char *fieldName, bool inUnion) {
    if (!val) return nullptr;

    // ref or bare ident used as value
    if (val->type == NODE_VAL_REF) {
        // if expected type is an enum ref validate as enum variant directly
        if (typeNode && typeNode->type == NODE_TYPE_REF) {
            // fall through to NODE_TYPE_REF case below
        } else {
            // treat as const reference
            char *err = nullptr;
            AstNode *constDecl = resolveConst(c, val->as.valRef.name, val->line, val->col, &err);
            if (!constDecl) return err;
            return checkValue(c, typeNode, constDecl->as.constDef.value, fieldName, inUnion);
        }
    }

    // base   overrides   validate base exists then treat as struct
    if (val->type == NODE_VAL_MERGE) {
        char *err = nullptr;
        resolveConst(c, val->as.merge.baseName, val->line, val->col, &err);
        if (err) return err;
        // detailed merge type compat is complex  defer to runtime accept here
        return nullptr;
    }

    if (!typeNode) return nullptr;

    switch (typeNode->type) {
        case NODE_TYPE_PRIMITIVE: {
            PrimType prim = typeNode->as.primitive.prim;
            if (!primCompatible(prim, val->type)) {
                char buf[256];
                snprintf(buf, sizeof(buf), "expected %s value", primName(prim));
                return makeErr(c.src, val->line, val->col, fieldName, buf);
            }
            return nullptr;
        }
        case NODE_TYPE_OPTIONAL: {
            if (val->type == NODE_VAL_NULL) return nullptr;
            return checkValue(c, typeNode->as.optional.inner, val, fieldName, inUnion);
        }
        case NODE_TYPE_LIST: {
            return checkValueList(c, typeNode->as.list.elem, val, fieldName);
        }
        case NODE_TYPE_MAP: {
            return checkValueMap(c, typeNode->as.map.key, typeNode->as.map.value,
                                 val, fieldName);
        }
        case NODE_TYPE_STRUCT: {
            return checkValueStruct(c, typeNode, val, fieldName);
        }
        case NODE_TYPE_UNION: {
            // value must match at least one variant
            for (size_t i = 0; i < typeNode->as.unionType.count; i++) {
                char *err = checkValue(c, typeNode->as.unionType.variants[i],
                                       val, fieldName, true);
                if (!err) return nullptr;
                free(err);
            }
            return makeErr(c.src, val->line, val->col, fieldName,
                           "value does not match any variant of union type");
        }
        case NODE_TYPE_REF: {
            // enum reference  value must be an ident matching one of the variants
            const char *enumName = typeNode->as.typeRef.name;
            auto it = c.scope.enums.find(enumName);
            if (it == c.scope.enums.end()) {
                char buf[256];
                snprintf(buf, sizeof(buf), "undefined type '%s'", enumName);
                return makeErr(c.src, typeNode->line, typeNode->col, fieldName, buf);
            }
            if (val->type != NODE_VAL_REF) {
                char buf[256];
                snprintf(buf, sizeof(buf), "expected enum variant of %s", enumName);
                return makeErr(c.src, val->line, val->col, fieldName, buf);
            }
            AstNode *enumDecl = it->second;
            for (AstEnumVariant *v = enumDecl->as.enumDef.variants; v; v = v->next) {
                if (strcmp(v->name, val->as.valRef.name) == 0) return nullptr;
            }
            char buf[256];
            snprintf(buf, sizeof(buf), "'%s' is not a variant of enum %s",
                     val->as.valRef.name, enumName);
            return makeErr(c.src, val->line, val->col, fieldName, buf);
        }
        default:
            return nullptr;
    }
}

//  null check for non-optional fields 
static char *checkNullability(const char *src, AstNode *typeNode, AstNode *val,
                               const char *fieldName) {
    if (!val || val->type != NODE_VAL_NULL) return nullptr;
    // null is only allowed if type is optional or explicitly null
    if (typeNode->type == NODE_TYPE_OPTIONAL) return nullptr;
    if (typeNode->type == NODE_TYPE_PRIMITIVE &&
        typeNode->as.primitive.prim == PRIM_NULL) return nullptr;
    if (typeNode->type == NODE_TYPE_UNION) {
        for (size_t i = 0; i < typeNode->as.unionType.count; i++) {
            AstNode *v = typeNode->as.unionType.variants[i];
            if (v->type == NODE_TYPE_PRIMITIVE && v->as.primitive.prim == PRIM_NULL)
                return nullptr;
        }
    }
    return makeErr(src, val->line, val->col, fieldName,
                   "null assigned to non-optional field");
}

//  main type check pass 

TypeResult sclTypeCheck(AstNode *doc, const char *src, Arena * /*arena*/) {
    TypeResult result = {};
    Checker c;
    c.src = src;

    if (!doc || doc->type != NODE_DOCUMENT) {
        result.error = strdup("type check: expected document node");
        return result;
    }

    // pass 1: register all enums and consts
    for (size_t i = 0; i < doc->as.document.count; i++) {
        AstNode *decl = doc->as.document.decls[i];
        if (decl->type == NODE_DIRECTIVE_ENUM) {
            const std::string name = decl->as.enumDef.name;
            if (c.scope.enums.count(name)) {
                char buf[256];
                snprintf(buf, sizeof(buf), "duplicate enum definition '%s'", name.c_str());
                result.error = makeErr(src, decl->line, decl->col, nullptr, buf);
                return result;
            }
            c.scope.enums[name] = decl;
        } else if (decl->type == NODE_DIRECTIVE_CONST) {
            const std::string name = decl->as.constDef.name;
            if (c.scope.consts.count(name)) {
                char buf[256];
                snprintf(buf, sizeof(buf), "duplicate const definition '%s'", name.c_str());
                result.error = makeErr(src, decl->line, decl->col, nullptr, buf);
                return result;
            }
            c.scope.consts[name] = decl;
        }
    }

    // pass 2: type-check all fields
    for (size_t i = 0; i < doc->as.document.count; i++) {
        AstNode *decl = doc->as.document.decls[i];
        if (decl->type != NODE_FIELD) continue;

        const char *name = decl->as.field.name;
        AstNode *typeNode = decl->as.field.typeNode;
        AstNode *val      = decl->as.field.value;

        // deprecated warning
        for (AstAnnotation *ann = decl->as.field.annotations; ann; ann = ann->next) {
            if (ann->node->type == NODE_ANN_DEPRECATED) {
                char *w = makeWarn(src, decl->line, decl->col, name,
                                   "field is deprecated");
                c.warnings.push_back(w);
                free(w);
            }
        }

        // null check
        char *err = checkNullability(src, typeNode, val, name);
        if (err) { result.error = err; return result; }

        // type check
        err = checkValue(c, typeNode, val, name, false);
        if (err) { result.error = err; return result; }

        // annotation validation
        if (decl->as.field.annotations) {
            err = sclCheckAnnotations(decl->as.field.annotations, val, name, src);
            if (err) { result.error = err; return result; }
        }
    }

    // pass 3: type-check const values against their declared types
    for (auto &[name, constDecl] : c.scope.consts) {
        c.resolving.insert(name);
        char *err = checkValue(c, constDecl->as.constDef.typeNode,
                               constDecl->as.constDef.value, name.c_str(), false);
        c.resolving.erase(name);
        if (err) { result.error = err; return result; }
    }

    result.ok = true;

    if (!c.warnings.empty()) {
        result.warningCount = c.warnings.size();
        result.warnings = (char **)malloc(result.warningCount * sizeof(char *));
        for (size_t i = 0; i < result.warningCount; i++) {
            result.warnings[i] = strdup(c.warnings[i].c_str());
        }
    }

    return result;
}

void typeResultFree(TypeResult *r) {
    if (!r) return;
    free(r->error);
    for (size_t i = 0; i < r->warningCount; i++) free(r->warnings[i]);
    free(r->warnings);
    r->error        = nullptr;
    r->warnings     = nullptr;
    r->warningCount = 0;
}
