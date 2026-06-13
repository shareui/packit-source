# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from ui.settings import Header, Switch
from elyx import strings


def build_debug_page():
    return [
        Header(text=strings.debug_menu),
        Switch(
            key="debug_logs",
            text=strings.debug_logs,
            subtext=strings.debug_logs_desc,
            default=False,
            icon="msg_log",
            link_alias="debug_logs"
        ),
    ]
