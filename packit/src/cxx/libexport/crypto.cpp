#include "crypto.hpp"

// internal helpers not exposed
static inline uint32_t rotl32(uint32_t v, int n) {
    return (v << n) | (v >> (32 - n));
}
static inline uint32_t load32_le(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static inline uint64_t load64_le(const uint8_t *p) {
    return (uint64_t)load32_le(p) | ((uint64_t)load32_le(p+4)<<32);
}

// sha-256

static const uint32_t SHA256_K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2,
};

static void sha256_transform(Sha256Ctx &ctx, const uint8_t *block) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++) {
        const uint8_t *b = block + i*4;
        w[i] = ((uint32_t)b[0]<<24)|((uint32_t)b[1]<<16)|((uint32_t)b[2]<<8)|(uint32_t)b[3];
    }
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = rotl32(w[i-15],25)^rotl32(w[i-15],14)^(w[i-15]>>3);
        uint32_t s1 = rotl32(w[i-2], 15)^rotl32(w[i-2], 13)^(w[i-2] >>10);
        w[i] = w[i-16]+s0+w[i-7]+s1;
    }
    uint32_t a=ctx.h[0],b=ctx.h[1],c=ctx.h[2],d=ctx.h[3];
    uint32_t e=ctx.h[4],f=ctx.h[5],g=ctx.h[6],h=ctx.h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t S1  = rotl32(e,26)^rotl32(e,21)^rotl32(e,7);
        uint32_t ch  = (e&f)^(~e&g);
        uint32_t t1  = h+S1+ch+SHA256_K[i]+w[i];
        uint32_t S0  = rotl32(a,30)^rotl32(a,19)^rotl32(a,10);
        uint32_t maj = (a&b)^(a&c)^(b&c);
        uint32_t t2  = S0+maj;
        h=g; g=f; f=e; e=d+t1;
        d=c; c=b; b=a; a=t1+t2;
    }
    ctx.h[0]+=a; ctx.h[1]+=b; ctx.h[2]+=c; ctx.h[3]+=d;
    ctx.h[4]+=e; ctx.h[5]+=f; ctx.h[6]+=g; ctx.h[7]+=h;
}

void sha256_init(Sha256Ctx &ctx) {
    ctx.h[0]=0x6a09e667; ctx.h[1]=0xbb67ae85; ctx.h[2]=0x3c6ef372; ctx.h[3]=0xa54ff53a;
    ctx.h[4]=0x510e527f; ctx.h[5]=0x9b05688c; ctx.h[6]=0x1f83d9ab; ctx.h[7]=0x5be0cd19;
    ctx.bits=0; ctx.buflen=0;
}

void sha256_update(Sha256Ctx &ctx, const uint8_t *data, size_t len) {
    for (size_t i = 0; i < len; i++) {
        ctx.buf[ctx.buflen++] = data[i];
        ctx.bits += 8;
        if (ctx.buflen == 64) { sha256_transform(ctx, ctx.buf); ctx.buflen=0; }
    }
}

void sha256_final(Sha256Ctx &ctx, uint8_t out[32]) {
    ctx.buf[ctx.buflen++] = 0x80;
    if (ctx.buflen > 56) {
        while (ctx.buflen < 64) ctx.buf[ctx.buflen++] = 0;
        sha256_transform(ctx, ctx.buf); ctx.buflen=0;
    }
    while (ctx.buflen < 56) ctx.buf[ctx.buflen++] = 0;
    uint64_t bits = ctx.bits;
    for (int i = 7; i >= 0; i--) { ctx.buf[56+i]=bits&0xFF; bits>>=8; }
    sha256_transform(ctx, ctx.buf);
    for (int i = 0; i < 8; i++) {
        out[i*4+0]=(ctx.h[i]>>24)&0xFF; out[i*4+1]=(ctx.h[i]>>16)&0xFF;
        out[i*4+2]=(ctx.h[i]>> 8)&0xFF; out[i*4+3]= ctx.h[i]      &0xFF;
    }
}

void sha256(const uint8_t *data, size_t len, uint8_t out[32]) {
    Sha256Ctx ctx; sha256_init(ctx); sha256_update(ctx,data,len); sha256_final(ctx,out);
}

// HMAC-SHA256

void hmac_sha256(const uint8_t *key, size_t klen,
                 const uint8_t *msg, size_t mlen,
                 uint8_t out[32]) {
    uint8_t k[64] = {};
    if (klen > 64) sha256(key, klen, k);
    else           memcpy(k, key, klen);

    uint8_t ipad[64], opad[64];
    for (int i = 0; i < 64; i++) { ipad[i]=k[i]^0x36; opad[i]=k[i]^0x5C; }

    Sha256Ctx ctx;
    sha256_init(ctx);
    sha256_update(ctx, ipad, 64);
    sha256_update(ctx, msg,  mlen);
    uint8_t inner[32]; sha256_final(ctx, inner);

    sha256_init(ctx);
    sha256_update(ctx, opad,  64);
    sha256_update(ctx, inner, 32);
    sha256_final(ctx, out);
}

// HKDF-SHA256

void hkdf_sha256(const uint8_t *ikm,  size_t ikm_len,
                 const uint8_t *salt, size_t salt_len,
                 const uint8_t *info, size_t info_len,
                 uint8_t *okm, size_t okm_len) {
    uint8_t prk[32];
    if (salt && salt_len > 0) {
        hmac_sha256(salt, salt_len, ikm, ikm_len, prk);
    } else {
        uint8_t zero[32] = {};
        hmac_sha256(zero, 32, ikm, ikm_len, prk);
    }

    uint8_t t[32] = {}; size_t t_len = 0, done = 0;
    for (uint8_t i = 1; done < okm_len; i++) {
        uint8_t k[64] = {}; memcpy(k, prk, 32);
        uint8_t ipad[64], opad[64];
        for (int j = 0; j < 64; j++) { ipad[j]=k[j]^0x36; opad[j]=k[j]^0x5C; }

        Sha256Ctx ctx;
        sha256_init(ctx);
        sha256_update(ctx, ipad, 64);
        if (t_len)              sha256_update(ctx, t,    t_len);
        if (info && info_len)   sha256_update(ctx, info, info_len);
        sha256_update(ctx, &i, 1);
        uint8_t inner[32]; sha256_final(ctx, inner);

        sha256_init(ctx);
        sha256_update(ctx, opad,  64);
        sha256_update(ctx, inner, 32);
        sha256_final(ctx, t);
        t_len = 32;

        size_t n = okm_len - done; if (n > 32) n = 32;
        memcpy(okm + done, t, n);
        done += n;
    }
}

// ChaCha20

#define CHACHA_QR(a,b,c,d) \
    a+=b; d^=a; d=rotl32(d,16); \
    c+=d; b^=c; b=rotl32(b,12); \
    a+=b; d^=a; d=rotl32(d, 8); \
    c+=d; b^=c; b=rotl32(b, 7)

static void chacha20_block(const uint32_t in[16], uint8_t out[64]) {
    uint32_t s[16]; memcpy(s, in, 64);
    for (int i = 0; i < 10; i++) {
        CHACHA_QR(s[0],s[4],s[8], s[12]); CHACHA_QR(s[1],s[5],s[9], s[13]);
        CHACHA_QR(s[2],s[6],s[10],s[14]); CHACHA_QR(s[3],s[7],s[11],s[15]);
        CHACHA_QR(s[0],s[5],s[10],s[15]); CHACHA_QR(s[1],s[6],s[11],s[12]);
        CHACHA_QR(s[2],s[7],s[8], s[13]); CHACHA_QR(s[3],s[4],s[9], s[14]);
    }
    for (int i = 0; i < 16; i++) store32_le(out+i*4, s[i]+in[i]);
}

void chacha20_xor(const uint8_t key[32], const uint8_t nonce[12],
                  uint32_t counter, uint8_t *buf, size_t len) {
    uint32_t state[16] = {
        0x61707865,0x3320646e,0x79622d32,0x6b206574,
        load32_le(key+0), load32_le(key+4), load32_le(key+8),  load32_le(key+12),
        load32_le(key+16),load32_le(key+20),load32_le(key+24), load32_le(key+28),
        counter,
        load32_le(nonce+0), load32_le(nonce+4), load32_le(nonce+8),
    };
    uint8_t block[64]; size_t i = 0;
    while (i < len) {
        chacha20_block(state, block); state[12]++;
        size_t n = (len-i < 64) ? len-i : 64;
        for (size_t j = 0; j < n; j++) buf[i+j] ^= block[j];
        i += n;
    }
}

// Poly1305

static void poly1305_block(Poly1305Ctx &ctx, const uint8_t *m, uint32_t hibit) {
    uint32_t r0=ctx.r[0],r1=ctx.r[1],r2=ctx.r[2],r3=ctx.r[3],r4=ctx.r[4];
    uint32_t s1=r1*5,s2=r2*5,s3=r3*5,s4=r4*5;
    uint32_t h0=ctx.h[0],h1=ctx.h[1],h2=ctx.h[2],h3=ctx.h[3],h4=ctx.h[4];

    h0 += (load32_le(m+ 0)      ) & 0x3FFFFFF;
    h1 += (load32_le(m+ 3) >> 2 ) & 0x3FFFFFF;
    h2 += (load32_le(m+ 6) >> 4 ) & 0x3FFFFFF;
    h3 += (load32_le(m+ 9) >> 6 ) & 0x3FFFFFF;
    h4 += (load32_le(m+12) >> 8 ) | hibit;

    uint64_t d0=((uint64_t)h0*r0)+((uint64_t)h1*s4)+((uint64_t)h2*s3)+((uint64_t)h3*s2)+((uint64_t)h4*s1);
    uint64_t d1=((uint64_t)h0*r1)+((uint64_t)h1*r0)+((uint64_t)h2*s4)+((uint64_t)h3*s3)+((uint64_t)h4*s2);
    uint64_t d2=((uint64_t)h0*r2)+((uint64_t)h1*r1)+((uint64_t)h2*r0)+((uint64_t)h3*s4)+((uint64_t)h4*s3);
    uint64_t d3=((uint64_t)h0*r3)+((uint64_t)h1*r2)+((uint64_t)h2*r1)+((uint64_t)h3*r0)+((uint64_t)h4*s4);
    uint64_t d4=((uint64_t)h0*r4)+((uint64_t)h1*r3)+((uint64_t)h2*r2)+((uint64_t)h3*r1)+((uint64_t)h4*r0);

    uint32_t c;
    c=(uint32_t)(d0>>26); h0=(uint32_t)d0&0x3FFFFFF; d1+=c;
    c=(uint32_t)(d1>>26); h1=(uint32_t)d1&0x3FFFFFF; d2+=c;
    c=(uint32_t)(d2>>26); h2=(uint32_t)d2&0x3FFFFFF; d3+=c;
    c=(uint32_t)(d3>>26); h3=(uint32_t)d3&0x3FFFFFF; d4+=c;
    c=(uint32_t)(d4>>26); h4=(uint32_t)d4&0x3FFFFFF; h0+=c*5;
    c=h0>>26; h0&=0x3FFFFFF; h1+=c;

    ctx.h[0]=h0; ctx.h[1]=h1; ctx.h[2]=h2; ctx.h[3]=h3; ctx.h[4]=h4;
}

void poly1305_init(Poly1305Ctx &ctx, const uint8_t key[32]) {
    uint8_t rc[16]; memcpy(rc, key, 16);
    rc[3]&=0x0F; rc[7]&=0x0F; rc[11]&=0x0F; rc[15]&=0x0F;
    rc[4]&=0xFC; rc[8]&=0xFC; rc[12]&=0xFC;
    ctx.r[0]=(load32_le(rc+ 0)      )&0x3FFFFFF;
    ctx.r[1]=(load32_le(rc+ 3)>> 2  )&0x3FFFFFF;
    ctx.r[2]=(load32_le(rc+ 6)>> 4  )&0x3FFFFFF;
    ctx.r[3]=(load32_le(rc+ 9)>> 6  )&0x3FFFFFF;
    ctx.r[4]=(load32_le(rc+12)>> 8  )&0x0FFFFFF;
    ctx.pad[0]=load32_le(key+16); ctx.pad[1]=load32_le(key+20);
    ctx.pad[2]=load32_le(key+24); ctx.pad[3]=load32_le(key+28);
    memset(ctx.h, 0, sizeof(ctx.h));
    ctx.buflen = 0;
}

void poly1305_update(Poly1305Ctx &ctx, const uint8_t *data, size_t len) {
    if (ctx.buflen) {
        size_t need = 16 - ctx.buflen;
        if (len < need) { memcpy(ctx.buf+ctx.buflen, data, len); ctx.buflen+=len; return; }
        memcpy(ctx.buf+ctx.buflen, data, need);
        poly1305_block(ctx, ctx.buf, 1u<<24);
        data+=need; len-=need; ctx.buflen=0;
    }
    while (len >= 16) { poly1305_block(ctx, data, 1u<<24); data+=16; len-=16; }
    if (len) { memcpy(ctx.buf, data, len); ctx.buflen=len; }
}

void poly1305_final(Poly1305Ctx &ctx, uint8_t mac[16]) {
    if (ctx.buflen) {
        ctx.buf[ctx.buflen++] = 1;
        while (ctx.buflen < 16) ctx.buf[ctx.buflen++] = 0;
        poly1305_block(ctx, ctx.buf, 0);
    }
    uint32_t h0=ctx.h[0],h1=ctx.h[1],h2=ctx.h[2],h3=ctx.h[3],h4=ctx.h[4];
    uint32_t c;
    c=h1>>26; h1&=0x3FFFFFF; h2+=c;
    c=h2>>26; h2&=0x3FFFFFF; h3+=c;
    c=h3>>26; h3&=0x3FFFFFF; h4+=c;
    c=h4>>26; h4&=0x3FFFFFF; h0+=c*5;
    c=h0>>26; h0&=0x3FFFFFF; h1+=c;

    uint32_t g0=h0+5, g1=h1+(g0>>26); g0&=0x3FFFFFF;
    uint32_t g2=h2+(g1>>26); g1&=0x3FFFFFF;
    uint32_t g3=h3+(g2>>26); g2&=0x3FFFFFF;
    uint32_t g4=h4+(g3>>26); g3&=0x3FFFFFF;
    uint32_t mask = (uint32_t)(-(int32_t)(g4>>26)); g4&=0x3FFFFFF; // 0xFFFFFFFF if h>=p else 0
    h0=(h0&~mask)|(g0&mask); h1=(h1&~mask)|(g1&mask);
    h2=(h2&~mask)|(g2&mask); h3=(h3&~mask)|(g3&mask);
    h4=(h4&~mask)|(g4&mask);

    uint64_t f;
    f  = (uint64_t)h0 | ((uint64_t)h1 << 26);
    f += (uint64_t)ctx.pad[0]; store32_le(mac+0, (uint32_t)f); f >>= 32;
    f += (uint64_t)h2 << 20;
    f += (uint64_t)ctx.pad[1]; store32_le(mac+4, (uint32_t)f); f >>= 32;
    f += (uint64_t)h3 << 14;
    f += (uint64_t)ctx.pad[2]; store32_le(mac+8, (uint32_t)f); f >>= 32;
    f += (uint64_t)h4 << 8;
    f += (uint64_t)ctx.pad[3]; store32_le(mac+12, (uint32_t)f);
}

// ChaCha20-Poly1305 AEAD

static void poly1305_key_gen(const uint8_t key[32], const uint8_t nonce[12], uint8_t otk[32]) {
    uint8_t block[64];
    uint32_t state[16] = {
        0x61707865,0x3320646e,0x79622d32,0x6b206574,
        load32_le(key+0), load32_le(key+4), load32_le(key+8),  load32_le(key+12),
        load32_le(key+16),load32_le(key+20),load32_le(key+24), load32_le(key+28),
        0,
        load32_le(nonce+0), load32_le(nonce+4), load32_le(nonce+8),
    };
    chacha20_block(state, block);
    memcpy(otk, block, 32);
}

static void aead_mac(const uint8_t key[32], const uint8_t nonce[12],
                     const uint8_t *aad, size_t aad_len,
                     const uint8_t *ct,  size_t ct_len,
                     uint8_t tag[16]) {
    uint8_t otk[32]; poly1305_key_gen(key, nonce, otk);
    Poly1305Ctx ctx; poly1305_init(ctx, otk);

    if (aad_len) poly1305_update(ctx, aad, aad_len);
    if (aad_len % 16) { uint8_t z[16]={}; poly1305_update(ctx, z, 16-(aad_len%16)); }

    poly1305_update(ctx, ct, ct_len);
    if (ct_len % 16) { uint8_t z[16]={}; poly1305_update(ctx, z, 16-(ct_len%16)); }

    uint8_t lens[16];
    store32_le(lens+0, (uint32_t)aad_len); store32_le(lens+4, 0);
    store32_le(lens+8, (uint32_t)ct_len);  store32_le(lens+12,0);
    poly1305_update(ctx, lens, 16);
    poly1305_final(ctx, tag);
}

void chacha20poly1305_encrypt(
        const uint8_t key[32], const uint8_t nonce[12],
        const uint8_t *aad, size_t aad_len,
        const uint8_t *pt, size_t len,
        uint8_t *ct, uint8_t tag[16]) {
    memcpy(ct, pt, len);
    chacha20_xor(key, nonce, 1, ct, len);
    aead_mac(key, nonce, aad, aad_len, ct, len, tag);
}

bool chacha20poly1305_decrypt(
        const uint8_t key[32], const uint8_t nonce[12],
        const uint8_t *aad, size_t aad_len,
        const uint8_t *ct, size_t len,
        uint8_t *pt, const uint8_t expected_tag[16]) {
    uint8_t tag[16];
    aead_mac(key, nonce, aad, aad_len, ct, len, tag);
    uint8_t diff = 0;
    for (int i = 0; i < 16; i++) diff |= tag[i] ^ expected_tag[i];
    if (diff) return false;
    memcpy(pt, ct, len);
    chacha20_xor(key, nonce, 1, pt, len);
    return true;
}
