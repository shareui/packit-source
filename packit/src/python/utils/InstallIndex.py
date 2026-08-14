# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import json
import os
import re
import threading



_lock = threading.Lock()

_pending = None


def _get_index_path(rm_rid: str) -> str:
    from .Paths import getRepoIndexPath
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
        from .HashUtil import matchesStoredHash
        return matchesStoredHash(
            local_path,
            sha256=str(p.get("hash") or ""),
            bithash=str(p.get("bithash") or ""),
            label=str(p.get("id") or local_path),
        )
    except Exception as e:
        logx(f"installIndex.purge: hash check error for '{local_path}': {e}", False)
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
        logx(f"installIndex.purge: cannot read repos: {e}", False)
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
                    logx(f"installIndex.purge: drop '{plugin_id}' — file missing: '{local_path}'", True)
                    removed_missing += 1
                    removed_ids.append(plugin_id)
                    continue
                if not _hash_matches(p):
                    stored_hash = str(p.get("hash") or "")
                    stored_bithash = str(p.get("bithash") or "")
                    logx(f"installIndex.purge: drop '{plugin_id}' — hash mismatch (hash='{stored_hash}', bithash='{stored_bithash}', path='{local_path}')", True)
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
                        logx(f"installIndex.purge: cleaned {len(ignore_list) - len(cleaned)} ignore_list entry(s) from '{rm_rid}-index.json'", True)
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if removed_missing:
                logx(f"installIndex.purge: removed {removed_missing} missing plugin(s) from '{rm_rid}-index.json'", True)
            if removed_hash:
                logx(f"installIndex.purge: removed {removed_hash} hash-mismatch plugin(s) from '{rm_rid}-index.json'", True)
        except Exception as e:
            logx(f"installIndex.purge: error processing '{rm_rid}': {e}", False)


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
        logx("installIndex: no rm_rid, skipping", True)
        return

    try:
        from .Paths import getPluginsDir, getRepoIndexPath
    except Exception as e:
        logx(f"installIndex: cannot import paths: {e}", False)
        return

    plugin_id = str(plugin_info.get("id") or "")
    if not plugin_id:
        logx("installIndex: no plugin id, skipping", True)
        return

    version = _strip_version(plugin_info.get("version") or "")
    state = str(plugin_info.get("state") or "")
    plugins_dir = getPluginsDir()
    candidate_path = ""
    file_type = "plugin"
    for ext in (".plugin", ".py"):
        p = plugins_dir + f"/{plugin_id}{ext}"
        if os.path.exists(p):
            candidate_path = p
            file_type = ext.lstrip(".")
            break
    if not candidate_path:
        candidate_path = plugins_dir + f"/{plugin_id}.py"
    file_exists = os.path.exists(candidate_path)
    local_path = candidate_path if file_exists else "Unknown"

    logx(f"installIndex: commit_pending '{plugin_id}' v={version} state={state} path_exists={file_exists} path='{candidate_path}'", True)

    if not file_exists:
        logx(f"installIndex: WARNING — plugin file not found at '{candidate_path}', local_path will be 'Unknown'", True)

    # hash the installed file, not the source index hash:
    # PluginsController may modify the file during install
    hash_val = ""
    bithash_val = ""
    if file_exists:
        try:
            from .HashUtil import _hashFileSha256, _hashFileBithash, _getBitHashLib
            hash_val = _hashFileSha256(candidate_path)
            if _getBitHashLib() is not None:
                bithash_val = _hashFileBithash(candidate_path)
            logx(f"installIndex: hashed '{plugin_id}' sha256='{hash_val[:16]}...' bithash='{bithash_val[:16] if bithash_val else ''}'", True)
        except Exception as e:
            logx(f"installIndex: failed to hash plugin file for '{plugin_id}': {e}", False)
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
                logx(f"installIndex: index file '{index_path}' is not a dict, resetting", True)
                data = {}
        else:
            logx(f"installIndex: index file not found, creating new '{index_path}'", True)
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
        logx(f"installIndex: wrote '{plugin_id}' to '{rm_rid}-index.json' (replaced={replaced}, total={len(plugins)}, local_path='{local_path}')", True)
    except Exception as e:
        logx(f"installIndex: write error for '{plugin_id}': {e}", False)


def commit_elyx_pending(plugin_info: dict, rm_rid: str, original_path: str = ""):
    # called after successful elyxcore install
    if not rm_rid:
        logx("installIndex.elyx: no rm_rid, skipping", True)
        return

    try:
        from .Paths import getPackitArchivesDir
    except Exception as e:
        logx(f"installIndex.elyx: cannot import paths: {e}", False)
        return

    plugin_id = str(plugin_info.get("id") or "")
    if not plugin_id:
        logx("installIndex.elyx: no plugin id, skipping", True)
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

    logx(f"installIndex.elyx: commit '{plugin_id}' v={version} state={state} original_path='{original_path}' dest='{archive_path}'", True)

    # copy original archive into packit dir if source is available
    if original_path and os.path.exists(original_path):
        try:
            os.makedirs(packit_dir, exist_ok=True)
            import shutil
            shutil.copy2(original_path, archive_path)
            logx(f"installIndex.elyx: saved original archive to '{archive_path}'", True)
        except Exception as e:
            logx(f"installIndex.elyx: failed to copy original archive for '{plugin_id}': {e}", False)

    # check file is present (either we copied it or elyxcore placed it)
    if not os.path.exists(archive_path):
        logx(f"installIndex.elyx: archive not found at '{archive_path}', using original_path for index", True)
        # still write index so the install is tracked; use original_path if available
        local_path = original_path if original_path and os.path.exists(original_path) else "Unknown"
    else:
        local_path = archive_path

    # hash the saved archive (or original_path if archive copy failed)
    hash_val = ""
    bithash_val = ""
    hash_source = local_path if local_path and local_path != "Unknown" else ""
    if hash_source:
        try:
            from .HashUtil import _hashFileSha256, _hashFileBithash, _getBitHashLib
            hash_val = _hashFileSha256(hash_source)
            if _getBitHashLib() is not None:
                bithash_val = _hashFileBithash(hash_source)
            logx(f"installIndex.elyx: hashed '{plugin_id}' sha256='{hash_val[:16]}...' bithash='{bithash_val[:16] if bithash_val else ''}'", True)
        except Exception as e:
            logx(f"installIndex.elyx: failed to hash archive for '{plugin_id}': {e}", False)
            hash_val = str(plugin_info.get("hash") or "")
            bithash_val = str(plugin_info.get("bithash") or "")
    else:
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
                logx(f"installIndex.elyx: index file '{index_path}' is not a dict, resetting", True)
                data = {}
        else:
            logx(f"installIndex.elyx: index file not found, creating new '{index_path}'", True)
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
        logx(f"installIndex.elyx: wrote '{plugin_id}' to '{rm_rid}-index.json' (replaced={replaced}, total={len(plugins)}, local_path='{local_path}')", True)
    except Exception as e:
        logx(f"installIndex.elyx: write error for '{plugin_id}': {e}", False)