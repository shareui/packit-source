import os
import json
import requests
from client_utils import get_last_fragment, run_on_queue
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
from android_utils import log
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()

OFFICIAL_REPO_URL = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/repomap.json"


def _get_cache_dir() -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache"


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
        """Fetch repomap.json from url, save to packitCache/{rm_rid}.json, return repometa dict."""
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                log(f"repom: failed to fetch repomap from '{url}': HTTP {r.status_code}")
                return None
            data = r.json()
            repometa = data.get("repometa")
            if not repometa:
                log(f"repom: no 'repometa' key in response from '{url}'")
                return None
            rm_rid = repometa.get("rm_rid")
            if not rm_rid:
                log(f"repom: 'rm_rid' missing in repometa")
                return None
            cache_dir = _get_cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{rm_rid}.json")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log(f"repom: saved repomap to {cache_path}")
            return repometa
        except Exception as e:
            log(f"repom: _fetch_and_save_repomap error: {e}")
            return None

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
            log(f"repom.removeRepository: invalid idx={idx}, repos count={len(repos)}")
            return

        repo = repos[idx]
        repo_id = repo.get("id")
        log(f"repom.removeRepository: removing idx={idx}, id={repr(repo_id)}, name={repr(repo.get('name'))}")

        try:
            if repo_id:
                cache_dir = _get_cache_dir()
                cache_path = os.path.join(cache_dir, f"{repo_id}.json")
                log(f"repom.removeRepository: looking for cache at {cache_path}")
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    log(f"repom.removeRepository: deleted cache {cache_path}")
                else:
                    log(f"repom.removeRepository: cache not found at {cache_path}")
            else:
                log("repom.removeRepository: repo has no id, skipping cache delete")
        except Exception as e:
            log(f"repom.removeRepository: failed to delete cache: {e}")

        repos.pop(idx)
        self.setRepositories(repos)
        log(f"repom.removeRepository: done, remaining repos={len(repos)}")
    
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

    def updateAllCaches(self):
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
                        r = requests.get(url, timeout=10)
                        if r.status_code != 200:
                            log(f"updateAllCaches: HTTP {r.status_code} for {url}")
                            continue
                        data = r.json()
                        repometa = data.get("repometa")
                        rm_rid = repometa.get("rm_rid") if repometa else None

                        # No repometa — remove repo
                        if not repometa or not rm_rid:
                            log(f"updateAllCaches: no repometa for '{url}', removing repo")
                            to_remove.append(i)
                            changed = True
                            continue

                        # Duplicate check
                        if rm_rid in seen_rids:
                            log(f"updateAllCaches: duplicate rm_rid='{rm_rid}', removing repo")
                            to_remove.append(i)
                            changed = True
                            continue
                        seen_rids.add(rm_rid)

                        if repo.get("id") != rm_rid:
                            repos[i]["id"] = rm_rid
                            changed = True
                            log(f"updateAllCaches: set id='{rm_rid}' for repo '{repo.get('name')}'")

                        cache_path = os.path.join(cache_dir, f"{rm_rid}.json")
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        log(f"updateAllCaches: updated cache for '{rm_rid}'")
                    except Exception as e:
                        log(f"updateAllCaches: error for {url}: {e}")

                # Remove in reverse order to keep indices valid
                for i in sorted(to_remove, reverse=True):
                    repos.pop(i)

                if changed:
                    self.setRepositories(repos)
                log("updateAllCaches: done")
            except Exception as e:
                log(f"updateAllCaches: task error: {e}")

        run_on_queue(task)
