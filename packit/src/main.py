from typing import Any
from base_plugin import BasePlugin, HookResult
from elyx import settings, strings
from .repom import RepositoryManager
from .core import PackItCore
from .settings import SettingsBuilder
from .chat_ui import ChatButton
from .deeplink import setup_deeplink_hook


class PackItPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.repoManager = RepositoryManager()
        self.core = PackItCore(self.repoManager)
        self.chatUI = ChatButton(self)
        self.settingsBuilder = SettingsBuilder(self.repoManager, self)
        self.on_send_message_hook_ref = None
        self.hook_settings_header_ref = None
        self.deeplink_hook_ref = None
    
    def on_plugin_load(self):
        self.hook_settings_header_ref = self.settingsBuilder._setup_settings_header_hook()
        self.deeplink_hook_ref = setup_deeplink_hook(self)
        self.chatUI.initialize_chat_menu()
        self._init_official_repository()
    
    def _init_official_repository(self):
        try:
            repos = self.repoManager.getRepositories()
            if not repos:
                self.repoManager.addRepository(isFirst=True)
        except Exception:
            pass
    
    def create_settings(self):
        return self.settingsBuilder.buildMainSettings()
