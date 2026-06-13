# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import run_on_ui_thread
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from urllib.parse import urlparse, parse_qs
import requests
import json
import os


def _get_cache_dir() -> str:
    from ..utils.paths import getCacheRoot
    return getCacheRoot()


def _run_update(repoManager):
    def task():
        try:
            repos = repoManager.getRepositories()
            cacheDir = _get_cache_dir()
            os.makedirs(cacheDir, exist_ok=True)
            changed = False
            toRemove = []
            seenRids = set()

            for i, repo in enumerate(repos):
                url = (repo.get("url") or "").strip()
                if not url:
                    continue
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code != 200:
                        logx(f"update deeplink: HTTP {r.status_code} for {url}", True)
                        continue
                    data = r.json()
                    repometa = data.get("repometa")
                    rmRid = repometa.get("rm_rid") if repometa else None

                    if not repometa or not rmRid:
                        logx(f"update deeplink: no repometa for '{url}', removing repo", True)
                        toRemove.append(i)
                        changed = True
                        continue

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

                    cachePath = os.path.join(cacheDir, f"{rmRid}.json")
                    with open(cachePath, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    logx(f"update deeplink: updated cache for '{rmRid}'", True)
                except Exception as e:
                    logx(f"update deeplink: error for {url}: {e}", False)

            for i in sorted(toRemove, reverse=True):
                repos.pop(i)

            if changed:
                repoManager.setRepositories(repos)

            run_on_ui_thread(lambda: BulletinHelper.show_success(strings.update_repos_success))
        except Exception as e:
            logx(f"update deeplink: task error: {e}", False)

    run_on_queue(task)


def _run_update_single(repoManager, repoId: str):
    def task():
        try:
            repos = repoManager.getRepositories()
            cacheDir = _get_cache_dir()
            os.makedirs(cacheDir, exist_ok=True)

            target = next((r for r in repos if r.get("id") == repoId), None)
            if not target:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_repo_not_found", repo_id=repoId))))
                return

            url = (target.get("url") or "").strip()
            if not url:
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_update_repo_no_url", repo_id=repoId))))
                return

            try:
                r = requests.get(url, timeout=10)
                if r.status_code != 200:
                    logx(f"update deeplink: HTTP {r.status_code} for {url}", True)
                    run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings("dl_update_repo_http_error", code=r.status_code))))
                    return
                data = r.json()
                repometa = data.get("repometa")
                rmRid = repometa.get("rm_rid") if repometa else None

                if not repometa or not rmRid:
                    logx(f"update deeplink: no repometa for '{url}'", True)
                    run_on_ui_thread(lambda: BulletinHelper.show_error(str(strings["dl_update_repo_no_meta"])))
                    return

                cachePath = os.path.join(cacheDir, f"{rmRid}.json")
                with open(cachePath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logx(f"update deeplink: updated cache for '{rmRid}'", True)

                idx = next((i for i, rp in enumerate(repos) if rp.get("id") == repoId), None)
                if idx is not None and repos[idx].get("id") != rmRid:
                    repos[idx]["id"] = rmRid
                    repoManager.setRepositories(repos)

                run_on_ui_thread(lambda: BulletinHelper.show_success(strings.update_repos_success))
            except Exception as e:
                logx(f"update deeplink: error for {url}: {e}", False)
                run_on_ui_thread(lambda: BulletinHelper.show_error(str(e)))
        except Exception as e:
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
    except Exception as e:
        logx(f"update deeplink: handle error: {e}", False)