from ui.settings import Header, Switch, Divider
from elyx import strings


def build_plugin_profile_page():
    return [
        Header(text=strings.plugin_profile_header),
        Switch(
            key="show_extended_desc",
            text=strings.show_extended_desc,
            subtext=strings.show_extended_desc_desc,
            default=False,
            icon="msg_info",
        ),
    ]
