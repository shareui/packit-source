# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import time
from typing import Any
from .other import text as _text
from .ChatActivity.inline.enterView import (
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

CHECK_PATHS = False
RENAME_PACKITCACHE = False


def _clearLatestLog():
    try:
        from .utils.paths import getCacheRoot, getPluginsDir
        import os, json
        settingsPath = getPluginsDir() + "/plugin_settings.json"
        # TEMP: clean_logs defaults to OFF while debugging the post-restart
        # settings breakage, so the failed session's log survives the next
        # start; only an explicit clean_logs=true wipes it. Revert to
        # default-True (and wipe when settings file is missing) afterwards.
        if not os.path.exists(settingsPath):
            return
        with open(settingsPath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("shareui_packit", {}).get("clean_logs", False):
            return
        path = getCacheRoot() + "/latestlog.txt"
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def startInit(plugin, launchStart):
    _clearLatestLog()

    from .RepositoryManager import RepositoryManager
    from .core import PackItCore
    from .MainActivity import SettingsBuilder
    from .DialogsActivity.button import ChatButton
    from .other.badges import BadgeManager

    plugin._launch_start = launchStart
    plugin.repoManager = RepositoryManager()
    plugin.core = PackItCore(plugin.repoManager)
    plugin.chatUI = ChatButton(plugin)
    plugin.settingsBuilder = SettingsBuilder(plugin.repoManager, plugin)
    plugin.badgeManager = BadgeManager(plugin)
    plugin.on_send_message_hook_ref = None
    plugin.hook_settings_header_ref = None
    plugin.deeplink_hook_ref = None
    plugin.policy_button_hook_ref = None
    plugin.hash_button_hook_ref = None
    plugin.links_button_hook_ref = None
    plugin.dialogs_menu_hook_ref = None
    plugin.install_dismiss_hook_ref = None
    plugin.pill_widget_hook_ref = None
    plugin.settings_activity_hook_refs = []
    plugin.fast_expandable_hook_ref = None
    plugin.everyone_hook_refs = []
    plugin.packit_hook_constructor_ref = None
    plugin._init_time = time.time() - plugin._launch_start
    logx(f"PackIt initialized in {plugin._init_time:.3f}s", True)


def _migrate_packitcache():
    import os
    try:
        from .utils.paths import _filesDir
        base = _filesDir()
        old = base + "/packitCache"
        new = base + "/packit"
        if os.path.exists(old) and not os.path.exists(new):
            os.rename(old, new)
            logx("PackIt: renamed packitCache -> packit", True)
    except Exception as e:
        logx(f"PackIt: rename packitCache error: {e}", False)


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
            logx(f"PackIt paths: {name} {'OK' if exists else 'NOT FOUND'} -> {path}", True)
    except Exception as e:
        logx(f"PackIt paths: check failed: {e}", False)


def loadPlugin(plugin):
    try:
        from elyx import settings
    except Exception as e:
        logx(f"PackIt: import settings failed: {e}", False)
        return

    from .ui.PluginActivity.fragment import process_start
    process_start()

    if RENAME_PACKITCACHE:
        _migrate_packitcache()
    if CHECK_PATHS:
        _check_paths()
    from .nativeLoader import CHECK_SO_PATHS, checkSoPaths
    if CHECK_SO_PATHS:
        checkSoPaths()
    from .utils.localConfig import LocalConfig
    LocalConfig.init()
    from .DialogsActivity.buildNotCorrect import setup_build_not_correct_check
    setup_build_not_correct_check()
    try:
        from .utils.installIndex import purge_missing
        purge_missing()
    except Exception as e:
        logx(f"PackIt: installIndex purge error: {e}", False)
    from .other import isBeta
    from .other import everyone as _everyone
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
        logx(f"PackIt: achievements sync error: {e}", False)
    try:
        plugin._check_identity_achievement()
    except Exception as e:
        logx(f"PackIt: identity achievement check error: {e}", False)
    plugin.repoManager.updateAllCaches()
    if settings.get("show_startup_status", False):
        plugin._show_startup_bulletin()
    plugin.add_on_send_message_hook()
    plugin.hook_settings_header_ref = plugin.settingsBuilder._setup_settings_header_hook()
    from .deeplinks import setup_deeplink_hook
    plugin.deeplink_hook_ref = setup_deeplink_hook(plugin)
    plugin.chatUI.initialize_chat_menu()
    plugin.badgeManager.setup_hooks()
    from .ChatActivity.SecurityBottomSheets import setup_policy_button_hook, setup_hash_button_hook
    plugin.policy_button_hook_ref = setup_policy_button_hook(plugin)
    plugin.hash_button_hook_ref = setup_hash_button_hook(plugin, plugin.repoManager)
    from .ChatActivity.LinksIcons import setup_links_buttons_hook
    plugin.links_button_hook_ref = setup_links_buttons_hook(plugin)
    from .standaloneHooks.InstallDismissHook import setup_install_dismiss_hook
    plugin.install_dismiss_hook_ref = setup_install_dismiss_hook(plugin)
    from .ChatActivity.export.DecryptorBottomSheet import setup_packit_file_hook
    setup_packit_file_hook(plugin)
    from .ChatActivity.afpFile import setup_afp_file_hook
    setup_afp_file_hook(plugin)
    from .standaloneHooks.addPluginFab import setup_plugins_activity_fab
    plugin.plugins_activity_fab_ref = setup_plugins_activity_fab(plugin)
    from .standaloneHooks.addIconsFab import setup_icon_packs_activity_fab
    plugin.icon_packs_activity_fab_ref = setup_icon_packs_activity_fab(plugin)
    from .standaloneHooks.settingsActivityHook import setup_settings_activity_hook
    plugin.settings_activity_hook_refs = setup_settings_activity_hook(plugin)
    from .SettingsActivity.service.fastExpandableHook import setup_fast_expandable_hook
    plugin.fast_expandable_hook_ref = setup_fast_expandable_hook(plugin, plugin.settingsBuilder.otherSettings)
    from .DialogsActivity.pillWidget import setup_pill_widget
    setup_pill_widget(plugin)
    from .DialogsActivity.updatesWidget import setup_updates_widget
    setup_updates_widget(plugin)
    plugin.dialogs_menu_hook_ref = plugin.chatUI.setup_dialogs_menu_hook()
    plugin.everyone_hook_refs = _everyone.setup_hook(plugin)
    from .ChatActivity.inline.enterView import setup_packit_autocomplete
    plugin.packit_hook_constructor_ref = setup_packit_autocomplete(plugin)
    from .ChatActivity.inline.inlineBtns import setup_inline_translate_button
    setup_inline_translate_button(plugin)
    plugin._init_official_repository()
    plugin._check_for_update()
    if settings.get("show_updates_on_startup", False):
        plugin._check_startup_updates()
    if settings.get("update_notifications_bulletin", False):
        plugin._check_update_notifications_bulletin()
    launchTime = time.time() - plugin._launch_start
    logx(f"PackIt was launched in {launchTime:.3f}s, launch time: {launchTime - plugin._init_time:.3f}s, initialization time: {plugin._init_time:.3f}s", True)


def _show_startup_bulletin(plugin):
    try:
        from android_utils import run_on_ui_thread
        from ui.bulletin import BulletinHelper
        totalTime = time.time() - plugin._launch_start
        startupTime = totalTime - plugin._init_time
        text = f"PackIt: init {plugin._init_time:.3f}s startup {startupTime:.3f}s total {totalTime:.3f}s"
        import threading
        threading.Timer(1.5, lambda: run_on_ui_thread(lambda: BulletinHelper.show_info(text))).start()
    except Exception as e:
        logx(f"PackIt: _show_startup_bulletin error: {e}", False)


def _check_for_update(plugin):
    try:
        from .DialogsActivity.PackitUpdateSheet import check_and_show
        check_and_show()
    except Exception as e:
        logx(f"PackIt: update check error: {e}", False)


def _check_startup_updates(plugin):
    try:
        from .ui.pluginsUpdates.startupSheet import check_and_show_startup_updates
        check_and_show_startup_updates(plugin=plugin)
    except Exception as e:
        logx(f"PackIt: startup updates check error: {e}", False)


def _check_update_notifications_bulletin(plugin):
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
                        logx(f"PackIt: update bulletin runnable error: {_e}", True)

            def show():
                try:
                    fragment = get_last_fragment()
                    if not fragment:
                        return
                    try:
                        from elyx import assets
                        from .utils.media import playSound
                        _snd = assets.sounds.available_updates.path_str
                        playSound(_snd, "sfx_available_updates")
                    except Exception as _e:
                        logx(f"PackIt: update bulletin sound error: {_e}", True)
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
                                    logx(f"PackIt: update bulletin install: repo '{repo_id}' not found", True)
                                    return
                                repo_url = str(repo.get("url") or "").strip()
                                plugins_url = _get_repo_plugins_url(None, repo_id, repo_url)
                                r = _req.get(plugins_url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
                                if r.status_code != 200:
                                    logx(f"PackIt: update bulletin install: HTTP {r.status_code}", True)
                                    return
                                data = r.json()
                                plugins_raw = data.get("plugins", {})
                                plugin_item = None
                                all_plugins = []
                                if isinstance(plugins_raw, dict):
                                    for _pid, info in plugins_raw.items():
                                        if isinstance(info, dict):
                                            all_plugins.append({"id": _pid, **info})
                                    info = plugins_raw.get(pid)
                                    if isinstance(info, dict):
                                        plugin_item = {"id": pid, **info}
                                elif isinstance(plugins_raw, list):
                                    all_plugins = [p for p in plugins_raw if isinstance(p, dict)]
                                    for p in plugins_raw:
                                        if isinstance(p, dict) and p.get("id") == pid:
                                            plugin_item = p
                                            break
                                if not plugin_item:
                                    logx(f"PackIt: update bulletin install: plugin '{pid}' not found in repo", True)
                                    return
                                from .core import install_plugin
                                run_on_ui_thread(lambda: install_plugin(plugin_item, all_plugins=all_plugins, rm_rid=repo_id))
                            except Exception as _e:
                                logx(f"PackIt: update bulletin install error: {_e}", True)
                        from client_utils import run_on_queue
                        _action = lambda: run_on_queue(_install)
                    else:
                        def _action():
                            try:
                                from .ui.pluginsUpdates.fragment import show_updates_fragment
                                show_updates_fragment()
                            except Exception as _e:
                                logx(f"PackIt: update bulletin open error: {_e}", True)
                    factory = BulletinFactory.of(fragment)
                    bulletin = factory.createSimpleBulletin(
                        R_tg.raw.info, text, btn_text, _Runnable(_action)
                    )
                    bulletin.show(True)
                except Exception as _e:
                    logx(f"PackIt: update bulletin show error: {_e}", True)

            run_on_ui_thread(show)
        except Exception as e:
            logx(f"PackIt: _check_update_notifications_bulletin error: {e}", False)

    threading.Thread(target=task, daemon=True).start()


def _check_identity_achievement(plugin):
    from org.telegram.messenger import UserConfig, MessagesController
    account = UserConfig.selectedAccount
    user = UserConfig.getInstance(account).getCurrentUser()
    if not user:
        return
    first_name = str(user.first_name) if user.first_name else ""
    if first_name.lower() in ("shareui", "fuchs"):
        from .ui.AchievementsActivity.service.AchivementsEngine import unlock_secret
        unlock_secret("identity")


def _init_official_repository(plugin):
    try:
        repos = plugin.repoManager.getRepositories()
        if not repos:
            plugin.repoManager.addRepository(isFirst=True)
    except Exception:
        pass


def on_send_message_hook(plugin, account: int, params: Any):
    from base_plugin import HookResult, HookStrategy
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


def on_plugin_unload(plugin):
    try:
        if hasattr(plugin, 'badgeManager'):
            plugin.badgeManager.cleanup()
        if hasattr(plugin, 'packit_hook_constructor_ref') and plugin.packit_hook_constructor_ref:
            try:
                plugin.unhook_method(plugin.packit_hook_constructor_ref)
            except Exception:
                pass
    except Exception as e:
        logx(f"Error cleaning up badge manager: {e}", False)


def create_settings(plugin):
    try:
        items = plugin.settingsBuilder.buildMainSettings()
        # TEMP: always-on diagnostic for the post-restart blank settings issue
        logx(f"PackIt: create_settings -> {len(items)} items", False)
        return items
    except Exception as e:
        import traceback
        logx(f"PackIt: create_settings failed: {e}\n{traceback.format_exc()}", False)
        raise


_AUTOCOMPLETE_METHODS = {
    "_packit_get_class": _packit_get_class,
    "_packit_hook_enter_view_constructor": _packit_hook_enter_view_constructor,
    "_packit_attach_text_watcher": _packit_attach_text_watcher,
    "_packit_load_plugins_from_cache": _packit_load_plugins_from_cache,
    "_packit_show_loading_popup": _packit_show_loading_popup,
    "_packit_search_in_background": _packit_search_in_background,
    "_packit_show_matching_plugins": _packit_show_matching_plugins,
    "_packit_show_plugins_popup": _packit_show_plugins_popup,
    "_packit_hide_popup": _packit_hide_popup,
    "_packit_hook_container_dismiss": _packit_hook_container_dismiss,
    "_packit_send_plugin_info": _packit_send_plugin_info,
}
