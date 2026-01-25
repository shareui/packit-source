from ui.settings import Header, Switch
from elyx import strings, settings


class OtherSettings:
    def __init__(self, chat_button=None):
        self.chat_button = chat_button
    
    def build(self):
        return [
            Header(text=strings.other_settings),
            Switch(
                key="show_chat_menu",
                text="Кнопка в меню чата",
                subtext="Добавляет кнопку настроек шаблонов в обычное меню чата.",
                default=False,
                icon="msg_settings",
                on_change=self.chat_button.on_chat_switch if self.chat_button else None
            ),
            Switch(
                key="show_drawer_menu",
                text="Кнопка в боковом меню",
                subtext="Добавляет кнопку настроек шаблонов в боковое меню.",
                default=False,
                icon="msg_info",
                on_change=self.chat_button.on_drawer_switch if self.chat_button else None
            ),
            Switch(
                key="show_chat_plugins_menu",
                text="Кнопка в плагинах в чате",
                subtext="Добавляет кнопку настроек шаблонов в меню плагинов в чате.",
                default=False,
                icon="msg_plugins",
                on_change=self.chat_button.on_chat_plugins_switch if self.chat_button else None
            ),
            Switch(
                key="auto_update_on_start",
                text="Auto-update",
                subtext="Update repos when starting app",
                default=False,
                icon="msg_retry"
            )
        ]