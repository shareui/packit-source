#pragma once
#include <cstdint>
#include <cstring>
#include <cstdio>

// little-endian store helpers used by exportbin.cpp
inline void store32_le(uint8_t *p, uint32_t v) {
    p[0]=v&0xFF; p[1]=(v>>8)&0xFF; p[2]=(v>>16)&0xFF; p[3]=(v>>24)&0xFF;
}
inline void store64_le(uint8_t *p, uint64_t v) {
    store32_le(p, (uint32_t)(v&0xFFFFFFFF));
    store32_le(p+4, (uint32_t)(v>>32));
}


// SHA-256
struct Sha256Ctx {
    uint32_t h[8];
    uint8_t  buf[64];
    uint64_t bits;
    uint32_t buflen;
};

void sha256_init(Sha256Ctx &ctx);
void sha256_update(Sha256Ctx &ctx, const uint8_t *data, size_t len);
void sha256_final(Sha256Ctx &ctx, uint8_t out[32]);
void sha256(const uint8_t *data, size_t len, uint8_t out[32]);

// HMAC-SHA256
void hmac_sha256(const uint8_t *key, size_t klen,
                 const uint8_t *msg, size_t mlen,
                 uint8_t out[32]);

// HKDF-SHA256 (RFC 5869), max okm_len = 255*32
void hkdf_sha256(const uint8_t *ikm,  size_t ikm_len,
                 const uint8_t *salt, size_t salt_len,
                 const uint8_t *info, size_t info_len,
                 uint8_t *okm, size_t okm_len);

// ChaCha20 (RFC 8439) — encrypt/decrypt in-place
void chacha20_xor(const uint8_t key[32], const uint8_t nonce[12],
                  uint32_t counter,
                  uint8_t *buf, size_t len);

// Poly1305 (RFC 8439)
struct Poly1305Ctx {
    uint32_t r[5];
    uint32_t h[5];
    uint32_t pad[4];
    uint8_t  buf[16];
    size_t   buflen;
};

void poly1305_init(Poly1305Ctx &ctx, const uint8_t key[32]);
void poly1305_update(Poly1305Ctx &ctx, const uint8_t *data, size_t len);
void poly1305_final(Poly1305Ctx &ctx, uint8_t mac[16]);

// ChaCha20-Poly1305 AEAD (RFC 8439)
void chacha20poly1305_encrypt(
        const uint8_t key[32], const uint8_t nonce[12],
        const uint8_t *aad, size_t aad_len,
        const uint8_t *pt,  size_t len,
        uint8_t *ct, uint8_t tag[16]);

// returns false if tag mismatch
bool chacha20poly1305_decrypt(
        const uint8_t key[32], const uint8_t nonce[12],
        const uint8_t *aad, size_t aad_len,
        const uint8_t *ct,  size_t len,
        uint8_t *pt, const uint8_t expected_tag[16]);
