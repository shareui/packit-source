# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android.view import View
from java import dynamic_proxy


def _chip_extent(child) -> int:
    # laid-out width plus the trailing margin the row adds after it
    w = child.getWidth()
    try:
        w += child.getLayoutParams().rightMargin
    except Exception:
        pass
    return w


def _measure_width(view) -> int:
    # the "+N" chip starts GONE, so it has no laid-out width yet — measure it
    # unconstrained to learn how much room it needs
    try:
        spec = View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
        view.measure(spec, spec)
        return view.getMeasuredWidth()
    except Exception:
        return 0


class _TagsOverflowListener(dynamic_proxy(View.OnLayoutChangeListener)):
    # Keeps the card's tag row on a single line: chips that don't fit are
    # dropped and summarised by a trailing "+N" chip (the full list is shown on
    # the plugin profile). The row's last child must be the "+N" chip.
    def __init__(self, plus_chip):
        super().__init__()
        self._done = False
        self._plus = plus_chip

    def onLayoutChange(self, v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom):
        if self._done:
            return
        row_width = v.getWidth()
        if row_width <= 0:
            return
        self._done = True

        tag_count = v.getChildCount() - 1  # last child is the "+N" chip
        if tag_count <= 0:
            return

        widths = []
        for i in range(tag_count):
            child = v.getChildAt(i)
            widths.append(_chip_extent(child) if child is not None else 0)

        if sum(widths) <= row_width:
            self._plus.setVisibility(View.GONE)
            return

        plus_width = _measure_width(self._plus)
        kept = 0
        used = 0
        for w in widths:
            if used + w + plus_width > row_width:
                break
            used += w
            kept += 1
        if kept == 0:
            kept = 1  # always leave at least one real tag on the card

        for i in range(kept, tag_count):
            child = v.getChildAt(i)
            if child is not None:
                child.setVisibility(View.GONE)

        self._plus.setText(f"+{tag_count - kept}")
        self._plus.setVisibility(View.VISIBLE)
        # do not call removeOnLayoutChangeListener — causes equals() crash on Chaquopy proxy
