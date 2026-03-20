#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

#define MAX_INDEXES     32
#define MAX_PLUGINS     4096
#define MAX_FIELD_LEN   2048
#define MAX_WORDS       64
#define MAX_WORD_LEN    128
#define MAX_TRIGRAMS    1024
#define MIN_SIMILARITY  0.15f

typedef struct {
    const char *s;
    int pos;
    int len;
} JsonReader;

static void jr_skip_ws(JsonReader *r) {
    while (r->pos < r->len && (r->s[r->pos] == ' ' || r->s[r->pos] == '\n' ||
           r->s[r->pos] == '\r' || r->s[r->pos] == '\t'))
        r->pos++;
}

static int jr_read_string(JsonReader *r, char *buf, int buflen) {
    jr_skip_ws(r);
    if (r->pos >= r->len || r->s[r->pos] != '"') return 0;
    r->pos++;
    int i = 0;
    while (r->pos < r->len && r->s[r->pos] != '"') {
        if (r->s[r->pos] == '\\') {
            r->pos++;
            if (r->pos >= r->len) break;
            char c = r->s[r->pos];
            if (c == '"' || c == '\\' || c == '/') {
                if (i < buflen - 1) buf[i++] = c;
            } else if (c == 'n') {
                if (i < buflen - 1) buf[i++] = '\n';
            } else if (c == 't') {
                if (i < buflen - 1) buf[i++] = '\t';
            } else if (c == 'u') {
                r->pos += 4;
            }
        } else {
            if (i < buflen - 1) buf[i++] = r->s[r->pos];
        }
        r->pos++;
    }
    if (r->pos < r->len) r->pos++;
    buf[i] = '\0';
    return 1;
}

static void jr_skip_value(JsonReader *r);

static void jr_skip_object(JsonReader *r) {
    jr_skip_ws(r);
    if (r->pos >= r->len || r->s[r->pos] != '{') return;
    r->pos++;
    int depth = 1;
    while (r->pos < r->len && depth > 0) {
        char c = r->s[r->pos];
        if (c == '"') {
            char tmp[8];
            jr_read_string(r, tmp, sizeof(tmp));
            continue;
        }
        if (c == '{') depth++;
        if (c == '}') depth--;
        r->pos++;
    }
}

static void jr_skip_array(JsonReader *r) {
    jr_skip_ws(r);
    if (r->pos >= r->len || r->s[r->pos] != '[') return;
    r->pos++;
    jr_skip_ws(r);
    while (r->pos < r->len && r->s[r->pos] != ']') {
        jr_skip_value(r);
        jr_skip_ws(r);
        if (r->pos < r->len && r->s[r->pos] == ',') r->pos++;
        jr_skip_ws(r);
    }
    if (r->pos < r->len) r->pos++;
}

static void jr_skip_value(JsonReader *r) {
    jr_skip_ws(r);
    if (r->pos >= r->len) return;
    char c = r->s[r->pos];
    if (c == '"') {
        char tmp[4];
        jr_read_string(r, tmp, sizeof(tmp));
    } else if (c == '{') {
        jr_skip_object(r);
    } else if (c == '[') {
        jr_skip_array(r);
    } else {
        while (r->pos < r->len) {
            char x = r->s[r->pos];
            if (x == ',' || x == '}' || x == ']' || x == ' ' || x == '\n' || x == '\r' || x == '\t')
                break;
            r->pos++;
        }
    }
}

static uint32_t utf8_next(const char **p, const char *end) {
    if (*p >= end) return 0;
    unsigned char c = (unsigned char)**p;
    (*p)++;
    if (c < 0x80) return c;
    if ((c & 0xE0) == 0xC0) {
        if (*p >= end) return '?';
        uint32_t cp = (c & 0x1F) << 6;
        cp |= ((unsigned char)**p & 0x3F);
        (*p)++;
        return cp;
    }
    if ((c & 0xF0) == 0xE0) {
        if (*p + 1 >= end) return '?';
        uint32_t cp = (c & 0x0F) << 12;
        cp |= ((unsigned char)**p & 0x3F) << 6; (*p)++;
        cp |= ((unsigned char)**p & 0x3F);       (*p)++;
        return cp;
    }
    if (*p + 1 < end) { (*p) += 2; }
    return '?';
}

static int utf8_encode(uint32_t cp, char *buf) {
    if (cp < 0x80) { buf[0] = (char)cp; return 1; }
    if (cp < 0x800) {
        buf[0] = (char)(0xC0 | (cp >> 6));
        buf[1] = (char)(0x80 | (cp & 0x3F));
        return 2;
    }
    buf[0] = (char)(0xE0 | (cp >> 12));
    buf[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
    buf[2] = (char)(0x80 | (cp & 0x3F));
    return 3;
}

static void utf8_lower(const char *src, char *dst, int buflen) {
    const char *p = src;
    const char *end = src + strlen(src);
    int out = 0;
    while (p < end && out < buflen - 4) {
        uint32_t cp = utf8_next(&p, end);
        if (cp >= 'A' && cp <= 'Z') cp += 32;
        else if (cp >= 0x0410 && cp <= 0x042F) cp += 0x20;
        else if (cp == 0x0401) cp = 0x0451;
        out += utf8_encode(cp, dst + out);
    }
    dst[out] = '\0';
}

typedef struct { uint32_t ru; const char *en; } TranslitEntry;

static const TranslitEntry TRANSLIT[] = {
    {0x0439, "q"}, {0x0446, "w"}, {0x0443, "e"}, {0x043A, "r"}, {0x0435, "t"},
    {0x043D, "y"}, {0x0433, "u"}, {0x0448, "i"}, {0x0449, "o"}, {0x0437, "p"},
    {0x0445, "["}, {0x044A, "]"}, {0x0444, "a"}, {0x044B, "s"}, {0x0432, "d"},
    {0x0430, "f"}, {0x043F, "g"}, {0x0440, "h"}, {0x043E, "j"}, {0x043B, "k"},
    {0x0434, "l"}, {0x0436, ";"}, {0x044D, "'"}, {0x044F, "z"}, {0x0447, "x"},
    {0x0441, "c"}, {0x043C, "v"}, {0x0438, "b"}, {0x0442, "n"}, {0x044C, "m"},
    {0x0431, ","}, {0x044E, "."},
};
#define TRANSLIT_COUNT ((int)(sizeof(TRANSLIT)/sizeof(TRANSLIT[0])))

static char translit_char(uint32_t cp) {
    for (int i = 0; i < TRANSLIT_COUNT; i++) {
        if (TRANSLIT[i].ru == cp) return TRANSLIT[i].en[0];
    }
    return 0;
}

static int translit(const char *src, char *dst, int buflen) {
    const char *p = src;
    const char *end = src + strlen(src);
    int out = 0;
    int changed = 0;
    while (p < end && out < buflen - 4) {
        uint32_t cp = utf8_next(&p, end);
        char t = translit_char(cp);
        if (t) {
            dst[out++] = t;
            changed = 1;
        } else {
            out += utf8_encode(cp, dst + out);
        }
    }
    dst[out] = '\0';
    return changed;
}

static int is_alpha_or_space(const char *s) {
    for (; *s; s++) {
        if (*s != ' ' && !isalpha((unsigned char)*s)) return 0;
    }
    return 1;
}

static uint32_t fnv3(unsigned char a, unsigned char b, unsigned char c) {
    uint32_t h = 2166136261u;
    h ^= a; h *= 16777619u;
    h ^= b; h *= 16777619u;
    h ^= c; h *= 16777619u;
    return h;
}

static int make_trigrams(const char *text, uint32_t *out, int maxout) {
    static uint32_t cps[MAX_FIELD_LEN + 2];
    const char *p = text;
    const char *end = text + strlen(text);
    int n = 0;
    cps[n++] = ' ';
    while (p < end && n < MAX_FIELD_LEN) {
        cps[n++] = utf8_next(&p, end);
    }
    cps[n++] = ' ';

    int count = 0;
    for (int i = 0; i < n - 2 && count < maxout; i++) {
        char ba[4], bb[4], bc[4];
        int la = utf8_encode(cps[i],   ba);
        int lb = utf8_encode(cps[i+1], bb);
        int lc = utf8_encode(cps[i+2], bc);
        (void)lb; (void)lc;
        uint32_t ha = 0, hb = 0, hc = 0;
        for (int k = 0; k < la; k++) ha ^= (unsigned char)ba[k] << (k * 5 % 24);
        for (int k = 0; k < lb; k++) hb ^= (unsigned char)bb[k] << (k * 5 % 24);
        for (int k = 0; k < lc; k++) hc ^= (unsigned char)bc[k] << (k * 5 % 24);
        out[count++] = fnv3((uint8_t)(ha & 0xFF), (uint8_t)(hb & 0xFF), (uint8_t)(hc & 0xFF));
    }
    return count;
}

static int cmp_u32(const void *a, const void *b) {
    uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
    return (x > y) - (x < y);
}

static int sort_dedup(uint32_t *arr, int n) {
    if (n == 0) return 0;
    qsort(arr, n, sizeof(uint32_t), cmp_u32);
    int w = 0;
    for (int i = 0; i < n; i++) {
        if (i == 0 || arr[i] != arr[i-1]) arr[w++] = arr[i];
    }
    return w;
}

static void sorted_intersect_union(const uint32_t *a, int na,
                                   const uint32_t *b, int nb,
                                   int *inter, int *uni) {
    int i = 0, j = 0, isect = 0;
    while (i < na && j < nb) {
        if (a[i] == b[j]) { isect++; i++; j++; }
        else if (a[i] < b[j]) i++;
        else j++;
    }
    *inter = isect;
    *uni   = na + nb - isect;
}

static float trigram_similarity(const uint32_t *a, int na,
                                 const uint32_t *b, int nb) {
    if (na == 0 || nb == 0) return 0.0f;
    int isect, uni;
    sorted_intersect_union(a, na, b, nb, &isect, &uni);
    return uni > 0 ? (float)isect / (float)uni : 0.0f;
}

typedef struct {
    char w[MAX_WORD_LEN];
} Word;

static int split_words(const char *text, Word *words, int maxwords) {
    char buf[MAX_FIELD_LEN];
    int n = 0;
    strncpy(buf, text, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';
    for (int i = 0; buf[i]; i++) { if (buf[i] == '_') buf[i] = ' '; }
    char *tok = strtok(buf, " \t\n\r");
    while (tok && n < maxwords) {
        strncpy(words[n].w, tok, MAX_WORD_LEN - 1);
        words[n].w[MAX_WORD_LEN - 1] = '\0';
        n++;
        tok = strtok(NULL, " \t\n\r");
    }
    return n;
}

static int edit_distance_1(const char *a, const char *b) {
    static uint32_t ca[MAX_WORD_LEN], cb[MAX_WORD_LEN];
    const char *p; const char *end;
    int la = 0, lb = 0;

    p = a; end = a + strlen(a);
    while (p < end && la < MAX_WORD_LEN) ca[la++] = utf8_next(&p, end);

    p = b; end = b + strlen(b);
    while (p < end && lb < MAX_WORD_LEN) cb[lb++] = utf8_next(&p, end);

    if (abs(la - lb) > 1) return 0;
    if (la == lb) {
        int diffs = 0;
        for (int i = 0; i < la; i++) if (ca[i] != cb[i]) diffs++;
        return diffs == 1;
    }
    uint32_t *shorter = (la < lb) ? ca : cb;
    uint32_t *longer  = (la < lb) ? cb : ca;
    int ls = (la < lb) ? la : lb;
    int ll = (la < lb) ? lb : la;
    (void)ll;
    int i = 0, j = 0, diffs = 0;
    while (i < ls && j < (ls + 1)) {
        if (shorter[i] != longer[j]) {
            diffs++;
            if (diffs > 1) return 0;
            j++;
        } else { i++; j++; }
    }
    return 1;
}

typedef struct {
    char id_raw[MAX_FIELD_LEN];
    char name_raw[MAX_FIELD_LEN];
    char author_raw[MAX_FIELD_LEN];
    char desc_en_raw[MAX_FIELD_LEN];
    char desc_ru_raw[MAX_FIELD_LEN];

    uint32_t tri_name[MAX_TRIGRAMS];    int tri_name_n;
    uint32_t tri_author[MAX_TRIGRAMS];  int tri_author_n;
    uint32_t tri_desc_en[MAX_TRIGRAMS]; int tri_desc_en_n;
    uint32_t tri_desc_ru[MAX_TRIGRAMS]; int tri_desc_ru_n;

    Word name_words[MAX_WORDS]; int name_words_n;
    Word id_words[MAX_WORDS];   int id_words_n;
} PluginEntry;

typedef struct {
    PluginEntry *entries;
    int count;
    int cap;
    int in_use;
} Index;

static Index g_indexes[MAX_INDEXES];

static void index_init(void) {
    static int done = 0;
    if (done) return;
    memset(g_indexes, 0, sizeof(g_indexes));
    done = 1;
}

static void build_entry(JsonReader *r, PluginEntry *e) {
    memset(e, 0, sizeof(*e));

    char raw_id[MAX_FIELD_LEN]     = "";
    char raw_name[MAX_FIELD_LEN]   = "";
    char raw_author[MAX_FIELD_LEN] = "";
    char raw_about0[MAX_FIELD_LEN] = "";
    char raw_about1[MAX_FIELD_LEN] = "";
    char raw_desc[MAX_FIELD_LEN]   = "";
    int  has_about_list = 0;

    jr_skip_ws(r);
    if (r->pos >= r->len || r->s[r->pos] != '{') return;
    r->pos++;

    while (r->pos < r->len) {
        jr_skip_ws(r);
        if (r->pos >= r->len) break;
        if (r->s[r->pos] == '}') { r->pos++; break; }
        if (r->s[r->pos] == ',') { r->pos++; continue; }

        char key[64] = "";
        if (!jr_read_string(r, key, sizeof(key))) break;
        jr_skip_ws(r);
        if (r->pos < r->len && r->s[r->pos] == ':') r->pos++;
        jr_skip_ws(r);

        if (strcmp(key, "id") == 0) {
            jr_read_string(r, raw_id, sizeof(raw_id));
        } else if (strcmp(key, "name") == 0) {
            jr_read_string(r, raw_name, sizeof(raw_name));
        } else if (strcmp(key, "author") == 0) {
            jr_read_string(r, raw_author, sizeof(raw_author));
        } else if (strcmp(key, "description") == 0) {
            jr_read_string(r, raw_desc, sizeof(raw_desc));
        } else if (strcmp(key, "about") == 0) {
            jr_skip_ws(r);
            if (r->pos < r->len && r->s[r->pos] == '[') {
                has_about_list = 1;
                r->pos++;
                jr_skip_ws(r);
                if (r->pos < r->len && r->s[r->pos] == '"')
                    jr_read_string(r, raw_about0, sizeof(raw_about0));
                jr_skip_ws(r);
                if (r->pos < r->len && r->s[r->pos] == ',') { r->pos++; jr_skip_ws(r); }
                if (r->pos < r->len && r->s[r->pos] == '"')
                    jr_read_string(r, raw_about1, sizeof(raw_about1));
                while (r->pos < r->len && r->s[r->pos] != ']') r->pos++;
                if (r->pos < r->len) r->pos++;
            } else {
                jr_skip_value(r);
            }
        } else {
            jr_skip_value(r);
        }
    }

    if (!raw_id[0]) return;

    char low_id[MAX_FIELD_LEN], low_name[MAX_FIELD_LEN];
    char low_author[MAX_FIELD_LEN];
    char low_desc_en[MAX_FIELD_LEN], low_desc_ru[MAX_FIELD_LEN];

    utf8_lower(raw_id,     low_id,     sizeof(low_id));
    utf8_lower(raw_name,   low_name,   sizeof(low_name));
    utf8_lower(raw_author, low_author, sizeof(low_author));

    if (has_about_list) {
        utf8_lower(raw_about0, low_desc_en, sizeof(low_desc_en));
        utf8_lower(raw_about1, low_desc_ru, sizeof(low_desc_ru));
    } else {
        utf8_lower(raw_desc, low_desc_en, sizeof(low_desc_en));
        strncpy(low_desc_ru, low_desc_en, sizeof(low_desc_ru) - 1);
    }

    strncpy(e->id_raw,      low_id,      sizeof(e->id_raw) - 1);
    strncpy(e->name_raw,    low_name,    sizeof(e->name_raw) - 1);
    strncpy(e->author_raw,  low_author,  sizeof(e->author_raw) - 1);
    strncpy(e->desc_en_raw, low_desc_en, sizeof(e->desc_en_raw) - 1);
    strncpy(e->desc_ru_raw, low_desc_ru, sizeof(e->desc_ru_raw) - 1);

    uint32_t tmp[MAX_TRIGRAMS]; int n;

    n = make_trigrams(low_name,    tmp, MAX_TRIGRAMS); e->tri_name_n    = sort_dedup(tmp, n); memcpy(e->tri_name,    tmp, e->tri_name_n    * sizeof(uint32_t));
    n = make_trigrams(low_author,  tmp, MAX_TRIGRAMS); e->tri_author_n  = sort_dedup(tmp, n); memcpy(e->tri_author,  tmp, e->tri_author_n  * sizeof(uint32_t));
    n = make_trigrams(low_desc_en, tmp, MAX_TRIGRAMS); e->tri_desc_en_n = sort_dedup(tmp, n); memcpy(e->tri_desc_en, tmp, e->tri_desc_en_n * sizeof(uint32_t));
    n = make_trigrams(low_desc_ru, tmp, MAX_TRIGRAMS); e->tri_desc_ru_n = sort_dedup(tmp, n); memcpy(e->tri_desc_ru, tmp, e->tri_desc_ru_n * sizeof(uint32_t));

    e->name_words_n = split_words(low_name, e->name_words, MAX_WORDS);
    e->id_words_n   = split_words(low_id,   e->id_words,   MAX_WORDS);
}

static PluginEntry *find_entry(Index *idx, const char *id_raw) {
    for (int i = 0; i < idx->count; i++) {
        if (strcmp(idx->entries[i].id_raw, id_raw) == 0) return &idx->entries[i];
    }
    return NULL;
}

EXPORT int search_build_index(const char *plugins_json) {
    index_init();

    int handle = -1;
    for (int i = 0; i < MAX_INDEXES; i++) {
        if (!g_indexes[i].in_use) { handle = i; break; }
    }
    if (handle < 0) return -1;

    Index *idx = &g_indexes[handle];
    idx->cap   = 256;
    idx->count = 0;
    idx->entries = (PluginEntry *)malloc(idx->cap * sizeof(PluginEntry));
    if (!idx->entries) return -1;
    idx->in_use = 1;

    JsonReader r;
    r.s   = plugins_json;
    r.len = (int)strlen(plugins_json);
    r.pos = 0;

    jr_skip_ws(&r);
    if (r.pos >= r.len || r.s[r.pos] != '[') goto done;
    r.pos++;

    while (r.pos < r.len) {
        jr_skip_ws(&r);
        if (r.pos >= r.len) break;
        if (r.s[r.pos] == ']') { r.pos++; break; }
        if (r.s[r.pos] == ',') { r.pos++; continue; }

        if (idx->count >= idx->cap) {
            int newcap = idx->cap * 2;
            if (newcap > MAX_PLUGINS) newcap = MAX_PLUGINS;
            if (idx->count >= newcap) break;
            PluginEntry *tmp = (PluginEntry *)realloc(idx->entries, newcap * sizeof(PluginEntry));
            if (!tmp) break;
            idx->entries = tmp;
            idx->cap = newcap;
        }

        PluginEntry *e = &idx->entries[idx->count];
        int saved_pos = r.pos;
        build_entry(&r, e);

        if (!e->id_raw[0]) {
            if (r.pos == saved_pos) {
                jr_skip_ws(&r);
                if (r.pos < r.len && r.s[r.pos] == '{') jr_skip_object(&r);
            }
            continue;
        }
        idx->count++;
    }

done:
    return handle;
}

EXPORT char *search_score(int handle, const char *pid, const char *query,
                           int is_russian, int fuzzy) {
    if (handle < 0 || handle >= MAX_INDEXES || !g_indexes[handle].in_use)
        return NULL;
    if (!query || !query[0]) {
        char *r = (char *)malloc(16);
        if (r) snprintf(r, 16, "[0,0,0.0]");
        return r;
    }

    Index *idx = &g_indexes[handle];

    char ql[MAX_FIELD_LEN];
    utf8_lower(query, ql, sizeof(ql));
    int start = 0, end = (int)strlen(ql);
    while (start < end && ql[start] == ' ') start++;
    while (end > start && ql[end-1] == ' ') end--;
    ql[end] = '\0';
    memmove(ql, ql + start, end - start + 1);

    char tq[MAX_FIELD_LEN];
    if (translit(ql, tq, sizeof(tq)) && strcmp(tq, ql) != 0) {
        char no_space[MAX_FIELD_LEN];
        int k = 0;
        for (int i = 0; tq[i]; i++) if (tq[i] != ' ') no_space[k++] = tq[i];
        no_space[k] = '\0';
        if (is_alpha_or_space(no_space)) strncpy(ql, tq, sizeof(ql) - 1);
    }

    char low_id[MAX_FIELD_LEN];
    utf8_lower(pid, low_id, sizeof(low_id));

    PluginEntry *e = find_entry(idx, low_id);
    if (!e) {
        char *r = (char *)malloc(16);
        if (r) snprintf(r, 16, "[6,0,0.0]");
        return r;
    }

    const char *nameRaw       = e->name_raw;
    const char *idRaw         = e->id_raw;
    const char *authorRaw     = e->author_raw;
    const char *descPrimary   = is_russian ? e->desc_ru_raw : e->desc_en_raw;
    const char *descSecondary = is_russian ? e->desc_en_raw : e->desc_ru_raw;
    Word *nameWords = e->name_words; int nameWordsN = e->name_words_n;
    Word *idWords   = e->id_words;   int idWordsN   = e->id_words_n;

    Word tokens[MAX_WORDS]; int tokenN;
    {
        char tmp[MAX_FIELD_LEN];
        strncpy(tmp, ql, sizeof(tmp) - 1);
        tokenN = split_words(tmp, tokens, MAX_WORDS);
    }

    int tier, sub; float sim;

    #define RESULT(t,s,m) do { tier=(t); sub=(s); sim=(m); goto emit; } while(0)

    if (strstr(nameRaw,       ql)) RESULT(1, strncmp(nameRaw,       ql, strlen(ql))==0 ? 0 : 1, 0.0f);
    if (strstr(descPrimary,   ql)) RESULT(2, strncmp(descPrimary,   ql, strlen(ql))==0 ? 0 : 1, 0.0f);
    if (strstr(descSecondary, ql)) RESULT(3, strncmp(descSecondary, ql, strlen(ql))==0 ? 0 : 1, 0.0f);
    if (strstr(idRaw,         ql)) RESULT(4, strncmp(idRaw,         ql, strlen(ql))==0 ? 0 : 1, 0.0f);
    if (strstr(authorRaw,     ql)) RESULT(5, strncmp(authorRaw,     ql, strlen(ql))==0 ? 0 : 1, 0.0f);

    for (int i = 0; i < nameWordsN; i++) {
        if (strncmp(nameWords[i].w, ql, strlen(ql)) == 0) RESULT(1, 2, 0.0f);
    }
    for (int i = 0; i < idWordsN; i++) {
        if (strncmp(idWords[i].w, ql, strlen(ql)) == 0) RESULT(4, 2, 0.0f);
    }

    if (tokenN > 1) {
        int all;
        all = 1; for (int i = 0; i < tokenN; i++) if (!strstr(nameRaw,       tokens[i].w)) { all=0; break; }
        if (all) RESULT(1, 3, 0.0f);
        all = 1; for (int i = 0; i < tokenN; i++) if (!strstr(descPrimary,   tokens[i].w)) { all=0; break; }
        if (all) RESULT(2, 3, 0.0f);
        all = 1; for (int i = 0; i < tokenN; i++) if (!strstr(descSecondary, tokens[i].w)) { all=0; break; }
        if (all) RESULT(3, 3, 0.0f);
        all = 1; for (int i = 0; i < tokenN; i++) if (!strstr(idRaw,         tokens[i].w)) { all=0; break; }
        if (all) RESULT(4, 3, 0.0f);
        all = 1; for (int i = 0; i < tokenN; i++) if (!strstr(authorRaw,     tokens[i].w)) { all=0; break; }
        if (all) RESULT(5, 3, 0.0f);
    }

    {
        uint32_t qtri[MAX_TRIGRAMS]; int qtrin;
        {
            uint32_t tmp[MAX_TRIGRAMS];
            int n = make_trigrams(ql, tmp, MAX_TRIGRAMS);
            qtrin = sort_dedup(tmp, n);
            memcpy(qtri, tmp, qtrin * sizeof(uint32_t));
        }

        float nameSim = trigram_similarity(qtri, qtrin, e->tri_name, e->tri_name_n);
        if (nameSim >= MIN_SIMILARITY) RESULT(1, 4, -nameSim);

        uint32_t *triPrimary    = is_russian ? e->tri_desc_ru : e->tri_desc_en;
        int       triPrimaryN   = is_russian ? e->tri_desc_ru_n : e->tri_desc_en_n;
        uint32_t *triSecondary  = is_russian ? e->tri_desc_en : e->tri_desc_ru;
        int       triSecondaryN = is_russian ? e->tri_desc_en_n : e->tri_desc_ru_n;

        float descPSim = trigram_similarity(qtri, qtrin, triPrimary, triPrimaryN);
        if (descPSim >= MIN_SIMILARITY) RESULT(2, 4, -descPSim);

        float descSSim = trigram_similarity(qtri, qtrin, triSecondary, triSecondaryN);
        if (descSSim >= MIN_SIMILARITY) RESULT(3, 4, -descSSim);

        uint32_t idtri[MAX_TRIGRAMS]; int idtrin;
        {
            uint32_t tmp[MAX_TRIGRAMS];
            int n = make_trigrams(idRaw, tmp, MAX_TRIGRAMS);
            idtrin = sort_dedup(tmp, n);
            memcpy(idtri, tmp, idtrin * sizeof(uint32_t));
        }
        float idSim = trigram_similarity(qtri, qtrin, idtri, idtrin);
        if (idSim >= MIN_SIMILARITY) RESULT(4, 4, -idSim);

        float authorSim = trigram_similarity(qtri, qtrin, e->tri_author, e->tri_author_n);
        if (authorSim >= MIN_SIMILARITY) RESULT(5, 4, -authorSim);
    }

    if (fuzzy) {
        for (int i = 0; i < nameWordsN; i++) {
            if (edit_distance_1(ql, nameWords[i].w)) RESULT(1, 5, 0.0f);
        }
        for (int i = 0; i < idWordsN; i++) {
            if (edit_distance_1(ql, idWords[i].w)) RESULT(4, 5, 0.0f);
        }
    }

    tier = 6; sub = 0; sim = 0.0f;

emit:;
    char *out = (char *)malloc(64);
    if (!out) return NULL;
    snprintf(out, 64, "[%d,%d,%.6f]", tier, sub, (double)sim);
    return out;

    #undef RESULT
}

EXPORT void search_free_index(int handle) {
    if (handle < 0 || handle >= MAX_INDEXES) return;
    Index *idx = &g_indexes[handle];
    if (!idx->in_use) return;
    free(idx->entries);
    idx->entries = NULL;
    idx->count = idx->cap = 0;
    idx->in_use = 0;
}

EXPORT void search_free_str(char *ptr) {
    free(ptr);
}
