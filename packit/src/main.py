# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# all load logic(init, on_plugin_load) moved to the loader/ floder

from typing import Any
from base_plugin import BasePlugin, HookResult, HookStrategy
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from .utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from .other import text as _text
from .ChatActivity.pluginAutocomplete import (
    _packit_get_class,
    _packit_hook_enter_view_constructor,
    _packit_attach_text_watcher,
    _packit_load_plugins_from_cache,
    _packit_show_loading_popup,
    _packit_search_in_background,
    _packit_show_matching_plugins,
    _packit_show_plugins_popup,
    _packit_hide_popup,
    _packit_hook_container_dismiss,
    _packit_send_plugin_info
)
from android_utils import log
import time

from .loader.initRuntime import startInit
from .loader.onLoad import loadPlugin

_launch_start = time.time()

# кстати тебя врядли выложат в utilits. Ты пофакту, повторил kpm. А как бы в utils правило второй вариант нельзя выкладыватьб
class PackItPlugin(BasePlugin):
    def __init__(self): # init logic in the loader/initRuntime.py
        super().__init__()
        startInit(self, _launch_start)

    def on_plugin_load(self):
        loadPlugin(self) # load logic in the loader/onLoad.py

    def _show_startup_bulletin(self):
        try:
            from android_utils import run_on_ui_thread
            from ui.bulletin import BulletinHelper
            totalTime = time.time() - self._launch_start
            startupTime = totalTime - self._init_time
            text = f"PackIt: init {self._init_time:.3f}s startup {startupTime:.3f}s total {totalTime:.3f}s"
            import threading
            threading.Timer(1.5, lambda: run_on_ui_thread(lambda: BulletinHelper.show_info(text))).start()
        except Exception as e:
            log(f"PackIt: _show_startup_bulletin error: {e}")

    def _check_for_update(self):
        try:
            from .DialogsActivity.PackitUpdateSheet import check_and_show
            check_and_show()
        except Exception as e:
            log(f"PackIt: update check error: {e}")

    def _check_startup_updates(self):
        try:
            from .ui.pluginsUpdates.startupSheet import check_and_show_startup_updates
            check_and_show_startup_updates(plugin=self)
        except Exception as e:
            log(f"PackIt: startup updates check error: {e}")

    def _check_update_notifications_bulletin(self):
        import threading

        def task():
            try:
                from .ui.pluginsUpdates.fragment import _check_updates, _filter_ignored
                updates = _filter_ignored(None, _check_updates(None))
                if not updates:
                    return
                count = len(updates)
                from elyx import strings
                single = count == 1
                if single:
                    text = str(strings.msg_one_plugin_updated)
                    btn_text = str(strings.msg_one_plugin_install)
                    single_update = updates[0]
                else:
                    text = str(strings.msg_plugins_updated).format(count=count)
                    btn_text = str(strings.msg_plugins_open)
                    single_update = None

                import time
                time.sleep(2.5)

                from android_utils import run_on_ui_thread
                from client_utils import get_last_fragment
                from org.telegram.ui.Components import BulletinFactory
                from org.telegram.messenger import R as R_tg
                from java import dynamic_proxy
                from java.lang import Runnable

                class _Runnable(dynamic_proxy(Runnable)):
                    def __init__(self, fn):
                        super().__init__()
                        self._fn = fn
                    def run(self):
                        try:
                            self._fn()
                        except Exception as _e:
                            log(f"PackIt: update bulletin runnable error: {_e}")

                def show():
                    try:
                        fragment = get_last_fragment()
                        if not fragment:
                            return
                        try:
                            import os as _os
                            from .utils.media import playSound
                            _snd = _os.path.join(_os.path.dirname(__file__), "../res/sounds/available-updates.opus")
                            playSound(_snd, "sfx_available_updates")
                        except Exception as _e:
                            log(f"PackIt: update bulletin sound error: {_e}")
                        if single_update is not None:
                            def _install():
                                try:
                                    from .ui.pluginsUpdates.fragment import _get_repos, _get_repo_plugins_url
                                    import requests as _req
                                    pid = str(single_update.get("id") or "")
                                    repo_id = str(single_update.get("repo_id") or "")
                                    repos = _get_repos()
                                    repo = next((r for r in repos if str(r.get("id") or "") == repo_id), None)
                                    if not repo:
                                        log(f"PackIt: update bulletin install: repo '{repo_id}' not found")
                                        return
                                    repo_url = str(repo.get("url") or "").strip()
                                    plugins_url = _get_repo_plugins_url(None, repo_id, repo_url)
                                    r = _req.get(plugins_url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
                                    if r.status_code != 200:
                                        log(f"PackIt: update bulletin install: HTTP {r.status_code}")
                                        return
                                    data = r.json()
                                    plugins_raw = data.get("plugins", {})
                                    plugin = None
                                    all_plugins = []
                                    if isinstance(plugins_raw, dict):
                                        for _pid, info in plugins_raw.items():
                                            if isinstance(info, dict):
                                                all_plugins.append({"id": _pid, **info})
                                        info = plugins_raw.get(pid)
                                        if isinstance(info, dict):
                                            plugin = {"id": pid, **info}
                                    elif isinstance(plugins_raw, list):
                                        all_plugins = [p for p in plugins_raw if isinstance(p, dict)]
                                        for p in plugins_raw:
                                            if isinstance(p, dict) and p.get("id") == pid:
                                                plugin = p
                                                break
                                    if not plugin:
                                        log(f"PackIt: update bulletin install: plugin '{pid}' not found in repo")
                                        return
                                    from .core import install_plugin
                                    run_on_ui_thread(lambda: install_plugin(plugin, all_plugins=all_plugins, rm_rid=repo_id))
                                except Exception as _e:
                                    log(f"PackIt: update bulletin install error: {_e}")
                            from client_utils import run_on_queue
                            _action = lambda: run_on_queue(_install)
                        else:
                            def _action():
                                try:
                                    from .ui.pluginsUpdates.fragment import show_updates_fragment
                                    show_updates_fragment()
                                except Exception as _e:
                                    log(f"PackIt: update bulletin open error: {_e}")
                        factory = BulletinFactory.of(fragment)
                        bulletin = factory.createSimpleBulletin(
                            R_tg.raw.info, text, btn_text, _Runnable(_action)
                        )
                        bulletin.show(True)
                    except Exception as _e:
                        log(f"PackIt: update bulletin show error: {_e}")

                run_on_ui_thread(show)
            except Exception as e:
                log(f"PackIt: _check_update_notifications_bulletin error: {e}")

        threading.Thread(target=task, daemon=True).start()

    def _check_identity_achievement(self):
        from org.telegram.messenger import UserConfig, MessagesController
        account = UserConfig.selectedAccount
        user = UserConfig.getInstance(account).getCurrentUser()
        if not user:
            return
        first_name = str(user.first_name) if user.first_name else ""
        if first_name.lower() in ("shareui", "fuchs"):
            from .ui.AchievementsActivity.service.AchivementsEngine import unlock_secret
            unlock_secret("identity")

    def _init_official_repository(self):
        try:
            repos = self.repoManager.getRepositories()
            if not repos:
                self.repoManager.addRepository(isFirst=True)
        except Exception:
            pass

    def on_send_message_hook(self, account: int, params: Any) -> HookResult:
        if not isinstance(params.message, str):
            return HookResult()

        _text.check_message(params.message)

        if params.message.startswith(".deleteachievements"):
            try:
                import os
                from .ui.AchievementsActivity.service.AchivementsEngine import _get_db_path, _get_snap_path
                for path in (_get_db_path(), _get_snap_path()):
                    if os.path.exists(path):
                        os.remove(path)
                params.message = "Achievements deleted!"
            except Exception as e:
                params.message = f"Failed to delete achievements: {e}"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)

        return HookResult()

    def on_plugin_unload(self):
        try:
            if hasattr(self, 'badgeManager'):
                self.badgeManager.cleanup()
            if hasattr(self, 'packit_hook_constructor_ref') and self.packit_hook_constructor_ref:
                try:
                    self.unhook_method(self.packit_hook_constructor_ref)
                except Exception:
                    pass
        except Exception as e:
            log(f"Error cleaning up badge manager: {e}")

    def create_settings(self):
        return self.settingsBuilder.buildMainSettings()


PackItPlugin._packit_get_class = _packit_get_class
PackItPlugin._packit_hook_enter_view_constructor = _packit_hook_enter_view_constructor
PackItPlugin._packit_attach_text_watcher = _packit_attach_text_watcher
PackItPlugin._packit_load_plugins_from_cache = _packit_load_plugins_from_cache
PackItPlugin._packit_show_loading_popup = _packit_show_loading_popup
PackItPlugin._packit_search_in_background = _packit_search_in_background
PackItPlugin._packit_show_matching_plugins = _packit_show_matching_plugins
PackItPlugin._packit_show_plugins_popup = _packit_show_plugins_popup
PackItPlugin._packit_hide_popup = _packit_hide_popup
PackItPlugin._packit_hook_container_dismiss = _packit_hook_container_dismiss
PackItPlugin._packit_send_plugin_info = _packit_send_plugin_info
