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
from .ui.securityUi import setup_policy_button_hook, setup_hash_button_hook
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
        log("PackIt initialized!")
    
    def on_plugin_load(self):
        LocalConfig.init()
        isBeta.init()
        self.repoManager.updateAllCaches()
        self.add_on_send_message_hook()
        self.hook_settings_header_ref = self.settingsBuilder._setup_settings_header_hook()
        self.deeplink_hook_ref = setup_deeplink_hook(self)
        self.chatUI.initialize_chat_menu()
        self.badgeManager.setup_hooks()
        self.policy_button_hook_ref = setup_policy_button_hook(self)
        self.hash_button_hook_ref = setup_hash_button_hook(self, self.repoManager)
        self.dialogs_menu_hook_ref = self.chatUI.setup_dialogs_menu_hook()
        self._init_official_repository()
        log("PackIt loaded!")
    
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
        
        return HookResult()
    
    def on_plugin_unload(self):
        try:
            if hasattr(self, 'badgeManager'):
                self.badgeManager.cleanup()
        except Exception as e:
            log(f"Error cleaning up badge manager: {e}")
    
    def create_settings(self):
        return self.settingsBuilder.buildMainSettings()