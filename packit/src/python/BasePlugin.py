# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import List, Any
from base_plugin import BasePlugin
from . import Main as main

import time

_launch_start = time.time()

# the launch logic has been delegated to Main.py
# there shouldn't be anything extra in this file (if it is not required)
class Main(BasePlugin):
    def __init__(self):
        super().__init__()
        main.startInit(self, _launch_start)

    def on_plugin_load(self):
        main.loadPlugin(self)

    def _show_startup_bulletin(self):
        main._show_startup_bulletin(self)

    def _check_for_update(self):
        main._check_for_update(self)

    def _check_startup_updates(self):
        main._check_startup_updates(self)

    def _check_update_notifications_bulletin(self):
        main._check_update_notifications_bulletin(self)

    def _check_identity_achievement(self):
        main._check_identity_achievement(self)

    def _init_official_repository(self):
        main._init_official_repository(self)

    def on_send_message_hook(self, account: int, params: Any):
        return main.on_send_message_hook(self, account, params)

    def on_plugin_unload(self):
        main.on_plugin_unload(self)

    def create_settings(self) -> List[Any]:
        return main.create_settings(self)

for _name, _method in main._AUTOCOMPLETE_METHODS.items():
    setattr(Main, _name, _method)
