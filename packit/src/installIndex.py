import json
import os
import re
import threading

from android_utils import log

_lock = threading.Lock()

_pending = None


def _get_index_path(pkg: str, rm_rid: str) -> str:
    return f"/data/data/{pkg}/files/packitCache/reposCache/{rm_rid}-index.json"


def _strip_version(raw: str) -> str:
    # keep only digits and dots
    return re.sub(r"[^0-9.]", "", str(raw or "")).strip(".")


def set_pending(plugin_info: dict, rm_rid: str):
    # called right before showInstallDialog for PluginsController path
    global _pending
    with _lock:
        _pending = (plugin_info, rm_rid)


def clear_pending():
    global _pending
    with _lock:
        _pending = None


def commit_pending():
    global _pending
    with _lock:
        entry = _pending
        _pending = None

    if not entry:
        return

    plugin_info, rm_rid = entry
    if not rm_rid:
        log("installIndex: no rm_rid, skipping")
        return

    try:
        from org.telegram.messenger import ApplicationLoader
        pkg = ApplicationLoader.applicationContext.getPackageName()
    except Exception as e:
        log(f"installIndex: cannot get pkg: {e}")
        return

    plugin_id = str(plugin_info.get("id") or "")
    if not plugin_id:
        log("installIndex: no plugin id, skipping")
        return

    version = _strip_version(plugin_info.get("version") or "")
    state = str(plugin_info.get("state") or "")
    candidate_path = f"/data/data/{pkg}/files/plugins/{plugin_id}.py"
    local_path = candidate_path if os.path.exists(candidate_path) else "Unknown"
    file_type = "plugin"
    hash_val = str(plugin_info.get("hash") or "")
    bithash_val = str(plugin_info.get("bithash") or "")

    record = {
        "id": plugin_id,
        "version": version,
        "state": state,
        "local_path": local_path,
        "file_type": file_type,
        "hash": hash_val,
        "bithash": bithash_val,
    }

    index_path = _get_index_path(pkg, rm_rid)
    try:
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}

        data[plugin_id] = record

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        log(f"installIndex: wrote entry for '{plugin_id}' in '{rm_rid}-index.json'")
    except Exception as e:
        log(f"installIndex: write error for '{plugin_id}': {e}")
