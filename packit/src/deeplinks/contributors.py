# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log


def handle(url):
    if url == "tg://packit?contributors":
        try:
            currentFragment = get_last_fragment()
            BulletinHelper.show_success("Contributors triggered", currentFragment)
        except Exception as e:
            log(f"[PackIt] Error: {e}")