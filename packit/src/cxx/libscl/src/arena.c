#include "arena.h"

#include <stdlib.h>
#include <string.h>

#define ARENA_BLOCK_SIZE (64 * 1024)

static ArenaBlock *newBlock(size_t minSize) {
    size_t cap = minSize > ARENA_BLOCK_SIZE ? minSize : ARENA_BLOCK_SIZE;
    ArenaBlock *b = malloc(sizeof(ArenaBlock) + cap);
    if (!b) return NULL;
    b->next = NULL;
    b->used = 0;
    b->cap  = cap;
    return b;
}

void arenaInit(Arena *a) {
    a->head = NULL;
}

void *arenaAlloc(Arena *a, size_t size) {
    // align to 8 bytes
    size = (size + 7) & ~(size_t)7;

    if (!a->head || a->head->used + size > a->head->cap) {
        ArenaBlock *b = newBlock(size);
        if (!b) return NULL;
        b->next = a->head;
        a->head = b;
    }

    void *ptr = a->head->data + a->head->used;
    a->head->used += size;
    return ptr;
}

char *arenaStrdup(Arena *a, const char *s) {
    if (!s) return NULL;
    size_t n = strlen(s) + 1;
    char *dst = arenaAlloc(a, n);
    if (!dst) return NULL;
    memcpy(dst, s, n);
    return dst;
}

char *arenaStrndup(Arena *a, const char *s, size_t n) {
    if (!s) return NULL;
    char *dst = arenaAlloc(a, n + 1);
    if (!dst) return NULL;
    memcpy(dst, s, n);
    dst[n] = '\0';
    return dst;
}

void arenaFree(Arena *a) {
    ArenaBlock *b = a->head;
    while (b) {
        ArenaBlock *next = b->next;
        free(b);
        b = next;
    }
    a->head = NULL;
}
