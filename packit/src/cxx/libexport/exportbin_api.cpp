#include "exportbin.hpp"
#include <cstring>
#include <cstdlib>
#include <fcntl.h>
#include <unistd.h>

// localuse library written entirely by @shareui

// documentation provided, good luck with the fork

// ctypes API Python
//
// write:
//   packit_write_file(user_id, install_ts, timestamp,
//                     keys_json,     -- JSON array of block key strings
//                     payloads_json, -- JSON array of payload strings (same order)
//                     out_path)      -- output file path
//   returns 0 on success, -1 on error
//
// read:
//   packit_read_file(file_path, user_id, install_ts,
//                    out_keys_buf,     out_keys_len,
//                    out_payloads_buf, out_payloads_len,
//                    out_user_id,      out_timestamp)
//   returns number of blocks on success, -1 on error
//   caller must free out_keys_buf and out_payloads_buf with packit_free_buf
//
//   out_keys_buf / out_payloads_buf are null-terminated strings of the form:
//     "key0\0key1\0key2\0"  -- each block's key/payload separated by \0
//
//   packit_last_error() returns last error string (static, valid until next call)

extern "C" {

// ----------------------------------------------------------------
// random via /dev/urandom
// ----------------------------------------------------------------

static void urandom_rng(uint8_t *buf, size_t len) {
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd < 0) {
        // fallback: fill with counter (should never happen on Android)
        static uint64_t ctr = 0x5EED5EED5EED5EEDULL;
        for (size_t i = 0; i < len; i++) {
            ctr ^= ctr << 13; ctr ^= ctr >> 7; ctr ^= ctr << 17;
            buf[i] = (uint8_t)(ctr & 0xFF);
        }
        return;
    }
    size_t done = 0;
    while (done < len) {
        ssize_t n = read(fd, buf + done, len - done);
        if (n > 0) done += (size_t)n;
    }
    close(fd);
}

// ----------------------------------------------------------------
// error buffer
// ----------------------------------------------------------------

static char g_last_error[256] = "";

static void set_error(const char *msg) {
    strncpy(g_last_error, msg, sizeof(g_last_error) - 1);
    g_last_error[sizeof(g_last_error) - 1] = '\0';
}

const char *packit_last_error() {
    return g_last_error;
}

// ----------------------------------------------------------------
// minimal JSON array parser — reads ["a","b","c"]
// returns number of strings parsed, fills out[] with malloc'd copies
// caller must free each out[i]
// ----------------------------------------------------------------

static int parse_json_str_array(const char *json, char **out, int maxn) {
    int n = 0;
    const char *p = json;
    while (*p && *p != '[') p++;
    if (*p != '[') return -1;
    p++;
    while (*p && n < maxn) {
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r' || *p == ',') p++;
        if (*p == ']') break;
        if (*p != '"') return -1;
        p++;
        // collect string with \uXXXX and \\ support
        char buf[65536]; int bi = 0;
        while (*p && *p != '"' && bi < (int)sizeof(buf) - 1) {
            if (*p == '\\') {
                p++;
                if (!*p) break;
                if (*p == '"' || *p == '\\' || *p == '/') buf[bi++] = *p;
                else if (*p == 'n') buf[bi++] = '\n';
                else if (*p == 't') buf[bi++] = '\t';
                else if (*p == 'r') buf[bi++] = '\r';
                else if (*p == 'u' && p[1] && p[2] && p[3] && p[4]) {
                    // decode \uXXXX to UTF-8
                    unsigned cp = 0;
                    for (int k = 1; k <= 4; k++) {
                        char h = p[k];
                        unsigned d = (h>='0'&&h<='9') ? (unsigned)(h-'0') :
                                     (h>='a'&&h<='f') ? (unsigned)(h-'a'+10) :
                                     (h>='A'&&h<='F') ? (unsigned)(h-'A'+10) : 0;
                        cp = (cp << 4) | d;
                    }
                    p += 4;
                    if (cp < 0x80) {
                        buf[bi++] = (char)cp;
                    } else if (cp < 0x800) {
                        if (bi < (int)sizeof(buf)-2) {
                            buf[bi++] = (char)(0xC0|(cp>>6));
                            buf[bi++] = (char)(0x80|(cp&0x3F));
                        }
                    } else {
                        if (bi < (int)sizeof(buf)-3) {
                            buf[bi++] = (char)(0xE0|(cp>>12));
                            buf[bi++] = (char)(0x80|((cp>>6)&0x3F));
                            buf[bi++] = (char)(0x80|(cp&0x3F));
                        }
                    }
                }
            } else {
                buf[bi++] = *p;
            }
            p++;
        }
        if (*p == '"') p++;
        buf[bi] = '\0';
        out[n] = (char*)malloc(bi + 1);
        if (!out[n]) return -1;
        memcpy(out[n], buf, bi + 1);
        n++;
    }
    return n;
}

// ----------------------------------------------------------------
// write
// ----------------------------------------------------------------

int packit_write_file(
        int64_t  user_id,
        uint32_t install_ts,
        uint32_t timestamp,
        const char *keys_json,
        const char *payloads_json,
        const char *out_path) {

    g_last_error[0] = '\0';

    static const int MAX_BLOCKS = 64;
    char *keys[MAX_BLOCKS]     = {};
    char *payloads[MAX_BLOCKS] = {};

    int nk = parse_json_str_array(keys_json,     keys,     MAX_BLOCKS);
    int np = parse_json_str_array(payloads_json, payloads, MAX_BLOCKS);

    if (nk < 0 || np < 0 || nk != np) {
        set_error("failed to parse keys/payloads JSON arrays");
        for (int i = 0; i < MAX_BLOCKS; i++) { free(keys[i]); free(payloads[i]); }
        return -1;
    }

    std::vector<PackitBlock> blocks;
    blocks.reserve((size_t)nk);
    for (int i = 0; i < nk; i++) {
        blocks.push_back({std::string(keys[i]), std::string(payloads[i])});
        free(keys[i]); free(payloads[i]);
    }

    auto wr = packit_write(user_id, install_ts, timestamp, blocks, urandom_rng);
    if (wr.err != PackitErr::OK) {
        set_error(packit_err_str(wr.err));
        return -1;
    }

    int fd = open(out_path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0) { set_error("failed to open output file"); return -1; }
    size_t done = 0;
    while (done < wr.data.size()) {
        ssize_t n = write(fd, wr.data.data() + done, wr.data.size() - done);
        if (n <= 0) { close(fd); set_error("write error"); return -1; }
        done += (size_t)n;
    }
    close(fd);
    return 0;
}

// ----------------------------------------------------------------
// read
// ----------------------------------------------------------------

// out_keys_buf / out_payloads_buf: caller passes pointer to char*,
// function allocates and fills, caller must free with packit_free_buf.
// format: "key0\0key1\0key2\0" (each entry null-terminated, packed)
// out_keys_len / out_payloads_len: total byte length of each buffer.

int packit_read_file(
        const char *file_path,
        int64_t     user_id,
        uint32_t    install_ts,
        char      **out_keys_buf,     size_t *out_keys_len,
        char      **out_payloads_buf, size_t *out_payloads_len,
        int64_t    *out_user_id,
        uint32_t   *out_timestamp) {

    g_last_error[0] = '\0';
    *out_keys_buf     = nullptr; *out_keys_len     = 0;
    *out_payloads_buf = nullptr; *out_payloads_len = 0;
    *out_user_id = 0; *out_timestamp = 0;

    int fd = open(file_path, O_RDONLY);
    if (fd < 0) { set_error("failed to open file"); return -1; }

    // read all
    std::vector<uint8_t> raw;
    uint8_t tmp[4096];
    ssize_t n;
    while ((n = read(fd, tmp, sizeof(tmp))) > 0)
        raw.insert(raw.end(), tmp, tmp + n);
    close(fd);

    if (raw.empty()) { set_error("empty file"); return -1; }

    auto rd = packit_read(raw.data(), raw.size(), user_id, install_ts);
    if (rd.err != PackitErr::OK) {
        set_error(packit_err_str(rd.err));
        return -1;
    }

    // pack keys and payloads into flat null-separated buffers
    size_t kbytes = 0, pbytes = 0;
    for (const auto &b : rd.blocks) {
        kbytes += b.key.size()     + 1;
        pbytes += b.payload.size() + 1;
    }

    char *kbuf = (char*)malloc(kbytes ? kbytes : 1);
    char *pbuf = (char*)malloc(pbytes ? pbytes : 1);
    if (!kbuf || !pbuf) {
        free(kbuf); free(pbuf);
        set_error("out of memory");
        return -1;
    }

    size_t koff = 0, poff = 0;
    for (const auto &b : rd.blocks) {
        memcpy(kbuf + koff, b.key.data(),     b.key.size());     kbuf[koff + b.key.size()]     = '\0'; koff += b.key.size()     + 1;
        memcpy(pbuf + poff, b.payload.data(), b.payload.size()); pbuf[poff + b.payload.size()] = '\0'; poff += b.payload.size() + 1;
    }

    *out_keys_buf     = kbuf;  *out_keys_len     = kbytes;
    *out_payloads_buf = pbuf;  *out_payloads_len = pbytes;
    *out_user_id   = rd.user_id;
    *out_timestamp = rd.timestamp;
    return (int)rd.blocks.size();
}

// ----------------------------------------------------------------
// free buffer allocated by packit_read_file
// ----------------------------------------------------------------

void packit_free_buf(char *buf) {
    free(buf);
}

} // extern "C"
