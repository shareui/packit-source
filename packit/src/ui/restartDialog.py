# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import ctypes
from android_utils import run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment

try:
    from elyx import strings
except Exception as e:
    logx(f"restartDialog: import elyx.strings failed: {e}", False)
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    logx(f"restartDialog: import Theme failed: {e}", False)
try:
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    logx(f"restartDialog: import AndroidUtilities/LayoutHelper failed: {e}", False)

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
        logx(f"restartDialog: _register_back_cb error: {e}", False)
        return None


def _unregister_back_cb(cb):
    try:
        if cb is not None:
            cb.remove()
    except Exception as e:
        logx(f"restartDialog: _unregister_back_cb error: {e}", False)


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
        logx(f"restartDialog: _animate_in error: {e}", False)


def _animate_out(overlay_ref, card, decor, on_end=None):
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
                if on_end:
                    on_end()

            def onAnimationStart(self, a, *args): pass
            def onAnimationCancel(self, a, *args): pass
            def onAnimationRepeat(self, a, *args): pass

        s = AnimatorSet()
        s.playTogether(fade_overlay, fade_card, scale_x, scale_y)
        s.addListener(_EndListener())
        s.start()
    except Exception as e:
        logx(f"restartDialog: _animate_out error: {e}", False)
        try:
            decor.removeView(overlay_ref[0])
        except Exception:
            pass
        if on_end:
            on_end()


def _make_icon_badge(act, is_required: bool):
    from android.widget import FrameLayout, ImageView
    from android.graphics.drawable import GradientDrawable

    dp = AndroidUtilities.dp

    if is_required:
        try:
            color = Theme.getColor(Theme.key_color_orange)
        except Exception:
            color = 0xFFFFA726
        icon_name = "msg_reset"
    else:
        try:
            color = Theme.getColor(Theme.key_featuredStickers_addButton)
        except Exception:
            color = 0xFF1E88E5
        icon_name = "msg_info_filled"

    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    badge_color = ctypes.c_int32((0x22 << 24) | (r << 16) | (g << 8) | b).value

    badge = FrameLayout(act)
    badge_bg = GradientDrawable()
    badge_bg.setShape(GradientDrawable.OVAL)
    badge_bg.setColor(badge_color)
    badge.setBackground(badge_bg)

    size = dp(64)
    badge_lp = FrameLayout.LayoutParams(size, size)
    badge.setLayoutParams(badge_lp)

    icon = ImageView(act)
    icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    icon.setPadding(dp(14), dp(14), dp(14), dp(14))
    try:
        from hook_utils import find_class
        R_tg = find_class("org.telegram.messenger.R")
        icon_id = getattr(R_tg.drawable, icon_name, 0)
        if icon_id:
            icon.setImageResource(icon_id)
        icon.setColorFilter(color)
    except Exception:
        pass

    badge.addView(icon, FrameLayout.LayoutParams(-1, -1))
    return badge, color


def _make_action_btn(act, text: str, accent_color: int, is_primary: bool):
    from android.widget import TextView, FrameLayout
    from android.view import Gravity
    from android.util import TypedValue
    from android.graphics.drawable import GradientDrawable

    dp = AndroidUtilities.dp

    btn = FrameLayout(act)
    btn.setClickable(True)
    btn.setFocusable(True)

    if is_primary:
        try:
            pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            pressed = accent_color
        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(dp(14), accent_color, pressed))
    else:
        try:
            base = Theme.getColor(Theme.key_windowBackgroundGray)
        except Exception:
            base = 0xFF303030
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(14))
        bg.setColor(base)
        btn.setBackground(bg)

    tv = TextView(act)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    tv.setGravity(Gravity.CENTER)
    tv.setPadding(dp(16), dp(14), dp(16), dp(14))

    if is_primary:
        tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    else:
        tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))

    try:
        tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        pass

    btn.addView(tv, FrameLayout.LayoutParams(-1, -2))
    return btn


def _show(restart_type: str, fragment):
    try:
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.view import Gravity, ViewGroup
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable

        curr_frag = fragment or get_last_fragment()
        if not curr_frag:
            logx("restartDialog: curr_frag is None", True)
            return
        act = curr_frag.getParentActivity()
        if not act:
            logx("restartDialog: activity is None", True)
            return

        dp = AndroidUtilities.dp
        decor = act.getWindow().getDecorView()
        overlay_ref = [None]
        back_cb_ref = [None]

        is_required = restart_type == "required"

        def _dismiss(on_end=None):
            _unregister_back_cb(back_cb_ref[0])
            back_cb_ref[0] = None
            _animate_out(overlay_ref, card, decor, on_end=on_end)

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
        card_bg.setCornerRadius(dp(20))
        card_bg.setColor(bg_color)
        card.setBackground(card_bg)
        card.setPadding(dp(24), dp(28), dp(24), dp(24))

        margin_h = dp(32)
        card_lp = FrameLayout.LayoutParams(-1, -2)
        card_lp.gravity = Gravity.CENTER
        card_lp.leftMargin = margin_h
        card_lp.rightMargin = margin_h
        overlay.addView(card, card_lp)

        # icon badge centered
        badge, accent_color = _make_icon_badge(act, is_required)
        badge_frame = FrameLayout(act)
        badge_lp_inner = FrameLayout.LayoutParams(dp(64), dp(64))
        badge_lp_inner.gravity = Gravity.CENTER_HORIZONTAL
        badge_frame.addView(badge, badge_lp_inner)
        badge_outer_lp = LinearLayout.LayoutParams(-1, -2)
        badge_outer_lp.bottomMargin = dp(16)
        card.addView(badge_frame, badge_outer_lp)

        # title
        if is_required:
            title_text = str(strings["install_restart_required_title"])
        else:
            title_text = str(strings["install_restart_optional_title"])

        title_tv = TextView(act)
        title_tv.setText(title_text)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        title_lp = LinearLayout.LayoutParams(-1, -2)
        title_lp.bottomMargin = dp(10)
        card.addView(title_tv, title_lp)

        # message
        if is_required:
            msg_text = str(strings["install_restart_required_message"])
        else:
            msg_text = str(strings["install_restart_optional_message"])

        msg_tv = TextView(act)
        msg_tv.setText(msg_text)
        msg_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        msg_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        msg_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        msg_tv.setSingleLine(False)
        msg_lp = LinearLayout.LayoutParams(-1, -2)
        msg_lp.bottomMargin = dp(24)
        card.addView(msg_tv, msg_lp)

        def _do_restart():
            try:
                from ..deeplinks import pkill
                pkill.handle("tg://packit?pkill")
            except Exception as e:
                logx(f"restartDialog: pkill error: {e}", False)

        restart_btn = _make_action_btn(act, str(strings["restart_now"]), accent_color, is_primary=True)
        restart_btn.setOnClickListener(OnClickListener(lambda v: _dismiss(on_end=_do_restart)))
        restart_lp = LinearLayout.LayoutParams(-1, -2)
        restart_lp.bottomMargin = dp(10)
        card.addView(restart_btn, restart_lp)

        later_btn = _make_action_btn(act, str(strings["restart_later"]), accent_color, is_primary=False)
        later_btn.setOnClickListener(OnClickListener(lambda v: _dismiss()))
        card.addView(later_btn, LinearLayout.LayoutParams(-1, -2))

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
        logx(f"restartDialog: _show error: {e}", False)


def show_restart_dialog(restart_type: str, fragment=None):
    if restart_type not in ("required", "optional"):
        return

    import threading
    threading.Timer(0.5, lambda: run_on_ui_thread(lambda: _show(restart_type, fragment))).start()
