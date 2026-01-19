from ui.settings import Header, Input, Text, Divider
from ui.alert import AlertDialogBuilder
from elyx import strings, settings
from client_utils import get_last_fragment


class CommandSettings:
    def __init__(self):
        pass
    
    def _showCommandInfo(self, title, description, usage):
        fragment = get_last_fragment()
        if not fragment:
            return
        
        activity = fragment.getParentActivity()
        if not activity:
            return
        
        builder = AlertDialogBuilder(activity)
        builder.set_title(title)
        builder.set_message(f"{description}\n\nUsage:\n{usage}")
        builder.set_positive_button("OK", lambda b, w: b.dismiss())
        builder.show()
    
    def _showInfoAbout(self, view):
        self._showCommandInfo(
            "Info Command",
            "Shows detailed information about a plugin including name, version, author, description and download links.",
            "packit info [plugin] [repository_name]\n\nExamples:\npackit info loggerplus\npackit info theme-switcher Official"
        )
    
    def _showSearchAbout(self, view):
        self._showCommandInfo(
            "Search Command",
            "Searches for plugins by query in their names and descriptions across all enabled repositories.",
            "packit search [query]\n\nExample:\npackit search logger"
        )
    
    def _showInstallAbout(self, view):
        self._showCommandInfo(
            "Install Command",
            "Downloads and installs a plugin from repository. Use -r flag to automatically restart the app after installation.",
            "packit install [plugin_id] [repository_name] [-r]\n\nExamples:\npackit install lolcat\npackit install theme-switcher Official\npackit install lolcat -r"
        )
    
    def _showUninstallAbout(self, view):
        self._showCommandInfo(
            "Uninstall Command",
            "Removes an installed plugin by query. Query can be plugin key from repository or displayName. Plugin ID is resolved from repository JSON. Use -r flag to automatically restart the app after uninstall.",
            "packit uninstall [query] [repository_name] [-r]\n\nExamples:\npackit uninstall lolcat\npackit uninstall theme-switcher Official\npackit uninstall lolcat -r"
        )
    
    def _showUpdateAbout(self, view):
        self._showCommandInfo(
            "Update Command",
            "Updates the plugin cache from all enabled repositories and shows statistics of successful and failed updates.",
            "packit update"
        )
    
    def _showUpgradeAbout(self, view):
        self._showCommandInfo(
            "Upgrade Command",
            "Upgrades an installed plugin to the latest version from repository. Query can be plugin key from repository or displayName. Plugin ID is resolved from repository JSON to find and replace the correct file. Removes old version and installs new one. Use -r flag to automatically restart the app.",
            "packit upgrade [query] [repository_name] [-r]\n\nExamples:\npackit upgrade lolcat\npackit upgrade theme-switcher Official\npackit upgrade lolcat -r"
        )
    
    def _showPluginlistAbout(self, view):
        self._showCommandInfo(
            "Plugin List Command",
            "Shows a list of all plugins available in the cache from all enabled repositories with their versions and repository names.",
            "packit pluginlist"
        )
    
    def _showRepolistAbout(self, view):
        self._showCommandInfo(
            "Repository List Command",
            "Shows a list of all enabled repositories with their names and URLs.",
            "packit repolist"
        )
    
    def _showShareAbout(self, view):
        self._showCommandInfo(
            "Share Command",
            "Shares a plugin download link. Finds the plugin in repositories and sends its download link.",
            "packit share [plugin] [repository_name]\n\nExamples:\npackit share loggerplus\npackit share theme-switcher Official"
        )
    
    def build(self):
        return [
            Header(text=strings.command_settings),
            
            Input(
                key="cmd_info",
                text=strings.cmd_info,
                default=settings.get("cmd_info", "packit info"),
                icon="msg_info"
            ),
            Input(
                key="cmd_search",
                text=strings.cmd_search,
                default=settings.get("cmd_search", "packit search"),
                icon="msg_search"
            ),
            Input(
                key="cmd_install",
                text=strings.cmd_install,
                default=settings.get("cmd_install", "packit install"),
                icon="msg_download"
            ),
            Input(
                key="cmd_uninstall",
                text=strings.cmd_uninstall,
                default=settings.get("cmd_uninstall", "packit uninstall"),
                icon="msg_delete"
            ),
            Input(
                key="cmd_update",
                text="Update command",
                default=settings.get("cmd_update", "packit update"),
                icon="msg_retry"
            ),
            Input(
                key="cmd_upgrade",
                text="Upgrade command",
                default=settings.get("cmd_upgrade", "packit upgrade"),
                icon="gift_upgrade"
            ),
            Input(
                key="cmd_pluginlist",
                text=strings.cmd_pluginlist,
                default=settings.get("cmd_pluginlist", "packit pluginlist"),
                icon="msg_list"
            ),
            Input(
                key="cmd_repolist",
                text=strings.cmd_repolist,
                default=settings.get("cmd_repolist", "packit repolist"),
                icon="msg_folders"
            ),
            Input(
                key="cmd_share",
                text=strings.cmd_share,
                default=settings.get("cmd_share", "packit share"),
                icon="msg_share"
            ),
            
            Header(text="About commands"),
            
            Text(
                text="About Info",
                icon="msg_help",
                on_click=self._showInfoAbout
            ),
            Text(
                text="About Search",
                icon="msg_help",
                on_click=self._showSearchAbout
            ),
            Text(
                text="About Install",
                icon="msg_help",
                on_click=self._showInstallAbout
            ),
            Text(
                text="About Uninstall",
                icon="msg_help",
                on_click=self._showUninstallAbout
            ),
            Text(
                text="About Update",
                icon="msg_help",
                on_click=self._showUpdateAbout
            ),
            Text(
                text="About Upgrade",
                icon="msg_help",
                on_click=self._showUpgradeAbout
            ),
            Text(
                text="About Plugin List",
                icon="msg_help",
                on_click=self._showPluginlistAbout
            ),
            Text(
                text="About Repository List",
                icon="msg_help",
                on_click=self._showRepolistAbout
            ),
            Text(
                text="About Share",
                icon="msg_help",
                on_click=self._showShareAbout
            )
        ]