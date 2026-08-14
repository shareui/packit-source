# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os
import json
import random
import string
import time
import ctypes

try:
    from org.telegram.messenger import ApplicationLoader, UserConfig
except Exception as e:
    import android_utils as _au; _au.log(f"exportBin.writer: import failed: {e}")

_BLOCK_KEYS = ["achievements", "installDate", "localConfig", "saved_plugins"]

_FILE_NAMES = {
    "achievements":  "achievements.json",
    "installDate":   "installDate.json",
    "localConfig":   "localConfig.json",
    "saved_plugins": "saved_plugins.json",
}


def _get_configs_dir() -> str:
    from .....utils.Paths import getConfigsDir
    return getConfigsDir()


def _get_user_id() -> int:
    try:
        account = getattr(UserConfig, "selectedAccount", 0)
        uc = UserConfig.getInstance(account)
        return int(uc.getClientUserId())
    except Exception as e:
        logx(f"exportBin.writer._get_user_id: {e}", False)
        return 0


def _get_install_ts() -> int:
    try:
        path = os.path.join(_get_configs_dir(), "installDate.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = int(data.get("ts", 0))
            logx(f"exportBin: install_ts={ts}", True)
            return ts
    except Exception as e:
        logx(f"exportBin.writer._get_install_ts: {e}", False)
    logx("exportBin: install_ts=0 (not found)", True)
    return 0


def _get_lib():
    from .....core.NativeLoader import loadExport
    return loadExport()


def _read_achievements_block() -> str:
    try:
        from .....ui.achievements.service.AchivementsEngine import (
            _load_account, _get_current_account_id
        )
        account_id = _get_current_account_id()
        data, _ = _load_account(account_id)
        content = json.dumps({account_id: data}, ensure_ascii=False)
        logx(f"exportBin: achievements block read ({len(content)} bytes)", True)
        return content
    except Exception as e:
        logx(f"exportBin: achievements block read error: {e}", False)
        return "{}"


def _read_saved_plugins_block() -> str:
    try:
        from .....ui.plugin.Fragment import _read_saved_plugins
        data = _read_saved_plugins()
        content = json.dumps(data, ensure_ascii=False)
        logx(f"exportBin: saved_plugins block read ({len(data)} items)", True)
        return content
    except Exception as e:
        logx(f"exportBin: saved_plugins block read error: {e}", False)
        return "[]"


def _read_block(key: str) -> str:
    if key == "achievements":
        return _read_achievements_block()
    if key == "saved_plugins":
        return _read_saved_plugins_block()
    path = os.path.join(_get_configs_dir(), _FILE_NAMES[key])
    if not os.path.exists(path):
        logx(f"exportBin: block '{key}' not found, using {{}}", True)
        return "{}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        json.loads(content)
        logx(f"exportBin: block '{key}' read ({len(content)} bytes)", True)
        return content
    except Exception as e:
        logx(f"exportBin: block '{key}' read error: {e}", False)
        return "{}"


def _rand_suffix(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def build_binary(
    include_local_config: bool = True,
    include_achievements: bool = True,
    include_saved_plugins: bool = True,
) -> bytes:
    user_id    = _get_user_id()
    install_ts = _get_install_ts()
    ts         = int(time.time())
    logx(f"exportBin: write user_id={user_id} install_ts={install_ts} ts={ts}", True)
    logx(f"exportBin: flags local_config={include_local_config} achievements={include_achievements} saved_plugins={include_saved_plugins}", True)

    lib = _get_lib()

    active_keys = ["installDate"]
    if include_achievements:
        active_keys.append("achievements")
    if include_local_config:
        active_keys.append("localConfig")
    if include_saved_plugins:
        active_keys.append("saved_plugins")

    keys     = json.dumps(active_keys)
    payloads = json.dumps([_read_block(k) for k in active_keys])

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".packit", delete=False) as f:
        tmp_path = f.name

    try:
        rc = lib.packit_write_file(
            ctypes.c_int64(user_id),
            ctypes.c_uint32(install_ts),
            ctypes.c_uint32(ts),
            keys.encode("utf-8"),
            payloads.encode("utf-8"),
            tmp_path.encode("utf-8"),
        )
        if rc != 0:
            err = lib.packit_last_error().decode("utf-8", errors="replace")
            logx(f"exportBin: packit_write_file failed: {err}", True)
            raise RuntimeError(f"packit_write_file failed: {err}")
        size = os.path.getsize(tmp_path)
        logx(f"exportBin: write ok, {size} bytes", True)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def export_to_downloads(download_path: str) -> str:
    os.makedirs(download_path, exist_ok=True)
    filename = f"backup-{_rand_suffix(4)}.packit"
    out_path = os.path.join(download_path, filename)
    data = build_binary()
    with open(out_path, "wb") as f:
        f.write(data)
    logx(f"exportBin: exported to {out_path}", True)
    return out_path