
from packutil import logx
import time

CHECK_PATHS = False
RENAME_PACKITCACHE = False


def _migrate_packitcache():
    import os
    try:
        from ..utils.paths import _filesDir
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
        from ..utils.paths import (
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

    from ..ui.PluginActivity.fragment import process_start
    process_start()

    if RENAME_PACKITCACHE:
        _migrate_packitcache()
    if CHECK_PATHS:
        _check_paths()
    from ..nativeLoader import CHECK_SO_PATHS, checkSoPaths
    if CHECK_SO_PATHS:
        checkSoPaths()
    from ..utils.localConfig import LocalConfig
    LocalConfig.init()
    from ..DialogsActivity.buildNotCorrect import setup_build_not_correct_check
    setup_build_not_correct_check()
    try:
        from ..utils.installIndex import purge_missing
        purge_missing()
    except Exception as e:
        logx(f"PackIt: installIndex purge error: {e}", False)
    from ..other import isBeta
    from ..other import everyone as _everyone
    isBeta.init()
    _everyone.init()
    try:
        from ..ui.AchievementsActivity.service.AchivementsEngine import sync_accounts, sync_completed, _load_account, _save_account
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
    from ..deeplinks import setup_deeplink_hook
    plugin.deeplink_hook_ref = setup_deeplink_hook(plugin)
    plugin.chatUI.initialize_chat_menu()
    plugin.badgeManager.setup_hooks()
    from ..ChatActivity.SecurityBottomSheets import setup_policy_button_hook, setup_hash_button_hook
    plugin.policy_button_hook_ref = setup_policy_button_hook(plugin)
    plugin.hash_button_hook_ref = setup_hash_button_hook(plugin, plugin.repoManager)
    from ..ChatActivity.LinksIcons import setup_links_buttons_hook
    plugin.links_button_hook_ref = setup_links_buttons_hook(plugin)
    from ..ui.PluginListActivity.service.InstallDismissHook import setup_install_dismiss_hook
    plugin.install_dismiss_hook_ref = setup_install_dismiss_hook(plugin)
    from ..ChatActivity.export.DecryptorBottomSheet import setup_packit_file_hook
    setup_packit_file_hook(plugin)
    from ..ChatActivity.afpFile import setup_afp_file_hook
    setup_afp_file_hook(plugin)
    from ..standaloneHooks.addPluginFab import setup_plugins_activity_fab
    plugin.plugins_activity_fab_ref = setup_plugins_activity_fab(plugin)
    from ..standaloneHooks.addIconsFab import setup_icon_packs_activity_fab
    plugin.icon_packs_activity_fab_ref = setup_icon_packs_activity_fab(plugin)
    from ..standaloneHooks.settingsActivityHook import setup_settings_activity_hook
    plugin.settings_activity_hook_refs = setup_settings_activity_hook(plugin)
    from ..SettingsActivity.service.fastExpandableHook import setup_fast_expandable_hook
    plugin.fast_expandable_hook_ref = setup_fast_expandable_hook(plugin, plugin.settingsBuilder.otherSettings)
    from ..DialogsActivity.pillWidget import setup_pill_widget
    setup_pill_widget(plugin)
    from ..DialogsActivity.updatesWidget import setup_updates_widget
    setup_updates_widget(plugin)
    plugin.dialogs_menu_hook_ref = plugin.chatUI.setup_dialogs_menu_hook()
    plugin.everyone_hook_refs = _everyone.setup_hook(plugin)
    from ..ChatActivity.pluginAutocomplete import setup_packit_autocomplete
    plugin.packit_hook_constructor_ref = setup_packit_autocomplete(plugin)
    from ..ChatActivity.inlineBtns import setup_inline_translate_button
    setup_inline_translate_button(plugin)
    plugin._init_official_repository()
    plugin._check_for_update()
    if settings.get("show_updates_on_startup", False):
        plugin._check_startup_updates()
    if settings.get("update_notifications_bulletin", False):
        plugin._check_update_notifications_bulletin()
    launchTime = time.time() - plugin._launch_start
    logx(f"PackIt was launched in {launchTime:.3f}s, launch time: {launchTime - plugin._init_time:.3f}s, initialization time: {plugin._init_time:.3f}s", True)
