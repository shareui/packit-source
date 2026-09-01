# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes
from android.view import View, MotionEvent, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ImageView, ProgressBar
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy
from hook_utils import find_class
from client_utils import get_last_fragment
try:
    from elyx import strings
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"uiHelpers: import elyx import strings failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"uiHelpers: import org.telegram.ui.ActionBar import Theme failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities
except Exception as _cython_exc_e:
    e = _cython_exc_e
    import android_utils as _au; _au.log(f"uiHelpers: import org.telegram.messenger import AndroidUtilities failed: {e}")

def apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self, fn):
                super().__init__()
                self._fn = fn
            def onTouch(self, v, event):
                return self._fn(v, event)
        def _on_touch(v, event):
            try:
                action = event.getActionMasked()
                if action == MotionEvent.ACTION_DOWN:
                    v.animate().scaleX(0.94).scaleY(0.94).setDuration(100).start()
                elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
            except Exception:
                pass
            return False
        view.setOnTouchListener(_TouchListener(_on_touch))
    except Exception:
        pass

def apply_press_scale_on_target(view, target):
    # touch on view animates target (the card row), not view itself
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self, fn):
                super().__init__()
                self._fn = fn
            def onTouch(self, v, event):
                return self._fn(v, event)
        def _on_touch(v, event):
            try:
                action = event.getActionMasked()
                if action == MotionEvent.ACTION_DOWN:
                    target.animate().scaleX(0.97).scaleY(0.97).setDuration(100).start()
                elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    target.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
            except Exception:
                pass
            return False
        view.setOnTouchListener(_TouchListener(_on_touch))
    except Exception:
        pass

def create_close_button(act, text=None):
    close_btn = FrameLayout(act)
    resolvedText = text if text is not None else strings["close_button"]
    try:
        base_color = Theme.getColor(Theme.key_featuredStickers_addButton)
    except Exception:
        base_color = Theme.getColor(Theme.key_dialogTextBlue)
    try:
        pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
    except Exception:
        pressed_color = base_color
    close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
        AndroidUtilities.dp(28), base_color, pressed_color
    ))
    close_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
    close_btn.setClickable(True)
    close_btn.setFocusable(True)
    close_text = TextView(act)
    close_text.setText(resolvedText)
    close_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    close_text.setTypeface(AndroidUtilities.bold())
    close_text.setGravity(Gravity.CENTER)
    close_text.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    close_btn.addView(close_text, FrameLayout.LayoutParams(-1, -2))
    return close_btn

def setup_bottom_sheet(sheet):
    for attr in ('setAllowNestedScroll', 'setResizeKeyboardArea', 'setUseSmoothKeyboard',
                 'setUseSmoothKeyboardTransition', 'setAnimateKeyboard'):
        try:
            m = getattr(sheet, attr, None)
            if m and attr in ('setUseSmoothKeyboard', 'setUseSmoothKeyboardTransition', 'setAnimateKeyboard'):
                if hasattr(sheet, attr):
                    m(True)
            elif m:
                m(True)
        except Exception:
            pass
    sheet.setApplyBottomPadding(False)
    sheet.setApplyTopPadding(False)

def create_rounded_bg(color):
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadii([
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        AndroidUtilities.dp(20), AndroidUtilities.dp(20),
        0, 0, 0, 0
    ])
    bg.setColor(color)
    return bg

def format_file_size(bytes_val):
    # returns e.g. "123.00 KB" or "1.23 MB"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    return f"{bytes_val / (1024 * 1024):.2f} MB"

def make_info_chip(act, text, color_key, size_sp=11):
    try:
        color = Theme.getColor(getattr(Theme, color_key))
    except Exception:
        color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
    text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    bg.setCornerRadius(AndroidUtilities.dp(6))
    bg.setColor(fill)
    tv = TextView(act)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, size_sp)
    tv.setTextColor(text_color)
    tv.setBackground(bg)
    tv.setPadding(
        AndroidUtilities.dp(7), AndroidUtilities.dp(2),
        AndroidUtilities.dp(7), AndroidUtilities.dp(2)
    )
    return tv

def create_pill(act, background, pressed, padding_h=14, padding_v=8):
    pill_btn = LinearLayout(act)
    pill_btn.setOrientation(LinearLayout.HORIZONTAL)
    pill_btn.setGravity(Gravity.CENTER_VERTICAL)
    pill_btn.setPadding(AndroidUtilities.dp(padding_h), AndroidUtilities.dp(padding_v),
                       AndroidUtilities.dp(padding_h), AndroidUtilities.dp(padding_v))
    pill_btn.setClickable(True)
    pill_btn.setFocusable(True)
    pill_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
        AndroidUtilities.dp(18), background, pressed
    ))
    return pill_btn

def resolve_icon(name):
    try:
        R_tg = find_class("org.telegram.messenger.R")
        return getattr(R_tg.drawable, name)
    except Exception:
        return 0

def get_theme_colors():
    is_dark_theme = False
    try:
        is_dark_theme = Theme.isCurrentThemeDark()
    except Exception:
        try:
            bg_color = Theme.getColor(Theme.key_dialogBackground)
            is_dark_theme = (bg_color & 0x00FFFFFF) < 0x00808080
        except Exception:
            pass
    from android.graphics import Color
    cardBgColor = Theme.getColor(Theme.key_windowBackgroundWhite)
    if is_dark_theme:
        return {
            "main_bg_color": Theme.getColor(Theme.key_windowBackgroundGray),
            "card_bg_color": cardBgColor,
            "card_pressed_color": Color.parseColor("#3C3C3C"),
            "text_color": Color.WHITE,
            "secondary_text_color": Color.parseColor("#CCCCCC"),
            "hint_text_color": Color.parseColor("#999999"),
            "cursor_color": Theme.getColor(Theme.key_chat_messagePanelCursor),
            "search_border_color": Color.parseColor("#3C3C3C"),
            "search_stroke_width": AndroidUtilities.dp(2)
        }
    return {
        "main_bg_color": Theme.getColor(Theme.key_windowBackgroundGray),
        "card_bg_color": cardBgColor,
        "card_pressed_color": Color.parseColor("#f5f5f5"),
        "text_color": Color.BLACK,
        "secondary_text_color": Color.parseColor("#666666"),
        "hint_text_color": Color.parseColor("#999999"),
        "cursor_color": Theme.getColor(Theme.key_chat_messagePanelCursor),
        "search_border_color": Color.parseColor("#e0e0e0"),
        "search_stroke_width": 0
    }

def create_circular_loading(act, size_dp=20):
    try:
        from org.telegram.ui.Components import CircularProgressDrawable
        color = Theme.getColor(Theme.key_featuredStickers_addButton)
        d = CircularProgressDrawable(color)
        try:
            d.size = float(AndroidUtilities.dp(size_dp))
            d.thickness = float(AndroidUtilities.dp(2))
        except Exception:
            pass
        v = ImageView(act)
        v.setImageDrawable(d)
        try:
            v.setScaleType(ImageView.ScaleType.CENTER)
        except Exception:
            pass
        return v
    except Exception:
        loading_view = ProgressBar(act)
        try:
            loading_view.setIndeterminate(True)
        except Exception:
            pass
        try:
            from android.content.res import ColorStateList
            color = Theme.getColor(Theme.key_featuredStickers_addButton)
            tint = ColorStateList.valueOf(color)
            try:
                loading_view.setIndeterminateTintList(tint)
            except Exception:
                pass
        except Exception:
            pass
        try:
            loading_view.setLayoutParams(FrameLayout.LayoutParams(AndroidUtilities.dp(size_dp), AndroidUtilities.dp(size_dp), Gravity.CENTER))
        except Exception:
            pass
        return loading_view

def create_center_loading_animation(parent_layout):
    try:
        act = get_last_fragment().getContext()
        loading_container = FrameLayout(act)
        loading_container.setLayoutParams(FrameLayout.LayoutParams(-1, -1, Gravity.CENTER))

        from org.telegram.ui.Components import CircularProgressDrawable
        size = 122
        color = Theme.getColor(Theme.key_featuredStickers_addButton)
        thickness = float(AndroidUtilities.dp(8))
        # use 3-arg ctor: size is set before setStyle, so m3IndicatorView gets correct size
        d = CircularProgressDrawable(float(size), thickness, color)
        d.setBounds(0, 0, size, size)

        spinner = ImageView(act)
        spinner.setImageDrawable(d)
        spinner.setScaleType(ImageView.ScaleType.FIT_CENTER)
        lp = FrameLayout.LayoutParams(size, size, Gravity.CENTER)
        loading_container.addView(spinner, lp)

        return loading_container, spinner
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        return None, None
