#include <stdint.h>
#include <stddef.h>
#include <string.h>
// localuse library written entirely by @shareui

#define ROR32(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
// please note that this was created to increase the cost of hacking, not to provide complete protection. therefore, don't brag about hacking anything
static const uint32_t K[64] = {
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
    c->bits = 0; c->pos = 0;
}

static void sha256_block(sha256_ctx *c, const uint8_t *b) {
    uint32_t w[64], a,e,t1,t2,i;
    for (i=0;i<16;i++)
        w[i]=((uint32_t)b[i*4]<<24)|((uint32_t)b[i*4+1]<<16)|((uint32_t)b[i*4+2]<<8)|b[i*4+3];
    for (i=16;i<64;i++) {
        uint32_t s0=ROR32(w[i-15],7)^ROR32(w[i-15],18)^(w[i-15]>>3);
        uint32_t s1=ROR32(w[i-2],17)^ROR32(w[i-2],19)^(w[i-2]>>10);
        w[i]=w[i-16]+s0+w[i-7]+s1;
    }
    a=c->h[0]; uint32_t bb2=c->h[1],cc=c->h[2],d=c->h[3];
    e=c->h[4]; uint32_t f=c->h[5],g=c->h[6],h=c->h[7];
    for (i=0;i<64;i++) {
        t1=h+(ROR32(e,6)^ROR32(e,11)^ROR32(e,25))+((e&f)^(~e&g))+K[i]+w[i];
        t2=(ROR32(a,2)^ROR32(a,13)^ROR32(a,22))+((a&bb2)^(a&cc)^(bb2&cc));
        h=g; g=f; f=e; e=d+t1; d=cc; cc=bb2; bb2=a; a=t1+t2;
    }
    c->h[0]+=a; c->h[1]+=bb2; c->h[2]+=cc; c->h[3]+=d;
    c->h[4]+=e; c->h[5]+=f;  c->h[6]+=g;  c->h[7]+=h;
}

static void sha256_update(sha256_ctx *c, const uint8_t *d, size_t n) {
    for (size_t i=0;i<n;i++) {
        c->buf[c->pos++]=d[i];
        if (c->pos==64) { sha256_block(c,c->buf); c->pos=0; c->bits+=512; }
    }
}

static void sha256_final(sha256_ctx *c, uint8_t out[32]) {
    c->bits += c->pos*8;
    c->buf[c->pos++]=0x80;
    if (c->pos>56) { while(c->pos<64) c->buf[c->pos++]=0; sha256_block(c,c->buf); c->pos=0; }
    while(c->pos<56) c->buf[c->pos++]=0;
    for (int i=7;i>=0;i--) { c->buf[56+(7-i)]=(c->bits>>(i*8))&0xff; }
    sha256_block(c,c->buf);
    for (int i=0;i<8;i++) {
        out[i*4]=(c->h[i]>>24)&0xff; out[i*4+1]=(c->h[i]>>16)&0xff;
        out[i*4+2]=(c->h[i]>>8)&0xff; out[i*4+3]=c->h[i]&0xff;
    }
}

static void sha256(const uint8_t *d, size_t n, uint8_t out[32]) {
    sha256_ctx c; sha256_init(&c); sha256_update(&c,d,n); sha256_final(&c,out);
}

static void hmac_sha256(const uint8_t *key, size_t klen,
                        const uint8_t *msg, size_t mlen,
                        uint8_t out[32]) {
    uint8_t k[64], ipad[64], opad[64], ih[32];
    memset(k,0,64);
    if (klen>64) { sha256(key,klen,k); }
    else         { memcpy(k,key,klen); }
    for (int i=0;i<64;i++) { ipad[i]=k[i]^0x36; opad[i]=k[i]^0x5c; }
    sha256_ctx c;
    sha256_init(&c);
    sha256_update(&c,ipad,64);
    sha256_update(&c,(const uint8_t*)msg,mlen);
    sha256_final(&c,ih);
    sha256_init(&c);
    sha256_update(&c,opad,64);
    sha256_update(&c,ih,32);
    sha256_final(&c,out);
}

static void _build_key(uint8_t out[32]) {
    static const uint8_t a[32] = {
        0xf3,0x1a,0x9e,0x72,0x4b,0xc8,0x05,0xdd,
        0x31,0x7f,0xaa,0x56,0x93,0xe1,0x2c,0x88,
        0x0f,0x64,0xb7,0x3a,0x51,0x9d,0xc2,0x6e,
        0xa0,0x17,0x8b,0xfc,0x44,0x2e,0x73,0x91,
    };
    static const uint8_t b[32] = {
        0x6d,0x82,0x41,0x3f,0xe7,0x55,0xbc,0x10,
        0xc4,0x98,0x37,0xdb,0x0a,0x72,0x8e,0x15,
        0x9c,0xf1,0x28,0x6a,0xe3,0x04,0x57,0xb9,
        0x35,0xca,0x12,0x7d,0xaf,0x61,0xd8,0x4e,
    };
    static const uint8_t c[32] = {
        0x90,0x71,0xde,0xad,0x5c,0x3f,0xb1,0x74,
        0xe5,0x08,0xfd,0x6c,0xbc,0x81,0xf0,0x2a,
        0x63,0x97,0x4e,0x51,0x12,0xc6,0x89,0x37,
        0xf4,0x5e,0x76,0xce,0x9b,0x0d,0xa5,0xd8,
    };
    for (int i=0;i<32;i++) out[i] = a[i] ^ b[i] ^ c[i];
}

static void _derive_account_key(const char *account_id, uint8_t out[32]) {
    uint8_t master[32];
    _build_key(master);
    hmac_sha256(master, 32,
                (const uint8_t*)account_id, strlen(account_id),
                out);
    memset(master, 0, 32);
}

static void bytes_to_hex(const uint8_t *b, size_t n, char *out) {
    static const char hx[] = "0123456789abcdef";
    for (size_t i=0;i<n;i++) {
        out[i*2]   = hx[b[i]>>4];
        out[i*2+1] = hx[b[i]&0xf];
    }
    out[n*2] = '\0';
}

static int hex_to_bytes(const char *hex, uint8_t *out, size_t n) {
    for (size_t i=0;i<n;i++) {
        unsigned int hi, lo;
        char hc = hex[i*2], lc = hex[i*2+1];
        if (hc>='0'&&hc<='9') hi=hc-'0';
        else if (hc>='a'&&hc<='f') hi=hc-'a'+10;
        else if (hc>='A'&&hc<='F') hi=hc-'A'+10;
        else return -1;
        if (lc>='0'&&lc<='9') lo=lc-'0';
        else if (lc>='a'&&lc<='f') lo=lc-'a'+10;
        else if (lc>='A'&&lc<='F') lo=lc-'A'+10;
        else return -1;
        out[i]=(uint8_t)((hi<<4)|lo);
    }
    return 0;
}

static int ct_eq(const uint8_t *a, const uint8_t *b, size_t n) {
    uint8_t acc = 0;
    for (size_t i=0;i<n;i++) acc |= (a[i]^b[i]);
    return acc == 0;
}

void ag_sign(const char *data, size_t len, const char *account_id, char out_hex[65]) {
    uint8_t key[32], mac[32];
    _derive_account_key(account_id, key);
    hmac_sha256(key, 32, (const uint8_t*)data, len, mac);
    bytes_to_hex(mac, 32, out_hex);
    memset(key, 0, 32);
    memset(mac, 0, 32);
}

int ag_verify(const char *data, size_t len, const char *account_id, const char *sig_hex) {
    if (!sig_hex || strlen(sig_hex) != 64) return 0;
    uint8_t key[32], mac[32], given[32];
    if (hex_to_bytes(sig_hex, given, 32) != 0) return 0;
    _derive_account_key(account_id, key);
    hmac_sha256(key, 32, (const uint8_t*)data, len, mac);
    int ok = ct_eq(mac, given, 32);
    memset(key, 0, 32);
    memset(mac, 0, 32);
    return ok;
}
