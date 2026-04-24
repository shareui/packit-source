import json
import os
import re
import threading

from android_utils import log

_lock = threading.Lock()

_pending = None


def _get_index_path(rm_rid: str) -> str:
    from .paths import getRepoIndexPath
    return getRepoIndexPath(rm_rid)


def _strip_version(raw: str) -> str:
    # keep only digits and dots
    return re.sub(r"[^0-9.]", "", str(raw or "")).strip(".")


def _hash_matches(p: dict) -> bool:
    # entries marked Outdated have no stored hash — skip hash verification
    if str(p.get("hash") or "") == "Outdated" or str(p.get("bithash") or "") == "Outdated":
        return True
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

        index_path = _get_index_path(rm_rid)
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
            removed_ids = []
            for p in plugins:
                plugin_id = str(p.get("id") or "<no_id>")
                local_path = str(p.get("local_path") or "")
                if not os.path.exists(local_path):
                    log(f"installIndex.purge: drop '{plugin_id}' — file missing: '{local_path}'")
                    removed_missing += 1
                    removed_ids.append(plugin_id)
                    continue
                if not _hash_matches(p):
                    stored_hash = str(p.get("hash") or "")
                    stored_bithash = str(p.get("bithash") or "")
                    log(f"installIndex.purge: drop '{plugin_id}' — hash mismatch (hash='{stored_hash}', bithash='{stored_bithash}', path='{local_path}')")
                    removed_hash += 1
                    removed_ids.append(plugin_id)
                    continue
                kept.append(p)

            if removed_missing == 0 and removed_hash == 0:
                continue

            data["installed_plugins"] = kept

            # remove purged plugins from ignore_list too
            if removed_ids:
                ignore_list = data.get("ignore_list")
                if isinstance(ignore_list, list):
                    cleaned = [e for e in ignore_list if str(e.get("id") or "") not in removed_ids]
                    if len(cleaned) != len(ignore_list):
                        data["ignore_list"] = cleaned
                        log(f"installIndex.purge: cleaned {len(ignore_list) - len(cleaned)} ignore_list entry(s) from '{rm_rid}-index.json'")
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
        from .paths import getPluginsDir, getRepoIndexPath
    except Exception as e:
        log(f"installIndex: cannot import paths: {e}")
        return

    plugin_id = str(plugin_info.get("id") or "")
    if not plugin_id:
        log("installIndex: no plugin id, skipping")
        return

    version = _strip_version(plugin_info.get("version") or "")
    state = str(plugin_info.get("state") or "")
    candidate_path = getPluginsDir() + f"/{plugin_id}.py"
    file_exists = os.path.exists(candidate_path)
    local_path = candidate_path if file_exists else "Unknown"
    file_type = "plugin"

    log(f"installIndex: commit_pending '{plugin_id}' v={version} state={state} path_exists={file_exists} path='{candidate_path}'")

    if not file_exists:
        log(f"installIndex: WARNING — plugin file not found at '{candidate_path}', local_path will be 'Unknown'")

    # hash the installed file, not the source index hash:
    # PluginsController may modify the file during install
    hash_val = ""
    bithash_val = ""
    if file_exists:
        try:
            from .hashUtil import _hashFileSha256, _hashFileBithash, _getBitHashLib
            hash_val = _hashFileSha256(candidate_path)
            if _getBitHashLib() is not None:
                bithash_val = _hashFileBithash(candidate_path)
            log(f"installIndex: hashed '{plugin_id}' sha256='{hash_val[:16]}...' bithash='{bithash_val[:16] if bithash_val else ''}'")
        except Exception as e:
            log(f"installIndex: failed to hash plugin file for '{plugin_id}': {e}")
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

    index_path = _get_index_path(rm_rid)
    try:
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                log(f"installIndex: index file '{index_path}' is not a dict, resetting")
                data = {}
        else:
            log(f"installIndex: index file not found, creating new '{index_path}'")
            data = {}

        plugins = data.get("installed_plugins")
        if not isinstance(plugins, list):
            plugins = []
        before_count = len(plugins)
        plugins = [p for p in plugins if str(p.get("id") or "") != plugin_id]
        after_dedup = len(plugins)
        plugins.append(record)
        data["installed_plugins"] = plugins

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        replaced = before_count != after_dedup
        log(f"installIndex: wrote '{plugin_id}' to '{rm_rid}-index.json' (replaced={replaced}, total={len(plugins)}, local_path='{local_path}')")
    except Exception as e:
        log(f"installIndex: write error for '{plugin_id}': {e}")


def commit_elyx_pending(plugin_info: dict, rm_rid: str, original_path: str = ""):
    # called after successful elyxcore install
    if not rm_rid:
        log("installIndex.elyx: no rm_rid, skipping")
        return

    try:
        from .paths import getPackitArchivesDir
    except Exception as e:
        log(f"installIndex.elyx: cannot import paths: {e}")
        return

    plugin_id = str(plugin_info.get("id") or "")
    if not plugin_id:
        log("installIndex.elyx: no plugin id, skipping")
        return

    version = _strip_version(plugin_info.get("version") or "")
    state = str(plugin_info.get("state") or "")

    # derive archive filename from original link
    link = str(plugin_info.get("link") or plugin_info.get("raw") or "")
    link_filename = link.split("/")[-1] if link else ""
    if not link_filename:
        link_filename = f"{plugin_id}.zip"

    packit_dir = getPackitArchivesDir()
    archive_path = packit_dir + f"/{link_filename}"

    log(f"installIndex.elyx: commit '{plugin_id}' v={version} state={state} original_path='{original_path}' dest='{archive_path}'")

    # copy original archive into packit dir if source is available
    if original_path and os.path.exists(original_path):
        try:
            os.makedirs(packit_dir, exist_ok=True)
            import shutil
            shutil.copy2(original_path, archive_path)
            log(f"installIndex.elyx: saved original archive to '{archive_path}'")
        except Exception as e:
            log(f"installIndex.elyx: failed to copy original archive for '{plugin_id}': {e}")

    # check file is present (either we copied it or elyxcore placed it)
    if not os.path.exists(archive_path):
        log(f"installIndex.elyx: archive not found at '{archive_path}', skipping index write")
        return

    local_path = archive_path

    # hash the saved original archive
    hash_val = ""
    bithash_val = ""
    try:
        from .hashUtil import _hashFileSha256, _hashFileBithash, _getBitHashLib
        hash_val = _hashFileSha256(archive_path)
        if _getBitHashLib() is not None:
            bithash_val = _hashFileBithash(archive_path)
        log(f"installIndex.elyx: hashed '{plugin_id}' sha256='{hash_val[:16]}...' bithash='{bithash_val[:16] if bithash_val else ''}'")
    except Exception as e:
        log(f"installIndex.elyx: failed to hash archive for '{plugin_id}': {e}")
        hash_val = str(plugin_info.get("hash") or "")
        bithash_val = str(plugin_info.get("bithash") or "")

    record = {
        "id": plugin_id,
        "version": version,
        "state": state,
        "local_path": local_path,
        "file_type": "elyxcore",
        "hash": hash_val,
        "bithash": bithash_val,
    }

    index_path = _get_index_path(rm_rid)
    try:
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                log(f"installIndex.elyx: index file '{index_path}' is not a dict, resetting")
                data = {}
        else:
            log(f"installIndex.elyx: index file not found, creating new '{index_path}'")
            data = {}

        plugins = data.get("installed_plugins")
        if not isinstance(plugins, list):
            plugins = []
        before_count = len(plugins)
        plugins = [p for p in plugins if str(p.get("id") or "") != plugin_id]
        after_dedup = len(plugins)
        plugins.append(record)
        data["installed_plugins"] = plugins

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        replaced = before_count != after_dedup
        log(f"installIndex.elyx: wrote '{plugin_id}' to '{rm_rid}-index.json' (replaced={replaced}, total={len(plugins)}, local_path='{local_path}')")
    except Exception as e:
        log(f"installIndex.elyx: write error for '{plugin_id}': {e}")
