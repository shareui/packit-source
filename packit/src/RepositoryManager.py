# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from .utils.NetQueue import run_serial_io
from .network import Storage
from .utils import CachedRepos
import json
from client_utils import get_last_fragment, run_on_queue
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from .utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()

try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from .utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()

OFFICIAL_REPO_URL = "https://raw.githubusercontent.com/shareui/packit/refs/heads/main/configs/repomap.json"

# A repository name is a label, not a document. It is drawn on one line in the
# source card, in both repository pickers and in the plugin list, and it arrives
# from a remote repomap that is free to put anything at all in rm_name — so the
# limit belongs here, on the way into storage, and not on each screen that has
# to render whatever it finds. Thirty-two is about what the card fits at 17sp on
# a narrow phone, and comfortably more than any real name so far ("exteraGram
# Utilities" is twenty).
REPO_NAME_MAX = 32


def clampRepoName(value) -> str:
    text = str(value or "")
    # the name is single-line everywhere it appears, so a newline or a tab in it
    # is only ever a way to break someone's layout
    text = " ".join(text.split())
    if len(text) > REPO_NAME_MAX:
        text = text[:REPO_NAME_MAX - 1].rstrip() + "…"
    return text


class RepositoryManager:
    def __init__(self):
        pass
    
    def getRepositories(self):
        reposJson = settings.get("repositories", "[]")
        try:
            repos = json.loads(reposJson)
            if not isinstance(repos, list):
                return []
            # also on the way out: names stored before the limit existed are
            # already on disk, and nothing rewrites them until the list changes
            for repo in repos:
                if isinstance(repo, dict) and "name" in repo:
                    repo["name"] = clampRepoName(repo.get("name"))
            return repos
        except Exception:
            return []
    
    def setRepositories(self, repos):
        # every write lands here — the add sheet, the edit dialog, the repo=add
        # deeplink, the startup cache refresh — so the name limit is applied
        # once, in place, and the caller's list matches what was stored
        for repo in repos:
            if isinstance(repo, dict) and "name" in repo:
                repo["name"] = clampRepoName(repo.get("name"))
        settings.set("repositories", json.dumps(repos), reload_settings=True)
        try:
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllItems"):
                fragment.rebuildAllItems()
        except Exception:
            pass
        # the sources screen is a plain fragment with no adapter, so
        # rebuildAllItems never reaches it — it listens here instead
        try:
            from .ui.reposactivity import notify_repos_changed
            notify_repos_changed()
        except Exception:
            pass
    
    def _fetch_and_save_repomap(self, url: str) -> dict | None:
        """Fetch a repomap, cache it, return its repometa. None if any of that fails."""
        data, error = Storage.fetch_repomap(url)
        if error:
            logx(f"repom: cannot fetch repomap from '{url}': {error}", True)
            return None
        repometa = data.get("repometa")
        if not CachedRepos.write(repometa.get("rm_rid"), data):
            return None
        return repometa

    def addRepositoryWithUrl(self, url: str):
        # returns (repometa, error_reason) — error_reason is None on success.
        #
        # This used to download into packitTemp and move the file into the cache
        # once it validated. Storage validates what it parsed before anything is
        # written, so there is nothing to stage: a repomap that fails its checks
        # never reaches the disk in the first place.
        logx(f"repom: addRepositoryWithUrl: GET {url}", True)
        data, error = Storage.fetch_repomap(url)
        if error:
            logx(f"repom: addRepositoryWithUrl: {error}", True)
            return None, error

        repometa = data.get("repometa")
        rm_rid = repometa.get("rm_rid")
        rm_name = repometa.get("rm_name")
        logx(f"repom: addRepositoryWithUrl: rm_rid={repr(rm_rid)} rm_name={repr(rm_name)}", True)
        if not rm_name:
            return None, "missing rm_name"

        if not CachedRepos.write(rm_rid, data):
            return None, "cache write failed"

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
            run_serial_io(task)
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

        if repo_id:
            dropped = CachedRepos.forget(repo_id)
            logx(f"repom.removeRepository: cache for '{repo_id}' "
                 f"{'deleted' if dropped else 'was not there'}", True)

        repos.pop(idx)
        self.setRepositories(repos)
        logx(f"repom.removeRepository: done, remaining repos={len(repos)}", True)
    
    def updateRepoField(self, idx, field, value):
        repos = self.getRepositories()
        if idx < len(repos):
            repos[idx][field] = value
            self.setRepositories(repos)
    
    def restoreDefaultRepository(self, on_done=None):
        # "restore" means make sure the official repository is there and usable,
        # not append another copy of it: it used to append unconditionally, so
        # pressing the item twice left two identical entries, and again a third.
        def task():
            repometa = self._fetch_and_save_repomap(OFFICIAL_REPO_URL)
            rm_rid = repometa.get("rm_rid") if repometa else "shareui_official"
            rm_name = repometa.get("rm_name", strings.official_repository) if repometa else strings.official_repository

            repos = self.getRepositories()
            existing = -1
            for i, repo in enumerate(repos):
                if str(repo.get("id") or "") == str(rm_rid):
                    existing = i
                    break
                if str(repo.get("url") or "").strip() == OFFICIAL_REPO_URL:
                    existing = i
                    break

            if existing >= 0:
                # already present: repair it instead — that is what someone
                # reaching for "restore" after disabling or renaming it wants
                repos[existing]["id"] = rm_rid
                repos[existing]["url"] = OFFICIAL_REPO_URL
                repos[existing]["enabled"] = True
                if not str(repos[existing].get("name") or "").strip():
                    repos[existing]["name"] = rm_name
                restored = False
            else:
                repos.append({
                    "id": rm_rid,
                    "name": rm_name,
                    "url": OFFICIAL_REPO_URL,
                    "enabled": True,
                    "collapsed": False,
                    "icon": "chats_pin",
                })
                restored = True

            self.setRepositories(repos)
            fragment = get_last_fragment()
            if fragment and hasattr(fragment, "rebuildAllItems"):
                fragment.rebuildAllItems()
            if on_done:
                try:
                    on_done(restored)
                except Exception as e:
                    logx(f"repom: restoreDefaultRepository on_done error: {e}", False)
        run_serial_io(task)
    
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
        run_serial_io(task)
    
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
                changed = False
                to_remove = []
                seen_rids = set()

                for i, repo in enumerate(repos):
                    url = (repo.get("url") or "").strip()
                    if not url:
                        continue
                    try:
                        data, error = Storage.fetch_repomap(url)
                        if error in ("missing repometa", "missing rm_rid"):
                            # it answered, and what it answered with is not a
                            # repository — drop it
                            logx(f"updateAllCaches: '{url}' is not a repomap ({error}), removing", True)
                            to_remove.append(i)
                            changed = True
                            continue
                        if error:
                            # unreachable or unparseable: keep the repository and
                            # whatever is already cached for it
                            logx(f"updateAllCaches: {error} for {url}", True)
                            continue
                        repometa = data.get("repometa")
                        rm_rid = repometa.get("rm_rid")

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

                        # a repository left without a name shows up as "unnamed"
                        # everywhere; the repomap has one, and this runs on every
                        # start, so take it back rather than leave it that way
                        if not str(repo.get("name") or "").strip():
                            rm_name = str(repometa.get("rm_name") or "").strip()
                            if rm_name:
                                repos[i]["name"] = rm_name
                                changed = True
                                logx(f"updateAllCaches: restored name '{rm_name}' for '{rm_rid}'", True)

                        CachedRepos.write(rm_rid, data)
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

        run_serial_io(task)