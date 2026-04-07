#ifndef SCL_ARENA_H
#define SCL_ARENA_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>

typedef struct ArenaBlock {
    struct ArenaBlock *next;
    size_t             used;
    size_t             cap;
    char               data[];
} ArenaBlock;

typedef struct {
    ArenaBlock *head;
} Arena;

void  arenaInit(Arena *a);
void *arenaAlloc(Arena *a, size_t size);
char *arenaStrdup(Arena *a, const char *s);
char *arenaStrndup(Arena *a, const char *s, size_t n);
void  arenaFree(Arena *a);

#ifdef __cplusplus
}
#endif

#endif
