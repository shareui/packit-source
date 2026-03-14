from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from client_utils import get_last_fragment
from android.content import Intent
from android.net import Uri
try:
    from org.telegram.messenger import ApplicationLoader
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()
from ..ui.DeeplinkBottomSheets import show_deeplink_sheet


class DeeplinksSettings:
    def __init__(self):
        pass

    def _show_plugins_menu(self, view):
        show_deeplink_sheet("dl_plugins_menu")

    def _show_all_repos(self, view):
        show_deeplink_sheet("dl_all_repos")

    def _show_add_repo(self, view):
        show_deeplink_sheet("dl_add_repo")

    def _show_specific_repo(self, view):
        show_deeplink_sheet("dl_specific_repo")

    def _show_specific_plugin(self, view):
        show_deeplink_sheet("dl_specific_plugin")

    def _show_specific_icon_pack(self, view):
        show_deeplink_sheet("dl_specific_icon_pack")

    def _show_update_all(self, view):
        show_deeplink_sheet("dl_update_all")

    def _show_update_repo(self, view):
        show_deeplink_sheet("dl_update_repo")

    def _show_settings(self, view):
        show_deeplink_sheet("dl_settings")

    def _show_forum(self, view):
        show_deeplink_sheet("dl_forum")

    def _show_problems(self, view):
        show_deeplink_sheet("dl_problems")

    def _show_restart(self, view):
        show_deeplink_sheet("dl_restart")

    def _openFullDocs(self, view):
        try:
            context = ApplicationLoader.applicationContext
            intent = Intent(Intent.ACTION_VIEW)
            intent.setData(Uri.parse("https://github.com/shareui/packit/blob/main/docs/deeplinks.md"))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
        except Exception:
            BulletinHelper.show_error(strings.failed_to_open_link)

    def build(self):
        return [
            Header(text=strings.deeplinks_repositories_header),

            Text(
                text=strings.deeplinks_all_repositories,
                icon="msg_folders",
                on_click=self._show_all_repos,
                link_alias="dl_all_repos"
            ),
            Text(
                text=strings.deeplinks_add_repository,
                icon="menu_folder_add",
                on_click=self._show_add_repo,
                link_alias="dl_add_repo"
            ),

            Divider(),
            Header(text=strings.deeplinks_installation_header),

            Text(
                text=strings.deeplinks_plugins_menu,
                icon="msg_list",
                on_click=self._show_plugins_menu,
                link_alias="dl_plugins_menu"
            ),
            Text(
                text=strings.deeplinks_specific_repository,
                icon="msg_saved",
                on_click=self._show_specific_repo,
                link_alias="dl_specific_repo"
            ),
            Text(
                text=strings.deeplinks_install_plugin,
                icon="msg_download",
                on_click=self._show_specific_plugin,
                link_alias="dl_specific_plugin"
            ),

            Text(
                text=strings.deeplinks_install_icon_pack,
                icon="msg_sticker",
                on_click=self._show_specific_icon_pack,
                link_alias="dl_specific_icon_pack"
            ),

            Divider(),
            Header(text=strings.deeplinks_updates_header),

            Text(
                text=strings.deeplinks_check_updates,
                icon="msg_retry",
                on_click=self._show_update_all,
                link_alias="dl_update_all"
            ),
            Text(
                text=strings.deeplinks_check_updates_repo,
                icon="msg_topics",
                on_click=self._show_update_repo,
                link_alias="dl_update_repo"
            ),

            Divider(),
            Header(text=strings.deeplinks_other_header),

            Text(
                text=strings.deeplinks_settings,
                icon="msg_settings",
                on_click=self._show_settings,
                link_alias="dl_settings"
            ),
            Text(
                text=strings.deeplinks_forum,
                icon="msg_groups",
                on_click=self._show_forum,
                link_alias="dl_forum"
            ),
            Text(
                text=strings.deeplinks_possible_problems,
                icon="msg_report",
                on_click=self._show_problems,
                link_alias="dl_problems"
            ),
            Text(
                text=strings.deeplinks_restart,
                icon="msg_retry",
                on_click=self._show_restart,
                link_alias="dl_restart"
            ),

            Divider(text="Complete documentation is available [here](https://github.com/shareui/packit/blob/main/docs/deeplinks.md) in markdown."),
        ]
