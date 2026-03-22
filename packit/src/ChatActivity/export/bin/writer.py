import os
import json
import random
import string
import time
import ctypes
from android_utils import log
try:
    from org.telegram.messenger import ApplicationLoader, UserConfig
except Exception as e:
    import android_utils as _au; _au.log(f"exportBin.writer: import failed: {e}")

_BLOCK_KEYS = ["achievements", "installDate", "localConfig"]

_FILE_NAMES = {
    "achievements": "achievements.json",
    "installDate":  "installDate.json",
    "localConfig":  "localConfig.json",
}


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


def _get_install_ts() -> int:
    try:
        path = os.path.join(_get_configs_dir(), "installDate.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = int(data.get("ts", 0))
            log(f"exportBin: install_ts={ts}")
            return ts
    except Exception as e:
        log(f"exportBin.writer._get_install_ts: {e}")
    log("exportBin: install_ts=0 (not found)")
    return 0


def _get_lib():
    so_path = os.path.join(
        os.path.dirname(__file__),
        "../../../../res/native/libexport.so"
    )
    so_path = os.path.normpath(so_path)
    lib = ctypes.CDLL(so_path)
    lib.packit_write_file.restype  = ctypes.c_int
    lib.packit_write_file.argtypes = [
        ctypes.c_int64, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
    ]
    lib.packit_read_file.restype  = ctypes.c_int
    lib.packit_read_file.argtypes = [
        ctypes.c_char_p, ctypes.c_int64, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_int64),  ctypes.POINTER(ctypes.c_uint32),
    ]
    lib.packit_free_buf.restype  = None
    lib.packit_free_buf.argtypes = [ctypes.c_char_p]
    lib.packit_last_error.restype  = ctypes.c_char_p
    lib.packit_last_error.argtypes = []
    return lib


def _read_achievements_block() -> str:
    try:
        from ....ui.AchievementsActivity.service.AchivementsEngine import (
            _load_account, _get_current_account_id
        )
        account_id = _get_current_account_id()
        data = _load_account(account_id)
        content = json.dumps({account_id: data}, ensure_ascii=False)
        log(f"exportBin: achievements block read ({len(content)} bytes)")
        return content
    except Exception as e:
        log(f"exportBin: achievements block read error: {e}")
        return "{}"


def _read_block(key: str) -> str:
    if key == "achievements":
        return _read_achievements_block()
    path = os.path.join(_get_configs_dir(), _FILE_NAMES[key])
    if not os.path.exists(path):
        log(f"exportBin: block '{key}' not found, using {{}}")
        return "{}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        json.loads(content)
        log(f"exportBin: block '{key}' read ({len(content)} bytes)")
        return content
    except Exception as e:
        log(f"exportBin: block '{key}' read error: {e}")
        return "{}"


def _rand_suffix(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def build_binary() -> bytes:
    user_id    = _get_user_id()
    install_ts = _get_install_ts()
    ts         = int(time.time())
    log(f"exportBin: write user_id={user_id} install_ts={install_ts} ts={ts}")

    lib = _get_lib()

    keys     = json.dumps(_BLOCK_KEYS)
    payloads = json.dumps([_read_block(k) for k in _BLOCK_KEYS])

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
            log(f"exportBin: packit_write_file failed: {err}")
            raise RuntimeError(f"packit_write_file failed: {err}")
        size = os.path.getsize(tmp_path)
        log(f"exportBin: write ok, {size} bytes")
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
    log(f"exportBin: exported to {out_path}")
    return out_path
