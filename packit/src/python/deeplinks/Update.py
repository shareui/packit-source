# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ..network import Storage
from ..utils import CachedRepos
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import run_on_ui_thread
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()
from urllib.parse import urlparse, parse_qs
import requests
import json
import os


def _run_update(repoManager):
    def task():
        try:
            repos = repoManager.getRepositories()
            changed = False
            toRemove = []
            seenRids = set()

            for i, repo in enumerate(repos):
                url = (repo.get("url") or "").strip()
                if not url:
                    continue
                try:
                    data, error = Storage.fetch_repomap(url)
                    if error in ("missing repometa", "missing rm_rid"):
                        logx(f"update deeplink: '{url}' is not a repomap ({error}), removing", True)
                        toRemove.append(i)
                        changed = True
                        continue
                    if error:
                        logx(f"update deeplink: {error} for {url}", True)
                        continue
                    repometa = data.get("repometa")
                    rmRid = repometa.get("rm_rid")

                    if rmRid in seenRids:
                        logx(f"update deeplink: duplicate rm_rid='{rmRid}', removing repo", True)
                        toRemove.append(i)
                        changed = True
                        continue
                    seenRids.add(rmRid)

                    if repo.get("id") != rmRid:
                        repos[i]["id"] = rmRid
                        changed = True
                        logx(f"update deeplink: set id='{rmRid}' for repo '{repo.get('name')}'", True)

                    CachedRepos.write(rmRid, data)
                    logx(f"update deeplink: updated cache for '{rmRid}'", True)
                except Exception as _cython_exc_e:
                    e = _cython_exc_e
                    logx(f"update deeplink: error for {url}: {e}", False)

            for i in sorted(toRemove, reverse=True):
                repos.pop(i)

            if changed:
                repoManager.setRepositories(repos)

            run_on_ui_thread(lambda: BulletinHelper.show_success(strings.update_repos_success))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"update deeplink: task error: {e}", False)

    run_on_queue(task)


def _run_update_single(repoManager, repoId: str):
    def task():
        try:
            repos = repoManager.getRepositories()

            target = next((r for r in repos if r.get("id") == repoId), None)
            if not target:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_repo_not_found", repo_id=repoId))))
                return

            url = (target.get("url") or "").strip()
            if not url:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_update_repo_no_url", repo_id=repoId))))
                return

            try:
                data, error = Storage.fetch_repomap(url)
                if error in ("missing repometa", "missing rm_rid"):
                    logx(f"update deeplink: no repometa for '{url}'", True)
                    run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings["dl_update_repo_no_meta"])))
                    return
                if error:
                    logx(f"update deeplink: {error} for {url}", True)
                    run_on_ui_thread(lambda e=error: BulletinHelper.show_error(str(strings("dl_update_repo_http_error", code=e))))
                    return
                repometa = data.get("repometa")
                rmRid = repometa.get("rm_rid")
                CachedRepos.write(rmRid, data)
                logx(f"update deeplink: updated cache for '{rmRid}'", True)

                idx = next((i for i, rp in enumerate(repos) if rp.get("id") == repoId), None)
                if idx is not None and repos[idx].get("id") != rmRid:
                    repos[idx]["id"] = rmRid
                    repoManager.setRepositories(repos)

                run_on_ui_thread(lambda: BulletinHelper.show_success(strings.update_repos_success))
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"update deeplink: error for {url}: {e}", False)
                run_on_ui_thread(lambda e=e: BulletinHelper.show_error(str(e)))
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"update deeplink: single task error: {e}", False)

    run_on_queue(task)


def handle(url, repoManager):
    if not url.startswith("tg://packit?update"):
        return
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        repoId = query.get("repo", [None])[0]

        if repoId:
            _run_update_single(repoManager, repoId.strip())
        elif url == "tg://packit?update":
            _run_update(repoManager)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"update deeplink: handle error: {e}", False)