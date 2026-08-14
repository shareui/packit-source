# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# <files>/packit/reposCache/{rm_rid}.json — the repomap a repository last
# served, and everything read out of it.
#
# The file is written whenever a repomap is fetched and read by nearly every
# screen: the plugin catalogue and the icon catalogue resolve their list urls
# through it, the sources screen draws a card from it, the report dialog takes
# its reasons from it, autocomplete and the deeplinks all start here. Reading it
# is the single most copied piece of code in the plugin, so it lives in one
# place and nowhere else.
#
# Nothing here touches the network. What fills the file is network/Storage.

from packutil import logx
import json
import os

from . import Jsonx as _jsonx
from .Paths import getRepoCachePath, getReposCacheDir


def path(rm_rid) -> str:
    return getRepoCachePath(str(rm_rid or ""))


def read(rm_rid):
    """The cached repomap for a repository, or None.

    Parsed leniently: the official repomap has shipped with a trailing comma
    more than once, and a screen that cannot draw a repository because of one
    character is worse than a screen that tolerates it.
    """
    rm_rid = str(rm_rid or "")
    if not rm_rid:
        return None
    file_path = path(rm_rid)
    try:
        if not os.path.isfile(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = _jsonx.loads(f.read())
        return data if isinstance(data, dict) else None
    except Exception as e:
        logx(f"cachedRepos: unreadable cache for '{rm_rid}': {e}", True)
        return None


def write(rm_rid, data) -> bool:
    rm_rid = str(rm_rid or "")
    if not rm_rid or not isinstance(data, dict):
        return False
    try:
        os.makedirs(getReposCacheDir(), exist_ok=True)
        with open(path(rm_rid), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logx(f"cachedRepos: cannot write cache for '{rm_rid}': {e}", False)
        return False


def forget(rm_rid) -> bool:
    """Drop a repository's cached repomap. True when there was one to drop."""
    rm_rid = str(rm_rid or "")
    if not rm_rid:
        return False
    try:
        file_path = path(rm_rid)
        if not os.path.isfile(file_path):
            return False
        os.remove(file_path)
        return True
    except Exception as e:
        logx(f"cachedRepos: cannot delete cache for '{rm_rid}': {e}", False)
        return False


def mtime(rm_rid) -> float:
    try:
        return os.path.getmtime(path(rm_rid))
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
            data = read(rm_rid)
            if isinstance(data, dict):
                out.append((rm_rid, data))
    except Exception as e:
        logx(f"cachedRepos: cannot list the cache: {e}", False)
    return out


# ----------------------------------------------------------- what is inside

def _repo_id_of(repo) -> str:
    if isinstance(repo, dict):
        return str(repo.get("id") or "")
    return str(repo or "")


def repometa(repo) -> dict:
    data = read(_repo_id_of(repo))
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
    data = read(_repo_id_of(repo))
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


def reasons(repo) -> list:
    data = read(_repo_id_of(repo))
    block = data.get("reasons") if isinstance(data, dict) else None
    items = block.get("reasons") if isinstance(block, dict) else None
    if not isinstance(items, list):
        return []
    return [str(r) for r in items if r]


def report_settings(repo):
    """(forum_username, topic_msg_id), or (None, None) when the repo has none."""
    data = read(_repo_id_of(repo))
    block = data.get("reasons") if isinstance(data, dict) else None
    values = block.get("settings") if isinstance(block, dict) else None
    if isinstance(values, list) and len(values) >= 2:
        try:
            return str(values[0]), int(values[1])
        except Exception:
            return None, None
    return None, None


def suggest_config(repo):
    data = read(_repo_id_of(repo))
    block = data.get("suggest_plugins") if isinstance(data, dict) else None
    return block if isinstance(block, dict) else None
