#ifndef SCL_H
#define SCL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#define SCL_VERSION_MAJOR 1
#define SCL_VERSION_MINOR 0

// symbol visibility: explicit export on all platforms
#if defined(_WIN32) || defined(__CYGWIN__)
#  ifdef SCL_BUILD_SHARED
#    define SCL_API __declspec(dllexport)
#  else
#    define SCL_API __declspec(dllimport)
#  endif
#elif defined(__GNUC__) && __GNUC__ >= 4
#  define SCL_API __attribute__((visibility("default")))
#else
#  define SCL_API
#endif

// opaque handles
typedef struct SclDoc   scl_doc_t;
typedef struct SclValue scl_value_t;

typedef enum {
    SCL_TYPE_NULL,
    SCL_TYPE_STRING,
    SCL_TYPE_INT,
    SCL_TYPE_UINT,
    SCL_TYPE_FLOAT,
    SCL_TYPE_BOOL,
    SCL_TYPE_BYTES,
    SCL_TYPE_DATE,
    SCL_TYPE_DATETIME,
    SCL_TYPE_DURATION,
    SCL_TYPE_LIST,
    SCL_TYPE_MAP,
    SCL_TYPE_STRUCT,
    SCL_TYPE_UNION
} scl_type_t;

typedef struct {
    char  *data;
    size_t len;
} scl_str_t;

// result of a parse operation
// on success: ok=true, doc is caller-owned, warnings/warning_count may be set
// on failure: ok=false, error is heap-allocated, caller must free
// warnings is a heap-allocated array of heap-allocated strings, caller must free each then the array
typedef struct {
    bool        ok;
    scl_doc_t  *doc;
    char       *error;
    char      **warnings;
    size_t      warning_count;
} scl_result_t;

// result of a serialization operation that may fail
// on success: ok=true, str is caller-owned, free via scl_str_free
// on failure: ok=false, error is heap-allocated, caller must free
typedef struct {
    bool      ok;
    scl_str_t str;
    char     *error;
} scl_str_result_t;

// options for parse variants, zero-init for defaults
typedef struct {
    bool allow_unknown_annotations; // do not error on unrecognised annotations
    bool strict_datetime;           // reject datetime values without explicit timezone
    int  max_depth;                 // max nesting depth, 0 = unlimited
    bool include_root;              // reserved: allow @include at document root (always true)
} scl_parse_opts_t;

// library version at runtime
SCL_API void scl_version(int *major, int *minor);

// parsing, caller owns the returned doc on success
SCL_API scl_result_t scl_parse_str(const char *src);
SCL_API scl_result_t scl_parse_file(const char *path);
SCL_API scl_result_t scl_parse_str_opts(const char *src, scl_parse_opts_t opts);
SCL_API scl_result_t scl_parse_file_opts(const char *path, scl_parse_opts_t opts);

// free helpers for scl_result_t fields that are not owned by a doc
SCL_API void scl_result_free_warnings(scl_result_t *r);

// document access
SCL_API scl_value_t *scl_get(scl_doc_t *doc, const char *key);
SCL_API scl_value_t *scl_get_path(scl_doc_t *doc, const char *path);
SCL_API void         scl_each_key(scl_doc_t *doc,
                                  bool (*cb)(const char *key, scl_value_t *val, void *userdata),
                                  void *userdata);
SCL_API void         scl_doc_free(scl_doc_t *doc);

SCL_API scl_type_t   scl_value_type(scl_value_t *val);
SCL_API bool         scl_value_string(scl_value_t *val, const char **out);
SCL_API bool         scl_value_int(scl_value_t *val, int64_t *out);
SCL_API bool         scl_value_uint(scl_value_t *val, uint64_t *out);
SCL_API bool         scl_value_float(scl_value_t *val, double *out);
SCL_API bool         scl_value_bool(scl_value_t *val, bool *out);
SCL_API bool         scl_value_bytes(scl_value_t *val, const uint8_t **out, size_t *len);
SCL_API bool         scl_value_date(scl_value_t *val, const char **out);
SCL_API bool         scl_value_datetime(scl_value_t *val, const char **out);
SCL_API bool         scl_value_duration(scl_value_t *val, const char **out);
SCL_API bool         scl_value_is_null(scl_value_t *val);
SCL_API size_t       scl_list_len(scl_value_t *val);
SCL_API scl_value_t *scl_list_get(scl_value_t *val, size_t index);
SCL_API scl_value_t *scl_struct_get(scl_value_t *val, const char *key);
SCL_API void         scl_struct_each(scl_value_t *val,
                                     bool (*cb)(const char *key, scl_value_t *val, void *userdata),
                                     void *userdata);

// building
SCL_API scl_doc_t   *scl_doc_new(void);
SCL_API scl_value_t *scl_val_string(scl_doc_t *doc, const char *s);
SCL_API scl_value_t *scl_val_int(scl_doc_t *doc, int64_t v);
SCL_API scl_value_t *scl_val_uint(scl_doc_t *doc, uint64_t v);
SCL_API scl_value_t *scl_val_float(scl_doc_t *doc, double v);
SCL_API scl_value_t *scl_val_bool(scl_doc_t *doc, bool v);
SCL_API scl_value_t *scl_val_null(scl_doc_t *doc);
SCL_API scl_value_t *scl_val_bytes(scl_doc_t *doc, const uint8_t *data, size_t len);
SCL_API scl_value_t *scl_val_list_new(scl_doc_t *doc);
SCL_API scl_value_t *scl_val_struct_new(scl_doc_t *doc);
SCL_API void         scl_list_push(scl_value_t *list, scl_value_t *val);
SCL_API void         scl_doc_list_push(scl_doc_t *doc, scl_value_t *list, scl_value_t *val);
SCL_API void         scl_struct_set(scl_value_t *strct, const char *key, scl_value_t *val);
SCL_API void         scl_doc_struct_set(scl_doc_t *doc, scl_value_t *strct, const char *key, scl_value_t *val);
SCL_API void         scl_doc_set(scl_doc_t *doc, const char *key, scl_value_t *val);

SCL_API scl_str_t        scl_serialize(scl_doc_t *doc);
SCL_API scl_str_t        scl_to_json(scl_doc_t *doc);
// scl_to_toml fails if document contains bytes or union values
SCL_API scl_str_result_t scl_to_toml(scl_doc_t *doc);
SCL_API void             scl_str_free(scl_str_t s);
SCL_API void             scl_str_result_free(scl_str_result_t *r);

#ifdef __cplusplus
}
#endif

#endif
