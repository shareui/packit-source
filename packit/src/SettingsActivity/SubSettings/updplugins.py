from ui.settings import Header, Switch, Text
from elyx import strings


def build_updplugins_page(other_settings):
    return [
        Header(text=strings.updating_plugins_header),
        Switch(
            key="show_updates_on_startup",
            text=strings.show_updates_on_startup,
            subtext=strings.show_updates_on_startup_desc,
            default=False,
            icon="msg_download",
            link_alias="show_updates_on_startup"
        ),
        Text(
            text=strings.clear_ignore_list,
            subtext=strings.clear_ignore_list_desc,
            icon="msg_delete",
            on_click=other_settings._onClearIgnoreListClick
        ),
    ]
