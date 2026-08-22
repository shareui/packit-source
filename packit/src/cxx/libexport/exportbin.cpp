#include "exportbin.hpp"
#include <cstring>

static const uint8_t PACKIT_MAGIC[4]  = {'P','C','K','T'};
static const uint8_t PACKIT_VERSION   = 3;
static const char   *PACKIT_SALT      = "packit-v3-export";
static const char   *PACKIT_INFO      = "chacha20poly1305-key";

// layout
//   [0:4]    magic       "PCKT"
//   [4]      version     u8 = 3
//   [5:9]    install_ts  u32 LE
//   [9:21]   nonce       12 bytes
//   [21:N]   ciphertext  ChaCha20-Poly1305(pt, key, nonce, aad=install_ts)
//   [N:N+16] tag

static inline void store_u32_le(uint8_t *p, uint32_t v) {
    p[0]=v&0xFF; p[1]=(v>>8)&0xFF; p[2]=(v>>16)&0xFF; p[3]=(v>>24)&0xFF;
}
static inline uint32_t load_u32_le(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static inline void store_u32_be(uint8_t *p, uint32_t v) {
    p[0]=(v>>24)&0xFF; p[1]=(v>>16)&0xFF; p[2]=(v>>8)&0xFF; p[3]=v&0xFF;
}
static inline uint32_t load_u32_be(const uint8_t *p) {
    return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|(uint32_t)p[3];
}
static inline void store_i64_be(uint8_t *p, int64_t v) {
    uint64_t u=(uint64_t)v;
    for(int i=7;i>=0;i--){p[i]=u&0xFF;u>>=8;}
}
static inline int64_t load_i64_be(const uint8_t *p) {
    uint64_t u=0;
    for(int i=0;i<8;i++) u=(u<<8)|p[i];
    return (int64_t)u;
}

void derive_key(int64_t user_id, uint32_t install_ts, uint8_t key[32]) {
    uint8_t ikm[12];
    store64_le(ikm,   (uint64_t)user_id);
    store32_le(ikm+8, install_ts);
    hkdf_sha256(ikm, 12,
                (const uint8_t*)PACKIT_SALT, strlen(PACKIT_SALT),
                (const uint8_t*)PACKIT_INFO, strlen(PACKIT_INFO),
                key, 32);
}

const char *packit_err_str(PackitErr e) {
    switch(e) {
        case PackitErr::OK:               return "ok";
        case PackitErr::BAD_MAGIC:        return "bad magic";
        case PackitErr::BAD_VERSION:      return "bad version";
        case PackitErr::TAG_MISMATCH:     return "tag mismatch (tampered or wrong key)";
        case PackitErr::TRUNCATED:        return "truncated";
        case PackitErr::KEY_TOO_LONG:     return "block key too long";
        case PackitErr::PAYLOAD_TOO_LARGE:return "payload too large";
    }
    return "unknown";
}

WriteResult packit_write(
        int64_t  user_id,
        uint32_t install_ts,
        uint32_t timestamp,
        const std::vector<PackitBlock> &blocks,
        PackitRng rng) {

    WriteResult res;

    for (const auto &b : blocks) {
        if (b.key.size() > 255)
            { res.err = PackitErr::KEY_TOO_LONG; return res; }
        if (b.payload.size() > 0xFFFFFFFFu)
            { res.err = PackitErr::PAYLOAD_TOO_LARGE; return res; }
    }

    std::vector<uint8_t> pt;
    pt.insert(pt.end(), PACKIT_MAGIC, PACKIT_MAGIC+4);
    pt.push_back(PACKIT_VERSION);
    uint8_t tmp[8];
    store_u32_be(tmp, timestamp); pt.insert(pt.end(), tmp, tmp+4);
    store_i64_be(tmp, user_id);   pt.insert(pt.end(), tmp, tmp+8);
    pt.push_back((uint8_t)blocks.size());

    for (const auto &b : blocks) {
        uint8_t klen = (uint8_t)b.key.size();
        pt.push_back(klen);
        pt.insert(pt.end(), b.key.begin(), b.key.end());
        store_u32_be(tmp, (uint32_t)b.payload.size());
        pt.insert(pt.end(), tmp, tmp+4);
        pt.insert(pt.end(), b.payload.begin(), b.payload.end());
    }

    uint8_t key[32], nonce[12], tag[16];
    derive_key(user_id, install_ts, key);
    rng(nonce, 12);

    // install_ts as AAD — authenticated but not encrypted
    uint8_t aad[4]; store_u32_le(aad, install_ts);

    std::vector<uint8_t> ct(pt.size());
    chacha20poly1305_encrypt(key, nonce, aad, 4,
                              pt.data(), pt.size(), ct.data(), tag);

    // header: magic(4) + version(1) + install_ts(4 LE) + nonce(12)
    res.data.insert(res.data.end(), PACKIT_MAGIC, PACKIT_MAGIC+4);
    res.data.push_back(PACKIT_VERSION);
    res.data.insert(res.data.end(), aad, aad+4);      // install_ts plaintext
    res.data.insert(res.data.end(), nonce, nonce+12);
    res.data.insert(res.data.end(), ct.begin(), ct.end());
    res.data.insert(res.data.end(), tag, tag+16);
    return res;
}

ReadResult packit_read(
        const uint8_t *file_data, size_t file_len,
        int64_t  user_id,
        uint32_t /*install_ts_hint*/) {   // ignored — read from file

    ReadResult res;

    // min: magic(4)+version(1)+install_ts(4)+nonce(12)+tag(16) = 37
    if (file_len < 37) { res.err = PackitErr::TRUNCATED; return res; }
    if (memcmp(file_data, PACKIT_MAGIC, 4) != 0)
        { res.err = PackitErr::BAD_MAGIC; return res; }
    if (file_data[4] != PACKIT_VERSION)
        { res.err = PackitErr::BAD_VERSION; return res; }

    // read install_ts from file (plaintext AAD)
    uint32_t install_ts = load_u32_le(file_data + 5);

    const uint8_t *nonce  = file_data + 9;
    const uint8_t *ct     = file_data + 21;
    size_t         ct_len = file_len - 21 - 16;
    const uint8_t *tag    = file_data + file_len - 16;

    uint8_t key[32];
    derive_key(user_id, install_ts, key);

    uint8_t aad[4]; store_u32_le(aad, install_ts);

    std::vector<uint8_t> pt(ct_len);
    if (!chacha20poly1305_decrypt(key, nonce, aad, 4,
                                   ct, ct_len, pt.data(), tag)) {
        res.err = PackitErr::TAG_MISMATCH;
        return res;
    }

    if (pt.size() < 18) { res.err = PackitErr::TRUNCATED; return res; }
    if (memcmp(pt.data(), PACKIT_MAGIC, 4) != 0)
        { res.err = PackitErr::BAD_MAGIC; return res; }
    if (pt[4] != PACKIT_VERSION)
        { res.err = PackitErr::BAD_VERSION; return res; }

    res.timestamp   = load_u32_be(pt.data() + 5);
    res.user_id     = load_i64_be(pt.data() + 9);
    uint8_t nblocks = pt[17];

    size_t off = 18;
    for (int i = 0; i < nblocks; i++) {
        if (off + 1 > pt.size()) { res.err = PackitErr::TRUNCATED; return res; }
        uint8_t klen = pt[off++];
        if (off + klen > pt.size()) { res.err = PackitErr::TRUNCATED; return res; }
        std::string bkey((char*)(pt.data()+off), klen); off += klen;
        if (off + 4 > pt.size()) { res.err = PackitErr::TRUNCATED; return res; }
        uint32_t dlen = load_u32_be(pt.data()+off); off += 4;
        if (off + dlen > pt.size()) { res.err = PackitErr::TRUNCATED; return res; }
        std::string payload((char*)(pt.data()+off), dlen); off += dlen;
        res.blocks.push_back({bkey, payload});
    }

    return res;
}
