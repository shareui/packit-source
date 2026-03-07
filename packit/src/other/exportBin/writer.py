import os
import json
import struct
import random
import string
from android_utils import log
try:
    from org.telegram.messenger import ApplicationLoader, UserConfig
except Exception as e:
    import android_utils as _au; _au.log(f"exportBin.writer: import failed: {e}")

# packit binary export format (.packit)
#
# file layout (after decryption):
#   [0:4]   magic      b"PCKT"
#   [4]     version    u8 = 2
#   [5:9]   ts         u32 big-endian unix timestamp
#   [9:17]  user_id    i64 big-endian telegram user id
#   [17]    num_blocks u8
#
#   for each block:
#     [0]          key_len  u8
#     [1:1+kl]     key      utf-8
#     [kl+1:kl+5]  data_len u32 big-endian
#     [kl+5:...]   payload  raw utf-8 json
#
# encryption:
#   the entire plaintext above is encrypted with _cipher()
#   seed = (ts ^ user_id) & 0xFFFFFFFF
#   file starts with 4-byte LE seed so reader can decrypt without
#   knowing user_id upfront (user_id check happens after decryption)

_MAGIC = b"PCKT"
_FORMAT_VERSION = 2

_BLOCK_KEYS = ["achievements", "installDate", "localConfig"]

_FILE_NAMES = {
    "achievements": "achievements.json",
    "installDate":  "installDate.json",
    "localConfig":  "localConfig.json",
}

def _lcg_stream(seed: int, length: int) -> bytearray:
    # LCG keystream, Knuth MMIX constants
    # high byte used — better distribution than low byte in LCG
    a = 6364136223846793005
    c = 1442695040888963407
    m = 2 ** 64
    state = seed & 0xFFFFFFFFFFFFFFFF
    out = bytearray(length)
    for i in range(length):
        state = (a * state + c) % m
        out[i] = (state >> 56) & 0xFF
    return out


def _shuffle_blocks(data: bytearray, seed: int, reverse: bool) -> bytearray:
    # permutes 8-byte blocks; tail bytes left untouched
    bsize = 8
    n = len(data) // bsize
    if n < 2:
        return data

    indices = list(range(n))
    rng = random.Random(seed ^ 0xDEADBEEF)
    rng.shuffle(indices)

    if reverse:
        restored = [0] * n
        for newPos, origPos in enumerate(indices):
            restored[origPos] = newPos
        indices = restored

    result = bytearray(len(data))
    for i, src in enumerate(indices):
        result[i * bsize:(i + 1) * bsize] = data[src * bsize:(src + 1) * bsize]
    tail_start = n * bsize
    result[tail_start:] = data[tail_start:]
    return result


def _cipher(data: bytes, seed: int) -> bytes:
    buf = bytearray(data)
    stream = _lcg_stream(seed, len(buf))
    for i in range(len(buf)):
        buf[i] ^= stream[i]
    return bytes(_shuffle_blocks(buf, seed, reverse=False))


def _decipher(data: bytes, seed: int) -> bytes:
    buf = bytearray(data)
    buf = _shuffle_blocks(buf, seed, reverse=True)
    stream = _lcg_stream(seed, len(buf))
    for i in range(len(buf)):
        buf[i] ^= stream[i]
    return bytes(buf)


def _get_configs_dir() -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache/packitConfigs"


def _get_user_id() -> int:
    try:
        account = getattr(UserConfig, "selectedAccount", 0)
        uc = UserConfig.getInstance(account)
        return int(uc.getClientUserId())
    except Exception as e:
        log(f"exportBin.writer._get_user_id: {e}")
        return 0


def _read_block(key: str) -> bytes:
    path = os.path.join(_get_configs_dir(), _FILE_NAMES[key])
    if not os.path.exists(path):
        return b"{}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        json.loads(content)
        return content.encode("utf-8")
    except Exception as e:
        log(f"exportBin.writer._read_block: error reading '{key}': {e}")
        return b"{}"


def _rand_suffix(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _pack_block(key: str, payload: bytes) -> bytes:
    keyBytes = key.encode("utf-8")
    if len(keyBytes) > 255:
        raise ValueError(f"block key too long: {key}")
    return struct.pack(">B", len(keyBytes)) + keyBytes + struct.pack(">I", len(payload)) + payload


# pub api 

def build_binary() -> bytes:
    import time
    ts = int(time.time())
    userId = _get_user_id()
    seed = (ts ^ userId) & 0xFFFFFFFF

    blocks = b"".join(_pack_block(k, _read_block(k)) for k in _BLOCK_KEYS)

    plaintext = (
        _MAGIC
        + struct.pack(">B", _FORMAT_VERSION)
        + struct.pack(">I", ts)
        + struct.pack(">q", userId)
        + struct.pack(">B", len(_BLOCK_KEYS))
        + blocks
    )

    encrypted = _cipher(plaintext, seed)
    # prepend seed (4 bytes LE) so reader can decrypt
    return struct.pack("<I", seed) + encrypted


def export_to_downloads(download_path: str) -> str:
    os.makedirs(download_path, exist_ok=True)
    filename = f"backup-{_rand_suffix(4)}.packit"
    out_path = os.path.join(download_path, filename)
    data = build_binary()
    with open(out_path, "wb") as f:
        f.write(data)
    log(f"exportBin.writer: exported {len(data)} bytes to {out_path}")
    return out_path
