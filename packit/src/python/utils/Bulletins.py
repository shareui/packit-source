# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Central bulletin factory for the whole plugin.
#
# Prefer BulletinFactory.of(fragment): the fragment overload anchors the
# bulletin inside the fragment's content container, which carries the
# navigation-bar insets, so the bulletin floats ABOVE the nav bar. The
# (decorView, resourceProvider) overload pins the bulletin to the raw window
# decor view — that draws it UNDER / behind the nav bar, which is the "bulletin
# sits too low" bug.
#
# Every PackIt bulletin site calls factory(...) instead of BulletinFactory.of
# directly, so the offset is applied uniformly. The original (container, rp)
# arguments are still passed through and used only as a fallback for the rare
# case where no host fragment is currently available.

from packutil import logx


def factory(*fallback_args):
    from hook_utils import find_class
    from client_utils import get_last_fragment
    BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
    frag = get_last_fragment()
    if frag is not None:
        try:
            return BulletinFactory.of(frag)
        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"bulletins: fragment factory failed, using fallback: {e}", True)
    return BulletinFactory.of(*fallback_args)
