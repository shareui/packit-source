#ifndef SCL_VALUE_H
#define SCL_VALUE_H

#include "scl.h"
#include "arena.h"

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

// key-value pair for structmap in SclValue  arena-allocated linked list
typedef struct SclKV {
    const char     *key;    // arena-owned
    scl_value_t    *val;
    struct SclKV   *next;
    bool            kv_heap; // true if this SclKV was mallocd, not arena-allocated
} SclKV;

// concrete definition of opaque scl_value_t
struct SclValue {
    scl_type_t type;

    union {
        // SCL_TYPE_STRING  SCL_TYPE_DATE  SCL_TYPE_DATETIME  SCL_TYPE_DURATION
        struct { const char *ptr; size_t len; } str;

        // SCL_TYPE_INT
        int64_t  i;

        // SCL_TYPE_UINT
        uint64_t u;

        // SCL_TYPE_FLOAT
        double   f;

        // SCL_TYPE_BOOL
        bool     b;

        // SCL_TYPE_BYTES
        struct { const uint8_t *ptr; size_t len; } bytes;

        // SCL_TYPE_LIST
        struct {
            scl_value_t **items;
            size_t        count;
            size_t        cap;
            bool          items_heap; // true if items was malloc'd, not arena-allocated
        } list;

        // SCL_TYPE_STRUCT  SCL_TYPE_MAP
        struct { SclKV *head; SclKV *tail; } kv;
    } as;
};

/*
 * allocate a zeroed SclValue from arena.
 * type is set; all other fields zero.
 */
scl_value_t *valueAlloc(Arena *arena, scl_type_t type);

/*
 * grow a list value by one slot, appending val.
 * uses arena for reallocation of the items array.
 */
void valueListPush(scl_value_t *list, scl_value_t *val, Arena *arena);

/*
 * append a key-value pair to a struct/map value.
 * key must be arena-owned or outlive the value.
 */
void valueKVSet(scl_value_t *strct, const char *key, scl_value_t *val, Arena *arena);

/*
 * look up a key in a struct/map value.
 * returns NULL if not found.
 */
scl_value_t *valueKVGet(scl_value_t *strct, const char *key);

#endif
