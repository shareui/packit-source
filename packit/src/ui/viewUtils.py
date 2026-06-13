# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from android.widget import TextView
from android.util import TypedValue



def makeTv(ctx, text="", size_dp=16, color=None, bold=False):
    # creates a TextView with current packit font applied
    tv = TextView(ctx)
    if text:
        tv.setText(str(text))
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, size_dp)
    if color is not None:
        tv.setTextColor(color)
    if bold:
        try:
            from org.telegram.messenger import AndroidUtilities
            tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
    applyFont(tv)
    return tv


def applyFont(view):
    # applies current packit font to the given view if it is a TextView
    try:
        from .FontManager import getCurrentTypeface
        tf = getCurrentTypeface()
        if tf is None:
            return
        if isinstance(view, TextView):
            view.setTypeface(tf)
    except Exception as e:
        logx(f"viewUtils: applyFont error: {e}", False)


def applyFontToTree(view_group):
    # recursively applies font to all TextViews in a view tree
    try:
        from android.view import ViewGroup as VG
        from .FontManager import getCurrentTypeface
        tf = getCurrentTypeface()
        if tf is None:
            return
        _applyRecursive(view_group, tf)
    except Exception as e:
        logx(f"viewUtils: applyFontToTree error: {e}", False)


def _applyRecursive(view, tf):
    try:
        if isinstance(view, TextView):
            view.setTypeface(tf)
            return
        from android.view import ViewGroup as VG
        if isinstance(view, VG):
            for i in range(view.getChildCount()):
                _applyRecursive(view.getChildAt(i), tf)
    except Exception:
        pass