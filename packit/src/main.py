# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any
from base_plugin import BasePlugin, HookResult, HookStrategy
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from .utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from .RepositoryManager import RepositoryManager
from .core import PackItCore
from .MainActivity import SettingsBuilder
from .DialogsActivity.button import ChatButton
from .deeplinks import setup_deeplink_hook
from .other.badges import BadgeManager
from .utils.localConfig import LocalConfig
from .other import isBeta
from .other import everyone as _everyone
from .other import text as _text
from .ChatActivity.SecurityBottomSheets import setup_policy_button_hook, setup_hash_button_hook
from .ChatActivity.LinksIcons import setup_links_buttons_hook
from .standaloneHooks.settingsActivityHook import setup_settings_activity_hook
from .SettingsActivity.service.fastExpandableHook import setup_fast_expandable_hook
from .DialogsActivity.pillWidget import setup_pill_widget, _unregister_pill
from .DialogsActivity.updatesWidget import setup_updates_widget
from .ui.PluginListActivity.service.InstallDismissHook import setup_install_dismiss_hook
from .ChatActivity.export.DecryptorBottomSheet import setup_packit_file_hook
from .ChatActivity.afpFile import setup_afp_file_hook
from .standaloneHooks.addPluginFab import setup_plugins_activity_fab
from .standaloneHooks.addIconsFab import setup_icon_packs_activity_fab
from .DialogsActivity.buildNotCorrect import setup_build_not_correct_check
from .ChatActivity.pluginAutocomplete import (
    setup_packit_autocomplete,
    _packit_get_class,
    _packit_hook_enter_view_constructor,
    _packit_attach_text_watcher,
    _packit_load_plugins_from_cache,
    _packit_show_loading_popup,
    _packit_search_in_background,
    _packit_show_matching_plugins,
    _packit_show_plugins_popup,
    _packit_hide_popup,
    _packit_send_plugin_info
)
from android_utils import log
import time

_launch_start = time.time()

CHECK_PATHS = False
RENAME_PACKITCACHE = False

def _migrate_packitcache():
    import os
    try:
        from .utils.paths import _filesDir
        base = _filesDir()
        old = base + "/packitCache"
        new = base + "/packit"
        if os.path.exists(old) and not os.path.exists(new):
            os.rename(old, new)
            log("PackIt: renamed packitCache -> packit")
    except Exception as e:
        log(f"PackIt: rename packitCache error: {e}")


def _check_paths():
    try:
        from .utils.paths import (
            getCacheRoot, getConfigsDir, getReposCacheDir,
            getTempDir, getPluginsDir, getElyxArchivesDir, getBitHashSoPath,
        )
        import os
        paths = {
            "cacheRoot": getCacheRoot(),
            "configsDir": getConfigsDir(),
            "reposCacheDir": getReposCacheDir(),
            "tempDir": getTempDir(),
            "pluginsDir": getPluginsDir(),
            "elyxArchivesDir": getElyxArchivesDir(),
            "bitHashSo": getBitHashSoPath(),
        }
        for name, path in paths.items():
            exists = os.path.exists(path)
            log(f"PackIt paths: {name} {'OK' if exists else 'NOT FOUND'} -> {path}")
    except Exception as e:
        log(f"PackIt paths: check failed: {e}")


# кстати тебя врядли выложат в utilits. Ты пофакту, повторил kpm. А как бы в utils правило второй вариант нельзя выкладыватьб
class PackItPlugin(BasePlugin):
    def __init__(self):
        self._launch_start = _launch_start
        super().__init__()
        self.repoManager = RepositoryManager()
        self.core = PackItCore(self.repoManager)
        self.chatUI = ChatButton(self)
        self.settingsBuilder = SettingsBuilder(self.repoManager, self)
        self.badgeManager = BadgeManager(self)
        self.on_send_message_hook_ref = None
        self.hook_settings_header_ref = None
        self.deeplink_hook_ref = None
        self.policy_button_hook_ref = None
        self.hash_button_hook_ref = None
        self.links_button_hook_ref = None
        self.dialogs_menu_hook_ref = None
        self.install_dismiss_hook_ref = None
        self.pill_widget_hook_ref = None
        self.settings_activity_hook_refs = []
        self.fast_expandable_hook_ref = None
        self.everyone_hook_refs = []
        self.packit_hook_constructor_ref = None
        self._init_time = time.time() - self._launch_start
        log(f"PackIt initialized in {self._init_time:.3f}s")
    
    def on_plugin_load(self):
        if RENAME_PACKITCACHE:
            _migrate_packitcache()
        if CHECK_PATHS:
            _check_paths()
        from .nativeLoader import CHECK_SO_PATHS, checkSoPaths
        if CHECK_SO_PATHS:
            checkSoPaths()
        LocalConfig.init()
        setup_build_not_correct_check()
        try:
            from .utils.installIndex import purge_missing
            purge_missing()
        except Exception as e:
            log(f"PackIt: installIndex purge error: {e}")
        isBeta.init()
        _everyone.init()
        try:
            from .ui.AchievementsActivity.service.AchivementsEngine import sync_accounts, sync_completed, _load_account, _save_account
            sync_accounts()
            loaded, load_ok = _load_account()
            data, _ = sync_completed(loaded)
            if load_ok:
                _save_account(data)
        except Exception as e:
            log(f"PackIt: achievements sync error: {e}")
        try:
            self._check_identity_achievement()
        except Exception as e:
            log(f"PackIt: identity achievement check error: {e}")
        self.repoManager.updateAllCaches()
        if settings.get("show_startup_status", False):
            self._show_startup_bulletin()
        self.add_on_send_message_hook()
        self.hook_settings_header_ref = self.settingsBuilder._setup_settings_header_hook()
        self.deeplink_hook_ref = setup_deeplink_hook(self)
        self.chatUI.initialize_chat_menu()
        self.badgeManager.setup_hooks()
        self.policy_button_hook_ref = setup_policy_button_hook(self)
        self.hash_button_hook_ref = setup_hash_button_hook(self, self.repoManager)
        self.links_button_hook_ref = setup_links_buttons_hook(self)
        self.install_dismiss_hook_ref = setup_install_dismiss_hook(self)
        setup_packit_file_hook(self)
        setup_afp_file_hook(self)
        self.plugins_activity_fab_ref = setup_plugins_activity_fab(self)
        self.icon_packs_activity_fab_ref = setup_icon_packs_activity_fab(self)
        self.settings_activity_hook_refs = setup_settings_activity_hook(self)
        self.fast_expandable_hook_ref = setup_fast_expandable_hook(self, self.settingsBuilder.otherSettings)
        setup_pill_widget(self)
        setup_updates_widget(self)
        self.dialogs_menu_hook_ref = self.chatUI.setup_dialogs_menu_hook()
        self.everyone_hook_refs = _everyone.setup_hook(self)
        self.packit_hook_constructor_ref = setup_packit_autocomplete(self)
        self._init_official_repository()
        self._check_for_update()
        if settings.get("show_updates_on_startup", False):
            self._check_startup_updates()
        if settings.get("update_notifications_bulletin", False):
            self._check_update_notifications_bulletin()
        launchTime = time.time() - self._launch_start
        log(f"PackIt was launched in {launchTime:.3f}s, launch time: {launchTime - self._init_time:.3f}s, initialization time: {self._init_time:.3f}s")

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
PackItPlugin._packit_send_plugin_info = _packit_send_plugin_info