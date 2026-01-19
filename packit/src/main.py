from typing import Any
from base_plugin import BasePlugin, HookResult
from elyx import settings
from .cmds import CommandProcessor
from .repom import RepositoryManager
from .core import PackItCore
from .settings import SettingsBuilder


class PackItPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.repoManager = RepositoryManager()
        self.core = PackItCore(self.repoManager)
        self.settingsBuilder = SettingsBuilder(self.repoManager)
        self.commandProcessor = CommandProcessor(self)
    
    def on_plugin_load(self):
        self.add_on_send_message_hook()
        self._initDefaultCommands()
        self.core.initializeRepositories()
    
    def _initDefaultCommands(self):
        if settings.get("cmd_info") is None:
            settings.set("cmd_info", "packit info")
        if settings.get("cmd_search") is None:
            settings.set("cmd_search", "packit search")
        if settings.get("cmd_install") is None:
            settings.set("cmd_install", "packit install")
        if settings.get("cmd_uninstall") is None:
            settings.set("cmd_uninstall", "packit uninstall")
        if settings.get("cmd_pluginlist") is None:
            settings.set("cmd_pluginlist", "packit pluginlist")
        if settings.get("cmd_repolist") is None:
            settings.set("cmd_repolist", "packit repolist")
        if settings.get("cmd_share") is None:
            settings.set("cmd_share", "packit share")
        if settings.get("cmd_update") is None:
            settings.set("cmd_update", "packit update")
        if settings.get("cmd_upgrade") is None:
            settings.set("cmd_upgrade", "packit upgrade")
    
    def create_settings(self):
        return self.settingsBuilder.buildMainSettings()
    
    def on_send_message_hook(self, account: int, params: Any) -> HookResult:
        return self.commandProcessor.processMessage(params)