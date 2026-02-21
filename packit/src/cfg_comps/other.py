from ui.settings import Header, Switch, Divider
from elyx import strings, settings


class OtherSettings:
    def __init__(self, chat_button=None):
        self.chat_button = chat_button
    
    def build(self):
        return [
            Header(text=strings.buttons_header),
            Switch(
                key="show_chat_menu",
                text=strings.button_in_chat_menu,
                subtext=strings.button_in_chat_menu_desc,
                default=False,
                icon="msg_settings",
                link_alias="show_chat_menu",
                on_change=self.chat_button.on_chat_switch if self.chat_button else None
            ),
            Switch(
                key="show_drawer_menu",
                text=strings.button_in_side_menu,
                subtext=strings.button_in_side_menu_desc,
                default=False,
                icon="msg_info",
                link_alias="show_drawer_menu",
                on_change=self.chat_button.on_drawer_switch if self.chat_button else None
            ),
            Switch(
                key="show_chat_plugins_menu",
                text=strings.button_in_chat_plugins,
                subtext=strings.button_in_chat_plugins_desc,
                default=False,
                icon="msg_plugins",
                link_alias="show_chat_plugins_menu",
                on_change=self.chat_button.on_chat_plugins_switch if self.chat_button else None
            ),
            Divider(),
            Header(text=strings.interface_header),
            Switch(
                key="old_sort_menu_design",
                text=strings.classic_sort_menu,
                subtext=strings.classic_sort_menu_desc,
                default=False,
                icon="msg_list",
                link_alias="old_sort_menu_design"
            ),
            Switch(
                key="show_default_sticker",
                text=strings.show_default_sticker,
                subtext=strings.show_default_sticker_desc,
                default=False,
                icon="msg_sticker",
                link_alias="show_default_sticker"
            ),
            Divider(),
            Header(text=strings.repository_selection_header),
            Switch(
                key="skip_repository_selection",
                text=strings.skip_repository_selection,
                subtext=strings.skip_repository_selection_desc,
                default=False,
                icon="msg_leave",
                link_alias="skip_repository_selection"
            ),
            Switch(
                key="hide_repository_selection_button",
                text=strings.hide_repository_selection_button,
                subtext=strings.hide_repository_selection_button_desc,
                default=False,
                icon="msg_unpin",
                link_alias="hide_repository_selection_button"
            ),
            Divider(),
        ]
