#define _POSIX_C_SOURCE 200809L
#include "scl.h"
#include "arena.h"
#include "parser.h"
#include "types.h"
#include "includes.h"
#include "doc.h"
#include "value.h"
#include "serialize.h"

#include <string.h>
#include <stdlib.h>
#include <stdio.h>

static scl_result_t makeErr(char *err) {
    scl_result_t r;
    r.ok            = false;
    r.doc           = NULL;
    r.error         = err;
    r.warnings      = NULL;
    r.warning_count = 0;
    return r;
}

static scl_result_t makeOk(scl_doc_t *doc, char **warnings, size_t wcount) {
    scl_result_t r;
    r.ok            = true;
    r.doc           = doc;
    r.error         = NULL;
    r.warnings      = warnings;
    r.warning_count = wcount;
    return r;
}

static char *readFile(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long size = ftell(f);
    if (size < 0) { fclose(f); return NULL; }
    rewind(f);
    char *buf = malloc((size_t)size + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t n = fread(buf, 1, (size_t)size, f);
    fclose(f);
    buf[n] = '\0';
    return buf;
}

// extract directory from path
static char *dirOf(const char *path) {
    const char *last = NULL;
    for (const char *p = path; *p; p++) {
        if (*p == '/' || *p == '\\') last = p;
    }
    if (!last) return strdup(".");
    size_t len = (size_t)(last - path);
    char *dir = malloc(len + 1);
    memcpy(dir, path, len);
    dir[len] = '\0';
    return dir;
}

// merge two warning arrays into one heap-allocated array
static char **mergeWarnings(char **a, size_t na, char **b, size_t nb, size_t *outCount) {
    size_t total = na + nb;
    *outCount = total;
    if (total == 0) return NULL;
    char **out = malloc(total * sizeof(char *));
    if (!out) {
        // free both on OOM and return NULL
        for (size_t i = 0; i < na; i++) free(a[i]);
        for (size_t i = 0; i < nb; i++) free(b[i]);
        free(a); free(b);
        *outCount = 0;
        return NULL;
    }
    for (size_t i = 0; i < na; i++) out[i]      = a[i];
    for (size_t i = 0; i < nb; i++) out[na + i] = b[i];
    free(a);
    free(b);
    return out;
}

static scl_result_t parseImpl(const char *src, const char *filePath,
                               scl_parse_opts_t opts) {
    size_t srcLen = strlen(src);
    Arena arena;
    arenaInit(&arena);

    ParseResult pr = sclParse(src, srcLen, &arena, opts.max_depth);
    if (!pr.ok) {
        arenaFree(&arena);
        return makeErr(pr.error);
    }

    TypeResult tr = sclTypeCheck(pr.node, src, &arena);
    if (!tr.ok) {
        for (size_t i = 0; i < tr.warningCount; i++) free(tr.warnings[i]);
        free(tr.warnings);
        arenaFree(&arena);
        return makeErr(tr.error);
    }

    // resolve include directives
    const char *baseDir  = ".";
    char *allocatedDir   = NULL;
    if (filePath) {
        allocatedDir = dirOf(filePath);
        baseDir      = allocatedDir;
    }

    IncludeResult ir = sclResolveIncludes(pr.node, baseDir, &arena, opts.max_depth);
    free(allocatedDir);
    if (!ir.ok) {
        for (size_t i = 0; i < tr.warningCount; i++) free(tr.warnings[i]);
        free(tr.warnings);
        for (size_t i = 0; i < ir.warningCount; i++) free(ir.warnings[i]);
        free(ir.warnings);
        arenaFree(&arena);
        return makeErr(ir.error);
    }

    // merge warnings from both passes
    size_t wcount = 0;
    char **warnings = mergeWarnings(tr.warnings, tr.warningCount,
                                    ir.warnings, ir.warningCount, &wcount);

    char *err = NULL;
    scl_doc_t *doc = docFromAst(&arena, pr.node, src, &err);
    arenaFree(&arena);

    if (!doc) {
        for (size_t i = 0; i < wcount; i++) free(warnings[i]);
        free(warnings);
        return makeErr(err);
    }
    return makeOk(doc, warnings, wcount);
}

// version

void scl_version(int *major, int *minor) {
    if (major) *major = SCL_VERSION_MAJOR;
    if (minor) *minor = SCL_VERSION_MINOR;
}

// parsing

scl_result_t scl_parse_str(const char *src) {
    scl_parse_opts_t opts;
    memset(&opts, 0, sizeof(opts));
    return parseImpl(src, NULL, opts);
}

scl_result_t scl_parse_file(const char *path) {
    scl_parse_opts_t opts;
    memset(&opts, 0, sizeof(opts));
    return scl_parse_file_opts(path, opts);
}

scl_result_t scl_parse_str_opts(const char *src, scl_parse_opts_t opts) {
    return parseImpl(src, NULL, opts);
}

scl_result_t scl_parse_file_opts(const char *path, scl_parse_opts_t opts) {
    char *src = readFile(path);
    if (!src) {
        char buf[512];
        snprintf(buf, sizeof(buf), "cannot open file \"%s\"", path);
        return makeErr(strdup(buf));
    }
    scl_result_t r = parseImpl(src, path, opts);
    free(src);
    return r;
}

void scl_result_free_warnings(scl_result_t *r) {
    if (!r) return;
    for (size_t i = 0; i < r->warning_count; i++) free(r->warnings[i]);
    free(r->warnings);
    r->warnings      = NULL;
    r->warning_count = 0;
}

// document access

scl_value_t *scl_get(scl_doc_t *doc, const char *key) {
    if (!doc || !key) return NULL;
    return valueKVGet(doc->root, key);
}

scl_value_t *scl_get_path(scl_doc_t *doc, const char *path) {
    if (!doc || !path) return NULL;

    size_t len = strlen(path);
    char *buf = malloc(len + 1);
    if (!buf) return NULL;
    memcpy(buf, path, len + 1);

    scl_value_t *cur = doc->root;
    char *seg = buf;
    while (seg && *seg) {
        char *dot = strchr(seg, '.');
        if (dot) *dot = '\0';

        if (cur->type != SCL_TYPE_STRUCT && cur->type != SCL_TYPE_MAP) {
            free(buf);
            return NULL;
        }
        cur = valueKVGet(cur, seg);
        if (!cur) {
            free(buf);
            return NULL;
        }

        seg = dot ? dot + 1 : NULL;
    }
    free(buf);
    return cur;
}

void scl_each_key(scl_doc_t *doc,
                  bool (*cb)(const char *key, scl_value_t *val, void *userdata),
                  void *userdata) {
    if (!doc || !cb) return;
    for (SclKV *kv = doc->root->as.kv.head; kv; kv = kv->next) {
        if (!cb(kv->key, kv->val, userdata)) return;
    }
}

// free any malloc'd list->items buffers and SclKV nodes in the value tree.
// arena nodes themselves are freed by arenaFree.
static void freeExternalBuffers(scl_value_t *val) {
    if (!val) return;
    switch (val->type) {
        case SCL_TYPE_LIST:
            for (size_t i = 0; i < val->as.list.count; i++) {
                freeExternalBuffers(val->as.list.items[i]);
            }
            if (val->as.list.items_heap) {
                free(val->as.list.items);
                val->as.list.items      = NULL;
                val->as.list.items_heap = false;
            }
            break;
        case SCL_TYPE_STRUCT:
        case SCL_TYPE_MAP: {
            SclKV *kv = val->as.kv.head;
            while (kv) {
                SclKV *next = kv->next;
                freeExternalBuffers(kv->val);
                if (kv->kv_heap) free(kv);
                kv = next;
            }
            break;
        }
        default:
            break;
    }
}

void scl_doc_free(scl_doc_t *doc) {
    if (!doc) return;
    freeExternalBuffers(doc->root);
    arenaFree(&doc->arena);
    free(doc);
}

// value reading

scl_type_t scl_value_type(scl_value_t *val) {
    if (!val) return SCL_TYPE_NULL;
    return val->type;
}

bool scl_value_string(scl_value_t *val, const char **out) {
    if (!val || val->type != SCL_TYPE_STRING) return false;
    if (out) *out = val->as.str.ptr;
    return true;
}

bool scl_value_int(scl_value_t *val, int64_t *out) {
    if (!val || val->type != SCL_TYPE_INT) return false;
    if (out) *out = val->as.i;
    return true;
}

bool scl_value_uint(scl_value_t *val, uint64_t *out) {
    if (!val || val->type != SCL_TYPE_UINT) return false;
    if (out) *out = val->as.u;
    return true;
}

bool scl_value_float(scl_value_t *val, double *out) {
    if (!val || val->type != SCL_TYPE_FLOAT) return false;
    if (out) *out = val->as.f;
    return true;
}

bool scl_value_bool(scl_value_t *val, bool *out) {
    if (!val || val->type != SCL_TYPE_BOOL) return false;
    if (out) *out = val->as.b;
    return true;
}

bool scl_value_bytes(scl_value_t *val, const uint8_t **out, size_t *len) {
    if (!val || val->type != SCL_TYPE_BYTES) return false;
    if (out) *out = val->as.bytes.ptr;
    if (len) *len = val->as.bytes.len;
    return true;
}

bool scl_value_date(scl_value_t *val, const char **out) {
    if (!val || val->type != SCL_TYPE_DATE) return false;
    if (out) *out = val->as.str.ptr;
    return true;
}

bool scl_value_datetime(scl_value_t *val, const char **out) {
    if (!val || val->type != SCL_TYPE_DATETIME) return false;
    if (out) *out = val->as.str.ptr;
    return true;
}

bool scl_value_duration(scl_value_t *val, const char **out) {
    if (!val || val->type != SCL_TYPE_DURATION) return false;
    if (out) *out = val->as.str.ptr;
    return true;
}

bool scl_value_is_null(scl_value_t *val) {
    return !val || val->type == SCL_TYPE_NULL;
}

size_t scl_list_len(scl_value_t *val) {
    if (!val || val->type != SCL_TYPE_LIST) return 0;
    return val->as.list.count;
}

scl_value_t *scl_list_get(scl_value_t *val, size_t index) {
    if (!val || val->type != SCL_TYPE_LIST) return NULL;
    if (index >= val->as.list.count) return NULL;
    return val->as.list.items[index];
}

scl_value_t *scl_struct_get(scl_value_t *val, const char *key) {
    if (!val) return NULL;
    if (val->type != SCL_TYPE_STRUCT && val->type != SCL_TYPE_MAP) return NULL;
    return valueKVGet(val, key);
}

void scl_struct_each(scl_value_t *val,
                     bool (*cb)(const char *key, scl_value_t *v, void *userdata),
                     void *userdata) {
    if (!val || !cb) return;
    if (val->type != SCL_TYPE_STRUCT && val->type != SCL_TYPE_MAP) return;
    for (SclKV *kv = val->as.kv.head; kv; kv = kv->next) {
        if (!cb(kv->key, kv->val, userdata)) return;
    }
}

// building

scl_doc_t *scl_doc_new(void) {
    scl_doc_t *doc = malloc(sizeof(scl_doc_t));
    if (!doc) return NULL;
    arenaInit(&doc->arena);
    doc->root = valueAlloc(&doc->arena, SCL_TYPE_STRUCT);
    return doc;
}

scl_value_t *scl_val_string(scl_doc_t *doc, const char *s) {
    scl_value_t *v = valueAlloc(&doc->arena, SCL_TYPE_STRING);
    size_t len = strlen(s);
    v->as.str.ptr = arenaStrndup(&doc->arena, s, len);
    v->as.str.len = len;
    return v;
}

scl_value_t *scl_val_int(scl_doc_t *doc, int64_t val) {
    scl_value_t *v = valueAlloc(&doc->arena, SCL_TYPE_INT);
    v->as.i = val;
    return v;
}

scl_value_t *scl_val_uint(scl_doc_t *doc, uint64_t val) {
    scl_value_t *v = valueAlloc(&doc->arena, SCL_TYPE_UINT);
    v->as.u = val;
    return v;
}

scl_value_t *scl_val_float(scl_doc_t *doc, double val) {
    scl_value_t *v = valueAlloc(&doc->arena, SCL_TYPE_FLOAT);
    v->as.f = val;
    return v;
}

scl_value_t *scl_val_bool(scl_doc_t *doc, bool val) {
    scl_value_t *v = valueAlloc(&doc->arena, SCL_TYPE_BOOL);
    v->as.b = val;
    return v;
}

scl_value_t *scl_val_null(scl_doc_t *doc) {
    return valueAlloc(&doc->arena, SCL_TYPE_NULL);
}

scl_value_t *scl_val_bytes(scl_doc_t *doc, const uint8_t *data, size_t len) {
    scl_value_t *v = valueAlloc(&doc->arena, SCL_TYPE_BYTES);
    uint8_t *copy = (uint8_t *)arenaAlloc(&doc->arena, len);
    if (copy && len > 0) memcpy(copy, data, len);
    v->as.bytes.ptr = copy;
    v->as.bytes.len = len;
    return v;
}

scl_value_t *scl_val_list_new(scl_doc_t *doc) {
    return valueAlloc(&doc->arena, SCL_TYPE_LIST);
}

scl_value_t *scl_val_struct_new(scl_doc_t *doc) {
    return valueAlloc(&doc->arena, SCL_TYPE_STRUCT);
}

void scl_list_push(scl_value_t *list, scl_value_t *val) {
    // kept for ABI compatibility — cannot allocate through arena without doc reference.
    // prefer scl_doc_list_push when building documents.
    if (!list || list->type != SCL_TYPE_LIST) return;
    if (list->as.list.count >= list->as.list.cap) {
        size_t newCap = list->as.list.cap == 0 ? 4 : list->as.list.cap * 2;
        scl_value_t **tmp = malloc(newCap * sizeof(scl_value_t *));
        if (!tmp) return;
        if (list->as.list.count > 0) {
            memcpy(tmp, list->as.list.items, list->as.list.count * sizeof(scl_value_t *));
        }
        // free previous heap buffer if present; arena-allocated buffer must not be freed
        if (list->as.list.items_heap) free(list->as.list.items);
        list->as.list.items      = tmp;
        list->as.list.cap        = newCap;
        list->as.list.items_heap = true;
    }
    list->as.list.items[list->as.list.count++] = val;
}

void scl_doc_list_push(scl_doc_t *doc, scl_value_t *list, scl_value_t *val) {
    if (!doc || !list || list->type != SCL_TYPE_LIST) return;
    valueListPush(list, val, &doc->arena);
}

void scl_struct_set(scl_value_t *strct, const char *key, scl_value_t *val) {
    // kept for ABI compatibility — cannot allocate through arena without doc reference.
    // prefer scl_doc_struct_set when building documents.
    if (!strct) return;
    if (strct->type != SCL_TYPE_STRUCT && strct->type != SCL_TYPE_MAP) return;

    for (SclKV *kv = strct->as.kv.head; kv; kv = kv->next) {
        if (strcmp(kv->key, key) == 0) {
            kv->val = val;
            return;
        }
    }

    SclKV *kv = malloc(sizeof(SclKV));
    if (!kv) return;
    kv->key      = key;
    kv->val      = val;
    kv->next     = NULL;
    kv->kv_heap  = true;

    if (!strct->as.kv.head) {
        strct->as.kv.head = kv;
        strct->as.kv.tail = kv;
    } else {
        strct->as.kv.tail->next = kv;
        strct->as.kv.tail       = kv;
    }
}

void scl_doc_struct_set(scl_doc_t *doc, scl_value_t *strct, const char *key, scl_value_t *val) {
    if (!doc || !strct || !key || !val) return;
    if (strct->type != SCL_TYPE_STRUCT && strct->type != SCL_TYPE_MAP) return;
    const char *arenaKey = arenaStrdup(&doc->arena, key);
    valueKVSet(strct, arenaKey, val, &doc->arena);
}

void scl_doc_set(scl_doc_t *doc, const char *key, scl_value_t *val) {
    if (!doc || !key || !val) return;
    scl_doc_struct_set(doc, doc->root, key, val);
}

// serialization implemented in serialize.cpp

scl_str_t scl_serialize(scl_doc_t *doc) {
    return sclSerialize(doc);
}

scl_str_t scl_to_json(scl_doc_t *doc) {
    return sclToJson(doc);
}

scl_str_result_t scl_to_toml(scl_doc_t *doc) {
    sclTomlResult r = sclToToml(doc);
    scl_str_result_t out;
    out.ok    = r.ok;
    out.str   = r.str;
    out.error = r.ok ? NULL : r.error;
    return out;
}

void scl_str_free(scl_str_t s) {
    free(s.data);
}

void scl_str_result_free(scl_str_result_t *r) {
    if (!r) return;
    free(r->str.data);
    free(r->error);
    r->str.data = NULL;
    r->str.len  = 0;
    r->error    = NULL;
}
