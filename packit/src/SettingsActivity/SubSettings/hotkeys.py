from ui.settings import Header, Switch, Divider
from elyx import strings


def build_hotkeys_page(other_settings, ctx):
    items = [
        Header(text=strings.hotkeys_header),
        other_settings._build_dialogs_btn_item(ctx),
        other_settings._build_dialogs_menu_toggle_item(ctx),
        other_settings._build_pill_stack_item(ctx),
        Switch(
            key="show_chat_menu",
            text=strings.button_in_chat_menu,
            subtext=strings.button_in_chat_menu_desc,
            default=False,
            icon="msg_settings",
            link_alias="show_chat_menu",
            on_change=other_settings.chat_button.on_chat_switch if other_settings.chat_button else None
        ),
        Switch(
            key="show_chat_plugins_menu",
            text=strings.button_in_chat_plugins,
            subtext=strings.button_in_chat_plugins_desc,
            default=False,
            icon="msg_plugins",
            link_alias="show_chat_plugins_menu",
            on_change=other_settings.chat_button.on_chat_plugins_switch if other_settings.chat_button else None
        ),
        Switch(
            key="show_settings_button",
            text=strings.show_settings_button,
            subtext=strings.show_settings_button_desc,
            default=True,
            icon="msg_settings",
            link_alias="show_settings_button",
            on_change=other_settings._onRestartRequiredSwitch
        ),
        Switch(
            key="show_plugin_list_fab",
            text=strings.show_plugin_list_fab,
            subtext=strings.show_plugin_list_fab_desc,
            default=True,
            icon="msg_addbot",
            link_alias="show_plugin_list_fab",
        ),
        Divider(text=strings.buttons_header_desc),
    ]
    return [item for item in items if item is not None]
