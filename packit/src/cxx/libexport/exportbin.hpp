#pragma once
#include "crypto.hpp"
#include <cstdint>
#include <vector>
#include <string>

// .packit doc
//
// file: magic(4) + version(1) + nonce(12) + ciphertext + tag(16)
//
// plaintext: magic(4) + version(1) + ts(4 BE) + user_id(8 BE) +
//            num_blocks(1) + blocks[]
//
// block: key_len(1) + key(utf8) + data_len(4 BE) + payload(utf8 json)
//
// key = HKDF-SHA256(ikm=user_id(8 LE)||install_ts(4 LE),
//                   salt="packit-v3-export",
//                   info="chacha20poly1305-key", len=32)

struct PackitBlock {
    std::string key;
    std::string payload;
};

enum class PackitErr {
    OK = 0,
    BAD_MAGIC,
    BAD_VERSION,
    TAG_MISMATCH,
    TRUNCATED,
    KEY_TOO_LONG,
    PAYLOAD_TOO_LARGE,
};

const char *packit_err_str(PackitErr e);

using PackitRng = void(*)(uint8_t*, size_t);

struct WriteResult {
    std::vector<uint8_t> data;
    PackitErr err = PackitErr::OK;
};

struct ReadResult {
    std::vector<PackitBlock> blocks;
    int64_t   user_id   = 0;
    uint32_t  timestamp = 0;
    PackitErr err = PackitErr::OK;
};

WriteResult packit_write(
        int64_t  user_id,
        uint32_t install_ts,
        uint32_t timestamp,
        const std::vector<PackitBlock> &blocks,
        PackitRng rng);

ReadResult packit_read(
        const uint8_t *file_data, size_t file_len,
        int64_t  user_id,
        uint32_t install_ts);

// expose for tests
void derive_key(int64_t user_id, uint32_t install_ts, uint8_t key[32]);
