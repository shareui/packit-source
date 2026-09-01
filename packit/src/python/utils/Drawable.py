# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later




from packutil import logx
def get_svg_drawable(asset_name: str, fallback_res_name: str, width: int = 24, height: int = 24, color_key: str = "key_actionBarDefaultIcon"):
    # loads SVG from assets, injects theme color in place of currentColor, then rasterizes;
    # supports "folder/file" path syntax; returns R.drawable fallback on any error
    try:
        from elyx import assets
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.ui.Components import SvgHelper
        from android.graphics.drawable import BitmapDrawable
        from client_utils import get_last_fragment

        asset = assets[asset_name]

        color_int = Theme.getColor(getattr(Theme, color_key))
        hex_color = "#{:06x}".format(color_int & 0xFFFFFF)

        svg_src = asset.content_string().replace("currentColor", hex_color)

        bitmap = SvgHelper.getBitmap(svg_src, width, height, False)
        if bitmap is None:
            raise ValueError("SvgHelper.getBitmap returned None")

        frag = get_last_fragment()
        res = frag.getParentActivity().getResources() if frag else None
        return BitmapDrawable(res, bitmap)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"drawable.get_svg_drawable: '{asset_name}' failed ({e}), using fallback '{fallback_res_name}'", False)
        return _get_fallback(fallback_res_name)


def tint_drawable(drawable, color_key: str):
    # applies a Theme color as a SRC_IN color filter; mutates and returns the drawable
    try:
        from android.graphics import PorterDuff
        from org.telegram.ui.ActionBar import Theme
        drawable.mutate().setColorFilter(Theme.getColor(getattr(Theme, color_key)), PorterDuff.Mode.SRC_IN)
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"drawable.tint_drawable: {e}", False)
    return drawable


def _get_fallback(res_name: str):
    try:
        from hook_utils import find_class
        R = find_class("org.telegram.messenger.R")
        res_id = getattr(R.drawable, res_name, None)
        if res_id is None or res_id == 0:
            logx(f"drawable._get_fallback: '{res_name}' not found in R.drawable", True)
            return None
        from client_utils import get_last_fragment
        frag = get_last_fragment()
        if frag is None:
            return None
        ctx = frag.getParentActivity()
        if ctx is None:
            return None
        return ctx.getResources().getDrawable(res_id, ctx.getTheme())
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"drawable._get_fallback: '{res_name}' error: {e}", False)
        return None