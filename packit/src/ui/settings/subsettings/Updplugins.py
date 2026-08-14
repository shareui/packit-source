# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.settings import Header, Switch, Text
from elyx import strings



def _open_pill_stack_settings(view):
    try:
        from hook_utils import find_class
        from client_utils import get_last_fragment
        PillStackPreferencesActivity = find_class("com.exteragram.messenger.pillstack.ui.PillStackPreferencesActivity")
        if PillStackPreferencesActivity is None:
            return
        frag = get_last_fragment()
        if frag:
            frag.presentFragment(PillStackPreferencesActivity())
    except Exception as e:
        logx(f"updplugins: _open_pill_stack_settings error: {e}", False)


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
        Switch(
            key="update_notifications_bulletin",
            text=strings.update_notifications,
            subtext=strings.update_notifications_desc,
            default=False,
            icon="msg_notifications",
            link_alias="update_notifications_bulletin"
        ),
        Text(
            text=strings.clear_ignore_list,
            subtext=strings.clear_ignore_list_desc,
            icon="msg_delete",
            on_click=other_settings._onClearIgnoreListClick
        ),
        Text(
            text=strings.updplugins_pill_stack_settings,
            subtext=strings.updplugins_pill_stack_settings_desc,
            icon="msg_retry",
            on_click=_open_pill_stack_settings
        ),
    ]