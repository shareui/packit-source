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


def _hash_matches(p: dict) -> bool:
    local_path = str(p.get("local_path") or "")
    try:
        from .hashUtil import matchesStoredHash
        return matchesStoredHash(
            local_path,
            sha256=str(p.get("hash") or ""),
            bithash=str(p.get("bithash") or ""),
            label=str(p.get("id") or local_path),
        )
    except Exception as e:
        log(f"installIndex.purge: hash check error for '{local_path}': {e}")
        return True


def purge_missing():
    # removes index entries whose file is absent or whose hash does not match
    try:
        from org.telegram.messenger import ApplicationLoader
        pkg = ApplicationLoader.applicationContext.getPackageName()
    except Exception as e:
        log(f"installIndex.purge: cannot get pkg: {e}")
        return

    try:
        from elyx import settings
        import json as _json
        repos_raw = settings.get("repositories", "[]")
        repos = _json.loads(repos_raw)
        if not isinstance(repos, list):
            repos = []
    except Exception as e:
        log(f"installIndex.purge: cannot read repos: {e}")
        return

    for repo in repos:
        rm_rid = str(repo.get("id") or "")
        if not rm_rid:
            continue

        index_path = _get_index_path(pkg, rm_rid)
        if not os.path.exists(index_path):
            continue

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue

            plugins = data.get("installed_plugins")
            if not isinstance(plugins, list):
                continue

            kept = []
            removed_missing = 0
            removed_hash = 0
            for p in plugins:
                local_path = str(p.get("local_path") or "")
                if not os.path.exists(local_path):
                    removed_missing += 1
                    continue
                if not _hash_matches(p):
                    removed_hash += 1
                    continue
                kept.append(p)

            if removed_missing == 0 and removed_hash == 0:
                continue

            data["installed_plugins"] = kept
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if removed_missing:
                log(f"installIndex.purge: removed {removed_missing} missing plugin(s) from '{rm_rid}-index.json'")
            if removed_hash:
                log(f"installIndex.purge: removed {removed_hash} hash-mismatch plugin(s) from '{rm_rid}-index.json'")
        except Exception as e:
            log(f"installIndex.purge: error processing '{rm_rid}': {e}")


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

        plugins = data.get("installed_plugins")
        if not isinstance(plugins, list):
            plugins = []
        plugins = [p for p in plugins if str(p.get("id") or "") != plugin_id]
        plugins.append(record)
        data["installed_plugins"] = plugins

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        log(f"installIndex: wrote entry for '{plugin_id}' in '{rm_rid}-index.json'")
    except Exception as e:
        log(f"installIndex: write error for '{plugin_id}': {e}")
