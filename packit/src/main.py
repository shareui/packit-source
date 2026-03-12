from typing import Any
from base_plugin import BasePlugin, HookResult, HookStrategy
try:
    from elyx import settings, strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import settings, strings failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
from .repom import RepositoryManager
from .core import PackItCore
from .settings import SettingsBuilder
from .packlog import packlog
from .chatUi import ChatButton
from .deeplinks import setup_deeplink_hook
from .other.badges import BadgeManager
from .other.localConfig import LocalConfig
from .other import isBeta
from .chatUi.securityUi import setup_policy_button_hook, setup_hash_button_hook
from .chatUi.pillWidget import setup_pill_widget
from .ui.installUi.installDismissHook import setup_install_dismiss_hook
from .chatUi.packitFileUi.decryptorUi import setup_packit_file_hook
from android_utils import log


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
        self.dialogs_menu_hook_ref = None
        self.install_dismiss_hook_ref = None
        self.pill_widget_hook_ref = None
        log("PackIt initialized!")
    
    def on_plugin_load(self):
        LocalConfig.init()
        isBeta.init()
        try:
            from .other.achievements import sync_accounts, sync_completed, _load_account, _save_account
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
        self.install_dismiss_hook_ref = setup_install_dismiss_hook(self)
        setup_packit_file_hook(self)
        if settings.get("show_pill_widget", False):
            self.pill_widget_hook_ref = setup_pill_widget(self)
        self.dialogs_menu_hook_ref = self.chatUI.setup_dialogs_menu_hook()
        self._init_official_repository()
        self._check_for_update()
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
            from .ui.updateSheet import check_and_show
            check_and_show()
        except Exception as e:
            log(f"PackIt: update check error: {e}")
    
    def _check_identity_achievement(self):
        from org.telegram.messenger import UserConfig, MessagesController
        account = UserConfig.selectedAccount
        user = UserConfig.getInstance(account).getCurrentUser()
        if not user:
            return
        first_name = str(user.first_name) if user.first_name else ""
        if first_name.lower() in ("shareui", "fuchs"):
            from .other.achievements import unlock_secret
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
        
        if params.message.startswith(".logtest"):
            packlog.info(f"log tested")
            params.message = f"Log tested! Check logs"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        if params.message.startswith(".logspam"):
            import threading
            def spamLogs():
                for i in range(20):
                    packlog.info(f"spam test {i+1}")
            threading.Thread(target=spamLogs).start()
            maxLogs = packlog._getMaxLogs()
            params.message = f"Spamming 20 logs in background! Max limit: {maxLogs}"
            return HookResult(strategy=HookStrategy.MODIFY, params=params)
        
        if params.message.startswith(".deleteachievements"):
            try:
                import os
                from .other.achievements import _get_achievements_path
                path = _get_achievements_path()
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
        except Exception as e:
            log(f"Error cleaning up badge manager: {e}")
    def create_settings(self):
        return self.settingsBuilder.buildMainSettings()