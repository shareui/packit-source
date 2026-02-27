from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment, run_on_queue
from android_utils import log, run_on_ui_thread
from urllib.parse import urlparse, parse_qs
from ..core import install_plugin
from ..ui.installUi.uiMain import InstallUI
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()
import requests
import json
import os

try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..other.importFailed import showImportFailedAlert as _sifa; _sifa()

# install&repo=<rm_id>: required: repo — optional: plugin
_INSTALL_REQUIRED = {"repo"}
_INSTALL_OPTIONAL = {"plugin"}
_INSTALL_ALL = _INSTALL_REQUIRED | _INSTALL_OPTIONAL


def _getCachePath(repoId: str) -> str:
    pkg = ApplicationLoader.applicationContext.getPackageName()
    return f"/data/data/{pkg}/files/packitCache/{repoId}.json"


def _findRepo(repoManager, repoId: str) -> dict | None:
    try:
        for r in (repoManager.getRepositories() or []):
            if r.get("id") == repoId:
                return r
    except Exception:
        pass
    return None


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


def handle(url, repoManager):
    try:
        if "install&repo=" not in url:
            if url == "tg://packit?install":
                _handleOpenInstall(repoManager)
            return

        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        # exclude the implicit 'install' flag key
        argKeys = {k for k in query.keys() if k != "install"}

        if not _INSTALL_REQUIRED.issubset(argKeys):
            BulletinHelper.show_error(strings.deeplink_too_few_args)
            return

        if not argKeys.issubset(_INSTALL_ALL):
            BulletinHelper.show_error(strings.deeplink_too_many_args)
            return

        repoId = query.get("repo", [""])[0].strip()
        pluginId = query.get("plugin", [""])[0].strip()

        if not repoId:
            BulletinHelper.show_error(strings.deeplink_too_few_args)
            return

        repo = _findRepo(repoManager, repoId)
        if not repo:
            BulletinHelper.show_error(f"Repository '{repoId}' not found")
            return

        if not pluginId:
            installUI = InstallUI(type("_P", (), {"repoManager": repoManager})())
            installUI._open_repo_plugins(repo)
            return

        _handleInstallPlugin(repo, pluginId)
    except Exception as e:
        log(f"deeplinks.install: error: {e}")


def _handleOpenInstall(repoManager):
    try:
        class _FakePlugin:
            def __init__(self, rm):
                self.repoManager = rm
        installUI = InstallUI(_FakePlugin(repoManager))
        installUI.open()
    except Exception as e:
        log(f"deeplinks.install: open error: {e}")


def _handleInstallPlugin(repo: dict, pluginId: str):
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
            if isinstance(pluginsRaw, dict):
                info = pluginsRaw.get(pluginId)
                if isinstance(info, dict):
                    plugin = {"id": pluginId, **info}
            elif isinstance(pluginsRaw, list):
                for item in pluginsRaw:
                    if isinstance(item, dict) and item.get("id") == pluginId:
                        plugin = item
                        break

            if not plugin:
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Plugin '{pluginId}' not found"))
                return

            run_on_ui_thread(lambda: install_plugin(plugin))
        except Exception as e:
            log(f"deeplinks.install: fetch error: {e}")
            run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while loading plugin"))

    run_on_queue(task)
