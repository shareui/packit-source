# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ..utils import CachedRepos
from urllib.parse import urlparse, parse_qs
from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
try:
    from elyx import strings
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"suggestion deeplink: import elyx failed: {e}")
import json
import os


def _load_repomap(rm_rid: str):
    return CachedRepos.read(rm_rid)


def _has_required_fields(data: dict) -> bool:
    sp = data.get("suggest_plugins")
    if not isinstance(sp, dict):
        return False
    return (
        "settings" in sp and
        "config" in sp
    )


def handle(url: str, plugin=None):
    try:
        if "suggestion=" not in url:
            return

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)

        rm_rid = query.get("suggestion", [""])[0].strip()
        if not rm_rid:
            return

        data = _load_repomap(rm_rid)
        if data is None:
            BulletinHelper.show_error(str(strings["suggest_repo_not_found"]))
            return

        if not _has_required_fields(data):
            BulletinHelper.show_error(str(strings["suggest_missing_fields"]))
            return

        run_on_ui_thread(lambda: _open_fragment(data, plugin))
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"suggestion deeplink: handle error: {e}", False)


def _open_fragment(data: dict, plugin=None):
    try:
        from ..ui.suggest.Fragment import show_suggest_fragment
        show_suggest_fragment(data, plugin)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"suggestion deeplink: _open_fragment error: {e}", False)