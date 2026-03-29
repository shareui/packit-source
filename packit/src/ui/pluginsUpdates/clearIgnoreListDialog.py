import ctypes
import json
import os

from android_utils import log, run_on_ui_thread, OnClickListener
from java import dynamic_proxy

try:
    from elyx import strings, settings
except Exception as e:
    log(f"clearIgnoreListDialog: import elyx failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"clearIgnoreListDialog: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities, ApplicationLoader
except Exception as e:
    log(f"clearIgnoreListDialog: import AndroidUtilities/LayoutHelper failed: {e}")


_ANIM_DURATION = 220
_SPRING_DURATION = 380


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
        log(f"clearIgnoreListDialog: _animate_in error: {e}")


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
        log(f"clearIgnoreListDialog: _animate_out error: {e}")
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


def _get_index_path(pkg: str, rm_rid: str) -> str:
    return f"/data/data/{pkg}/files/packitCache/reposCache/{rm_rid}-index.json"


def _clear_all_ignore_lists():
    # clears ignore_list in every repo index file
    try:
        pkg = ApplicationLoader.applicationContext.getPackageName()
        raw = settings.get("repositories", "[]")
        repos = json.loads(raw)
        if not isinstance(repos, list):
            repos = []
        for repo in repos:
            rm_rid = repo.get("rm_rid") or repo.get("id") or ""
            if not rm_rid:
                continue
            path = _get_index_path(pkg, rm_rid)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["ignore_list"] = []
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log(f"clearIgnoreListDialog: clear repo '{rm_rid}' error: {e}")
        log("clearIgnoreListDialog: all ignore lists cleared")
        try:
            from ui.bulletin import BulletinHelper
            run_on_ui_thread(lambda: BulletinHelper.show_success(str(strings["clear_ignore_list_done"])))
        except Exception as e:
            log(f"clearIgnoreListDialog: bulletin error: {e}")
    except Exception as e:
        log(f"clearIgnoreListDialog: _clear_all_ignore_lists error: {e}")


def _remove_plugin_from_ignore_lists(pid: str):
    # removes a specific plugin id from ignore_list across all repos
    try:
        pkg = ApplicationLoader.applicationContext.getPackageName()
        raw = settings.get("repositories", "[]")
        repos = json.loads(raw)
        if not isinstance(repos, list):
            repos = []
        for repo in repos:
            rm_rid = repo.get("rm_rid") or repo.get("id") or ""
            if not rm_rid:
                continue
            path = _get_index_path(pkg, rm_rid)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lst = data.get("ignore_list")
                if not isinstance(lst, list):
                    continue
                filtered = [e for e in lst if e.get("id") != pid]
                if len(filtered) == len(lst):
                    continue
                data["ignore_list"] = filtered
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log(f"clearIgnoreListDialog: remove plugin '{pid}' from repo '{rm_rid}' error: {e}")
        log(f"clearIgnoreListDialog: plugin '{pid}' removed from all ignore lists")
        try:
            from ui.bulletin import BulletinHelper
            run_on_ui_thread(lambda: BulletinHelper.show_success(str(strings["clear_ignore_list_specific_done"])))
        except Exception as e:
            log(f"clearIgnoreListDialog: specific bulletin error: {e}")
    except Exception as e:
        log(f"clearIgnoreListDialog: _remove_plugin_from_ignore_lists error: {e}")


def show_clear_ignore_list_dialog(act):
    # shows custom dialog: Specific plugin (opens input) / Clear all / Cancel
    try:
        from android.widget import LinearLayout, TextView, FrameLayout
        from android.view import Gravity, ViewGroup
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable
        from android.text import InputType

        dp = AndroidUtilities.dp
        decor = act.getWindow().getDecorView()

        overlay_ref = [None]

        def _dismiss(on_end=None):
            _animate_out(overlay_ref, card, decor, on_end=on_end)

        # dim overlay
        overlay = FrameLayout(act)
        overlay_ref[0] = overlay
        overlay.setBackgroundColor(ctypes.c_int32(0x99000000).value)
        overlay.setClickable(True)
        overlay.setFocusable(True)
        overlay.setOnClickListener(OnClickListener(lambda v: _dismiss()))

        # card
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

        # title
        title_tv = TextView(act)
        title_tv.setText(str(strings["clear_ignore_list_dialog_title"]))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        card.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 20))

        accent_color = Theme.getColor(Theme.key_featuredStickers_addButton)

        # specific plugin button replaced by input field on click
        specific_btn = _make_btn(act, str(strings["clear_ignore_list_specific"]), accent=True)
        card.addView(specific_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 10))

        # pill input field, same margins as the button it replaces, hidden by default
        from org.telegram.ui.Components import EditTextBoldCursor
        input_container = FrameLayout(act)
        input_container.setVisibility(FrameLayout.GONE)
        pill_bg = GradientDrawable()
        pill_bg.setShape(GradientDrawable.RECTANGLE)
        pill_bg.setCornerRadius(dp(50))
        pill_bg.setColor(Theme.getColor(Theme.key_dialogBackgroundGray))
        pill_bg.setStroke(dp(2), accent_color)
        input_container.setBackground(pill_bg)
        input_container.setPadding(dp(16), 0, dp(16), 0)

        edit_text = EditTextBoldCursor(act)
        edit_text.setHint("Enter plugin ID")
        edit_text.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        edit_text.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        edit_text.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        edit_text.setBackgroundColor(0)
        edit_text.setSingleLine(True)
        edit_text.setInputType(InputType.TYPE_CLASS_TEXT)
        try:
            edit_text.setCursorColor(accent_color)
        except Exception:
            pass
        edit_text.setPadding(0, 0, 0, 0)
        input_container.addView(edit_text, FrameLayout.LayoutParams(-1, dp(42)))
        # same bottom margin as the button: 10dp
        card.addView(input_container, LayoutHelper.createLinear(-1, dp(42), 0, 0, 0, 10))

        def _on_specific_click(v):
            try:
                specific_btn.setVisibility(FrameLayout.GONE)
                input_container.setVisibility(FrameLayout.VISIBLE)
                input_container.setAlpha(0.0)
                input_container.setTranslationY(float(-dp(10)))

                from android.animation import AnimatorSet, ObjectAnimator
                from android.view.animation import OvershootInterpolator, DecelerateInterpolator

                fade = ObjectAnimator.ofFloat(input_container, "alpha", 0.0, 1.0)
                fade.setDuration(_ANIM_DURATION)
                fade.setInterpolator(DecelerateInterpolator())

                slide = ObjectAnimator.ofFloat(input_container, "translationY", float(-dp(10)), 0.0)
                slide.setDuration(_SPRING_DURATION)
                slide.setInterpolator(OvershootInterpolator(1.6))

                s = AnimatorSet()
                s.playTogether(fade, slide)
                s.start()

                edit_text.requestFocus()
                AndroidUtilities.showKeyboard(edit_text)
            except Exception as e:
                log(f"clearIgnoreListDialog: _on_specific_click error: {e}")

        specific_btn.setOnClickListener(OnClickListener(_on_specific_click))

        # clear all button becomes remove button in context, shown always
        clear_all_btn = _make_btn(act, str(strings["clear_ignore_list_all"]), accent=True)
        card.addView(clear_all_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 10))

        def _on_clear_all_click(v):
            # if input is visible, treat as remove specific
            if input_container.getVisibility() == FrameLayout.VISIBLE:
                pid = str(edit_text.getText()).strip()
                if not pid:
                    return
                AndroidUtilities.hideKeyboard(edit_text)
                _dismiss(on_end=lambda: _remove_plugin_from_ignore_lists(pid))
            else:
                _dismiss(on_end=_clear_all_ignore_lists)

        clear_all_btn.setOnClickListener(OnClickListener(_on_clear_all_click))

        def _on_specific_shown():
            # swap button label to "Remove" when input is active
            try:
                for i in range(clear_all_btn.getChildCount()):
                    child = clear_all_btn.getChildAt(i)
                    child.setText(str(strings["clear_ignore_list_remove"]))
            except Exception as e:
                log(f"clearIgnoreListDialog: label swap error: {e}")

        # patch specific click to also swap the label
        original_specific_click = _on_specific_click
        def _on_specific_click_with_label(v):
            original_specific_click(v)
            _on_specific_shown()
        specific_btn.setOnClickListener(OnClickListener(_on_specific_click_with_label))

        # cancel button
        cancel_btn = _make_btn(act, str(strings["clear_ignore_list_cancel"]), accent=False)
        cancel_btn.setOnClickListener(OnClickListener(lambda v: _dismiss()))
        card.addView(cancel_btn, LayoutHelper.createLinear(-1, -2))

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
        run_on_ui_thread(lambda: _animate_in(overlay, card))
    except Exception as e:
        log(f"clearIgnoreListDialog: show_clear_ignore_list_dialog error: {e}")
