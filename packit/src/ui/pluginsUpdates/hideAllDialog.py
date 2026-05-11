import ctypes
from android_utils import log, run_on_ui_thread, OnClickListener
from java import dynamic_proxy

try:
    from elyx import strings
except Exception as e:
    log(f"hideAllDialog: import elyx.strings failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"hideAllDialog: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    log(f"hideAllDialog: import AndroidUtilities/LayoutHelper failed: {e}")


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
        log(f"hideAllDialog: _register_back_cb error: {e}")
        return None


def _unregister_back_cb(cb):
    try:
        if cb is not None:
            cb.remove()
    except Exception as e:
        log(f"hideAllDialog: _unregister_back_cb error: {e}")


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
        log(f"hideAllDialog: _animate_in error: {e}")


def _animate_out(overlay_ref, card, decor, on_end=None):
    try:
        from android.animation import AnimatorSet, ObjectAnimator, Animator

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
        log(f"hideAllDialog: _animate_out error: {e}")
        try:
            decor.removeView(overlay_ref[0])
        except Exception:
            pass
        if on_end:
            on_end()


def _make_btn(act, text: str, accent: bool):
    from android.widget import TextView, FrameLayout
    from android.view import Gravity
    from android.util import TypedValue
    from android.graphics.drawable import GradientDrawable

    dp = AndroidUtilities.dp

    btn = FrameLayout(act)
    btn.setClickable(True)
    btn.setFocusable(True)

    if accent:
        bg_color = Theme.getColor(Theme.key_featuredStickers_addButton)
        pressed_color = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        bg = Theme.createSimpleSelectorRoundRectDrawable(dp(12), bg_color, pressed_color)
    else:
        try:
            base = Theme.getColor(Theme.key_windowBackgroundGray)
        except Exception:
            base = 0xFF303030
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(12))
        bg.setColor(base)

    btn.setBackground(bg)

    tv = TextView(act)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    tv.setGravity(Gravity.CENTER)
    tv.setPadding(dp(16), dp(14), dp(16), dp(14))

    if accent:
        tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    else:
        tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))

    try:
        tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        pass

    btn.addView(tv, FrameLayout.LayoutParams(-1, -2))
    return btn


def show_hide_all_dialog(act, on_confirm):
    # shows a simple confirm dialog: title + Yes + No
    # on_confirm() is called when user taps Yes
    try:
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.view import Gravity, ViewGroup
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable

        dp = AndroidUtilities.dp
        decor = act.getWindow().getDecorView()

        overlay_ref = [None]
        back_cb_ref = [None]

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
        card_bg.setCornerRadius(dp(16))
        card_bg.setColor(bg_color)
        card.setBackground(card_bg)
        card.setPadding(dp(20), dp(20), dp(20), dp(20))

        margin_h = dp(32)
        card_lp = FrameLayout.LayoutParams(-1, -2)
        card_lp.gravity = Gravity.CENTER
        card_lp.leftMargin = margin_h
        card_lp.rightMargin = margin_h
        overlay.addView(card, card_lp)

        title_tv = TextView(act)
        title_tv.setText(str(strings["ignore_all_title"]))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        card.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        yes_btn = _make_btn(act, str(strings["yes"]), accent=True)
        yes_btn.setOnClickListener(OnClickListener(
            lambda v: _dismiss(on_end=on_confirm)
        ))
        card.addView(yes_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 10))

        no_btn = _make_btn(act, str(strings["no"]), accent=False)
        no_btn.setOnClickListener(OnClickListener(lambda v: _dismiss()))
        card.addView(no_btn, LayoutHelper.createLinear(-1, -2))

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
        log(f"hideAllDialog: show_hide_all_dialog error: {e}")
