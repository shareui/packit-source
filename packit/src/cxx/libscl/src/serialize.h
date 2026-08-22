#ifndef SCL_SERIALIZE_H
#define SCL_SERIALIZE_H

#ifdef __cplusplus
extern "C" {
#endif

#include "scl.h"
#include "doc.h"
#include <stdbool.h>

// internal result type used between serialize.cpp and api.c
typedef struct {
    bool      ok;
    scl_str_t str;
    char     *error;
} sclTomlResult;

scl_str_t    sclSerialize(scl_doc_t *doc);
scl_str_t    sclToJson(scl_doc_t *doc);
sclTomlResult sclToToml(scl_doc_t *doc);

#ifdef __cplusplus
}
#endif

#endif
