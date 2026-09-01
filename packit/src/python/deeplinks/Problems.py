# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from client_utils import get_last_fragment
from android.net import Uri
try:
    from org.telegram.messenger.browser import Browser
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"import org.telegram.messenger.browser import Browser failed: {e}")
    from ..utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()


def handle(url):
    if url == "tg://packit?problems":
        try:
            frag = get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                uri = Uri.parse("https://t.me/packitGround/13/350")
                Browser.openUrl(act, uri, True, True, True, None, None, False, False, False)
        except Exception:
            pass