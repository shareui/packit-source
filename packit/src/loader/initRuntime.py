
from packutil import logx
import time


def startInit(plugin, launchStart):
    from ..RepositoryManager import RepositoryManager
    from ..core import PackItCore
    from ..MainActivity import SettingsBuilder
    from ..DialogsActivity.button import ChatButton
    from ..other.badges import BadgeManager

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
