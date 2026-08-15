# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
try:
    from org.telegram.ui.Components import ItemOptions
except Exception as e:
    import android_utils as _au; _au.log(f"contextMenu: import ItemOptions failed: {e}")
    ItemOptions = None

try:
    from org.telegram.messenger import R as R_tg
except Exception as e:
    import android_utils as _au; _au.log(f"contextMenu: import R failed: {e}")
    R_tg = None

try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    import android_utils as _au; _au.log(f"contextMenu: import Theme failed: {e}")
    Theme = None

from java import dynamic_proxy
from java.lang import Runnable, String



def _resolve_icon(name: str) -> int:
    try:
        return getattr(R_tg.drawable, name, 0)
    except Exception:
        return 0


def _make_runnable(fn) -> Runnable:
    class _R(dynamic_proxy(Runnable)):
        def __init__(self, f):
            super().__init__()
            self._f = f
        def run(self):
            try:
                self._f()
            except Exception as e:
                logx(f"contextMenu: runnable error: {e}", False)
    return _R(fn)


def show_plugin_context_menu(container, anchor_view, items: list):
    """
    shows standard telegram popup menu.

    container   - ViewGroup (e.g. anchor_view.getRootView())
    anchor_view - View to anchor the popup to
    items       - list of dicts:
        {
            "icon":   str,       # drawable name, e.g. "msg_copy"
            "text":   str,       # label
            "action": callable,  # called on tap
            "red":    bool,      # optional, default False
            "show":   bool,      # optional, default True - controls visibility
        }
    """
    if ItemOptions is None:
        logx("contextMenu: ItemOptions not available", True)
        return

    try:
        menu = ItemOptions.makeOptions(container, None, anchor_view)

        for item in items:
            if not item.get("show", True):
                continue

            icon_res = _resolve_icon(item.get("icon", ""))
            text = String(item.get("text", ""))
            action = item.get("action")
            is_red = bool(item.get("red", False))

            if action is None:
                continue

            runnable = _make_runnable(action)

            # use explicit color-key overload: add(int, CharSequence, int iconKey, int textKey, Runnable)
            # Chaquopy cannot resolve Python bool as Java boolean
            if is_red and Theme is not None:
                menu.add(icon_res, text, Theme.key_text_RedRegular, Theme.key_text_RedRegular, runnable)
            else:
                menu.add(icon_res, text, runnable)

        menu.show()
    except Exception as e:
        logx(f"contextMenu: show_plugin_context_menu error: {e}", False)