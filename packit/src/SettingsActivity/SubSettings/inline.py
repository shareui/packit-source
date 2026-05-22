# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from ui.settings import Header, Switch, Divider, Input, Text
from elyx import strings


def build_inline_page(other_settings, fmt_inline_str, reload_plugin_settings, open_url):
    items = [
        Header(text=strings.inline_search_header),
        Input(
            key="inline_search_command",
            text=strings.inline_search_command,
            default=".packit",
            icon="msg_edit",
            on_change=lambda v: reload_plugin_settings()
        ),
        Switch(
            key="inline_search_double_space",
            text=strings.inline_search_double_space,
            subtext=fmt_inline_str(str(strings.inline_search_double_space_desc)),
            default=False,
            icon="msg_search",
            link_alias="inline_search_double_space"
        ),
        Switch(
            key="inline_search_clear_field",
            text=strings.inline_search_clear_field,
            subtext=strings.inline_search_clear_field_desc,
            default=False,
            icon="msg_clear",
            link_alias="inline_search_clear_field"
        ),
        Text(
            text=strings.inline_view_guide,
            icon="msg_info",
            on_click=lambda v: open_url("https://github.com/shareui/packit/blob/main/docs/inline.md")
        ),
        other_settings._make_expandable_switch("inline_send_enabled", strings.inline_send_header, [
            ("inline_send_name", True),
            ("inline_send_version", True),
            ("inline_send_author", True),
            ("inline_send_description", True),
            ("inline_send_install", True),
        ]),
        other_settings._make_es_child("inline_send_name", strings.inline_send_name, True) if other_settings._es_is_expanded("inline_send_enabled") else None,
        other_settings._make_es_child("inline_send_version", strings.inline_send_version, True) if other_settings._es_is_expanded("inline_send_enabled") else None,
        other_settings._make_es_child("inline_send_author", strings.inline_send_author, True) if other_settings._es_is_expanded("inline_send_enabled") else None,
        other_settings._make_es_child("inline_send_description", strings.inline_send_description, True) if other_settings._es_is_expanded("inline_send_enabled") else None,
        other_settings._make_es_child("inline_send_install", strings.inline_send_install, True) if other_settings._es_is_expanded("inline_send_enabled") else None,
        Divider(text=fmt_inline_str(str(strings.inline_search_divider))),
    ]
    return [item for item in items if item is not None]