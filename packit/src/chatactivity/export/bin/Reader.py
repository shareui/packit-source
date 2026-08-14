# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import json
import os
import ctypes

from .Writer import _get_configs_dir, _get_lib, _FILE_NAMES


def _write_blocks(blocks: dict, account_id: str):
    configs_dir = _get_configs_dir()
    os.makedirs(configs_dir, exist_ok=True)
    logx(f"exportBin: restoring {len(blocks)} blocks for account {account_id[:8]}...", True)

    for key, payload in blocks.items():
        filename = _FILE_NAMES.get(key)
        if not filename:
            logx(f"exportBin: unknown block key '{key}', skipping", True)
            continue

        if key == "achievements":
            _merge_achievements(payload, account_id)
        else:
            out_path = os.path.join(configs_dir, filename)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(payload)
            logx(f"exportBin: restored '{key}' ({len(payload)} bytes)", True)


def _merge_achievements(payload: str, account_id: str):
    try:
        incoming = json.loads(payload)
    except Exception as e:
        logx(f"exportBin: achievements parse error: {e}", False)
        return

    def _is_hashed_id(k: str) -> bool:
        return len(k) == 16 and all(c in "0123456789abcdef" for c in k)

    if incoming and all(_is_hashed_id(k) for k in incoming):
        account_data = incoming.get(account_id, {})
        logx(f"exportBin: achievements per-account format, keys={list(incoming.keys())[:3]}", True)
    else:
        account_data = incoming
        logx("exportBin: achievements flat format", True)

    # strip sig wrappers from legacy exports
    depth = 0
    while isinstance(account_data, dict) and "d" in account_data and "s" in account_data and depth < 20:
        account_data = account_data["d"]
        depth += 1

    from ....ui.achievementsactivity.service.AchivementsEngine import load_account_data_for_import
    load_account_data_for_import(account_id, account_data)
    logx(f"exportBin: merged achievements for account {account_id}", True)


def read_file(file_path: str, user_id: int, install_ts: int) -> tuple:
    logx(f"exportBin: read file={os.path.basename(file_path)} user_id={user_id}", True)
    lib = _get_lib()

    keys_buf     = ctypes.c_char_p()
    keys_len     = ctypes.c_size_t()
    payloads_buf = ctypes.c_char_p()
    payloads_len = ctypes.c_size_t()
    out_uid      = ctypes.c_int64()
    out_ts       = ctypes.c_uint32()

    n = lib.packit_read_file(
        file_path.encode("utf-8"),
        ctypes.c_int64(user_id),
        ctypes.c_uint32(install_ts),
        ctypes.byref(keys_buf),     ctypes.byref(keys_len),
        ctypes.byref(payloads_buf), ctypes.byref(payloads_len),
        ctypes.byref(out_uid),      ctypes.byref(out_ts),
    )

    if n < 0:
        err = lib.packit_last_error().decode("utf-8", errors="replace")
        logx(f"exportBin: read failed: {err}", True)
        raise RuntimeError(f"packit_read_file failed: {err}")

    def _split_buf(buf, length):
        raw = ctypes.string_at(buf, length)
        return [s.decode("utf-8") for s in raw.split(b"\x00") if s]

    try:
        keys     = _split_buf(keys_buf,     keys_len.value)
        payloads = _split_buf(payloads_buf, payloads_len.value)
    finally:
        lib.packit_free_buf(keys_buf)
        lib.packit_free_buf(payloads_buf)

    blocks = dict(zip(keys, payloads))
    logx(f"exportBin: read ok, {n} blocks={list(blocks.keys())} export_user_id={out_uid.value}", True)
    return blocks, int(out_uid.value)