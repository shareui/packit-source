#include "value.h"
#include "arena.h"

#include <string.h>
#include <stdlib.h>

scl_value_t *valueAlloc(Arena *arena, scl_type_t type) {
    scl_value_t *v = arenaAlloc(arena, sizeof(scl_value_t));
    memset(v, 0, sizeof(scl_value_t));
    v->type = type;
    return v;
}

void valueListPush(scl_value_t *list, scl_value_t *val, Arena *arena) {
    if (list->as.list.count >= list->as.list.cap) {
        size_t newCap = list->as.list.cap == 0 ? 4 : list->as.list.cap * 2;
        scl_value_t **newItems = arenaAlloc(arena, newCap * sizeof(scl_value_t *));
        if (list->as.list.count > 0) {
            memcpy(newItems, list->as.list.items,
                   list->as.list.count * sizeof(scl_value_t *));
        }
        list->as.list.items = newItems;
        list->as.list.cap   = newCap;
    }
    list->as.list.items[list->as.list.count++] = val;
}

void valueKVSet(scl_value_t *strct, const char *key, scl_value_t *val, Arena *arena) {
    // update existing key if present
    for (SclKV *kv = strct->as.kv.head; kv; kv = kv->next) {
        if (strcmp(kv->key, key) == 0) {
            kv->val = val;
            return;
        }
    }

    SclKV *kv = arenaAlloc(arena, sizeof(SclKV));
    kv->key      = key;
    kv->val      = val;
    kv->next     = NULL;
    kv->kv_heap  = false;

    if (!strct->as.kv.head) {
        strct->as.kv.head = kv;
        strct->as.kv.tail = kv;
    } else {
        strct->as.kv.tail->next = kv;
        strct->as.kv.tail       = kv;
    }
}

scl_value_t *valueKVGet(scl_value_t *strct, const char *key) {
    for (SclKV *kv = strct->as.kv.head; kv; kv = kv->next) {
        if (strcmp(kv->key, key) == 0) return kv->val;
    }
    return NULL;
}
