# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment



def handle(url):
    if url == "tg://packit?other":
        try:
            currentFragment = get_last_fragment()
            BulletinHelper.show_success("Other settings triggered", currentFragment)
        except Exception as e:
            logx(f"[PackIt] Error: {e}", False)