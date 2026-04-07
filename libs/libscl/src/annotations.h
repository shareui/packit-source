#ifndef SCL_ANNOTATIONS_H
#define SCL_ANNOTATIONS_H

#ifdef __cplusplus
extern "C" {
#endif

#include "ast.h"

/*
 * validate all annotations on a field value.
 * returns heap-allocated error string on violation, NULL on success.
 * caller must free() the returned string.
 */
char *sclCheckAnnotations(AstAnnotation *annotations, AstNode *val,
                          const char *fieldName, const char *src);

#ifdef __cplusplus
}
#endif

#endif
