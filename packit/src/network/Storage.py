# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# One way to ask a repository for anything: its repomap, its plugin list, its
# icon packs, its avatar.
#
# Before this, every screen that wanted a repository's plugin list wrote the
# same twenty lines — open <files>/packit/reposCache/{rm_rid}.json, walk down to
# repomap.plugins, fall back to the stored url, GET it, and unpack a "plugins"
# value that is a dict in some repositories and a list in others. Nine copies of
# that walk existed, no two identical: some used json.loads and choked on a
# repomap with a trailing comma, some sent the plugin's User-Agent and some sent
# python-requests', and the timeouts ranged from 10 to 20 seconds for the same
# file. A repository is one thing and it is read from one place.
#
# Two layers, and callers should know which they are using:
#   read_*  — off disk, no network, safe to call anywhere
#   fetch_* — over the network, must not be called on the ui thread

from packutil import logx
import json
import os

import requests

from ..utils import jsonx as _jsonx
from ..utils.paths import (
    getRepoCachePath, getReposCacheDir,
    getRepoIconCachePath, getRepoIconCacheDir,
)

# repositories are served from github raw and the like; some of them log this
HEADERS = {"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"}

TIMEOUT = 15
TIMEOUT_LIST = 20  # plugin and icon lists run to hundreds of kilobytes


# ---------------------------------------------------------------- repomap cache

def repomap_path(rm_rid) -> str:
    return getRepoCachePath(str(rm_rid or ""))


def read_repomap(rm_rid):
    """The cached repomap for a repository, or None. Never touches the network.

    Parsed leniently: the official repomap has shipped with a trailing comma
    more than once, and a screen that cannot draw a repository because of one
    character is worse than a screen that tolerates it.
    """
    rm_rid = str(rm_rid or "")
    if not rm_rid:
        return None
    path = repomap_path(rm_rid)
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = _jsonx.loads(f.read())
        return data if isinstance(data, dict) else None
    except Exception as e:
        logx(f"Storage: unreadable repomap cache for '{rm_rid}': {e}", True)
        return None


def write_repomap(rm_rid, data) -> bool:
    rm_rid = str(rm_rid or "")
    if not rm_rid or not isinstance(data, dict):
        return False
    try:
        os.makedirs(getReposCacheDir(), exist_ok=True)
        with open(repomap_path(rm_rid), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logx(f"Storage: cannot write repomap cache for '{rm_rid}': {e}", False)
        return False


def forget_repomap(rm_rid) -> bool:
    """Drop a repository's cached repomap. True when there was one to drop."""
    rm_rid = str(rm_rid or "")
    if not rm_rid:
        return False
    try:
        path = repomap_path(rm_rid)
        if not os.path.isfile(path):
            return False
        os.remove(path)
        return True
    except Exception as e:
        logx(f"Storage: cannot delete repomap cache for '{rm_rid}': {e}", False)
        return False


def repomap_mtime(rm_rid) -> float:
    try:
        return os.path.getmtime(repomap_path(rm_rid))
    except Exception:
        return 0.0


def all_cached() -> list:
    """[(rm_rid, repomap), …] for every repository with a cache on disk."""
    out = []
    try:
        cache_dir = getReposCacheDir()
        if not os.path.isdir(cache_dir):
            return out
        for name in sorted(os.listdir(cache_dir)):
            if not name.endswith(".json"):
                continue
            # the installed-plugin index and the counts live in this directory
            # too, and neither of them is a repomap
            if name.endswith("-index.json") or name.endswith("-stats.json"):
                continue
            rm_rid = name[:-len(".json")]
            data = read_repomap(rm_rid)
            if isinstance(data, dict):
                out.append((rm_rid, data))
    except Exception as e:
        logx(f"Storage: cannot list the repomap cache: {e}", False)
    return out


# -------------------------------------------------------------- repomap fields

def _repo_id_of(repo) -> str:
    if isinstance(repo, dict):
        return str(repo.get("id") or "")
    return str(repo or "")


def repometa(rm_rid) -> dict:
    data = read_repomap(_repo_id_of(rm_rid))
    meta = data.get("repometa") if isinstance(data, dict) else None
    return meta if isinstance(meta, dict) else {}


def section_url(repo, key: str, fallback: str = "") -> str:
    """repomap.<key> out of the cache, falling back to the stored url.

    `repo` is either the stored dict or a bare rm_rid. The fallback matters:
    a repomap that is itself the plugin list has no repomap section at all,
    and then the repository's own url is the list.
    """
    if isinstance(repo, dict) and not fallback:
        fallback = str(repo.get("url") or "").strip()
    data = read_repomap(_repo_id_of(repo))
    repomap = data.get("repomap") if isinstance(data, dict) else None
    if isinstance(repomap, dict):
        url = str(repomap.get(key) or "").strip()
        if url:
            return url
    return fallback


def plugins_url(repo, fallback: str = "") -> str:
    return section_url(repo, "plugins", fallback)


def icons_url(repo, fallback: str = "") -> str:
    return section_url(repo, "icons", fallback)


def icon_url(repo) -> str:
    """repometa.rm_icon, but only when it is a picture.

    Repositories written before rm_icon was a link put an R.drawable name here.
    Nothing resolves those any more, so anything that is not http(s) is no icon.
    """
    url = str(repometa(repo).get("rm_icon") or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else ""


def reasons(rm_rid) -> list:
    data = read_repomap(_repo_id_of(rm_rid))
    block = data.get("reasons") if isinstance(data, dict) else None
    items = block.get("reasons") if isinstance(block, dict) else None
    if not isinstance(items, list):
        return []
    return [str(r) for r in items if r]


def report_settings(rm_rid):
    """(forum_username, topic_msg_id), or (None, None) when the repo has none."""
    data = read_repomap(_repo_id_of(rm_rid))
    block = data.get("reasons") if isinstance(data, dict) else None
    values = block.get("settings") if isinstance(block, dict) else None
    if isinstance(values, list) and len(values) >= 2:
        try:
            return str(values[0]), int(values[1])
        except Exception:
            return None, None
    return None, None


def suggest_config(rm_rid):
    data = read_repomap(_repo_id_of(rm_rid))
    block = data.get("suggest_plugins") if isinstance(data, dict) else None
    return block if isinstance(block, dict) else None


# ------------------------------------------------------------------- shapes

def normalize_entries(raw) -> list:
    """A repository's "plugins"/"icons" value as a list of dicts, each with an id.

    Both shapes are in the wild: an object keyed by id, and an array of objects
    that carry their own. Every caller used to unpack this itself, and they did
    not agree on what to do with a malformed entry.
    """
    out = []
    if isinstance(raw, dict):
        for entry_id, info in raw.items():
            if isinstance(info, dict):
                out.append({"id": entry_id, **info})
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id"):
                out.append(item)
    return out


# ------------------------------------------------------------------- network

# The add dialog localises a failure by matching these exact strings, so they
# are the vocabulary of this module and not free text.
_STATUS_REASONS = {
    301: "permanently redirected",
    302: "redirected",
    303: "see other",
    307: "temporarily redirected",
    308: "permanently redirected",
    400: "bad request",
    401: "unauthorized",
    403: "forbidden",
    404: "file not found",
    408: "request timeout",
    410: "resource gone",
    429: "rate limited, try again later",
    451: "unavailable for legal reasons",
    500: "server error",
    502: "bad gateway",
    503: "service unavailable",
    504: "gateway timeout",
}


def fetch_json(url: str, timeout: int = TIMEOUT):
    """(data, error). error is a lowercase english reason, or None on success."""
    url = str(url or "").strip()
    if not url:
        return None, "file not found"
    try:
        r = requests.get(url, timeout=timeout, headers=HEADERS)
    except Exception as e:
        logx(f"Storage: request failed for '{url}': {e}", False)
        return None, str(e)
    if r.status_code != 200:
        logx(f"Storage: HTTP {r.status_code} for '{url}'", True)
        return None, _STATUS_REASONS.get(r.status_code, f"HTTP {r.status_code}")
    try:
        return _jsonx.loads(r.text), None
    except Exception as e:
        logx(f"Storage: bad json at '{url}': {e}", True)
        return None, "invalid json"


def fetch_repomap(url: str, timeout: int = TIMEOUT):
    """(repomap, error) — a repomap is only one if it declares who it is."""
    data, error = fetch_json(url, timeout)
    if error:
        return None, error
    meta = data.get("repometa") if isinstance(data, dict) else None
    if not isinstance(meta, dict) or not meta:
        return None, "missing repometa"
    if not meta.get("rm_rid"):
        return None, "missing rm_rid"
    return data, None


def fetch_entries(url: str, key: str, timeout: int = TIMEOUT_LIST):
    """(entries, error) for a plugin or icon list."""
    data, error = fetch_json(url, timeout)
    if error:
        return None, error
    raw = data.get(key, []) if isinstance(data, dict) else []
    return normalize_entries(raw), None


def fetch_plugins(url: str, timeout: int = TIMEOUT_LIST):
    return fetch_entries(url, "plugins", timeout)


def fetch_icons(url: str, timeout: int = TIMEOUT_LIST):
    return fetch_entries(url, "icons", timeout)


# ------------------------------------------------------- repository avatars

_MEM_CAP = 64
_mem = None
_mem_lock = None


def _mem_store():
    global _mem
    if _mem is None:
        from collections import OrderedDict
        _mem = OrderedDict()
    return _mem


def _lock():
    global _mem_lock
    if _mem_lock is None:
        import threading
        _mem_lock = threading.Lock()
    return _mem_lock


def _mem_key(url: str, px: int) -> str:
    # px is part of the key: the same icon is decoded at different sizes for a
    # card and for a sheet, and the smaller decode looks soft blown up
    return f"{url}|{px}"


def peek_icon(url: str, px: int):
    """The already-decoded avatar, or None. Cheap enough for the ui thread.

    Routing a bitmap that is already in memory through the worker pool costs a
    hop out and a hop back, and a card rebuilt in those two frames shows its
    monogram — which is what made avatars blink whenever the list repainted.
    """
    if not url:
        return None
    key = _mem_key(url, px)
    with _lock():
        store = _mem_store()
        bmp = store.get(key)
        if bmp is not None:
            store.move_to_end(key)
        return bmp


def load_icon(url: str, px: int):
    """memory -> disk -> network, decoded to a px-sized bitmap. Off the ui thread."""
    from ..utils import imagePool

    bmp = peek_icon(url, px)
    if bmp is not None:
        return bmp

    path = getRepoIconCachePath(url)
    data = None
    try:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                data = f.read()
    except Exception:
        data = None

    if not data:
        data = imagePool.fetch(url)
        if not data:
            return None
        try:
            os.makedirs(getRepoIconCacheDir(), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            logx(f"Storage: icon cache write failed: {e}", True)

    bmp = imagePool.decode(data, px, imagePool.looks_like_svg(url, data))
    if bmp is None:
        # a corrupted cache entry would keep failing forever
        try:
            os.unlink(path)
        except Exception:
            pass
        return None
    with _lock():
        store = _mem_store()
        store[_mem_key(url, px)] = bmp
        while len(store) > _MEM_CAP:
            store.popitem(last=False)
    return bmp
