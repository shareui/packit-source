# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# What a repository turned out to hold, remembered from the last time something
# actually looked.
#
# repomap does not carry counts — repomap.plugins and repomap.icons are urls,
# not lists — so the sources screen has no way to say how big a source is
# without downloading a file that can run to hundreds of kilobytes. The
# catalogues download it anyway, every time they open, so they leave the number
# behind here and the sources screen reads it for free. A source nobody has
# opened yet simply has no number, which is honest: nothing has counted it.

from packutil import logx
import json
import os

_FILE = "{}-stats.json"


def _path(rm_rid: str) -> str:
    from .Paths import getReposCacheDir
    return os.path.join(getReposCacheDir(), _FILE.format(rm_rid))


def read(rm_rid: str) -> dict:
    rm_rid = str(rm_rid or "")
    if not rm_rid:
        return {}
    try:
        path = _path(rm_rid)
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logx(f"repoStats: read error for '{rm_rid}': {e}", True)
        return {}


def remember(rm_rid: str, **counts):
    """remember(rid, plugins=1011) — only the keys passed are touched."""
    rm_rid = str(rm_rid or "")
    if not rm_rid:
        return
    clean = {k: int(v) for k, v in counts.items() if isinstance(v, int) and v >= 0}
    if not clean:
        return
    try:
        data = read(rm_rid)
        if all(data.get(k) == v for k, v in clean.items()):
            return  # same numbers as last time, no write
        data.update(clean)
        path = _path(rm_rid)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logx(f"repoStats: write error for '{rm_rid}': {e}", True)


def installed_count(rm_rid: str) -> int:
    # the per-repository install index the installer keeps
    rm_rid = str(rm_rid or "")
    if not rm_rid:
        return 0
    try:
        from .Paths import getRepoIndexPath
        path = getRepoIndexPath(rm_rid)
        if not os.path.isfile(path):
            return 0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        plugins = data.get("installed_plugins") if isinstance(data, dict) else None
        return len(plugins) if isinstance(plugins, list) else 0
    except Exception as e:
        logx(f"repoStats: index read error for '{rm_rid}': {e}", True)
        return 0
