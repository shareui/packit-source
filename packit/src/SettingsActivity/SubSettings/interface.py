from ui.settings import Header, Switch, Divider, Custom, Text
from elyx import strings


def build_interface_page(other_settings, ctx):
    items = [
        Header(text=strings.interface_header),
        other_settings._build_sort_menu_design_item(ctx),
        other_settings._build_font_picker_item(ctx),
        Text(
            text=strings.edit_plugin_card,
            subtext=strings.edit_plugin_card_desc,
            icon="msg_edit",
            create_sub_fragment=other_settings._open_card_editor
        ),
        Switch(
            key="hide_unavailable_plugins",
            text=strings.hide_unavailable_plugins,
            subtext=strings.hide_unavailable_plugins_desc,
            default=False,
            icon="msg_block",
            link_alias="hide_unavailable_plugins"
        ),
        Switch(
            key="scroll_button_bottom_right",
            text=strings.scroll_button_bottom_right,
            subtext=strings.scroll_button_bottom_right_desc,
            default=False,
            icon="msg_to_beginning",
            link_alias="scroll_button_bottom_right"
        ),
    ]
    return [item for item in items if item is not None]
