import json
import os
import struct
from android_utils import log
from .writer import _decipher, _get_configs_dir, _FILE_NAMES, _MAGIC, _FORMAT_VERSION


def _parse_user_id(plaintext: bytes) -> int:
    # user_id is at [9:17], i64 big-endian
    return struct.unpack(">q", plaintext[9:17])[0]


def _parse_blocks(plaintext: bytes) -> dict:
    if plaintext[:4] != _MAGIC:
        raise ValueError("invalid magic bytes")

    version = struct.unpack(">B", plaintext[4:5])[0]
    if version != _FORMAT_VERSION:
        raise ValueError(f"unsupported format version: {version}")

    num_blocks = struct.unpack(">B", plaintext[17:18])[0]

    offset = 18
    blocks = {}
    for _ in range(num_blocks):
        key_len = struct.unpack(">B", plaintext[offset:offset + 1])[0]
        offset += 1
        key = plaintext[offset:offset + key_len].decode("utf-8")
        offset += key_len
        data_len = struct.unpack(">I", plaintext[offset:offset + 4])[0]
        offset += 4
        payload = plaintext[offset:offset + data_len].decode("utf-8")
        offset += data_len
        blocks[key] = payload

    return blocks


def _write_blocks(blocks: dict, account_id: str):
    configs_dir = _get_configs_dir()
    os.makedirs(configs_dir, exist_ok=True)

    for key, payload in blocks.items():
        filename = _FILE_NAMES.get(key)
        if not filename:
            log(f"exportBin.reader: unknown block key '{key}', skipping")
            continue

        if key == "achievements":
            _merge_achievements(payload, account_id)
        else:
            out_path = os.path.join(configs_dir, filename)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(payload)
            log(f"exportBin.reader: restored '{key}' -> {out_path}")


def _merge_achievements(payload: str, account_id: str):
    # account_id is already a hashed id (from achievements._hash_account_id)
    # payload may be flat {achievement: value} (exported before per-account refactor)
    # or already per-account {hashed_id: {achievement: value}}
    try:
        incoming = json.loads(payload)
    except Exception as e:
        log(f"exportBin.reader: failed to parse achievements payload: {e}")
        return

    # detect per-account format: all keys are 16-char hex strings
    def _is_hashed_id(k: str) -> bool:
        return len(k) == 16 and all(c in "0123456789abcdef" for c in k)

    if incoming and all(_is_hashed_id(k) for k in incoming):
        # per-account format — extract this account's data
        account_data = incoming.get(account_id, {})
    else:
        # flat format — the whole dict is one account's data
        account_data = incoming

    from ....ui.AchievementsActivity.service.AchivementsEngine import load_account_data_for_import
    load_account_data_for_import(account_id, account_data)
    log(f"exportBin.reader: merged achievements for account {account_id}")


def restore_from_file(file_path: str):
    with open(file_path, "rb") as f:
        raw = f.read()

    seed = struct.unpack("<I", raw[:4])[0]
    plaintext = _decipher(raw[4:], seed)
    account_id = str(_parse_user_id(plaintext))
    blocks = _parse_blocks(plaintext)
    _write_blocks(blocks, account_id)
