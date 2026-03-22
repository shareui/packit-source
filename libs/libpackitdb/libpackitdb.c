#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define PACKDB_MAGIC     0x504B4442u
#define PACKDB_VERSION   2
#define HMAC_SIZE        32
#define MAX_KEYS         256
#define MAX_KEY_LEN      64
#define MAX_AWARDED      128
#define MAX_AWARDED_LEN  64
#define MAX_ACCOUNT_LEN  64

#define ROR32(x,n) (((x)>>(n))|((x)<<(32-(n))))

static const uint32_t K256[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,
    0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
    0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
    0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,
    0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
    0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,
    0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,
    0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
    0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2,
};

typedef struct { uint8_t buf[64]; uint64_t bits; uint32_t h[8]; size_t pos; } sha256_ctx;

static void sha256_init(sha256_ctx *c) {
    c->h[0]=0x6a09e667; c->h[1]=0xbb67ae85; c->h[2]=0x3c6ef372; c->h[3]=0xa54ff53a;
    c->h[4]=0x510e527f; c->h[5]=0x9b05688c; c->h[6]=0x1f83d9ab; c->h[7]=0x5be0cd19;
    c->bits=0; c->pos=0;
}

static void sha256_block(sha256_ctx *c, const uint8_t *b) {
    uint32_t w[64],a,bb,cc,d,e,f,g,h,t1,t2;
    for (int i=0;i<16;i++)
        w[i]=((uint32_t)b[i*4]<<24)|((uint32_t)b[i*4+1]<<16)|((uint32_t)b[i*4+2]<<8)|b[i*4+3];
    for (int i=16;i<64;i++) {
        uint32_t s0=ROR32(w[i-15],7)^ROR32(w[i-15],18)^(w[i-15]>>3);
        uint32_t s1=ROR32(w[i-2],17)^ROR32(w[i-2],19)^(w[i-2]>>10);
        w[i]=w[i-16]+s0+w[i-7]+s1;
    }
    a=c->h[0]; bb=c->h[1]; cc=c->h[2]; d=c->h[3];
    e=c->h[4]; f=c->h[5]; g=c->h[6]; h=c->h[7];
    for (int i=0;i<64;i++) {
        t1=h+(ROR32(e,6)^ROR32(e,11)^ROR32(e,25))+((e&f)^(~e&g))+K256[i]+w[i];
        t2=(ROR32(a,2)^ROR32(a,13)^ROR32(a,22))+((a&bb)^(a&cc)^(bb&cc));
        h=g; g=f; f=e; e=d+t1; d=cc; cc=bb; bb=a; a=t1+t2;
    }
    c->h[0]+=a; c->h[1]+=bb; c->h[2]+=cc; c->h[3]+=d;
    c->h[4]+=e; c->h[5]+=f;  c->h[6]+=g;  c->h[7]+=h;
}

static void sha256_update(sha256_ctx *c, const uint8_t *d, size_t n) {
    for (size_t i=0;i<n;i++) {
        c->buf[c->pos++]=d[i];
        if (c->pos==64) { sha256_block(c,c->buf); c->pos=0; c->bits+=512; }
    }
}

static void sha256_final(sha256_ctx *c, uint8_t out[32]) {
    c->bits+=c->pos*8;
    c->buf[c->pos++]=0x80;
    if (c->pos>56) { while(c->pos<64) c->buf[c->pos++]=0; sha256_block(c,c->buf); c->pos=0; }
    while(c->pos<56) c->buf[c->pos++]=0;
    for (int i=7;i>=0;i--) c->buf[56+(7-i)]=(c->bits>>(i*8))&0xff;
    sha256_block(c,c->buf);
    for (int i=0;i<8;i++) {
        out[i*4]=(c->h[i]>>24)&0xff; out[i*4+1]=(c->h[i]>>16)&0xff;
        out[i*4+2]=(c->h[i]>>8)&0xff; out[i*4+3]=c->h[i]&0xff;
    }
}

static void sha256_hash(const uint8_t *d, size_t n, uint8_t out[32]) {
    sha256_ctx c; sha256_init(&c); sha256_update(&c,d,n); sha256_final(&c,out);
}

static void hmac_sha256(const uint8_t *key, size_t klen,
                        const uint8_t *msg, size_t mlen, uint8_t out[32]) {
    uint8_t k[64]={0}, ipad[64], opad[64], ih[32];
    if (klen>64) sha256_hash(key,klen,k); else memcpy(k,key,klen);
    for (int i=0;i<64;i++) { ipad[i]=k[i]^0x36; opad[i]=k[i]^0x5c; }
    sha256_ctx c;
    sha256_init(&c); sha256_update(&c,ipad,64); sha256_update(&c,msg,mlen); sha256_final(&c,ih);
    sha256_init(&c); sha256_update(&c,opad,64); sha256_update(&c,ih,32);   sha256_final(&c,out);
}

static void build_master_key(uint8_t out[32]) {
    static const uint8_t a[32]={
        0xf3,0x1a,0x9e,0x72,0x4b,0xc8,0x05,0xdd,
        0x31,0x7f,0xaa,0x56,0x93,0xe1,0x2c,0x88,
        0x0f,0x64,0xb7,0x3a,0x51,0x9d,0xc2,0x6e,
        0xa0,0x17,0x8b,0xfc,0x44,0x2e,0x73,0x91,
    };
    static const uint8_t b[32]={
        0x6d,0x82,0x41,0x3f,0xe7,0x55,0xbc,0x10,
        0xc4,0x98,0x37,0xdb,0x0a,0x72,0x8e,0x15,
        0x9c,0xf1,0x28,0x6a,0xe3,0x04,0x57,0xb9,
        0x35,0xca,0x12,0x7d,0xaf,0x61,0xd8,0x4e,
    };
    static const uint8_t c[32]={
        0x90,0x71,0xde,0xad,0x5c,0x3f,0xb1,0x74,
        0xe5,0x08,0xfd,0x6c,0xbc,0x81,0xf0,0x2a,
        0x63,0x97,0x4e,0x51,0x12,0xc6,0x89,0x37,
        0xf4,0x5e,0x76,0xce,0x9b,0x0d,0xa5,0xd8,
    };
    for (int i=0;i<32;i++) out[i]=a[i]^b[i]^c[i];
}

static void derive_key(const char *account_id, uint8_t out[32]) {
    uint8_t master[32];
    build_master_key(master);
    hmac_sha256(master,32,(const uint8_t*)account_id,strlen(account_id),out);
    memset(master,0,32);
}

static int ct_eq(const uint8_t *a, const uint8_t *b, size_t n) {
    uint8_t acc=0;
    for (size_t i=0;i<n;i++) acc|=a[i]^b[i];
    return acc==0;
}

typedef struct {
    char    key[MAX_KEY_LEN];
    int64_t val;
} kv_entry;

typedef struct {
    char     path[512];
    char     account_id[MAX_ACCOUNT_LEN];
    kv_entry entries[MAX_KEYS];
    int      entry_count;
    char     awarded[MAX_AWARDED][MAX_AWARDED_LEN];
    int      awarded_count;
    int      dirty;
} packdb;

static void write_u8(uint8_t **p, uint8_t v)   { **p=v; (*p)++; }
static void write_u32(uint8_t **p, uint32_t v) {
    (*p)[0]=(v>>24)&0xff; (*p)[1]=(v>>16)&0xff;
    (*p)[2]=(v>>8)&0xff;  (*p)[3]=v&0xff; (*p)+=4;
}
static void write_i64(uint8_t **p, int64_t v) {
    uint64_t u=(uint64_t)v;
    write_u32(p,(uint32_t)(u>>32)); write_u32(p,(uint32_t)(u&0xffffffffu));
}
static void write_str(uint8_t **p, const char *s) {
    uint8_t len=(uint8_t)strlen(s); write_u8(p,len);
    memcpy(*p,s,len); (*p)+=len;
}

static uint8_t  read_u8(const uint8_t **p)  { return *(*p)++; }
static uint32_t read_u32(const uint8_t **p) {
    uint32_t v=((uint32_t)(*p)[0]<<24)|((uint32_t)(*p)[1]<<16)|
               ((uint32_t)(*p)[2]<<8)|(*p)[3]; (*p)+=4; return v;
}
static int64_t read_i64(const uint8_t **p) {
    uint64_t hi=read_u32(p); uint64_t lo=read_u32(p);
    return (int64_t)((hi<<32)|lo);
}
static void read_str(const uint8_t **p, char *out, size_t max) {
    uint8_t len=read_u8(p);
    size_t n=len<max-1?len:max-1;
    memcpy(out,*p,n); out[n]='\0'; (*p)+=len;
}

static uint8_t *serialize(const packdb *db, size_t *out_len) {
    size_t cap = 8 + (size_t)db->entry_count*(1+MAX_KEY_LEN+8)
                   + (size_t)db->awarded_count*(1+MAX_AWARDED_LEN) + 16;
    uint8_t *buf = malloc(cap);
    if (!buf) return NULL;
    uint8_t *p = buf;
    write_u32(&p,(uint32_t)db->entry_count);
    for (int i=0;i<db->entry_count;i++) {
        write_str(&p, db->entries[i].key);
        write_i64(&p, db->entries[i].val);
    }
    write_u32(&p,(uint32_t)db->awarded_count);
    for (int i=0;i<db->awarded_count;i++)
        write_str(&p, db->awarded[i]);
    *out_len = (size_t)(p - buf);
    return buf;
}

static int deserialize(packdb *db, const uint8_t *buf, size_t len) {
    const uint8_t *p = buf, *end = buf+len;
    if (p+4>end) return -1;
    uint32_t ec=read_u32(&p);
    if (ec>MAX_KEYS) return -1;
    db->entry_count=(int)ec;
    for (int i=0;i<db->entry_count;i++) {
        if (p>=end) return -1;
        read_str(&p, db->entries[i].key, MAX_KEY_LEN);
        if (p+8>end) return -1;
        db->entries[i].val=read_i64(&p);
    }
    if (p+4>end) return -1;
    uint32_t ac=read_u32(&p);
    if (ac>MAX_AWARDED) return -1;
    db->awarded_count=(int)ac;
    for (int i=0;i<db->awarded_count;i++) {
        if (p>=end) return -1;
        read_str(&p, db->awarded[i], MAX_AWARDED_LEN);
    }
    return 0;
}

int packdb_write_raw(const char *path, const char *account_id,
                     const uint8_t *payload, uint32_t payload_len) {
    uint8_t key[32], mac[HMAC_SIZE];
    derive_key(account_id, key);
    hmac_sha256(key, 32, payload, payload_len, mac);
    memset(key, 0, 32);

    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    uint32_t magic = PACKDB_MAGIC;
    uint8_t  ver   = PACKDB_VERSION;
    fwrite(&magic, 4, 1, f);
    fwrite(&ver,   1, 1, f);
    fwrite(mac, HMAC_SIZE, 1, f);
    fwrite(&payload_len, 4, 1, f);
    fwrite(payload, payload_len, 1, f);
    fclose(f);
    return 0;
}

int packdb_read_raw(const char *path, const char *account_id,
                    uint8_t *out_buf, uint32_t *out_len) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;

    uint32_t magic=0; uint8_t ver=0;
    uint8_t mac[HMAC_SIZE]; uint32_t plen=0;

    if (fread(&magic,4,1,f)!=1 || magic!=PACKDB_MAGIC) { fclose(f); return -2; }
    if (fread(&ver,1,1,f)!=1   || ver!=PACKDB_VERSION)  { fclose(f); return -2; }
    if (fread(mac,HMAC_SIZE,1,f)!=1) { fclose(f); return -2; }
    if (fread(&plen,4,1,f)!=1)        { fclose(f); return -2; }

    if (plen > *out_len) { fclose(f); return -4; }
    if (fread(out_buf, plen, 1, f)!=1) { fclose(f); return -2; }
    fclose(f);

    uint8_t key[32], expected[HMAC_SIZE];
    derive_key(account_id, key);
    hmac_sha256(key, 32, out_buf, plen, expected);
    memset(key, 0, 32);

    if (!ct_eq(mac, expected, HMAC_SIZE)) return -3;
    *out_len = plen;
    return 0;
}

static int write_db(const packdb *db, const uint8_t *payload, uint32_t plen) {
    return packdb_write_raw(db->path, db->account_id, payload, plen);
}

packdb *packdb_open_from_payload(const char *path, const char *account_id,
                                  const uint8_t *payload, uint32_t payload_len) {
    packdb *db = calloc(1, sizeof(packdb));
    if (!db) return NULL;
    strncpy(db->path, path, sizeof(db->path)-1);
    strncpy(db->account_id, account_id, sizeof(db->account_id)-1);
    if (payload && payload_len > 0)
        deserialize(db, payload, payload_len);
    return db;
}

int packdb_serialize_to(packdb *db, uint8_t *out_buf, uint32_t *out_len) {
    size_t raw_len;
    uint8_t *raw = serialize(db, &raw_len);
    if (!raw) return -1;
    if (raw_len > *out_len) { free(raw); return -4; }
    memcpy(out_buf, raw, raw_len);
    *out_len = (uint32_t)raw_len;
    free(raw);
    return 0;
}

packdb *packdb_open(const char *path, const char *account_id) {
    packdb *db = calloc(1, sizeof(packdb));
    if (!db) return NULL;
    strncpy(db->path, path, sizeof(db->path)-1);
    strncpy(db->account_id, account_id, sizeof(db->account_id)-1);
    return db;
}

int packdb_close(packdb *db) {
    if (!db) return -1;
    free(db);
    return 0;
}

int64_t packdb_get(packdb *db, const char *key, int64_t def) {
    if (!db) return def;
    for (int i=0;i<db->entry_count;i++)
        if (strcmp(db->entries[i].key, key)==0) return db->entries[i].val;
    return def;
}

int packdb_set(packdb *db, const char *key, int64_t val) {
    if (!db) return -1;
    for (int i=0;i<db->entry_count;i++) {
        if (strcmp(db->entries[i].key, key)==0) {
            db->entries[i].val=val; db->dirty=1; return 0;
        }
    }
    if (db->entry_count>=MAX_KEYS) return -1;
    strncpy(db->entries[db->entry_count].key, key, MAX_KEY_LEN-1);
    db->entries[db->entry_count].val=val;
    db->entry_count++;
    db->dirty=1;
    return 0;
}

int64_t packdb_increment(packdb *db, const char *key, int64_t by) {
    if (!db) return 0;
    int64_t next = packdb_get(db, key, 0) + by;
    packdb_set(db, key, next);
    return next;
}

int packdb_award_has(packdb *db, const char *id) {
    if (!db) return 0;
    for (int i=0;i<db->awarded_count;i++)
        if (strcmp(db->awarded[i], id)==0) return 1;
    return 0;
}

int packdb_award_add(packdb *db, const char *id) {
    if (!db || packdb_award_has(db, id)) return 0;
    if (db->awarded_count>=MAX_AWARDED) return -1;
    strncpy(db->awarded[db->awarded_count], id, MAX_AWARDED_LEN-1);
    db->awarded_count++;
    db->dirty=1;
    return 1;
}

int packdb_award_list(packdb *db, char *out_buf, size_t buf_size) {
    if (!db || !out_buf || buf_size==0) return 0;
    size_t pos=0;
    for (int i=0;i<db->awarded_count;i++) {
        size_t slen=strlen(db->awarded[i]);
        if (pos+slen+1>=buf_size) break;
        memcpy(out_buf+pos, db->awarded[i], slen);
        pos+=slen;
        out_buf[pos++]='\n';
    }
    out_buf[pos]='\0';
    return db->awarded_count;
}

int packdb_award_count(packdb *db) { return db ? db->awarded_count : 0; }
int packdb_entry_count(packdb *db) { return db ? db->entry_count   : 0; }
