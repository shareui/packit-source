from ui.settings import Header, Switch, Divider
from elyx import strings, settings


class OtherSettings:
    def __init__(self, chat_button=None):
        self.chat_button = chat_button
    
    def build(self):
        return [
            Header(text="Buttons"),
            Switch(
                key="show_chat_menu",
                text="Button in chat menu",
                subtext="Adds a template settings button to the regular chat menu.",
                default=False,
                icon="msg_settings",
                on_change=self.chat_button.on_chat_switch if self.chat_button else None
            ),
            Switch(
                key="show_drawer_menu",
                text="Button in side menu",
                subtext="Adds a template settings button to the side menu.",
                default=False,
                icon="msg_info",
                on_change=self.chat_button.on_drawer_switch if self.chat_button else None
            ),
            Switch(
                key="show_chat_plugins_menu",
                text="Button in chat plugins",
                subtext="Adds a template settings button to the chat plugins menu.",
                default=False,
                icon="msg_plugins",
                on_change=self.chat_button.on_chat_plugins_switch if self.chat_button else None
            ),
            Divider(),
            Header(text="Interface"),
            Switch(
                key="old_sort_menu_design",
                text="Classic sort menu",
                subtext="Use the classic design for the plugin sorting menu with better visual feedback.",
                default=False,
                icon="msg_list"
            ),
            Divider(),
        ]