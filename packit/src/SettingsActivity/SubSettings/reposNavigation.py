from ui.settings import Header, Switch, Divider
from elyx import strings


def build_repos_navigation_page():
    return [
        Header(text=strings.repos_navigation_header),
        Switch(
            key="skip_repository_selection",
            text=strings.skip_repository_selection,
            subtext=strings.skip_repository_selection_desc,
            default=False,
            icon="msg_leave",
            link_alias="skip_repository_selection"
        ),
        Switch(
            key="version_picker_auto_expand",
            text=strings.version_picker_auto_expand,
            subtext=strings.version_picker_auto_expand_desc,
            default=False,
            icon="msg_list",
            link_alias="version_picker_auto_expand"
        ),
        Divider(text=strings.navigation_header_desc),
    ]
