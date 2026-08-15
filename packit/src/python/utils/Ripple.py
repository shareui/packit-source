# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Every ripple background in the plugin goes through here.
#
# A raw RippleDrawable can throw from draw() deep inside the framework — seen
# in the wild as
#   NPE: Attempt to read from null array
#     at ColorStateList.getColorForState
#     at RippleDrawable.updateRipplePaint
#     at RippleDrawable.drawPatterned      <- the Android 12+ patterned ripple
#     at RippleDrawable.draw
# and because that happens inside the render pass it takes the whole app down.
#
# The host hit the same thing and wrapped every ripple it builds in
# org.telegram.ui.Cells.BaseCell$RippleDrawableSafe, which simply catches
# exceptions thrown by super.draw(). All Theme.createSelectorDrawable* helpers
# return that class — only the ripples we construct ourselves were unguarded.
# safe_ripple() builds the host's safe subclass, falling back to a plain
# RippleDrawable (and finally to the content drawable) when it is unavailable.

from packutil import logx

_SAFE_CLS = None
_SAFE_LOOKED_UP = False


def _safe_ripple_class():
    global _SAFE_CLS, _SAFE_LOOKED_UP
    if not _SAFE_LOOKED_UP:
        _SAFE_LOOKED_UP = True
        try:
            from hook_utils import find_class
            _SAFE_CLS = find_class("org.telegram.ui.Cells.BaseCell$RippleDrawableSafe")
        except Exception as e:
            logx(f"ripple: RippleDrawableSafe unavailable: {e}", False)
            _SAFE_CLS = None
    return _SAFE_CLS


def safe_ripple(color_state_list, content, mask):
    # returns a crash-guarded RippleDrawable, or `content` if none can be built
    cls = _safe_ripple_class()
    if cls is not None:
        try:
            return cls(color_state_list, content, mask)
        except Exception as e:
            logx(f"ripple: safe ripple construction failed: {e}", False)
    try:
        from android.graphics.drawable import RippleDrawable
        return RippleDrawable(color_state_list, content, mask)
    except Exception as e:
        logx(f"ripple: plain ripple construction failed: {e}", False)
    return content
