from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import log, run_on_ui_thread
from urllib.parse import urlparse, parse_qs
import requests
import json
import os

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"deeplinks.plugin: import strings failed: {e}")

try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"deeplinks.plugin: import ApplicationLoader failed: {e}")


_REQUIRED = {"plugin", "repo"}


def _getCachePath(repoId: str) -> str:
    from ..utils._paths import getRepoCachePath
    return getRepoCachePath(repoId)


def _resolvePluginsUrl(repo: dict) -> str:
    repoId = (repo.get("id") or "").strip()
    fallback = (repo.get("url") or "").strip()
    if not repoId:
        return fallback
    try:
        cachePath = _getCachePath(repoId)
        if os.path.exists(cachePath):
            with open(cachePath, "r", encoding="utf-8") as f:
                cached = json.load(f)
            return cached.get("repomap", {}).get("plugins") or fallback
    except Exception:
        pass
    return fallback


def _findRepo(repoManager, repoId: str) -> dict | None:
    try:
        for r in (repoManager.getRepositories() or []):
            if r.get("id") == repoId:
                return r
    except Exception:
        pass
    return None


def handle(url, repoManager):
    try:
        # decode HTML entities (e.g. &amp; -> &)
        url = url.replace("&amp;", "&")

        if "plugin&" not in url and "?plugin=" not in url:
            return

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)

        pluginId = query.get("plugin", [""])[0].strip()
        repoId = query.get("repo", [""])[0].strip()

        if not pluginId or not repoId:
            BulletinHelper.show_error(str(strings.deeplink_too_few_args))
            return

        repo = _findRepo(repoManager, repoId)
        if not repo:
            BulletinHelper.show_error(f"Repository '{repoId}' not found")
            return

        _openPluginProfile(repo, pluginId, repoId, repoManager)
    except Exception as e:
        log(f"deeplinks.plugin: error: {e}")


def _openPluginProfile(repo: dict, pluginId: str, repoId: str, repoManager):
    def task():
        try:
            pluginsUrl = _resolvePluginsUrl(repo)
            if not pluginsUrl:
                run_on_ui_thread(lambda: BulletinHelper.show_error("Repository URL is empty"))
                return

            r = requests.get(pluginsUrl, timeout=15)
            if r.status_code != 200:
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Failed to load repository: HTTP {r.status_code}"))
                return

            data = r.json()
            pluginsRaw = data.get("plugins", [])

            plugin = None
            all_plugins = []
            if isinstance(pluginsRaw, dict):
                for pid, info in pluginsRaw.items():
                    if isinstance(info, dict):
                        all_plugins.append({"id": pid, **info})
                info = pluginsRaw.get(pluginId)
                if isinstance(info, dict):
                    plugin = {"id": pluginId, **info}
            elif isinstance(pluginsRaw, list):
                all_plugins = [p for p in pluginsRaw if isinstance(p, dict)]
                for item in all_plugins:
                    if item.get("id") == pluginId:
                        plugin = item
                        break

            if not plugin:
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Plugin '{pluginId}' not found"))
                return

            from ..ui.PluginListActivity.fragment import InstallUI

            class _FakePlugin:
                def __init__(self, rm):
                    self.repoManager = rm

            installUI = InstallUI(_FakePlugin(repoManager))

            def _show(_p=plugin, _all=all_plugins, _rid=repoId):
                from ..ui.PluginActivity.fragment import show_plugin_profile
                show_plugin_profile(_p, installUI, _all, repo_id=_rid)

            run_on_ui_thread(_show)
        except Exception as e:
            log(f"deeplinks.plugin: fetch error: {e}")
            run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while loading plugin"))

    run_on_queue(task)
