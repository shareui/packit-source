from ui.settings import Header, Text, Divider
from elyx import strings
from .cfg_comps.interface import InterfaceSettings
from .cfg_comps.command import CommandSettings
from .cfg_comps.repos import RepositoriesSettings
from .cfg_comps.other import OtherSettings
from .cfg_comps.docs import DocumentationSettings


class SettingsBuilder:
    def __init__(self, repoManager, plugin):
        self.repoManager = repoManager
        self.plugin = plugin
        self.interfaceSettings = InterfaceSettings()
        self.interfaceSettings.setPlugin(plugin)
        self.commandSettings = CommandSettings()
        self.repositoriesSettings = RepositoriesSettings(repoManager)
        self.otherSettings = OtherSettings()
        self.documentationSettings = DocumentationSettings()
    
    def buildMainSettings(self):
        return [
            
            Text(
                text=strings.interface_settings,
                icon="msg_palette",
                create_sub_fragment=self.interfaceSettings.build
            ),
            
            Text(
                text=strings.command_settings,
                icon="msg_edit",
                create_sub_fragment=self.commandSettings.build
            ),
            
            Text(
                text=strings.repositories,
                icon="msg_folders",
                create_sub_fragment=self.repositoriesSettings.build
            ),
            
            Text(
                text="Documentation",
                icon="msg_help",
                create_sub_fragment=self.documentationSettings.build
            ),
            
            Text(
                text=strings.other_settings,
                icon="msg_settings",
                create_sub_fragment=self.otherSettings.build
            ),
            
            Divider(text="With love <3")
        ]