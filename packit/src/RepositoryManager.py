# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os
import json
import requests
from client_utils import get_last_fragment, run_on_queue
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from .utils.importFailed import showImportFailedAlert as _sifa; _sifa()

try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from .utils.importFailed import showImportFailedAlert as _sifa; _sifa()

_HEADERS = {"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"}

OFFICIAL_REPO_URL = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/repomap.json"


def _get_cache_dir() -> str:
    from .utils.paths import getReposCacheDir
    return getReposCacheDir()


class RepositoryManager:
    def __init__(self):
        pass
    
    def getRepositories(self):
        reposJson = settings.get("repositories", "[]")
        try:
            repos = json.loads(reposJson)
            if not isinstance(repos, list):
                return []
            return repos
        except Exception:
            return []
    
    def setRepositories(self, repos):
        settings.set("repositories", json.dumps(repos), reload_settings=True)
        try:
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllItems"):
                fragment.rebuildAllItems()
        except Exception:
            pass
    
    def _fetch_and_save_repomap(self, url: str) -> dict | None:
        """Fetch repomap.json from url, save to packit/{rm_rid}.json, return repometa dict."""
        try:
            r = requests.get(url, timeout=15, headers=_HEADERS)
            if r.status_code != 200:
                logx(f"repom: failed to fetch repomap from '{url}': HTTP {r.status_code}", True)
                return None
            data = r.json()
            repometa = data.get("repometa")
            if not repometa:
                logx(f"repom: no 'repometa' key in response from '{url}'", True)
                return None
            rm_rid = repometa.get("rm_rid")
            if not rm_rid:
                logx(f"repom: 'rm_rid' missing in repometa", True)
                return None
            cache_dir = _get_cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{rm_rid}.json")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logx(f"repom: saved repomap to {cache_path}", True)
            return repometa
        except Exception as e:
            logx(f"repom: _fetch_and_save_repomap error: {e}", False)
            return None

    def _get_temp_dir(self) -> str:
        from .utils.paths import getTempDir
        return getTempDir()

    def _cleanup_temp_dir(self):
        import shutil
        temp_dir = self._get_temp_dir()
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logx("repom: cleaned up packitTemp", True)
        except Exception as e:
            logx(f"repom: _cleanup_temp_dir error: {e}", False)

    def addRepositoryWithUrl(self, url: str):
        # download to packitTemp, validate, move to reposCache or discard
        # returns (repometa, error_reason) — error_reason is None on success
        import shutil

        temp_dir = self._get_temp_dir()
        temp_path = os.path.join(temp_dir, "repomap_download.json")

        try:
            os.makedirs(temp_dir, exist_ok=True)
            logx(f"repom: addRepositoryWithUrl: GET {url}", True)
            logx(f"repom: addRepositoryWithUrl: sending headers={_HEADERS}", True)
            r = requests.get(url, timeout=15, headers=_HEADERS)
            status = r.status_code
            logx(f"repom: addRepositoryWithUrl: status={status}", True)
            try:
                resp_headers = dict(r.headers)
                logx(f"repom: addRepositoryWithUrl: resp_headers={resp_headers}", True)
            except Exception as ex:
                logx(f"repom: addRepositoryWithUrl: could not read resp headers: {ex}", True)
            try:
                logx(f"repom: addRepositoryWithUrl: body[:500]={r.text[:500]}", True)
            except Exception as ex:
                logx(f"repom: addRepositoryWithUrl: could not read body: {ex}", True)
            if status != 200:
                reasons = {
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
                reason = reasons.get(status, f"HTTP {status}")
                self._cleanup_temp_dir()
                return None, reason

            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(r.text)
            logx(f"repom: downloaded to {temp_path}", True)
        except Exception as e:
            self._cleanup_temp_dir()
            return None, str(e)

        # validate
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logx(f"repom: addRepositoryWithUrl: json parse error: {e}", False)
            self._cleanup_temp_dir()
            return None, "invalid json"

        logx(f"repom: addRepositoryWithUrl: parsed ok, keys={list(data.keys())}", True)
        repometa = data.get("repometa")
        if not repometa:
            logx("repom: addRepositoryWithUrl: missing repometa", True)
            self._cleanup_temp_dir()
            return None, "missing repometa"

        rm_rid = repometa.get("rm_rid")
        logx(f"repom: addRepositoryWithUrl: rm_rid={repr(rm_rid)}", True)
        if not rm_rid:
            logx("repom: addRepositoryWithUrl: missing rm_rid", True)
            self._cleanup_temp_dir()
            return None, "missing rm_rid"

        rm_name = repometa.get("rm_name")
        logx(f"repom: addRepositoryWithUrl: rm_name={repr(rm_name)}", True)
        if not rm_name:
            logx("repom: addRepositoryWithUrl: missing rm_name", True)
            self._cleanup_temp_dir()
            return None, "missing rm_name"

        # move to reposCache
        try:
            cache_dir = _get_cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{rm_rid}.json")
            shutil.move(temp_path, cache_path)
            logx(f"repom: moved repomap to {cache_path}", True)
        except Exception as e:
            logx(f"repom: addRepositoryWithUrl: move to cache error: {e}", False)
            self._cleanup_temp_dir()
            return None, "cache write failed"

        self._cleanup_temp_dir()

        repos = self.getRepositories()
        newRepo = {
            "id": rm_rid,
            "name": rm_name,
            "url": url,
            "enabled": True,
            "collapsed": False
        }
        repos.append(newRepo)
        self.setRepositories(repos)
        return repometa, None

    def addRepository(self, isFirst=False):
        if isFirst:
            repos = self.getRepositories()
            def task():
                repometa = self._fetch_and_save_repomap(OFFICIAL_REPO_URL)
                if repometa:
                    newRepo = {
                        "id": repometa.get("rm_rid"),
                        "name": repometa.get("rm_name", strings.official_repository),
                        "url": OFFICIAL_REPO_URL,
                        "enabled": True,
                        "collapsed": False,
                        "icon": "chats_pin"
                    }
                else:
                    newRepo = {
                        "id": "shareui_official",
                        "name": strings.official_repository,
                        "url": OFFICIAL_REPO_URL,
                        "enabled": True,
                        "collapsed": False,
                        "icon": "chats_pin"
                    }
                repos.append(newRepo)
                self.setRepositories(repos)
            run_on_queue(task)
        else:
            repos = self.getRepositories()
            newRepo = {
                "id": None,
                "name": "",
                "url": "",
                "enabled": True,
                "collapsed": False
            }
            repos.append(newRepo)
            self.setRepositories(repos)

        fragment = get_last_fragment()
        if fragment and hasattr(fragment, "rebuildAllItems"):
            fragment.rebuildAllItems()
    
    def removeRepository(self, idx):
        repos = self.getRepositories()
        if idx < 0 or idx >= len(repos):
            logx(f"repom.removeRepository: invalid idx={idx}, repos count={len(repos)}", True)
            return

        repo = repos[idx]
        repo_id = repo.get("id")
        logx(f"repom.removeRepository: removing idx={idx}, id={repr(repo_id)}, name={repr(repo.get('name'))}", True)

        try:
            if repo_id:
                cache_dir = _get_cache_dir()
                cache_path = os.path.join(cache_dir, f"{repo_id}.json")
                logx(f"repom.removeRepository: looking for cache at {cache_path}", True)
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    logx(f"repom.removeRepository: deleted cache {cache_path}", True)
                else:
                    logx(f"repom.removeRepository: cache not found at {cache_path}", True)
            else:
                logx("repom.removeRepository: repo has no id, skipping cache delete", True)
        except Exception as e:
            logx(f"repom.removeRepository: failed to delete cache: {e}", False)

        repos.pop(idx)
        self.setRepositories(repos)
        logx(f"repom.removeRepository: done, remaining repos={len(repos)}", True)
    
    def updateRepoField(self, idx, field, value):
        repos = self.getRepositories()
        if idx < len(repos):
            repos[idx][field] = value
            self.setRepositories(repos)
    
    def restoreDefaultRepository(self):
        def task():
            repometa = self._fetch_and_save_repomap(OFFICIAL_REPO_URL)
            newRepo = {
                "id": repometa.get("rm_rid") if repometa else "shareui_official",
                "name": repometa.get("rm_name", strings.official_repository) if repometa else strings.official_repository,
                "url": OFFICIAL_REPO_URL,
                "enabled": True,
                "collapsed": False,
                "icon": "chats_pin"
            }
            repos = self.getRepositories()
            repos.append(newRepo)
            self.setRepositories(repos)
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllItems"):
                fragment.rebuildAllItems()
        run_on_queue(task)
    
    def resetRepositories(self):
        def task():
            repometa = self._fetch_and_save_repomap(OFFICIAL_REPO_URL)
            defaultRepo = {
                "id": repometa.get("rm_rid") if repometa else "shareui_official",
                "name": repometa.get("rm_name", strings.official_repository) if repometa else strings.official_repository,
                "url": OFFICIAL_REPO_URL,
                "enabled": True,
                "collapsed": False,
                "icon": "chats_pin"
            }
            self.setRepositories([defaultRepo])
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllItems"):
                fragment.rebuildAllItems()
        run_on_queue(task)
    
    def clearAllExceptFirst(self):
        repos = self.getRepositories()
        if len(repos) > 0:
            self.setRepositories([repos[0]])
            
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllItems"):
                fragment.rebuildAllItems()

    def updateAllCaches(self, on_complete=None):
        def task():
            try:
                repos = self.getRepositories()
                cache_dir = _get_cache_dir()
                os.makedirs(cache_dir, exist_ok=True)
                changed = False
                to_remove = []
                seen_rids = set()

                for i, repo in enumerate(repos):
                    url = (repo.get("url") or "").strip()
                    if not url:
                        continue
                    try:
                        r = requests.get(url, timeout=10, headers=_HEADERS)
                        if r.status_code != 200:
                            logx(f"updateAllCaches: HTTP {r.status_code} for {url}", True)
                            continue
                        data = r.json()
                        repometa = data.get("repometa")
                        rm_rid = repometa.get("rm_rid") if repometa else None

                        # No repometa — remove repo
                        if not repometa or not rm_rid:
                            logx(f"updateAllCaches: no repometa for '{url}', removing repo", True)
                            to_remove.append(i)
                            changed = True
                            continue

                        # Duplicate check
                        if rm_rid in seen_rids:
                            logx(f"updateAllCaches: duplicate rm_rid='{rm_rid}', removing repo", True)
                            to_remove.append(i)
                            changed = True
                            continue
                        seen_rids.add(rm_rid)

                        if repo.get("id") != rm_rid:
                            repos[i]["id"] = rm_rid
                            changed = True
                            logx(f"updateAllCaches: set id='{rm_rid}' for repo '{repo.get('name')}'", True)

                        cache_path = os.path.join(cache_dir, f"{rm_rid}.json")
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        logx(f"updateAllCaches: updated cache for '{rm_rid}'", True)
                    except Exception as e:
                        logx(f"updateAllCaches: error for {url}: {e}", False)

                # Remove in reverse order to keep indices valid
                for i in sorted(to_remove, reverse=True):
                    repos.pop(i)

                if changed:
                    self.setRepositories(repos)
                logx("updateAllCaches: done", True)
            except Exception as e:
                logx(f"updateAllCaches: task error: {e}", False)
            finally:
                if on_complete:
                    try:
                        on_complete()
                    except Exception as e:
                        logx(f"updateAllCaches: on_complete error: {e}", False)

        run_on_queue(task)