# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
from ...utils.ripple import safe_ripple as _safe_ripple
from ...utils.bulletins import factory as _pbf
import ctypes
from android_utils import run_on_ui_thread, OnClickListener

try:
    from elyx import strings
except Exception as e:
    logx(f"infoDialog: import elyx.strings failed: {e}", False)
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    logx(f"infoDialog: import Theme failed: {e}", False)
try:
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    logx(f"infoDialog: import AndroidUtilities/LayoutHelper failed: {e}", False)

_ANIM_DURATION = 220
_SPRING_DURATION = 380


def _register_back_cb(act, on_back):
    try:
        from androidx.activity import OnBackPressedCallback
        from extera_utils.classes import Base, java_subclass, joverride

        @java_subclass(OnBackPressedCallback)
        class _Cb(Base):
            @joverride()
            def handleOnBackPressed(self):
                on_back()

        cb = _Cb.new_instance(True)
        act.getOnBackPressedDispatcher().addCallback(act, cb.java)
        return cb
    except Exception as e:
        logx(f"infoDialog: _register_back_cb error: {e}", False)
        return None

def _unregister_back_cb(cb):
    try:
        if cb is not None:
            cb.remove()
    except Exception as e:
        logx(f"infoDialog: _unregister_back_cb error: {e}", False)


def _animate_in(overlay, card):
    try:
        from android.animation import AnimatorSet, ObjectAnimator
        from android.view.animation import OvershootInterpolator, DecelerateInterpolator

        fade_overlay = ObjectAnimator.ofFloat(overlay, "alpha", 0.0, 1.0)
        fade_overlay.setDuration(_ANIM_DURATION)
        fade_overlay.setInterpolator(DecelerateInterpolator())

        fade_card = ObjectAnimator.ofFloat(card, "alpha", 0.0, 1.0)
        fade_card.setDuration(_ANIM_DURATION)
        fade_card.setInterpolator(DecelerateInterpolator())

        scale_x = ObjectAnimator.ofFloat(card, "scaleX", 0.88, 1.0)
        scale_x.setDuration(_SPRING_DURATION)
        scale_x.setInterpolator(OvershootInterpolator(2.0))

        scale_y = ObjectAnimator.ofFloat(card, "scaleY", 0.88, 1.0)
        scale_y.setDuration(_SPRING_DURATION)
        scale_y.setInterpolator(OvershootInterpolator(2.0))

        s = AnimatorSet()
        s.playTogether(fade_overlay, fade_card, scale_x, scale_y)
        s.start()
    except Exception as e:
        logx(f"infoDialog: _animate_in error: {e}", False)


def _animate_out(overlay_ref, card, decor):
    try:
        from android.animation import AnimatorSet, ObjectAnimator, Animator
        from java import dynamic_proxy

        fade_overlay = ObjectAnimator.ofFloat(overlay_ref[0], "alpha", overlay_ref[0].getAlpha(), 0.0)
        fade_overlay.setDuration(_ANIM_DURATION)

        fade_card = ObjectAnimator.ofFloat(card, "alpha", card.getAlpha(), 0.0)
        fade_card.setDuration(_ANIM_DURATION)

        scale_x = ObjectAnimator.ofFloat(card, "scaleX", card.getScaleX(), 0.92)
        scale_x.setDuration(_ANIM_DURATION)

        scale_y = ObjectAnimator.ofFloat(card, "scaleY", card.getScaleY(), 0.92)
        scale_y.setDuration(_ANIM_DURATION)

        class _EndListener(dynamic_proxy(Animator.AnimatorListener)):
            def onAnimationEnd(self, a, *args):
                try:
                    decor.removeView(overlay_ref[0])
                except Exception:
                    pass

            def onAnimationStart(self, a, *args): pass
            def onAnimationCancel(self, a, *args): pass
            def onAnimationRepeat(self, a, *args): pass

        s = AnimatorSet()
        s.playTogether(fade_overlay, fade_card, scale_x, scale_y)
        s.addListener(_EndListener())
        s.start()
    except Exception as e:
        logx(f"infoDialog: _animate_out error: {e}", False)
        try:
            decor.removeView(overlay_ref[0])
        except Exception:
            pass


def _copy_to_clipboard(decor, label: str, text: str):
    try:
        from org.telegram.messenger import AndroidUtilities, R as R_tg
        from org.telegram.ui.Components import BulletinFactory
        AndroidUtilities.addToClipboard(text)
        _pbf(decor, None).createSimpleBulletin(
            R_tg.raw.copy,
            str(strings["info_copied"]).format(label=label)
        ).show()
    except Exception as e:
        logx(f"infoDialog: _copy_to_clipboard error: {e}", False)


def _make_row_bg(act, corner_dp: int):
    # RippleDrawable over solid card-white bg, same pattern as PluginList fragment
    from android.graphics.drawable import GradientDrawable, RippleDrawable
    from android.graphics import Color as AColor
    from android.content.res import ColorStateList as AColorStateList

    dp = AndroidUtilities.dp

    bg_color = Theme.getColor(Theme.key_windowBackgroundWhite)
    try:
        pressed_color = Theme.getColor(Theme.key_listSelector) & 0x40FFFFFF | 0x30000000
    except Exception:
        pressed_color = AColor.parseColor("#D0D0D0")

    btn_bg = GradientDrawable()
    btn_bg.setCornerRadius(dp(corner_dp))
    btn_bg.setColor(bg_color)

    try:
        ripple_color = AColorStateList.valueOf(AColor.parseColor("#40000000"))
        pressed_bg = GradientDrawable()
        pressed_bg.setCornerRadius(dp(corner_dp))
        pressed_bg.setColor(pressed_color)
        return _safe_ripple(ripple_color, btn_bg, pressed_bg)
    except Exception:
        try:
            return Theme.createSimpleSelectorRoundRectDrawable(dp(corner_dp), bg_color, pressed_color)
        except Exception:
            return btn_bg


def _make_row(act, decor, label: str, value: str, icon_name: str, copy_value: str):
    from android.widget import LinearLayout, TextView, ImageView
    from android.view import Gravity
    from android.util import TypedValue

    dp = AndroidUtilities.dp

    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setPadding(dp(12), dp(8), dp(12), dp(8))
    row.setClickable(True)
    row.setFocusable(True)
    row.setBackground(_make_row_bg(act, 10))
    row.setOnClickListener(OnClickListener(lambda v: _copy_to_clipboard(decor, label, copy_value)))

    if icon_name:
        try:
            from hook_utils import find_class
            R_tg = find_class("org.telegram.messenger.R")
            icon_id = getattr(R_tg.drawable, icon_name, 0)
            if icon_id:
                icon_iv = ImageView(act)
                icon_iv.setImageResource(icon_id)
                icon_iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayIcon))
                icon_iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                icon_lp = LinearLayout.LayoutParams(dp(18), dp(18))
                icon_lp.rightMargin = dp(10)
                row.addView(icon_iv, icon_lp)
        except Exception:
            pass

    col = LinearLayout(act)
    col.setOrientation(LinearLayout.VERTICAL)

    label_tv = TextView(act)
    label_tv.setText(label)
    label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    label_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    try:
        label_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        pass
    col.addView(label_tv, LinearLayout.LayoutParams(-2, -2))

    value_tv = TextView(act)
    value_tv.setText(value)
    value_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
    value_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
    value_tv.setSingleLine(False)
    col.addView(value_tv, LinearLayout.LayoutParams(-1, -2))

    row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    return row


def _build_display(info: dict) -> list:
    # returns list of (label, display_value, copy_value, icon)
    rows = []

    path = info.get("full_path")
    if path:
        rows.append((str(strings["info_path"]), path, path, "menu_storage_path"))

    is_dir = info.get("is_dir", False)
    ext = info.get("extension", "")
    if is_dir:
        type_label = str(strings["info_type_dir"])
    else:
        if ext and ext != "(none)":
            type_label = str(strings["info_type_file_ext"]).format(ext=ext)
        else:
            type_label = str(strings["info_type_file"])
    rows.append((str(strings["info_type_file"]), type_label, type_label, "msg_filehq"))

    if is_dir:
        children = info.get("children")
        if children is not None:
            rows.append((str(strings["info_items"]), str(children), str(children), "msg_addfolder"))
        dir_size = info.get("dir_size_human")
        if dir_size:
            rows.append((str(strings["info_content_size"]), dir_size, dir_size, "msg_filled_storageusage"))
    else:
        size_bytes = info.get("size_bytes")
        size_human = info.get("size_human", "")
        if size_bytes is not None:
            if size_bytes >= 1024:
                bytes_fmt = f"{size_bytes:,}".replace(",", "\u202f")
                size_display = f"{size_human} ({bytes_fmt} B)"
                size_copy = size_display
            else:
                size_display = size_human
                size_copy = size_human
            rows.append((str(strings["info_size"]), size_display, size_copy, "msg_filled_storageusage"))

    modified = info.get("modified")
    if modified:
        rows.append((str(strings["info_modified"]), modified, modified, "msg_calendar2"))

    created = info.get("created")
    if created:
        rows.append((str(strings["info_created"]), created, created, "msg_calendar"))

    return rows


def show_info_dialog(act, name: str, info: dict):
    try:
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.view import Gravity, ViewGroup
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable

        dp = AndroidUtilities.dp
        decor = act.getWindow().getDecorView()
        overlay_ref = [None]
        back_cb_ref = [None]

        def _dismiss():
            _unregister_back_cb(back_cb_ref[0])
            back_cb_ref[0] = None
            _animate_out(overlay_ref, card, decor)

        overlay = FrameLayout(act)
        overlay_ref[0] = overlay
        overlay.setBackgroundColor(ctypes.c_int32(0x99000000).value)
        overlay.setClickable(True)
        overlay.setFocusable(True)
        overlay.setOnClickListener(OnClickListener(lambda v: _dismiss()))

        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        card.setClickable(True)
        card.setFocusable(True)
        card.setOnClickListener(OnClickListener(lambda v: None))

        bg_color = Theme.getColor(Theme.key_dialogBackground)
        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(dp(16))
        card_bg.setColor(bg_color)
        card.setBackground(card_bg)
        card.setPadding(dp(16), dp(20), dp(16), dp(16))

        margin_h = dp(24)
        card_lp = FrameLayout.LayoutParams(-1, -2)
        card_lp.gravity = Gravity.CENTER
        card_lp.leftMargin = margin_h
        card_lp.rightMargin = margin_h
        overlay.addView(card, card_lp)

        title_tv = TextView(act)
        title_tv.setText(name)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        title_tv.setSingleLine(True)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        card.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 12))

        rows_layout = LinearLayout(act)
        rows_layout.setOrientation(LinearLayout.VERTICAL)

        for label, display_val, copy_val, icon in _build_display(info):
            row = _make_row(act, decor, label, display_val, icon, copy_val)
            lp = LinearLayout.LayoutParams(-1, -2)
            lp.bottomMargin = AndroidUtilities.dp(4)
            rows_layout.addView(row, lp)

        card.addView(rows_layout, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 12))

        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        accent_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)

        close_btn = FrameLayout(act)
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(12), accent, accent_pressed))

        close_tv = TextView(act)
        close_tv.setText(str(strings["info_dialog_ok"]))
        close_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        close_tv.setGravity(Gravity.CENTER)
        close_tv.setPadding(dp(16), dp(13), dp(16), dp(13))
        close_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        try:
            close_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        close_btn.addView(close_tv, FrameLayout.LayoutParams(-1, -2))
        close_btn.setOnClickListener(OnClickListener(lambda v: _dismiss()))
        card.addView(close_btn, LayoutHelper.createLinear(-1, -2))

        overlay.setAlpha(0.0)
        card.setAlpha(0.0)
        card.setScaleX(0.92)
        card.setScaleY(0.92)

        try:
            from ..viewUtils import applyFontToTree
            applyFontToTree(card)
        except Exception:
            pass

        decor.addView(overlay, ViewGroup.LayoutParams(-1, -1))
        back_cb_ref[0] = _register_back_cb(act, _dismiss)
        run_on_ui_thread(lambda: _animate_in(overlay, card))
    except Exception as e:
        logx(f"infoDialog: show_info_dialog error: {e}", False)