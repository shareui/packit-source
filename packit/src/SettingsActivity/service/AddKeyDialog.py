# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

import ctypes

from android_utils import log, run_on_ui_thread, OnClickListener
from java import dynamic_proxy

try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"AddKeyDialog: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper, EditTextBoldCursor, OutlineTextContainerView
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    log(f"AddKeyDialog: import AndroidUtilities/LayoutHelper failed: {e}")

_ANIM_DURATION = 220
_SPRING_DURATION = 380
_KB_ANIM_DURATION = 280


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
        log(f"AddKeyDialog: _register_back_cb error: {e}")
        return None


def _unregister_back_cb(cb):
    try:
        if cb is not None:
            cb.remove()
    except Exception as e:
        log(f"AddKeyDialog: _unregister_back_cb error: {e}")


def _animate_in(overlay, card, on_end=None):
    try:
        from android.animation import AnimatorSet, ObjectAnimator, Animator

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

        if on_end is not None:
            from java import dynamic_proxy

            class _EndListener(dynamic_proxy(Animator.AnimatorListener)):
                def onAnimationEnd(self, a, *args):
                    on_end()

                def onAnimationStart(self, a, *args): pass
                def onAnimationCancel(self, a, *args): pass
                def onAnimationRepeat(self, a, *args): pass

            s.addListener(_EndListener())

        s.start()
    except Exception as e:
        log(f"AddKeyDialog: _animate_in error: {e}")
        if on_end is not None:
            on_end()


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
        log(f"AddKeyDialog: _animate_out error: {e}")
        try:
            decor.removeView(overlay_ref[0])
        except Exception:
            pass
        if on_end:
            on_end()


def _attach_keyboard_listener(act, decor, card):
    # tracks keyboard height via getWindowVisibleDisplayFrame and shifts card up
    # requires SOFT_INPUT_ADJUST_RESIZE on the window to receive layout updates
    try:
        from android.view import ViewTreeObserver
        from android.graphics import Rect
        from android.animation import ObjectAnimator
        from android.view.animation import DecelerateInterpolator
        from android.view import WindowManager

        window = act.getWindow()
        orig_soft_input_mode = window.getAttributes().softInputMode
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        log("AddKeyDialog: keyboard listener attached, SOFT_INPUT_ADJUST_RESIZE set")

        visible_rect = Rect()
        kb_height_ref = [0]
        anim_ref = [None]
        orig_mode_ref = [orig_soft_input_mode]

        def _update_translation(new_kb_height):
            # subtle nudge upward so the user feels the dialog is aware of the keyboard
            target_ty = float(-new_kb_height) * 0.12
            current_ty = card.getTranslationY()
            if abs(current_ty - target_ty) < 1:
                return
            if anim_ref[0] is not None:
                try:
                    anim_ref[0].cancel()
                except Exception:
                    pass
            anim = ObjectAnimator.ofFloat(card, "translationY", current_ty, target_ty)
            anim.setDuration(_KB_ANIM_DURATION)
            anim.setInterpolator(DecelerateInterpolator(2.0))
            anim.start()
            anim_ref[0] = anim

        class _LayoutListener(dynamic_proxy(ViewTreeObserver.OnGlobalLayoutListener)):
            def onGlobalLayout(self):
                try:
                    decor.getWindowVisibleDisplayFrame(visible_rect)
                    decor_height = decor.getHeight()
                    kb_height = decor_height - visible_rect.bottom
                    if kb_height < AndroidUtilities.dp(100):
                        kb_height = 0
                    if kb_height != kb_height_ref[0]:
                        log(f"AddKeyDialog: keyboard height changed {kb_height_ref[0]} -> {kb_height}")
                        kb_height_ref[0] = kb_height
                        _update_translation(kb_height)
                except Exception as e:
                    log(f"AddKeyDialog: _LayoutListener error: {e}")

        listener = _LayoutListener()
        decor.getViewTreeObserver().addOnGlobalLayoutListener(listener)
        return listener, orig_mode_ref
    except Exception as e:
        log(f"AddKeyDialog: _attach_keyboard_listener error: {e}")
        return None, None


def _detach_keyboard_listener(act, decor, listener, orig_mode_ref):
    try:
        if listener is not None:
            decor.getViewTreeObserver().removeOnGlobalLayoutListener(listener)
        if orig_mode_ref is not None and orig_mode_ref[0] is not None:
            act.getWindow().setSoftInputMode(orig_mode_ref[0])
    except Exception as e:
        log(f"AddKeyDialog: _detach_keyboard_listener error: {e}")


def show_add_key_dialog(act, title: str, subtitle: str, hint: str, button_text: str, on_confirm=None, outline_label: str = None):
    # universal dialog: bold title, gray subtitle, rounded input, accent confirm button
    # on_confirm(key: str) called with the entered value; dialog closes on confirm
    try:
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.view import Gravity, ViewGroup
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable
        from android.text import InputType

        dp = AndroidUtilities.dp
        decor = act.getWindow().getDecorView()

        overlay_ref = [None]
        back_cb_ref = [None]
        kb_listener_ref = [None]
        orig_mode_ref = [None]

        def _dismiss(on_end=None):
            _unregister_back_cb(back_cb_ref[0])
            back_cb_ref[0] = None
            _detach_keyboard_listener(act, decor, kb_listener_ref[0], orig_mode_ref[0])
            kb_listener_ref[0] = None
            orig_mode_ref[0] = None
            _animate_out(overlay_ref, card, decor, on_end=on_end)

        # dim overlay
        overlay = FrameLayout(act)
        overlay_ref[0] = overlay
        overlay.setBackgroundColor(ctypes.c_int32(0x99000000).value)
        overlay.setClickable(True)
        overlay.setFocusable(True)
        def _dismiss_from_overlay(v):
            AndroidUtilities.hideKeyboard(edit_text)
            _dismiss()

        overlay.setOnClickListener(OnClickListener(_dismiss_from_overlay))

        # card
        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        card.setClickable(True)
        card.setFocusable(True)
        card.setOnClickListener(OnClickListener(lambda v: None))

        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(dp(16))
        card_bg.setColor(Theme.getColor(Theme.key_dialogBackground))
        card.setBackground(card_bg)
        card.setPadding(dp(20), dp(24), dp(20), dp(20))

        margin_h = dp(32)
        card_lp = FrameLayout.LayoutParams(-1, -2)
        card_lp.gravity = Gravity.CENTER
        card_lp.leftMargin = margin_h
        card_lp.rightMargin = margin_h
        overlay.addView(card, card_lp)

        # title (bold)
        title_tv = TextView(act)
        title_tv.setText(title)
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception as e:
            log(f"AddKeyDialog: title typeface error: {e}")
        card.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        # subtitle (gray)
        subtitle_tv = TextView(act)
        subtitle_tv.setText(subtitle)
        subtitle_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        subtitle_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        subtitle_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        card.addView(subtitle_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        # rounded input with outline
        accent_color = Theme.getColor(Theme.key_featuredStickers_addButton)

        outline = OutlineTextContainerView(act)
        outline.setText(outline_label if outline_label is not None else hint)
        outline.animateSelection(1, False)
        outline.setClipChildren(True)
        outline.setClipToPadding(True)

        edit_text = EditTextBoldCursor(act)
        edit_text.setHint(hint)
        edit_text.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        edit_text.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        edit_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        edit_text.setBackground(None)
        edit_text.setSingleLine(True)
        edit_text.setHorizontallyScrolling(True)
        edit_text.setInputType(InputType.TYPE_CLASS_TEXT)
        try:
            edit_text.setCursorColor(accent_color)
            edit_text.setCursorWidth(1.5)
        except Exception as e:
            log(f"AddKeyDialog: cursor color error: {e}")
        edit_text.setPadding(dp(16), dp(14), dp(16), dp(14))
        try:
            from android.text import TextUtils
            edit_text.setEllipsize(TextUtils.TruncateAt.END)
        except Exception as e:
            log(f"AddKeyDialog: ellipsize error: {e}")

        from android.view import View

        class _FocusListener(dynamic_proxy(View.OnFocusChangeListener)):
            def onFocusChange(self, v, hasFocus):
                outline.animateSelection(1 if hasFocus else 0)

        edit_text.setOnFocusChangeListener(_FocusListener())
        outline.addView(edit_text, LayoutHelper.createFrame(-1, -2))
        outline.attachEditText(edit_text)
        card.addView(outline, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 16))

        # accent confirm button
        confirm_btn = TextView(act)
        confirm_btn.setText(button_text)
        confirm_btn.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        confirm_btn.setGravity(Gravity.CENTER)
        confirm_btn.setPadding(dp(16), dp(14), dp(16), dp(14))
        confirm_btn.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        confirm_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            dp(12),
            accent_color,
            Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        ))
        try:
            confirm_btn.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception as e:
            log(f"AddKeyDialog: confirm typeface error: {e}")

        def _on_confirm(v):
            try:
                key_value = str(edit_text.getText()).strip()
                AndroidUtilities.hideKeyboard(edit_text)
                _dismiss(on_end=lambda: on_confirm(key_value) if on_confirm else None)
            except Exception as e:
                log(f"AddKeyDialog: _on_confirm error: {e}")

        confirm_btn.setOnClickListener(OnClickListener(_on_confirm))
        card.addView(confirm_btn, LayoutHelper.createLinear(-1, -2))

        overlay.setAlpha(0.0)
        card.setAlpha(0.0)
        card.setScaleX(0.92)
        card.setScaleY(0.92)

        decor.addView(overlay, ViewGroup.LayoutParams(-1, -1))
        back_cb_ref[0] = _register_back_cb(act, _dismiss)

        listener, orig_mode = _attach_keyboard_listener(act, decor, card)
        kb_listener_ref[0] = listener
        orig_mode_ref[0] = orig_mode

        def _open():
            edit_text.requestFocus()
            _animate_in(overlay, card, on_end=lambda: AndroidUtilities.showKeyboard(edit_text))

        run_on_ui_thread(_open)
    except Exception as e:
        log(f"AddKeyDialog: show_add_key_dialog error: {e}")