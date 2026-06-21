# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android.view import View
from java import dynamic_proxy

class _TagsLayoutListener(dynamic_proxy(View.OnLayoutChangeListener)):
    def __init__(self):
        super().__init__()
        self._done = False

    def onLayoutChange(self, v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom):
        if self._done:
            return
        row_width = v.getWidth()
        if row_width <= 0:
            return
        self._done = True
        found_hidden = False
        for i in range(v.getChildCount()):
            child = v.getChildAt(i)
            if child is None:
                continue
            if found_hidden or child.getRight() > row_width:
                child.setVisibility(View.GONE)
                found_hidden = True
        # do not call removeOnLayoutChangeListener — causes equals() crash on Chaquopy proxy
