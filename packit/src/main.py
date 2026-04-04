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
from .ChatActivity.SecurityBottomSheets import setup_policy_button_hook, setup_hash_button_hook
from .ChatActivity.LinksIcons import setup_links_buttons_hook
from .SettingsActivity.service.settingsActivityHook import setup_settings_activity_hook
from .DialogsActivity.pillWidget import setup_pill_widget
from .ui.PluginListActivity.service.InstallDismissHook import setup_install_dismiss_hook
from .ChatActivity.export.DecryptorBottomSheet import setup_packit_file_hook
from .ChatActivity.plugin_autocomplete import (
    setup_packit_autocomplete,
    _packit_get_class,
    _packit_hook_enter_view_constructor,
    _packit_attach_text_watcher,
    _packit_load_plugins_from_cache,
    _packit_show_matching_plugins,
    _packit_show_plugins_popup,
    _packit_hide_popup,
    _packit_send_plugin_info
)
from android_utils import log

CHECK_PATHS = True
RENAME_PACKITCACHE = True


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
        self.everyone_hook_refs = []
        self.packit_hook_constructor_ref = None
        log("PackIt initialized!")
    
    def on_plugin_load(self):
        if RENAME_PACKITCACHE:
            _migrate_packitcache()
        if CHECK_PATHS:
            _check_paths()
        from .nativeLoader import CHECK_SO_PATHS, checkSoPaths
        if CHECK_SO_PATHS:
            checkSoPaths()
        LocalConfig.init()
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
            data, _ = sync_completed(_load_account())
            _save_account(data)
        except Exception as e:
            log(f"PackIt: achievements sync error: {e}")
        try:
            self._check_identity_achievement()
        except Exception as e:
            log(f"PackIt: identity achievement check error: {e}")
        self.repoManager.updateAllCaches(
            on_complete=self._on_caches_updated if settings.get("show_startup_status", False) else None
        )
        if settings.get("show_startup_status", False):
            self._show_startup_loading()
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
        self.settings_activity_hook_refs = setup_settings_activity_hook(self)
        setup_pill_widget(self)
        self.dialogs_menu_hook_ref = self.chatUI.setup_dialogs_menu_hook()
        self.everyone_hook_refs = _everyone.setup_hook(self)
        self.packit_hook_constructor_ref = setup_packit_autocomplete(self)
        self._init_official_repository()
        self._check_for_update()
        if settings.get("show_updates_on_startup", False):
            self._check_startup_updates()
        log("PackIt loaded!")

    def _show_startup_loading(self):
        try:
            from android_utils import run_on_ui_thread
            from ui.bulletin import BulletinHelper
            def show():
                try:
                    BulletinHelper.show_info(strings.startup_loading)
                except Exception as e:
                    log(f"PackIt: startup loading bulletin error: {e}")
            # delay to let the UI settle after app start
            import threading
            threading.Timer(1.5, lambda: run_on_ui_thread(show)).start()
        except Exception as e:
            log(f"PackIt: _show_startup_loading error: {e}")

    def _on_caches_updated(self):
        try:
            from android_utils import run_on_ui_thread
            from ui.bulletin import BulletinHelper
            def show():
                try:
                    BulletinHelper.show_success(strings.startup_done)
                except Exception as e:
                    log(f"PackIt: startup done bulletin error: {e}")
            run_on_ui_thread(show)
        except Exception as e:
            log(f"PackIt: _on_caches_updated error: {e}")

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
PackItPlugin._packit_show_matching_plugins = _packit_show_matching_plugins
PackItPlugin._packit_show_plugins_popup = _packit_show_plugins_popup
PackItPlugin._packit_hide_popup = _packit_hide_popup
PackItPlugin._packit_send_plugin_info = _packit_send_plugin_info