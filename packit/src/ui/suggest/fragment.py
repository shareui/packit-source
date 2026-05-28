# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android.view import Gravity, View
from android.widget import FrameLayout, ImageView, LinearLayout, ScrollView, TextView
from android.util import TypedValue
from java import dynamic_proxy
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class
from elyx import strings

try:
    from org.telegram.ui.ActionBar import Theme
except Exception as e:
    log(f"suggest: import Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper
except Exception as e:
    log(f"suggest: import LayoutHelper failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, R as R_tg
except Exception as e:
    log(f"suggest: import AndroidUtilities failed: {e}")
try:
    from com.exteragram.messenger.plugins.ui.components.templates import UniversalFragment
except Exception as e:
    log(f"suggest: import UniversalFragment failed: {e}")


def _resolve_icon(name):
    try:
        R = find_class("org.telegram.messenger.R")
        return getattr(R.drawable, name)
    except Exception as e:
        log(f"suggest: _resolve_icon {name} failed: {e}")
        return 0


def _apply_ripple(view, corner_dp=12, bounded=True):
    # MD3 ripple feedback
    try:
        from android.graphics.drawable import RippleDrawable, ColorDrawable
        from android.content.res import ColorStateList
        ripple_color = Theme.getColor(Theme.key_listSelector)
        mask = None
        if bounded:
            try:
                from android.graphics.drawable import GradientDrawable
                mask = GradientDrawable()
                mask.setShape(GradientDrawable.RECTANGLE)
                mask.setCornerRadius(AndroidUtilities.dp(corner_dp))
                mask.setColor(0xFFFFFFFF)
            except Exception:
                pass
        existing = view.getBackground()
        ripple = RippleDrawable(
            ColorStateList.valueOf(ripple_color),
            existing,
            mask
        )
        view.setBackground(ripple)
    except Exception as e:
        log(f"suggest: _apply_ripple error: {e}")


def _make_upload_card(act):
    dp = AndroidUtilities.dp

    # MD3 outlined card: transparent bg + outline stroke
    try:
        from android.graphics.drawable import GradientDrawable
        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(dp(12))
        card_bg.setColor(0x00000000)
        try:
            card_bg.setStroke(
                dp(1),
                Theme.getColor(Theme.key_windowBackgroundWhiteGrayText) & 0x60FFFFFF | 0x30000000
            )
        except Exception as e:
            log(f"suggest: card stroke error: {e}")
    except Exception as e:
        log(f"suggest: card_bg error: {e}")
        card_bg = None

    card = FrameLayout(act)
    card.setClickable(True)
    card.setFocusable(True)
    card.setMinimumHeight(dp(112))
    if card_bg:
        card.setBackground(card_bg)

    inner = LinearLayout(act)
    inner.setOrientation(LinearLayout.VERTICAL)
    inner.setGravity(Gravity.CENTER)
    inner.setPadding(dp(24), dp(24), dp(24), dp(24))

    icon_view = ImageView(act)
    icon_id = _resolve_icon("msg_archive")
    if icon_id:
        icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
    icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    inner.addView(icon_view, LayoutHelper.createLinear(32, 32, Gravity.CENTER_HORIZONTAL, 0, 0, 0, 10))

    # MD3 titleMedium: 16sp medium
    label = TextView(act)
    label.setText(strings.suggest_upload_label)
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    label.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
    label.setGravity(Gravity.CENTER)
    try:
        label.setTypeface(AndroidUtilities.bold())
    except Exception:
        pass
    inner.addView(label, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL))

    # MD3 bodySmall: 12sp
    sub = TextView(act)
    sub.setText(strings.suggest_upload_sub)
    sub.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    sub.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    sub.setGravity(Gravity.CENTER)
    inner.addView(sub, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 0, 4, 0, 0))

    card.addView(inner, FrameLayout.LayoutParams(-1, -2))
    _apply_ripple(card, corner_dp=12)
    return card


def _make_selected_file_card(act, file_name, file_size_bytes=None):
    dp = AndroidUtilities.dp

    # MD3 filled tonal card: primary container color, corner 12dp
    try:
        from android.graphics.drawable import GradientDrawable
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(12))
        primary = Theme.getColor(Theme.key_featuredStickers_addButton)
        bg.setColor(primary & 0x1AFFFFFF | 0x12000000)
    except Exception as e:
        log(f"suggest: selected card bg error: {e}")
        bg = None

    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setPadding(dp(16), dp(12), dp(16), dp(12))
    if bg:
        row.setBackground(bg)

    icon_view = ImageView(act)
    icon_id = _resolve_icon("msg_sendfile")
    if icon_id:
        icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
    icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    row.addView(icon_view, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

    # MD3 bodyMedium: 14sp
    name_tv = TextView(act)
    name_tv.setText(file_name)
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    name_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
    name_tv.setSingleLine(True)
    try:
        from android.text import TextUtils
        name_tv.setEllipsize(TextUtils.TruncateAt.MIDDLE)
    except Exception as e:
        log(f"suggest: ellipsize error: {e}")
    row.addView(name_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    if file_size_bytes is not None:
        # MD3 labelSmall: 11sp
        size_tv = TextView(act)
        size_tv.setText(_format_file_size(file_size_bytes))
        size_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
        size_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        size_tv.setGravity(Gravity.CENTER_VERTICAL)
        row.addView(size_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

    return row


def _animate_card_transition(upload_card, selected_container):
    try:
        from android.animation import AnimatorSet, ObjectAnimator, Animator, ValueAnimator
        from android.view.animation import DecelerateInterpolator, AccelerateInterpolator, AccelerateDecelerateInterpolator
        from android.view import ViewGroup
        from java import dynamic_proxy

        dp = AndroidUtilities.dp

        # measure upload_card real height so we can collapse it smoothly
        upload_card.measure(
            ViewGroup.MeasureSpec.makeMeasureSpec(upload_card.getWidth(), ViewGroup.MeasureSpec.EXACTLY),
            ViewGroup.MeasureSpec.makeMeasureSpec(0, ViewGroup.MeasureSpec.UNSPECIFIED),
        )
        from_h = upload_card.getMeasuredHeight()

        # upload card: fade out — MD3 short duration
        out_alpha = ObjectAnimator.ofFloat(upload_card, "alpha", 1.0, 0.0)
        out_alpha.setDuration(150)
        out_alpha.setInterpolator(AccelerateInterpolator())

        # collapse upload_card height smoothly
        class _CollapseAnimator(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
            def onAnimationUpdate(self, anim):
                try:
                    h = int(float(str(anim.getAnimatedValue())) * from_h)
                    lp = upload_card.getLayoutParams()
                    lp.height = h
                    upload_card.setLayoutParams(lp)
                except Exception:
                    pass

        collapse = ValueAnimator.ofFloat(1.0, 0.0)
        collapse.setDuration(250)
        collapse.setStartDelay(60)
        collapse.setInterpolator(AccelerateDecelerateInterpolator())
        collapse.addUpdateListener(_CollapseAnimator())

        class _CollapseEnd(dynamic_proxy(Animator.AnimatorListener)):
            def onAnimationEnd(self, a, *args):
                try:
                    upload_card.setVisibility(View.GONE)
                    lp = upload_card.getLayoutParams()
                    lp.height = from_h
                    upload_card.setLayoutParams(lp)
                except Exception:
                    pass
            def onAnimationStart(self, a, *args): pass
            def onAnimationCancel(self, a, *args): pass
            def onAnimationRepeat(self, a, *args): pass

        collapse.addListener(_CollapseEnd())

        # MD3 standard: fade in + slide up 8dp (не 16dp), FastOutSlowIn ≈ DecelerateInterpolator
        in_alpha = ObjectAnimator.ofFloat(selected_container, "alpha", 0.0, 1.0)
        in_alpha.setDuration(200)
        in_alpha.setStartDelay(120)
        in_alpha.setInterpolator(DecelerateInterpolator())

        in_ty = ObjectAnimator.ofFloat(selected_container, "translationY", float(dp(8)), 0.0)
        in_ty.setDuration(250)
        in_ty.setStartDelay(100)
        in_ty.setInterpolator(DecelerateInterpolator(2.0))

        animators = [out_alpha, collapse, in_alpha, in_ty]

        full = AnimatorSet()
        full.playTogether(*animators)
        full.start()
    except Exception as e:
        log(f"suggest: _animate_card_transition error: {e}")
        try:
            upload_card.setVisibility(View.GONE)
        except Exception:
            pass


def _get_file_size(uri, ctx):
    try:
        cr = ctx.getContentResolver()
        cursor = cr.query(uri, None, None, None, None)
        if cursor:
            try:
                col = cursor.getColumnIndex("_size")
                if col >= 0 and cursor.moveToFirst():
                    val = cursor.getLong(col)
                    return int(val)
            finally:
                cursor.close()
    except Exception as e:
        log(f"suggest: _get_file_size error: {e}")
    return None


def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        kb = size_bytes / 1024.0
        return f"{kb:.1f} KB"
    mb = size_bytes / (1024.0 * 1024.0)
    return f"{mb:.2f} MB"


def _get_display_name(uri, ctx):
    try:
        cr = ctx.getContentResolver()
        cursor = cr.query(uri, None, None, None, None)
        if cursor:
            try:
                col = cursor.getColumnIndex("_display_name")
                if col >= 0 and cursor.moveToFirst():
                    return str(cursor.getString(col) or "")
            finally:
                cursor.close()
    except Exception as e:
        log(f"suggest: _get_display_name error: {e}")
    return str(uri)


_PICK_REQUEST_CODE = 7742
_PICK_EXTRA_REQUEST_CODE = 7743
_MAX_FILES = 10


def _make_add_another_card(act, card_height_px):
    dp = AndroidUtilities.dp

    # MD3 Filter Chip pill: filled tonal + outlined
    try:
        from android.graphics.drawable import GradientDrawable
        primary = Theme.getColor(Theme.key_featuredStickers_addButton)
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(100))
        bg.setColor(_to_color(0x18000000 | (primary & 0x00FFFFFF)))
        bg.setStroke(dp(1), _to_color(0x60000000 | (primary & 0x00FFFFFF)))
    except Exception as e:
        log(f"suggest: add_another bg error: {e}")
        bg = None

    from android.widget import FrameLayout as FL

    # outer FrameLayout fills full width for tap target, centers pill inside
    outer = FL(act)
    outer.setClickable(True)
    outer.setFocusable(True)

    pill = LinearLayout(act)
    pill.setOrientation(LinearLayout.HORIZONTAL)
    pill.setGravity(Gravity.CENTER)
    pill.setPadding(dp(16), dp(12), dp(16), dp(12))
    if bg:
        pill.setBackground(bg)

    icon_view = ImageView(act)
    icon_id = _resolve_icon("msg_addbot")
    if icon_id:
        icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
    icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    pill.addView(icon_view, LayoutHelper.createLinear(18, 18, Gravity.CENTER_VERTICAL, 0, 0, 6, 0))

    # MD3 labelMedium: 12sp medium
    label = TextView(act)
    label.setText(strings.suggest_add_another_file)
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    label.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
    label.setGravity(Gravity.CENTER_VERTICAL)
    try:
        label.setTypeface(AndroidUtilities.bold())
    except Exception:
        pass
    pill.addView(label, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

    pill_lp = FL.LayoutParams(-1, -2)
    pill_lp.gravity = Gravity.CENTER
    outer.addView(pill, pill_lp)

    _apply_ripple(pill, corner_dp=100)
    return outer, -2


def _hook_activity_result(plugin, act, request_codes, result_callback):
    from base_plugin import MethodHook

    try:
        cls = act.getClass()
        target_method = None
        while cls is not None:
            for m in cls.getDeclaredMethods():
                try:
                    if str(m.getName()) == "onActivityResult" and len(m.getParameterTypes()) == 3:
                        target_method = m
                        break
                except Exception:
                    pass
            if target_method:
                break
            try:
                cls = cls.getSuperclass()
            except Exception:
                break

        if not target_method:
            log("suggest: onActivityResult method not found")
            return None

        target_method.setAccessible(True)

        class _ActResHook(MethodHook):
            def after_hooked_method(self, param):
                try:
                    req = int(param.args[0])
                    res = int(param.args[1])
                    data = param.args[2]
                except Exception as e:
                    log(f"suggest: onActivityResult args error: {e}")
                    return
                if (req & 0xFFFF) not in request_codes:
                    return
                if res != -1 or not data:
                    return
                try:
                    uri = data.getData()
                except Exception as e:
                    log(f"suggest: getData error: {e}")
                    return
                if uri is None:
                    return
                import threading
                threading.Thread(target=result_callback, args=(uri, req & 0xFFFF), daemon=True).start()

        return plugin.hook_method(target_method, _ActResHook())
    except Exception as e:
        log(f"suggest: _hook_activity_result error: {e}")
        return None


def _hook_is_internal_uri(plugin, allowed_paths: set):
    from base_plugin import MethodHook
    from hook_utils import find_class
    try:
        cls = find_class("org.telegram.messenger.AndroidUtilities")

        class _InternalUriHook(MethodHook):
            def after_hooked_method(self, param):
                try:
                    # overload (Uri) has 1 arg; overload (int) also has 1 arg — check type
                    arg = param.args[0]
                    if arg is None or not hasattr(arg, "getPath"):
                        return
                    path = str(arg.getPath())
                    if path in allowed_paths:
                        log(f"suggest: isInternalUri override -> False for {path}")
                        param.setResult(False)
                except Exception as e:
                    log(f"suggest: _InternalUriHook error: {e}")

        hooks = plugin.hook_all_methods(cls, "isInternalUri", _InternalUriHook())
        log(f"suggest: hooked isInternalUri ({len(hooks)} overload(s))")
        return hooks
    except Exception as e:
        log(f"suggest: _hook_is_internal_uri error: {e}")
        return None


def _launch_file_picker(act, request_code):
    try:
        from android.content import Intent
        try:
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("*/*")
            try:
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            except Exception:
                pass
            act.startActivityForResult(intent, request_code)
            return
        except Exception as e:
            log(f"suggest: ACTION_OPEN_DOCUMENT failed, fallback: {e}")
        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType("*/*")
        try:
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        except Exception:
            pass
        act.startActivityForResult(intent, request_code)
    except Exception as e:
        log(f"suggest: _launch_file_picker error: {e}")




def _shake_view(view):
    try:
        from android.animation import ObjectAnimator, AnimatorSet
        from android.view.animation import CycleInterpolator
        shaker = ObjectAnimator.ofFloat(view, "translationX", 0.0, 14.0, -14.0, 10.0, -10.0, 6.0, -6.0, 0.0)
        shaker.setDuration(400)
        shaker.setInterpolator(CycleInterpolator(1.0))
        shaker.start()
    except Exception as e:
        log(f"suggest: _shake_view error: {e}")


def _hide_keyboard(act):
    try:
        from android.view.inputmethod import InputMethodManager
        imm = act.getSystemService("input_method")
        focused = act.getCurrentFocus()
        token = focused.getWindowToken() if focused is not None else act.getWindow().getDecorView().getWindowToken()
        imm.hideSoftInputFromWindow(token, 0)
    except Exception as e:
        log(f"suggest: _hide_keyboard error: {e}")


def _animate_reveal(view, delay_ms=0):
    # MD3 standard enter: fade + slide up 12dp, FastOutSlowIn easing
    try:
        from android.animation import AnimatorSet, ObjectAnimator
        from android.view.animation import DecelerateInterpolator
        view.setAlpha(0.0)
        view.setTranslationY(float(AndroidUtilities.dp(12)))
        a_alpha = ObjectAnimator.ofFloat(view, "alpha", 0.0, 1.0)
        a_alpha.setDuration(200)
        a_alpha.setInterpolator(DecelerateInterpolator())
        a_ty = ObjectAnimator.ofFloat(view, "translationY", float(AndroidUtilities.dp(12)), 0.0)
        a_ty.setDuration(250)
        a_ty.setInterpolator(DecelerateInterpolator(2.0))
        aset = AnimatorSet()
        aset.playTogether(a_alpha, a_ty)
        if delay_ms > 0:
            aset.setStartDelay(delay_ms)
        aset.start()
    except Exception as e:
        log(f"suggest: _animate_reveal error: {e}")
        try:
            view.setAlpha(1.0)
            view.setTranslationY(0.0)
        except Exception:
            pass


_chip_refs = {}


def _get_y(view):
    try:
        loc = [0, 0]
        view.getLocationOnScreen(loc)
        return loc[1]
    except Exception:
        return -1


def _make_md3_chip(act):
    # MD3 Filter Chip: outlined pill, unchecked by default
    try:
        from android.widget import LinearLayout as LL

        dp = AndroidUtilities.dp

        chip = LL(act)
        chip.setOrientation(LL.HORIZONTAL)
        chip.setGravity(Gravity.CENTER)
        chip.setPadding(dp(12), 0, dp(12), 0)
        chip.setClickable(True)
        chip.setFocusable(True)
        # state: False = unchecked
        chip.setTag(False)

        check_icon = ImageView(act)
        check_id = _resolve_icon("msg_select")
        if check_id:
            check_icon.setImageResource(check_id)
        check_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        check_icon.setVisibility(View.GONE)
        chip.addView(check_icon, LayoutHelper.createLinear(16, 16, Gravity.CENTER_VERTICAL, 0, 0, 4, 0))

        label = TextView(act)
        label.setText("No")
        label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        label.setGravity(Gravity.CENTER_VERTICAL)
        chip.addView(label, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

        # store child refs by chip identity since Java objects don't support custom attributes
        _chip_refs[id(chip)] = (check_icon, label)

        _update_md3_chip(chip, False)
        return chip
    except Exception as e:
        log(f"suggest: _make_md3_chip error: {e}")
        return None


def _to_color(value):
    # clamp to signed int32 range that Android expects
    v = int(value) & 0xFFFFFFFF
    if v >= 0x80000000:
        v -= 0x100000000
    return v


def _update_md3_chip(chip, checked: bool):
    # updates chip visual state: bg, text color, icon visibility
    try:
        from android.graphics.drawable import GradientDrawable
        dp = AndroidUtilities.dp
        primary = Theme.getColor(Theme.key_featuredStickers_addButton)
        on_surface = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        surface = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)

        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(100))

        refs = _chip_refs.get(id(chip))
        check_icon = refs[0] if refs else None
        label = refs[1] if refs else None

        if checked:
            bg.setColor(_to_color(0x28000000 | (primary & 0x00FFFFFF)))
            bg.setStroke(dp(1), _to_color(0x99000000 | (primary & 0x00FFFFFF)))
            if check_icon:
                check_icon.setColorFilter(primary)
                check_icon.setVisibility(View.VISIBLE)
            if label:
                label.setText("Yes")
                label.setTextColor(primary)
        else:
            bg.setColor(0x00000000)
            bg.setStroke(dp(1), _to_color(0x40000000 | (surface & 0x00FFFFFF)))
            if check_icon:
                check_icon.setVisibility(View.GONE)
            if label:
                label.setText("No")
                label.setTextColor(on_surface)

        chip.setBackground(bg)
        _apply_ripple(chip, corner_dp=100)
    except Exception as e:
        log(f"suggest: _update_md3_chip error: {e}")


def _make_outlined_et_bg():
    # MD3 outlined text field border: corner 8dp, stroke 1dp on-surface-variant
    try:
        from android.graphics.drawable import GradientDrawable
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(8))
        bg.setColor(0x00000000)
        bg.setStroke(
            AndroidUtilities.dp(1),
            _to_color(0x40000000 | (Theme.getColor(Theme.key_windowBackgroundWhiteGrayText) & 0x00FFFFFF))
        )
        return bg
    except Exception as e:
        log(f"suggest: _make_outlined_et_bg error: {e}")
        return None


def _make_section_card(act, radius_dp=12):
    try:
        from android.graphics.drawable import GradientDrawable
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(AndroidUtilities.dp(radius_dp))
        bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        return bg
    except Exception as e:
        log(f"suggest: _make_section_card error: {e}")
        return None


def _make_social_input_row(act, hint_text, on_delete):
    dp = AndroidUtilities.dp
    from android.widget import EditText as AEditText

    bg = _make_outlined_et_bg()

    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setPadding(dp(12), dp(10), dp(8), dp(10))
    if bg:
        row.setBackground(bg)

    et = AEditText(act)
    et.setHint(hint_text)
    et.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    et.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
    et.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    et.setBackground(None)
    et.setSingleLine(True)
    try:
        from android.text import InputType
        et.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI)
    except Exception:
        pass
    row.addView(et, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    del_btn = ImageView(act)
    del_icon = _resolve_icon("msg_close")
    if del_icon:
        del_btn.setImageResource(del_icon)
        try:
            del_btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
    del_btn.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    del_btn.setClickable(True)
    del_btn.setFocusable(True)
    del_btn.setOnClickListener(OnClickListener(on_delete))
    row.addView(del_btn, LayoutHelper.createLinear(32, 32, Gravity.CENTER_VERTICAL, 4, 0, 0, 0))

    return row, et


import json as _json
import os as _os

import re as _re

_META_DUNDER_RE = _re.compile(
    r"^__(\w+)__\s*=\s*(.+?)(?=\n__\w+__\s*=|\Z)",
    _re.MULTILINE | _re.DOTALL,
)
_META_PLAIN_RE = _re.compile(
    r"^(\w+)\s*=\s*(.+?)(?=\n\w+\s*=|\Z)",
    _re.MULTILINE | _re.DOTALL,
)
_META_WANTED = {"id", "version", "name", "author", "description"}


def _meta_unescape(s: str) -> str:
    return s.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")


def _meta_parse_value(raw: str):
    # returns parsed string value or None if unparseable
    if not raw:
        return None
    if _re.match(r'^f["\']', raw):
        return None
    for q in ('"""', "'''"):
        if raw.startswith(q):
            end = raw.find(q, len(q))
            inner = raw[len(q):end] if end != -1 else raw[len(q):]
            return _meta_unescape(inner)
    for q in ('"', "'"):
        if raw.startswith(q):
            result = []
            i = 1
            while i < len(raw):
                ch = raw[i]
                if ch == "\\" and i + 1 < len(raw):
                    nxt = raw[i + 1]
                    result.append({"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}.get(nxt, nxt))
                    i += 2
                elif ch == q:
                    break
                else:
                    result.append(ch)
                    i += 1
            return "".join(result)
    return None


def _parse_plugin_meta(path: str) -> dict:
    # reads __id__, __version__ etc from .plugin or .py file
    meta = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for m in _META_DUNDER_RE.finditer(content):
            key = m.group(1)
            if key not in _META_WANTED or key in meta:
                continue
            val = _meta_parse_value(m.group(2).strip())
            if val is not None:
                meta[key] = val
        for m in _META_PLAIN_RE.finditer(content):
            key = m.group(1)
            if key not in _META_WANTED or key in meta:
                continue
            raw = m.group(2).strip()
            if not raw or raw[0] not in ('"', "'"):
                continue
            val = _meta_parse_value(raw)
            if val is not None:
                meta[key] = val
    except Exception as e:
        log(f"suggest: _parse_plugin_meta error: {e}")
    return meta


def _copy_uri_to_temp(uri, act, display_name: str = "") -> str:
    # copies content uri to a temp file preserving original extension, returns path or ""
    import tempfile, os
    try:
        # derive suffix from display_name to avoid sending a .tmp file
        suffix = ".tmp"
        if display_name:
            dot_idx = display_name.rfind(".")
            if dot_idx >= 0:
                suffix = display_name[dot_idx:]
        log(f"suggest: _copy_uri_to_temp suffix={suffix} name={display_name!r}")

        cr = act.getContentResolver()
        stream = cr.openInputStream(uri)
        if stream is None:
            log("suggest: _copy_uri_to_temp openInputStream returned None")
            return ""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        buf = bytearray(8192)
        total = 0
        while True:
            n = stream.read(buf)
            if n < 0:
                break
            tmp.write(bytes(buf[:n]))
            total += n
        tmp.close()
        stream.close()
        log(f"suggest: _copy_uri_to_temp wrote {total} bytes -> {tmp.name}")
        return tmp.name
    except Exception as e:
        log(f"suggest: _copy_uri_to_temp error: {e}")
        return ""


def _parse_eaf_description(eaf_path: str) -> str:
    # reads description from .eaf archive via refmap.yml or refmap.json -> metainfo field
    import zipfile, os, json as _json
    try:
        with zipfile.ZipFile(eaf_path, "r") as zf:
            names = zf.namelist()

            # find refmap: prefer .yml, fallback to .json
            refmap_data = None
            refmap_fmt = None
            for candidate, fmt in (("refmap.yml", "yaml"), ("refmap.yaml", "yaml"), ("refmap.json", "json")):
                if candidate in names:
                    raw = zf.read(candidate).decode("utf-8", errors="replace")
                    if fmt == "yaml":
                        # minimal yaml key: value parser, no external deps
                        refmap_data = {}
                        for line in raw.splitlines():
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if ":" in line:
                                k, _, v = line.partition(":")
                                refmap_data[k.strip()] = v.strip().strip('"').strip("'")
                    else:
                        refmap_data = _json.loads(raw)
                    refmap_fmt = fmt
                    break

            if not refmap_data:
                log("suggest: _parse_eaf_description: no refmap found in archive")
                return ""

            metainfo_path = refmap_data.get("metainfo", "")
            if not metainfo_path:
                log("suggest: _parse_eaf_description: metainfo key missing in refmap")
                return ""

            if metainfo_path not in names:
                log(f"suggest: _parse_eaf_description: metainfo file not found: {metainfo_path}")
                return ""

            meta_raw = zf.read(metainfo_path).decode("utf-8", errors="replace")
            meta_ext = metainfo_path.rsplit(".", 1)[-1].lower()

            if meta_ext == "json":
                meta = _json.loads(meta_raw)
                return str(meta.get("description", ""))

            # yaml metainfo: parse description field
            for line in meta_raw.splitlines():
                line = line.strip()
                if line.startswith("description"):
                    _, _, v = line.partition(":")
                    v = v.strip().strip('"').strip("'")
                    # handle yaml template strings like "{plugin_description} ..."
                    if v.startswith("{"):
                        end = v.find("}")
                        if end != -1:
                            v = v[end + 1:].strip()
                    return v
    except Exception as e:
        log(f"suggest: _parse_eaf_description error: {e}")
    return ""


def _try_parse_plugin_meta(uri, act, suggest_config, on_description=None, on_update_found=None):
    import threading
    def _worker():
        try:
            name = _get_display_name(uri, act)
            ext = (name or "").rsplit(".", 1)[-1].lower()
            if ext not in ("eaf", "plugin", "py"):
                return

            tmp_path = _copy_uri_to_temp(uri, act, name or "")
            if not tmp_path:
                return

            import os
            try:
                if ext == "eaf":
                    description = _parse_eaf_description(tmp_path)
                    if description and on_description is not None:
                        try:
                            on_description(description)
                        except Exception as e:
                            log(f"suggest: on_description callback error: {e}")
                    return
                meta = _parse_plugin_meta(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

            description = meta.get("description", "")
            if description and on_description is not None:
                try:
                    on_description(description)
                except Exception as e:
                    log(f"suggest: on_description callback error: {e}")

            plugin_id = meta.get("id")
            if not plugin_id:
                return

            # look up plugin in repo
            rm_rid = None
            if isinstance(suggest_config, dict):
                pass
            repometa = None
            try:
                from ...utils.paths import getRepoCachePath
                import json as _json

                # suggest_config may carry rm_rid indirectly; scan all caches
                # find by checking suggest_config origin — passed as is, so use paths util
                cache_dir_path = getRepoCachePath("")
                import os as _os
                cache_dir = _os.path.dirname(cache_dir_path)
                for fname in (_os.listdir(cache_dir) if _os.path.isdir(cache_dir) else []):
                    if not fname.endswith(".json"):
                        continue
                    fpath = _os.path.join(cache_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            cached = _json.load(f)
                        repomap = cached.get("repomap", {})
                        plugins_url = repomap.get("plugins", "")
                        if not plugins_url:
                            continue
                        import requests as _req
                        r = _req.get(plugins_url, timeout=10)
                        if r.status_code != 200:
                            continue
                        data = r.json()
                        plugins = data.get("plugins", {})
                        repo_plugin = None
                        if isinstance(plugins, dict):
                            repo_plugin = plugins.get(plugin_id)
                        elif isinstance(plugins, list):
                            for item in plugins:
                                if isinstance(item, dict) and item.get("id") == plugin_id:
                                    repo_plugin = item
                                    break
                        if repo_plugin is not None:
                            repo_version = repo_plugin.get("version", "?")
                            meta_version = meta.get("version", "?")
                            log(f"suggest: updated {repo_version} -> {meta_version}")
                            if on_update_found is not None:
                                try:
                                    on_update_found(repo_version, meta_version)
                                except Exception as e:
                                    log(f"suggest: on_update_found callback error: {e}")
                            return
                    except Exception:
                        continue
            except Exception as e:
                log(f"suggest: meta repo lookup error: {e}")
        except Exception as e:
            log(f"suggest: _try_parse_plugin_meta worker error: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def _fill_description(et, text: str):
    try:
        et.setText(text)
        et.setSelection(len(text))
    except Exception as e:
        log(f"suggest: _fill_description error: {e}")


def _load_forked_plugins(repo_data: dict) -> list:
    # loads plugin list from repo cache; returns list of plugin dicts
    try:
        import json as _json, os as _os, requests as _req
        repometa = repo_data.get("repometa") if isinstance(repo_data, dict) else None
        rm_rid = repometa.get("rm_rid") if isinstance(repometa, dict) else None
        if not rm_rid:
            return []
        from ...utils.paths import getRepoCachePath
        path = getRepoCachePath(rm_rid)
        if not _os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            cached = _json.load(f)
        plugins_url = cached.get("repomap", {}).get("plugins", "")
        if not plugins_url:
            return []
        r = _req.get(plugins_url, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        plugins_raw = data.get("plugins", [])
        plugins = []
        if isinstance(plugins_raw, dict):
            for pid, info in plugins_raw.items():
                if isinstance(info, dict):
                    plugins.append({"id": pid, **info})
        elif isinstance(plugins_raw, list):
            for item in plugins_raw:
                if isinstance(item, dict) and item.get("id"):
                    plugins.append(item)
        return plugins
    except Exception as e:
        log(f"suggest: _load_forked_plugins error: {e}")
        return []


def _search_plugins(plugins: list, query: str) -> list:
    # instant search: filter by name/id/author matching query, max 5 results
    q = query.strip().lower()
    if not q or not plugins:
        return []
    results = []
    for p in plugins:
        name = (p.get("name") or p.get("id") or "").lower()
        pid = (p.get("id") or "").lower()
        author = (p.get("author") or "").lower()
        if q in name or q in pid or q in author:
            results.append(p)
        if len(results) >= 5:
            break
    return results


def _make_forked_not_found_popup(act):
    # builds a popup with single "Plugin not found" row
    from android.widget import LinearLayout as LL, TextView
    from android.view import Gravity
    from android.util import TypedValue
    from org.telegram.messenger import AndroidUtilities

    dp = AndroidUtilities.dp

    try:
        from android.graphics.drawable import GradientDrawable
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(16))
        bg.setColor(Theme.getColor(Theme.key_dialogBackground))
    except Exception as e:
        log(f"suggest: not_found popup bg error: {e}")
        bg = None

    popup = LL(act)
    popup.setOrientation(LL.VERTICAL)
    popup.setPadding(dp(16), dp(12), dp(16), dp(12))
    popup.setElevation(float(dp(8)))
    popup.setClickable(True)
    popup.setFocusable(True)
    if bg:
        popup.setBackground(bg)
    else:
        popup.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))

    label = TextView(act)
    label.setText(strings.suggest_forked_not_found)
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    label.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    label.setGravity(Gravity.CENTER)
    popup.addView(label, LL.LayoutParams(-1, -2))

    return popup


def _make_forked_popup(act, plugins: list, on_select):
    # builds a popup panel with up to 5 plugin rows
    # returns the popup view (FrameLayout)
    from android.widget import LinearLayout as LL, FrameLayout as FL, TextView, ImageView
    from android.view import Gravity, View
    from android.util import TypedValue
    from org.telegram.ui.Components import BackupImageView, LayoutHelper
    from org.telegram.messenger import AndroidUtilities, MediaDataController

    dp = AndroidUtilities.dp

    try:
        from android.graphics.drawable import GradientDrawable
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(16))
        bg.setColor(Theme.getColor(Theme.key_dialogBackground))
        bg.setElevation(float(dp(8))) if hasattr(bg, 'setElevation') else None
    except Exception as e:
        log(f"suggest: popup bg error: {e}")
        bg = None

    popup = LL(act)
    popup.setOrientation(LL.VERTICAL)
    popup.setPadding(dp(8), dp(8), dp(8), dp(8))
    popup.setElevation(float(dp(8)))
    popup.setClickable(True)
    popup.setFocusable(True)
    if bg:
        popup.setBackground(bg)
    else:
        popup.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))

    for i, p in enumerate(plugins):
        row = LL(act)
        row.setOrientation(LL.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setPadding(dp(12), dp(10), dp(12), dp(10))
        row.setClickable(True)
        row.setFocusable(True)

        # icon
        icon_str = str(p.get("icon") or "")
        icon_size_dp = 36
        if icon_str and icon_str != "Unknown" and "/" in icon_str:
            try:
                from org.telegram.messenger import ImageLocation
                icon_view = BackupImageView(act)
                icon_view.setRoundRadius(dp(8))
                try:
                    icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
                except Exception:
                    pass
                icon_size_px = dp(icon_size_dp)
                icon_lp = LL.LayoutParams(icon_size_px, icon_size_px)
                icon_lp.rightMargin = dp(12)
                row.addView(icon_view, icon_lp)

                def _try_load(iv=icon_view, s=icon_str):
                    try:
                        pack_name, index_str = s.split("/", 1)
                        idx = int(index_str)
                        mdc = MediaDataController.getInstance(0)
                        ss = None
                        try:
                            ss = mdc.getStickerSetByName(pack_name)
                        except Exception:
                            pass
                        if not ss:
                            try:
                                ss = mdc.getStickerSetByEmojiOrName(pack_name)
                            except Exception:
                                pass
                        if ss and getattr(ss, "documents", None) and ss.documents.size() > idx:
                            doc = ss.documents.get(idx)
                            iv.setImage(
                                ImageLocation.getForDocument(doc),
                                f"{icon_size_dp}_{icon_size_dp}",
                                None, None, 0, 1
                            )
                            return True
                        return False
                    except Exception:
                        return False

                if not _try_load():
                    try:
                        pack_name = icon_str.split("/", 1)[0]
                        MediaDataController.getInstance(0).loadStickersByEmojiOrName(pack_name, False, False)
                    except Exception:
                        pass
                    import threading
                    def _retry(iv=icon_view, loader=_try_load):
                        import time
                        for d in (0.5, 1.0, 2.0):
                            time.sleep(d)
                            try:
                                run_on_ui_thread(loader)
                                return
                            except Exception:
                                pass
                    threading.Thread(target=_retry, daemon=True).start()
            except Exception as e:
                log(f"suggest: popup icon error: {e}")
                _add_stub_icon(act, row, icon_size_dp, dp)
        else:
            _add_stub_icon(act, row, icon_size_dp, dp)

        # text column
        col = LL(act)
        col.setOrientation(LL.VERTICAL)

        name_tv = TextView(act)
        display_name = str(p.get("name") or p.get("id") or "Unknown")
        name_tv.setText(display_name)
        name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        name_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
        name_tv.setSingleLine(True)
        try:
            name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        col.addView(name_tv, LayoutHelper.createLinear(-2, -2))

        version_text = str(p.get("version") or "").strip()
        author_text = str(p.get("author") or "").strip()
        if version_text or author_text:
            sub_tv = TextView(act)
            if version_text and author_text:
                try:
                    from com.exteragram.messenger.utils.text import LocaleUtils
                    sub_tv.setText(LocaleUtils.fullyFormatText(f"{author_text} • v{version_text}"))
                except Exception:
                    sub_tv.setText(f"{author_text} • v{version_text}")
            elif author_text:
                try:
                    from com.exteragram.messenger.utils.text import LocaleUtils
                    sub_tv.setText(LocaleUtils.fullyFormatText(author_text))
                except Exception:
                    sub_tv.setText(author_text)
            else:
                sub_tv.setText(f"v{version_text}")
            sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
            sub_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            try:
                from android.text.method import LinkMovementMethod
                sub_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                sub_tv.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                pass
            sub_tv.setSingleLine(True)
            lp_sub = LL.LayoutParams(-2, -2)
            lp_sub.topMargin = dp(2)
            col.addView(sub_tv, lp_sub)

        row.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        def _make_click(plugin=p):
            def _on_click(v):
                on_select(plugin)
            return _on_click

        row.setOnClickListener(OnClickListener(_make_click()))
        _apply_ripple(row, corner_dp=8)

        lp_row = LL.LayoutParams(-1, -2)
        if i > 0:
            lp_row.topMargin = dp(2)
        popup.addView(row, lp_row)

    return popup


def _add_stub_icon(act, row, size_dp, dp):
    # plain ImageView fallback when icon_str absent or invalid
    try:
        from android.widget import ImageView, LinearLayout as LL
        from android.graphics import PorterDuffColorFilter, PorterDuff
        from hook_utils import find_class
        stub = ImageView(act)
        stub.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
        p_pad = dp(8)
        stub.setPadding(p_pad, p_pad, p_pad, p_pad)
        stub.setBackground(Theme.createCircleDrawable(
            dp(size_dp),
            Theme.getColor(Theme.key_featuredStickers_addButton)
        ))
        try:
            R = find_class("org.telegram.messenger.R")
            stub.setImageResource(int(R.drawable.plugins_filled))
            stub.setColorFilter(PorterDuffColorFilter(
                Theme.getColor(Theme.key_featuredStickers_buttonText),
                PorterDuff.Mode.SRC_IN
            ))
        except Exception:
            pass
        icon_lp = LL.LayoutParams(dp(size_dp), dp(size_dp))
        icon_lp.rightMargin = dp(10)
        row.addView(stub, icon_lp)
    except Exception as e:
        log(f"suggest: _add_stub_icon error: {e}")


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
        log(f"suggest: _register_back_cb error: {e}")
        return None


def _unregister_back_cb(cb):
    try:
        if cb is not None:
            cb.remove()
    except Exception as e:
        log(f"suggest: _unregister_back_cb error: {e}")


def _register_keyboard_back(act, et):
    # clears focus automatically when keyboard is dismissed (e.g. via back gesture)
    try:
        from android.view import ViewTreeObserver as _VTO
        from java import dynamic_proxy

        root = act.getWindow().getDecorView()
        _VtoProxy = dynamic_proxy(_VTO.OnGlobalLayoutListener)

        class _KeyboardWatcher(_VtoProxy):
            def __init__(self2):
                super().__init__()
                self2._was_open = [False]

            def onGlobalLayout(self2):
                try:
                    if not et.hasFocus():
                        return
                    r = __import__("android.graphics", fromlist=["Rect"]).Rect()
                    root.getWindowVisibleDisplayFrame(r)
                    screen_h = root.getRootView().getHeight()
                    keyboard_h = screen_h - r.bottom
                    is_open = keyboard_h > screen_h * 0.15
                    if self2._was_open[0] and not is_open:
                        et.clearFocus()
                    self2._was_open[0] = is_open
                except Exception as e:
                    log(f"suggest: keyboard watcher error: {e}")

        watcher = _KeyboardWatcher()
        root.getViewTreeObserver().addOnGlobalLayoutListener(watcher)
    except Exception as e:
        log(f"suggest: _register_keyboard_back setup error: {e}")


def _get_draft_path(rm_rid: str) -> str:
    import os
    from org.telegram.messenger import ApplicationLoader
    files_dir = ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath()
    draft_dir = os.path.join(files_dir, "packit", ".cache", "suggest_drafts")
    os.makedirs(draft_dir, exist_ok=True)
    safe = rm_rid.replace("/", "_").replace("\\", "_") if rm_rid else "default"
    return os.path.join(draft_dir, f"{safe}.json")


def _get_draft_files_dir(rm_rid: str) -> str:
    import os
    from org.telegram.messenger import ApplicationLoader
    files_dir = ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath()
    safe = rm_rid.replace("/", "_").replace("\\", "_") if rm_rid else "default"
    d = os.path.join(files_dir, "packit", ".cache", "suggest_drafts", "files", safe)
    os.makedirs(d, exist_ok=True)
    return d


def _clear_draft_files(rm_rid: str):
    import os, shutil
    try:
        d = _get_draft_files_dir(rm_rid)
        shutil.rmtree(d, ignore_errors=True)
    except Exception as e:
        log(f"suggest: _clear_draft_files error: {e}")


def _save_draft(rm_rid: str, data: dict):
    try:
        path = _get_draft_path(rm_rid)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_json.dumps(data, ensure_ascii=False))
    except Exception as e:
        log(f"suggest: _save_draft error: {e}")


def _load_draft(rm_rid: str) -> dict:
    try:
        path = _get_draft_path(rm_rid)
        with open(path, "r", encoding="utf-8") as f:
            return _json.loads(f.read())
    except Exception as e:
        log(f"suggest: _load_draft error: {e}")
    return {}


def _clear_draft(rm_rid: str):
    try:
        path = _get_draft_path(rm_rid)
        if _os.path.isfile(path):
            _os.unlink(path)
    except Exception as e:
        log(f"suggest: _clear_draft error: {e}")
    _clear_draft_files(rm_rid)


def _has_draft(rm_rid: str) -> bool:
    try:
        path = _get_draft_path(rm_rid)
        result = _os.path.isfile(path)
        log(f"suggest: _has_draft rm_rid={rm_rid!r} path={path} exists={result}")
        return result
    except Exception as e:
        log(f"suggest: _has_draft error: {e}")
        return False


def _copy_uri_to_draft_file(uri, act, rm_rid: str, slot: str, display_name: str = "") -> str:
    # copies uri into suggest_drafts/files/{rm_rid}/{slot}/{original_name}, returns path or ""
    import os
    try:
        dest_dir = os.path.join(_get_draft_files_dir(rm_rid), slot)
        # clear previous file for this slot
        if os.path.isdir(dest_dir):
            import shutil
            shutil.rmtree(dest_dir, ignore_errors=True)
        os.makedirs(dest_dir, exist_ok=True)
        file_name = display_name if display_name else f"{slot}.tmp"
        dest = os.path.join(dest_dir, file_name)
        cr = act.getContentResolver()
        stream = cr.openInputStream(uri)
        if stream is None:
            return ""
        buf = bytearray(8192)
        with open(dest, "wb") as out:
            while True:
                n = stream.read(buf)
                if n < 0:
                    break
                out.write(bytes(buf[:n]))
        stream.close()
        log(f"suggest: draft file saved slot={slot} name={file_name} -> {dest}")
        return dest
    except Exception as e:
        log(f"suggest: _copy_uri_to_draft_file error: {e}")
        return ""


class SuggestFragment(dynamic_proxy(UniversalFragment.UniversalFragmentDelegate)):

    def __init__(self, repo_data: dict, plugin):
        super().__init__()
        self.content_view = None
        self._fragment_ref = [None]
        self._repo_data = repo_data
        self._plugin = plugin
        self._selected_uri = None
        self._selected_name = None
        self._selected_size = None
        self._extra_uris = []
        self._upload_card_ref = [None]
        self._selected_card_container_ref = [None]
        self._add_another_btn_ref = [None]
        self._rules_tv_ref = [None]
        self._picker_hook_ref = None
        self._suggest_config = None
        self._fields_section_ref = [None]
        self._desc_edit_ref = [None]
        self._social_links_container_ref = [None]
        self._social_inputs = []
        self._submit_btn_ref = None
        self._submit_wrapper_ref = [None]
        self._scroll_ref = [None]
        self._submit_lbl_ref = [None]
        self._pending_description = [None]
        self._forked_switch_ref = [None]
        self._forked_search_ref = [None]
        self._forked_search_wrap_ref = [None]
        self._forked_search_container_ref = [None]
        self._forked_popup_ref = [None]
        self._forked_plugins_cache = [None]
        self._forked_selected_plugin = [None]
        self._forked_selected_card_ref = [None]
        self._back_cb_ref = [None]
        self._changelog_edit_ref = [None]
        self._changelog_card_ref = [None]
        self._pending_versions = [None]
        self._note_edit_ref = [None]
        self._rm_rid = None
        self._pending_draft = None
        self._draft_main_path = None
        self._draft_extra_paths = []
        self._submitted = False

    def onFragmentCreate(self, *_):
        try:
            rm_rid = None
            repometa = self._repo_data.get("repometa") if isinstance(self._repo_data, dict) else None
            if isinstance(repometa, dict):
                rm_rid = repometa.get("rm_rid")
            self._rm_rid = rm_rid or "default"
            if rm_rid:
                import json, os
                from ...utils.paths import getRepoCachePath
                path = getRepoCachePath(rm_rid)
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sp = data.get("suggest_plugins")
                    if isinstance(sp, dict):
                        self._suggest_config = sp
                        log(f"suggest: loaded suggest_plugins for {rm_rid}")
                    else:
                        log(f"suggest: suggest_plugins missing in cache for {rm_rid}")
                else:
                    log(f"suggest: cache file not found for {rm_rid}")
            else:
                sp = self._repo_data.get("suggest_plugins") if isinstance(self._repo_data, dict) else None
                if isinstance(sp, dict):
                    self._suggest_config = sp
        except Exception as e:
            log(f"suggest: onFragmentCreate load error: {e}")

    def onFragmentDestroy(self, *_):
        # save form state so it can be restored on next open
        if self._submitted:
            log("suggest: onFragmentDestroy skipping draft save (already submitted)")
        else:
            self._save_current_draft()
        try:
            if self._picker_hook_ref is not None and self._plugin is not None:
                try:
                    self._plugin.unhook_method(self._picker_hook_ref)
                except Exception as e:
                    log(f"suggest: unhook error: {e}")
                self._picker_hook_ref = None
        except Exception:
            pass
        try:
            if self.content_view is not None:
                parent = self.content_view.getParent()
                if parent is not None:
                    parent.removeView(self.content_view)
                self.content_view = None
        except Exception as e:
            log(f"suggest: onFragmentDestroy removeView error: {e}")
        self._suggest_config = None
        self._extra_uris = []
        self._add_another_btn_ref[0] = None
        self._fields_section_ref[0] = None
        self._desc_edit_ref[0] = None
        self._social_links_container_ref[0] = None
        self._social_inputs = []
        try:
            self._dismiss_forked_popup()
        except Exception:
            pass
        self._forked_plugins_cache[0] = None
        self._forked_selected_plugin[0] = None
        self._forked_selected_card_ref[0] = None
        try:
            _unregister_back_cb(self._back_cb_ref[0])
        except Exception:
            pass
        self._back_cb_ref[0] = None
        self._changelog_edit_ref[0] = None
        self._changelog_card_ref[0] = None
        self._pending_versions[0] = None
        self._note_edit_ref[0] = None

    def getTitle(self):
        return strings.suggest_title

    def onBackPressed(self):
        return False

    def afterCreateView(self, v):
        return None

    def fillItems(self, items, adapter):
        pass

    def onClick(self, item, view, pos, x, y):
        pass

    def onLongClick(self, item, view, pos, x, y):
        return False

    def onMenuItemClick(self, mid):
        if mid == -1:
            try:
                frag = self._fragment_ref[0]
                if frag:
                    frag.finishFragment()
                else:
                    fragment = get_last_fragment()
                    if fragment:
                        fragment.finishFragment()
            except Exception as e:
                log(f"suggest: failed to finish fragment: {e}")

    def _on_file_picked(self, uri, request_code):
        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            return
        name = _get_display_name(uri, act)
        size = _get_file_size(uri, act)

        is_extra = request_code == _PICK_EXTRA_REQUEST_CODE

        if not is_extra:
            # first file must be a .eaf or .plugin
            ext = (name or "").rsplit(".", 1)[-1].lower()
            if ext not in ("eaf", "plugin"):
                log(f"suggest: first file ignored, expected .eaf/.plugin got .{ext}")
                def _show_ext_error():
                    try:
                        from org.telegram.ui.Components import BulletinFactory
                        decor = act.getWindow().getDecorView()
                        BulletinFactory.of(decor, None).createErrorBulletin(
                            "The first file should be .eaf/.plugin"
                        ).show()
                    except Exception as e:
                        log(f"suggest: error bulletin error: {e}")
                run_on_ui_thread(_show_ext_error)
                return

            self_ref_desc = self

            def _on_description(desc):
                self_ref_desc._pending_description[0] = desc
                et = self_ref_desc._desc_edit_ref[0]
                if et is not None:
                    run_on_ui_thread(lambda: _fill_description(et, desc))

            def _on_update_found(repo_ver, meta_ver):
                sp = self_ref_desc._suggest_config
                allow_changelog = False
                if isinstance(sp, dict):
                    raw_cl = sp.get("settings", {}).get("allow_changelog", 0)
                    try:
                        allow_changelog = bool(int(raw_cl))
                    except (TypeError, ValueError):
                        allow_changelog = bool(raw_cl)
                if not allow_changelog:
                    return
                self_ref_desc._pending_versions[0] = (repo_ver, meta_ver)
                run_on_ui_thread(lambda: self_ref_desc._show_changelog_card(frag.getParentActivity() if get_last_fragment() else None, repo_ver, meta_ver))

            self._selected_uri = uri
            self._selected_name = name
            self._selected_size = size
            _try_parse_plugin_meta(uri, act, self._suggest_config, on_description=_on_description, on_update_found=_on_update_found)

            # save main file to draft dir in background
            self_ref_file = self
            import threading
            def _save_main_file():
                path = _copy_uri_to_draft_file(uri, act, self_ref_file._rm_rid, "main", name or "")
                if path:
                    self_ref_file._draft_main_path = path
                    self_ref_file._save_current_draft()
            threading.Thread(target=_save_main_file, daemon=True).start()
        else:
            self._extra_uris.append((uri, name, size))

            # save extra file to draft dir in background
            self_ref_extra = self
            extra_idx = len(self._extra_uris) - 1
            import threading
            def _save_extra_file(idx=extra_idx):
                path = _copy_uri_to_draft_file(uri, act, self_ref_extra._rm_rid, f"extra_{idx}", name or "")
                if path:
                    while len(self_ref_extra._draft_extra_paths) <= idx:
                        self_ref_extra._draft_extra_paths.append(None)
                    self_ref_extra._draft_extra_paths[idx] = path
                    self_ref_extra._save_current_draft()
            threading.Thread(target=_save_extra_file, daemon=True).start()

        def _update_ui():
            try:
                container = self._selected_card_container_ref[0]
                upload_card = self._upload_card_ref[0]
                if container is None or upload_card is None:
                    return

                if not is_extra:
                    # first file: rebuild container, animate upload_card away
                    selected = _make_selected_file_card(act, name, size)
                    container.removeAllViews()
                    container.addView(selected, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))
                    container.setAlpha(0.0)
                    container.setTranslationY(float(AndroidUtilities.dp(24)))
                    container.setVisibility(View.VISIBLE)
                    _animate_card_transition(upload_card, container)

                    # show submit button sliding up from bottom
                    try:
                        self._show_submit_btn(act)
                    except Exception as e:
                        log(f"suggest: _show_submit_btn error: {e}")

                    # delay so button appears after the transition animation (max ~380ms) finishes
                    self_ref2 = self
                    import threading
                    def _delayed_add_btn():
                        import time
                        time.sleep(0.42)
                        run_on_ui_thread(lambda: self_ref2._refresh_add_another_btn(act, container))
                    threading.Thread(target=_delayed_add_btn, daemon=True).start()

                    # show description + socials after file selection
                    self._show_fields_section(act)
                else:
                    # extra file: animate via height expand so rules_tv doesn't jump
                    selected = _make_selected_file_card(act, name, size)
                    btn = self._add_another_btn_ref[0]

                    if btn is not None:
                        idx = container.indexOfChild(btn)
                        insert_idx = idx if idx >= 0 else -1
                    else:
                        insert_idx = -1

                    # add with height=0 so layout doesn't shift yet
                    lp_selected = LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0)
                    selected.setAlpha(0.0)
                    if insert_idx >= 0:
                        container.addView(selected, insert_idx, lp_selected)
                    else:
                        container.addView(selected, lp_selected)

                    try:
                        from android.animation import AnimatorSet, ObjectAnimator, Animator, ValueAnimator
                        from android.view.animation import DecelerateInterpolator, AccelerateInterpolator
                        from android.view import ViewGroup
                        from java import dynamic_proxy

                        # measure real height first
                        selected.measure(
                            ViewGroup.MeasureSpec.makeMeasureSpec(container.getWidth(), ViewGroup.MeasureSpec.EXACTLY),
                            ViewGroup.MeasureSpec.makeMeasureSpec(0, ViewGroup.MeasureSpec.UNSPECIFIED),
                        )
                        target_h = selected.getMeasuredHeight()

                        lp_s = selected.getLayoutParams()
                        lp_s.height = 0
                        selected.setLayoutParams(lp_s)

                        class _SelExpand(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                            def onAnimationUpdate(self2, anim):
                                try:
                                    h = int(float(str(anim.getAnimatedValue())) * target_h)
                                    p = selected.getLayoutParams()
                                    p.height = h
                                    selected.setLayoutParams(p)
                                except Exception:
                                    pass

                        class _SelExpandEnd(dynamic_proxy(Animator.AnimatorListener)):
                            def onAnimationEnd(self2, a, *args):
                                try:
                                    p = selected.getLayoutParams()
                                    p.height = -2
                                    selected.setLayoutParams(p)
                                except Exception:
                                    pass
                            def onAnimationStart(self2, a, *args): pass
                            def onAnimationCancel(self2, a, *args): pass
                            def onAnimationRepeat(self2, a, *args): pass

                        sel_expand = ValueAnimator.ofFloat(0.0, 1.0)
                        sel_expand.setDuration(220)
                        sel_expand.setInterpolator(DecelerateInterpolator(2.0))
                        sel_expand.addUpdateListener(_SelExpand())
                        sel_expand.addListener(_SelExpandEnd())

                        sel_fade = ObjectAnimator.ofFloat(selected, "alpha", 0.0, 1.0)
                        sel_fade.setDuration(200)
                        sel_fade.setStartDelay(40)
                        sel_fade.setInterpolator(DecelerateInterpolator())

                        animators = [sel_expand, sel_fade]

                        if btn is not None:
                            btn_out_a = ObjectAnimator.ofFloat(btn, "alpha", 1.0, 0.0)
                            btn_out_a.setDuration(150)
                            btn_out_a.setInterpolator(AccelerateInterpolator())
                            animators.append(btn_out_a)

                        aset = AnimatorSet()
                        aset.playTogether(*animators)

                        self_ref = self
                        old_btn_ref = btn

                        class _ExtraAnimEnd(dynamic_proxy(Animator.AnimatorListener)):
                            def onAnimationEnd(self2, a, *args):
                                try:
                                    if old_btn_ref is not None:
                                        container.removeView(old_btn_ref)
                                    self_ref._add_another_btn_ref[0] = None
                                    self_ref._refresh_add_another_btn(act, container)
                                except Exception as e:
                                    log(f"suggest: extra anim end error: {e}")
                            def onAnimationStart(self2, a, *args): pass
                            def onAnimationCancel(self2, a, *args): pass
                            def onAnimationRepeat(self2, a, *args): pass

                        self._add_another_btn_ref[0] = None
                        aset.addListener(_ExtraAnimEnd())
                        aset.start()
                    except Exception as e:
                        log(f"suggest: extra file anim error: {e}")
                        if btn is not None:
                            container.removeView(btn)
                            self._add_another_btn_ref[0] = None
                        self._refresh_add_another_btn(act, container)
                        self._refresh_add_another_btn(act, container)
            except Exception as e:
                log(f"suggest: _update_ui error: {e}")

        run_on_ui_thread(_update_ui)

    def _refresh_add_another_btn(self, act, container):
        # remove existing add-another button if present
        old_btn = self._add_another_btn_ref[0]
        if old_btn is not None:
            container.removeView(old_btn)
            self._add_another_btn_ref[0] = None

        sp = self._suggest_config
        max_files = 1
        if isinstance(sp, dict):
            raw = sp.get("settings", {}).get("allow_multi_files", 0)
            try:
                val = int(raw)
            except (TypeError, ValueError):
                val = 1 if raw else 0
            if val >= 2:
                max_files = val

        total_files = 1 + len(self._extra_uris)
        if total_files >= max_files:
            return

        dp = AndroidUtilities.dp

        btn, btn_h = _make_add_another_card(act, 0)
        btn.setClickable(True)
        btn.setFocusable(True)

        def _on_add_click(v):
            _launch_file_picker(act, _PICK_EXTRA_REQUEST_CODE)

        btn.setOnClickListener(OnClickListener(_on_add_click))

        lp = LinearLayout.LayoutParams(-1, -2)
        lp.topMargin = AndroidUtilities.dp(4)

        # log rules_tv position before adding btn
        rules_tv = self._rules_tv_ref[0]
        try:
            if rules_tv is not None:
                loc = [0, 0]
                rules_tv.getLocationOnScreen(loc)
                log(f"suggest: rules_tv Y before btn add = {loc[1]}, alpha={rules_tv.getAlpha()}, transY={rules_tv.getTranslationY()}")
                parent = rules_tv.getParent()
                log(f"suggest: rules_tv parent = {parent}")
                container_loc = [0, 0]
                container.getLocationOnScreen(container_loc)
                log(f"suggest: container Y before btn add = {container_loc[1]}, childCount={container.getChildCount()}, height={container.getHeight()}")
        except Exception as e:
            log(f"suggest: rules_tv pre-log error: {e}")

        btn.setAlpha(0.0)
        container.addView(btn, lp)
        self._add_another_btn_ref[0] = btn

        # log rules_tv position after adding btn
        try:
            if rules_tv is not None:
                loc = [0, 0]
                rules_tv.getLocationOnScreen(loc)
                log(f"suggest: rules_tv Y after btn add = {loc[1]}, transY={rules_tv.getTranslationY()}")
                log(f"suggest: container height after = {container.getHeight()}, childCount={container.getChildCount()}")
        except Exception as e:
            log(f"suggest: rules_tv post-log error: {e}")

        try:
            from android.animation import AnimatorSet, ObjectAnimator, ValueAnimator, Animator
            from android.view.animation import DecelerateInterpolator
            from android.view import ViewGroup
            from java import dynamic_proxy

            # measure real height before expand animation
            btn.measure(
                ViewGroup.MeasureSpec.makeMeasureSpec(0, ViewGroup.MeasureSpec.UNSPECIFIED),
                ViewGroup.MeasureSpec.makeMeasureSpec(0, ViewGroup.MeasureSpec.UNSPECIFIED),
            )
            real_btn_h = btn.getMeasuredHeight()
            if real_btn_h <= 0:
                real_btn_h = AndroidUtilities.dp(44)

            # expand height 0 -> real_btn_h so rules_tv flows naturally without jump
            lp.height = 0
            btn.setLayoutParams(lp)

            class _HeightUpdater(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                def onAnimationUpdate(self2, anim):
                    try:
                        h = int(float(str(anim.getAnimatedValue())) * real_btn_h)
                        p = btn.getLayoutParams()
                        p.height = h
                        btn.setLayoutParams(p)
                    except Exception:
                        pass

            class _HeightEnd(dynamic_proxy(Animator.AnimatorListener)):
                def onAnimationEnd(self2, a, *args):
                    try:
                        p = btn.getLayoutParams()
                        p.height = -2
                        btn.setLayoutParams(p)
                        log(f"suggest: btn height expand done, rules_tv Y now = {_get_y(rules_tv)}")
                    except Exception:
                        pass
                def onAnimationStart(self2, a, *args): pass
                def onAnimationCancel(self2, a, *args): pass
                def onAnimationRepeat(self2, a, *args): pass

            expand = ValueAnimator.ofFloat(0.0, 1.0)
            expand.setDuration(220)
            expand.setInterpolator(DecelerateInterpolator(2.0))
            expand.addUpdateListener(_HeightUpdater())
            expand.addListener(_HeightEnd())

            fade = ObjectAnimator.ofFloat(btn, "alpha", 0.0, 1.0)
            fade.setDuration(200)
            fade.setStartDelay(40)
            fade.setInterpolator(DecelerateInterpolator())

            aset = AnimatorSet()
            aset.playTogether(expand, fade)
            aset.start()
        except Exception as e:
            log(f"suggest: add_another_btn appear anim error: {e}")
            btn.setAlpha(1.0)
            lp.height = -2
            btn.setLayoutParams(lp)

    def _show_fields_section(self, act):
        try:
            fields = self._fields_section_ref[0]
            if fields is not None:
                return

            sp = self._suggest_config
            max_socials = 0
            if isinstance(sp, dict):
                raw = sp.get("settings", {}).get("allow_socials", 0)
                try:
                    max_socials = int(raw)
                except (TypeError, ValueError):
                    max_socials = 0

            dp = AndroidUtilities.dp

            section = LinearLayout(act)
            section.setOrientation(LinearLayout.VERTICAL)

            # description card
            try:
                desc_card = LinearLayout(act)
                desc_card.setOrientation(LinearLayout.VERTICAL)
                desc_card.setPadding(dp(16), dp(12), dp(16), dp(12))
                desc_bg = _make_section_card(act)
                if desc_bg:
                    desc_card.setBackground(desc_bg)

                label_row = LinearLayout(act)
                label_row.setOrientation(LinearLayout.HORIZONTAL)
                label_row.setGravity(Gravity.CENTER_VERTICAL)
                label_row.setPadding(0, 0, 0, dp(8))

                label_icon = ImageView(act)
                icon_id = _resolve_icon("msg_edit")
                if icon_id:
                    label_icon.setImageResource(icon_id)
                    label_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
                label_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                label_row.addView(label_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

                # MD3 titleSmall: 14sp medium
                label_tv = TextView(act)
                label_tv.setText(str(strings.suggest_description_label))
                label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                label_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                label_tv.setTypeface(label_tv.getTypeface(), 1)
                label_row.addView(label_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

                desc_card.addView(label_row, LayoutHelper.createLinear(-1, -2))

                from android.widget import EditText as AEditText
                desc_et = AEditText(act)
                desc_et.setHint(str(strings.suggest_description_hint))
                desc_et.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                desc_et.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                desc_et.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                desc_et.setBackground(None)
                desc_et.setGravity(Gravity.TOP | Gravity.START)
                try:
                    from android.text import InputType
                    desc_et.setInputType(
                        InputType.TYPE_CLASS_TEXT |
                        InputType.TYPE_TEXT_FLAG_MULTI_LINE |
                        InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                    )
                    desc_et.setMinLines(5)
                    desc_et.setMaxLines(10)
                except Exception:
                    pass

                self._desc_edit_ref[0] = desc_et
                _register_keyboard_back(act, desc_et)
                # autofill from plugin meta if already parsed
                pending = self._pending_description[0]
                if pending:
                    _fill_description(desc_et, pending)

                et_bg = _make_outlined_et_bg()
                if et_bg:
                    from android.widget import FrameLayout as FL
                    et_wrap = FL(act)
                    et_wrap.setBackground(et_bg)
                    et_wrap.setPadding(dp(12), dp(8), dp(12), dp(8))
                    et_wrap.addView(desc_et, FL.LayoutParams(-1, -2))
                    desc_card.addView(et_wrap, LayoutHelper.createLinear(-1, -2))
                else:
                    desc_card.addView(desc_et, LayoutHelper.createLinear(-1, -2))

                lp_desc = LinearLayout.LayoutParams(-1, -2)
                section.addView(desc_card, lp_desc)
            except Exception as e:
                log(f"suggest: desc_card error: {e}")

            # note card
            try:
                note_card = LinearLayout(act)
                note_card.setOrientation(LinearLayout.VERTICAL)
                note_card.setPadding(dp(16), dp(12), dp(16), dp(12))
                note_bg = _make_section_card(act)
                if note_bg:
                    note_card.setBackground(note_bg)

                note_label_row = LinearLayout(act)
                note_label_row.setOrientation(LinearLayout.HORIZONTAL)
                note_label_row.setGravity(Gravity.CENTER_VERTICAL)
                note_label_row.setPadding(0, 0, 0, dp(8))

                note_icon = ImageView(act)
                note_icon_id = _resolve_icon("msg_info")
                if note_icon_id:
                    note_icon.setImageResource(note_icon_id)
                    note_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
                note_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                note_label_row.addView(note_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

                note_label_tv = TextView(act)
                note_label_tv.setText("Note")
                note_label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                note_label_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                note_label_tv.setTypeface(note_label_tv.getTypeface(), 1)
                note_label_row.addView(note_label_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

                note_card.addView(note_label_row, LayoutHelper.createLinear(-1, -2))

                from android.widget import EditText as AEditText
                note_et = AEditText(act)
                note_et.setHint(str(strings.suggest_note_hint))
                note_et.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                note_et.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                note_et.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                note_et.setBackground(None)
                note_et.setGravity(Gravity.TOP | Gravity.START)
                try:
                    from android.text import InputType
                    note_et.setInputType(
                        InputType.TYPE_CLASS_TEXT |
                        InputType.TYPE_TEXT_FLAG_MULTI_LINE |
                        InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                    )
                    note_et.setMinLines(2)
                    note_et.setMaxLines(5)
                except Exception:
                    pass

                self._note_edit_ref[0] = note_et
                _register_keyboard_back(act, note_et)

                note_et_bg = _make_outlined_et_bg()
                if note_et_bg:
                    from android.widget import FrameLayout as FL
                    note_et_wrap = FL(act)
                    note_et_wrap.setBackground(note_et_bg)
                    note_et_wrap.setPadding(dp(12), dp(8), dp(12), dp(8))
                    note_et_wrap.addView(note_et, FL.LayoutParams(-1, -2))
                    note_card.addView(note_et_wrap, LayoutHelper.createLinear(-1, -2))
                else:
                    note_card.addView(note_et, LayoutHelper.createLinear(-1, -2))

                lp_note = LinearLayout.LayoutParams(-1, -2)
                lp_note.topMargin = dp(12)
                section.addView(note_card, lp_note)
            except Exception as e:
                log(f"suggest: note_card error: {e}")

            # socials card
            if max_socials > 0:
                try:
                    socials_card = LinearLayout(act)
                    socials_card.setOrientation(LinearLayout.VERTICAL)
                    socials_card.setPadding(dp(16), dp(12), dp(16), dp(12))
                    soc_bg = _make_section_card(act)
                    if soc_bg:
                        socials_card.setBackground(soc_bg)

                    soc_label_row = LinearLayout(act)
                    soc_label_row.setOrientation(LinearLayout.HORIZONTAL)
                    soc_label_row.setGravity(Gravity.CENTER_VERTICAL)
                    soc_label_row.setPadding(0, 0, 0, dp(8))

                    soc_icon = ImageView(act)
                    soc_icon_id = _resolve_icon("msg_link")
                    if soc_icon_id:
                        soc_icon.setImageResource(soc_icon_id)
                        soc_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
                    soc_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                    soc_label_row.addView(soc_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

                    # MD3 titleSmall: 14sp medium
                    soc_label_tv = TextView(act)
                    soc_label_tv.setText(str(strings.suggest_social_links_label))
                    soc_label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                    soc_label_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                    soc_label_tv.setTypeface(soc_label_tv.getTypeface(), 1)
                    soc_label_row.addView(soc_label_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

                    socials_card.addView(soc_label_row, LayoutHelper.createLinear(-1, -2))

                    inputs_container = LinearLayout(act)
                    inputs_container.setOrientation(LinearLayout.VERTICAL)
                    self._social_links_container_ref[0] = inputs_container
                    socials_card.addView(inputs_container, LayoutHelper.createLinear(-1, -2))

                    self_ref3 = self
                    max_socials_ref = [max_socials]

                    add_btn_row = LinearLayout(act)
                    add_btn_row.setOrientation(LinearLayout.HORIZONTAL)
                    add_btn_row.setGravity(Gravity.CENTER_VERTICAL)
                    add_btn_row.setPadding(0, dp(10), 0, 0)
                    add_btn_row.setClickable(True)
                    add_btn_row.setFocusable(True)

                    plus_icon = ImageView(act)
                    plus_id = _resolve_icon("msg_add")
                    if plus_id:
                        plus_icon.setImageResource(plus_id)
                        plus_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
                    plus_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                    add_btn_row.addView(plus_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

                    # MD3 labelMedium: 12sp medium
                    add_tv = TextView(act)
                    add_tv.setText(str(strings.suggest_add_social_btn))
                    add_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
                    add_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
                    try:
                        add_tv.setTypeface(AndroidUtilities.bold())
                    except Exception:
                        pass
                    add_btn_row.addView(add_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

                    def _on_add_social(v):
                        try:
                            ic = inputs_container
                            existing = self_ref3._social_inputs
                            if existing:
                                last_et = existing[-1][1]
                                try:
                                    text = str(last_et.getText()).strip()
                                except Exception:
                                    text = ""
                                if not text:
                                    _shake_view(add_btn_row)
                                    return
                            if len(existing) >= max_socials_ref[0]:
                                return

                            row_ref = [None]

                            def _on_delete(v2):
                                try:
                                    row, et = row_ref[0]
                                    ic.removeView(row)
                                    self_ref3._social_inputs = [x for x in self_ref3._social_inputs if x[0] is not row]
                                    _hide_keyboard(act)
                                except Exception as e2:
                                    log(f"suggest: social delete error: {e2}")

                            row, et = _make_social_input_row(act, str(strings.suggest_social_placeholder), _on_delete)
                            row_ref[0] = (row, et)
                            self_ref3._social_inputs.append((row, et))
                            _register_keyboard_back(act, et)

                            lp_row = LinearLayout.LayoutParams(-1, -2)
                            lp_row.topMargin = AndroidUtilities.dp(8)
                            ic.addView(row, lp_row)

                            _animate_reveal(row, delay_ms=0)
                            _hide_keyboard(act)
                        except Exception as e3:
                            log(f"suggest: _on_add_social error: {e3}")

                    add_btn_row.setOnClickListener(OnClickListener(_on_add_social))
                    socials_card.addView(add_btn_row, LayoutHelper.createLinear(-1, -2))

                    lp_soc = LinearLayout.LayoutParams(-1, -2)
                    lp_soc.topMargin = dp(12)
                    section.addView(socials_card, lp_soc)
                except Exception as e:
                    log(f"suggest: socials_card error: {e}")

            # forked card: toggle + plugin name input, shown after file selection
            allow_forks = False
            if isinstance(sp, dict):
                raw_forks = sp.get("settings", {}).get("allow_forks", 0)
                try:
                    allow_forks = bool(int(raw_forks))
                except (TypeError, ValueError):
                    allow_forks = bool(raw_forks)

            if allow_forks:
              try:
                forked_card = LinearLayout(act)
                forked_card.setOrientation(LinearLayout.VERTICAL)
                forked_card.setPadding(dp(16), dp(12), dp(16), dp(12))
                forked_bg = _make_section_card(act)
                if forked_bg:
                    forked_card.setBackground(forked_bg)

                toggle_row = LinearLayout(act)
                toggle_row.setOrientation(LinearLayout.HORIZONTAL)
                toggle_row.setGravity(Gravity.CENTER_VERTICAL)

                toggle_icon = ImageView(act)
                fork_icon_id = _resolve_icon("msg_fave")
                if fork_icon_id:
                    toggle_icon.setImageResource(fork_icon_id)
                    toggle_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
                toggle_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                toggle_row.addView(toggle_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

                toggle_label = TextView(act)
                toggle_label.setText(str(strings.suggest_forked_label))
                toggle_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                toggle_label.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                toggle_row.addView(toggle_label, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

                # MD3 Filter Chip instead of ugly system Switch
                forked_toggle = _make_md3_chip(act)
                self._forked_switch_ref[0] = forked_toggle
                toggle_row.addView(forked_toggle, LayoutHelper.createLinear(-2, 28, Gravity.CENTER_VERTICAL))

                forked_card.addView(toggle_row, LayoutHelper.createLinear(-1, -2))

                # plugin name input, hidden by default
                from android.widget import EditText as AEditText
                search_container = LinearLayout(act)
                search_container.setOrientation(LinearLayout.VERTICAL)
                search_container.setVisibility(View.GONE)
                self._forked_search_container_ref[0] = search_container

                name_et = AEditText(act)
                name_et.setHint(str(strings.suggest_forked_name_hint))
                name_et.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                name_et.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                name_et.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                name_et.setBackground(None)
                name_et.setSingleLine(True)
                try:
                    from android.text import InputType
                    name_et.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_WORDS)
                except Exception:
                    pass
                self._forked_search_ref[0] = name_et
                _register_keyboard_back(act, name_et)

                # wire instant search on text change
                self_ref_tw = self

                try:
                    from android.text import TextWatcher as _TW
                    _TwProxy = dynamic_proxy(_TW)

                    class _ForkedTextWatcher(_TwProxy):
                        def __init__(self2):
                            super().__init__()
                            self2._timer = [None]

                        def beforeTextChanged(self2, s, start, count, after): pass
                        def onTextChanged(self2, s, start, before, count): pass
                        def afterTextChanged(self2, s):
                            try:
                                query = str(s.toString())
                                t = self2._timer[0]
                                if t is not None:
                                    t.cancel()
                                if not query.strip():
                                    run_on_ui_thread(lambda: self_ref_tw._dismiss_forked_popup())
                                    return

                                import threading

                                def _run():
                                    run_on_ui_thread(lambda: self_ref_tw._update_forked_popup(act, query))

                                timer = threading.Timer(0.25, _run)
                                self2._timer[0] = timer
                                timer.start()
                            except Exception as e:
                                log(f"suggest: forked text watcher error: {e}")

                    name_et.addTextChangedListener(_ForkedTextWatcher())
                except Exception as e:
                    log(f"suggest: forked text watcher setup error: {e}")

                lp_name = LinearLayout.LayoutParams(-1, -2)
                lp_name.topMargin = dp(8)
                et_bg = _make_outlined_et_bg()
                if et_bg:
                    from android.widget import FrameLayout as FL
                    et_wrap = FL(act)
                    et_wrap.setBackground(et_bg)
                    et_wrap.setPadding(dp(12), dp(10), dp(12), dp(10))
                    et_wrap.addView(name_et, FL.LayoutParams(-1, -2))
                    search_container.addView(et_wrap, lp_name)
                    self._forked_search_wrap_ref[0] = et_wrap
                else:
                    search_container.addView(name_et, lp_name)
                forked_card.addView(search_container, LayoutHelper.createLinear(-1, -2))

                if forked_toggle is not None:
                    self_ref_forked = self

                    def _on_chip_click(v):
                        try:
                            chip = self_ref_forked._forked_switch_ref[0]
                            if chip is None:
                                return
                            isChecked = not bool(chip.getTag())
                            chip.setTag(isChecked)
                            _update_md3_chip(chip, isChecked)
                            sc = self_ref_forked._forked_search_container_ref[0]
                            if sc is None:
                                return
                            if isChecked:
                                sc.setVisibility(View.VISIBLE)
                                sc.setAlpha(0.0)
                                sc.animate().alpha(1.0).setDuration(200).start()
                            else:
                                sc.animate().alpha(0.0).setDuration(150).start()
                                sc.setVisibility(View.GONE)
                        except Exception as e:
                            log(f"suggest: chip click error: {e}")

                    forked_toggle.setOnClickListener(OnClickListener(_on_chip_click))

                lp_forked = LinearLayout.LayoutParams(-1, -2)
                lp_forked.topMargin = dp(12)
                section.addView(forked_card, lp_forked)
              except Exception as e:
                log(f"suggest: forked card error: {e}")

            # find content LinearLayout to append section into
            try:
                scroll = self.content_view.getChildAt(0)
                content_ll = scroll.getChildAt(0)
                lp_section = LinearLayout.LayoutParams(-1, -2)
                lp_section.topMargin = dp(16)
                content_ll.addView(section, lp_section)
            except Exception as e:
                log(f"suggest: section attach error: {e}")

            self._fields_section_ref[0] = section
            # animate children one by one with staggered delay
            delay = 60
            for i in range(section.getChildCount()):
                child = section.getChildAt(i)
                if child is not None:
                    _animate_reveal(child, delay_ms=delay)
                    delay += 120

            # restore draft fields now that all inputs are created
            if self._pending_draft:
                self._apply_draft(self._pending_draft, act)
                self._pending_draft = None
        except Exception as e:
            log(f"suggest: _show_fields_section error: {e}")

    def _show_changelog_card(self, act, repo_ver: str, meta_ver: str):
        try:
            if self._changelog_card_ref[0] is not None:
                # update version badge if card already exists
                try:
                    badge = self._changelog_card_ref[0].getTag()
                    if badge is not None:
                        badge.setText(f"{repo_ver} → {meta_ver}")
                except Exception:
                    pass
                return

            fields = self._fields_section_ref[0]
            if fields is None or act is None:
                return

            dp = AndroidUtilities.dp
            from android.widget import EditText as AEditText

            card = LinearLayout(act)
            card.setOrientation(LinearLayout.VERTICAL)
            card.setPadding(dp(16), dp(12), dp(16), dp(12))
            card_bg = _make_section_card(act)
            if card_bg:
                card.setBackground(card_bg)

            # header row: icon + "Changelog" label + version badge
            header_row = LinearLayout(act)
            header_row.setOrientation(LinearLayout.HORIZONTAL)
            header_row.setGravity(Gravity.CENTER_VERTICAL)
            header_row.setPadding(0, 0, 0, dp(8))

            icon_view = ImageView(act)
            icon_id = _resolve_icon("msg_log")
            if icon_id:
                icon_view.setImageResource(icon_id)
                icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
            icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            header_row.addView(icon_view, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

            # MD3 titleSmall: 14sp medium
            label_tv = TextView(act)
            label_tv.setText(str(strings.suggest_changelog_label))
            label_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            label_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            label_tv.setTypeface(label_tv.getTypeface(), 1)
            header_row.addView(label_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            badge_tv = TextView(act)
            badge_tv.setText(f"{repo_ver} → {meta_ver}")
            badge_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
            badge_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            badge_tv.setGravity(Gravity.END | Gravity.CENTER_VERTICAL)
            header_row.addView(badge_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

            # store badge ref via tag for future updates
            card.setTag(badge_tv)

            card.addView(header_row, LayoutHelper.createLinear(-1, -2))

            # url input
            url_et = AEditText(act)
            url_et.setHint(str(strings.suggest_changelog_hint))
            url_et.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            url_et.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            url_et.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            url_et.setBackground(None)
            url_et.setSingleLine(True)
            try:
                from android.text import InputType
                url_et.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI)
            except Exception:
                pass

            et_bg = _make_outlined_et_bg()
            if et_bg:
                from android.widget import FrameLayout as FL
                et_wrap = FL(act)
                et_wrap.setBackground(et_bg)
                et_wrap.setPadding(dp(12), dp(10), dp(12), dp(10))
                et_wrap.addView(url_et, FL.LayoutParams(-1, -2))
                card.addView(et_wrap, LayoutHelper.createLinear(-1, -2))
            else:
                card.addView(url_et, LayoutHelper.createLinear(-1, -2))

            self._changelog_edit_ref[0] = url_et
            _register_keyboard_back(act, url_et)
            self._changelog_card_ref[0] = card

            lp = LinearLayout.LayoutParams(-1, -2)
            lp.topMargin = dp(12)
            # insert before the last child (forked card)
            count = fields.getChildCount()
            insert_idx = max(0, count - 1)
            fields.addView(card, insert_idx, lp)
        except Exception as e:
            log(f"suggest: _show_changelog_card error: {e}")

    def _dismiss_forked_popup(self):
        popup = self._forked_popup_ref[0]
        if popup is None:
            return
        try:
            frag = self._fragment_ref[0] or get_last_fragment()
            act = frag.getParentActivity() if frag else None
            if act:
                decor = act.getWindow().getDecorView()
                try:
                    decor.removeView(popup)
                except Exception:
                    pass
        except Exception as e:
            log(f"suggest: _dismiss_forked_popup error: {e}")
        self._forked_popup_ref[0] = None
        _unregister_back_cb(self._back_cb_ref[0])
        self._back_cb_ref[0] = None

    def _update_forked_popup(self, act, query: str):
        try:
            # load plugins once, cache per fragment lifetime
            if self._forked_plugins_cache[0] is None:
                import threading
                self_ref = self

                def _load():
                    plugins = _load_forked_plugins(self_ref._repo_data)
                    self_ref._forked_plugins_cache[0] = plugins
                    run_on_ui_thread(lambda: self_ref._update_forked_popup(act, query))

                threading.Thread(target=_load, daemon=True).start()
                return

            plugins = self._forked_plugins_cache[0]
            results = _search_plugins(plugins, query)

            self._dismiss_forked_popup()

            name_et = self._forked_search_ref[0]
            if name_et is None:
                return

            decor = act.getWindow().getDecorView()

            if not results:
                popup = _make_forked_not_found_popup(act)
            else:
                popup = _make_forked_popup(act, results, self._on_forked_plugin_selected)

            # position popup anchored above the name_et field
            loc = [0, 0]
            name_et.getLocationInWindow(loc)
            anchor_y = loc[1]
            anchor_x = loc[0]
            field_w = name_et.getWidth()

            from android.widget import FrameLayout as FL
            from android.view import ViewGroup
            popup_lp = FL.LayoutParams(field_w if field_w > 0 else ViewGroup.LayoutParams.MATCH_PARENT, -2)
            popup_lp.leftMargin = anchor_x
            # place above the field
            popup.measure(0, 0)
            popup_h = popup.getMeasuredHeight()
            popup_lp.topMargin = max(0, anchor_y - popup_h - AndroidUtilities.dp(4))
            popup.setAlpha(0.0)
            popup.setTranslationY(float(AndroidUtilities.dp(8)))
            self._forked_popup_ref[0] = popup
            decor.addView(popup, popup_lp)

            self_ref_back = self
            self._back_cb_ref[0] = _register_back_cb(act, lambda: run_on_ui_thread(self_ref_back._dismiss_forked_popup))

            try:
                from android.animation import AnimatorSet, ObjectAnimator
                from android.view.animation import DecelerateInterpolator
                a_alpha = ObjectAnimator.ofFloat(popup, "alpha", 0.0, 1.0)
                a_alpha.setDuration(160)
                a_alpha.setInterpolator(DecelerateInterpolator())
                a_ty = ObjectAnimator.ofFloat(popup, "translationY", float(AndroidUtilities.dp(8)), 0.0)
                a_ty.setDuration(180)
                a_ty.setInterpolator(DecelerateInterpolator(1.2))
                aset = AnimatorSet()
                aset.playTogether(a_alpha, a_ty)
                aset.start()
            except Exception as e:
                log(f"suggest: forked popup anim error: {e}")
                popup.setAlpha(1.0)
                popup.setTranslationY(0.0)
        except Exception as e:
            log(f"suggest: _update_forked_popup error: {e}")

    def _on_forked_plugin_selected(self, plugin: dict):
        self._dismiss_forked_popup()
        self._forked_selected_plugin[0] = plugin

        frag = self._fragment_ref[0] or get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if act is None:
            return

        run_on_ui_thread(lambda: self._show_forked_selected_card(act, plugin))

    def _show_forked_selected_card(self, act, plugin: dict):
        try:
            sc = self._forked_search_container_ref[0]
            name_et = self._forked_search_ref[0]
            if sc is None or name_et is None:
                return

            dp = AndroidUtilities.dp

            # hide search field (et_wrap contains the outline border)
            et_wrap = self._forked_search_wrap_ref[0]
            target = et_wrap if et_wrap is not None else name_et
            target.setVisibility(View.GONE)
            _hide_keyboard(act)

            # remove previous selected card if any
            old_card = self._forked_selected_card_ref[0]
            if old_card is not None:
                sc.removeView(old_card)
                self._forked_selected_card_ref[0] = None

            # mini card: same row as popup rows + delete button
            card = LinearLayout(act)
            card.setOrientation(LinearLayout.HORIZONTAL)
            card.setGravity(Gravity.CENTER_VERTICAL)
            card.setPadding(dp(12), dp(10), dp(10), dp(10))

            try:
                from android.graphics.drawable import GradientDrawable
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadius(dp(12))
                primary = Theme.getColor(Theme.key_featuredStickers_addButton)
                bg.setColor(primary & 0x15FFFFFF | 0x0D000000)
                card.setBackground(bg)
            except Exception as e:
                log(f"suggest: forked selected card bg error: {e}")

            # icon
            icon_str = str(plugin.get("icon") or "")
            icon_size_dp = 36
            if icon_str and icon_str != "Unknown" and "/" in icon_str:
                try:
                    from org.telegram.ui.Components import BackupImageView
                    from org.telegram.messenger import MediaDataController
                    icon_view = BackupImageView(act)
                    icon_view.setRoundRadius(dp(8))
                    icon_size_px = dp(icon_size_dp)
                    icon_lp = LinearLayout.LayoutParams(icon_size_px, icon_size_px)
                    icon_lp.rightMargin = dp(10)
                    card.addView(icon_view, icon_lp)

                    def _try_load(iv=icon_view, s=icon_str):
                        try:
                            from org.telegram.messenger import ImageLocation
                            pack_name, index_str = s.split("/", 1)
                            idx = int(index_str)
                            mdc = MediaDataController.getInstance(0)
                            ss = None
                            try:
                                ss = mdc.getStickerSetByName(pack_name)
                            except Exception:
                                pass
                            if not ss:
                                try:
                                    ss = mdc.getStickerSetByEmojiOrName(pack_name)
                                except Exception:
                                    pass
                            if ss and getattr(ss, "documents", None) and ss.documents.size() > idx:
                                doc = ss.documents.get(idx)
                                iv.setImage(
                                    ImageLocation.getForDocument(doc),
                                    f"{icon_size_dp}_{icon_size_dp}",
                                    None, None, 0, 1
                                )
                                return True
                            return False
                        except Exception:
                            return False

                    if not _try_load():
                        try:
                            pack_name = icon_str.split("/", 1)[0]
                            MediaDataController.getInstance(0).loadStickersByEmojiOrName(pack_name, False, False)
                        except Exception:
                            pass
                        import threading
                        def _retry(iv=icon_view, loader=_try_load):
                            import time
                            for d in (0.5, 1.0, 2.0):
                                time.sleep(d)
                                try:
                                    run_on_ui_thread(loader)
                                    return
                                except Exception:
                                    pass
                        threading.Thread(target=_retry, daemon=True).start()
                except Exception as e:
                    log(f"suggest: forked selected icon error: {e}")
                    _add_stub_icon(act, card, icon_size_dp, dp)
            else:
                _add_stub_icon(act, card, icon_size_dp, dp)

            # text column
            col = LinearLayout(act)
            col.setOrientation(LinearLayout.VERTICAL)

            name_tv = TextView(act)
            display_name = str(plugin.get("name") or plugin.get("id") or "Unknown")
            name_tv.setText(display_name)
            name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            name_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            name_tv.setSingleLine(True)
            try:
                name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                pass
            col.addView(name_tv, LayoutHelper.createLinear(-2, -2))

            version_text = str(plugin.get("version") or "").strip()
            author_text = str(plugin.get("author") or "").strip()
            if version_text or author_text:
                sub_tv = TextView(act)
                if version_text and author_text:
                    try:
                        from com.exteragram.messenger.utils.text import LocaleUtils
                        sub_tv.setText(LocaleUtils.fullyFormatText(f"{author_text} • v{version_text}"))
                    except Exception:
                        sub_tv.setText(f"{author_text} • v{version_text}")
                elif author_text:
                    try:
                        from com.exteragram.messenger.utils.text import LocaleUtils
                        sub_tv.setText(LocaleUtils.fullyFormatText(author_text))
                    except Exception:
                        sub_tv.setText(author_text)
                else:
                    sub_tv.setText(f"v{version_text}")
                sub_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
                sub_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                try:
                    from android.text.method import LinkMovementMethod
                    sub_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                    sub_tv.setMovementMethod(LinkMovementMethod.getInstance())
                except Exception:
                    pass
                sub_tv.setSingleLine(True)
                lp_sub = LinearLayout.LayoutParams(-2, -2)
                lp_sub.topMargin = dp(2)
                col.addView(sub_tv, lp_sub)

            card.addView(col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

            # reset button
            self_ref = self
            del_btn = ImageView(act)
            del_icon = _resolve_icon("msg_close")
            if del_icon:
                del_btn.setImageResource(del_icon)
                del_btn.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            del_btn.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            del_btn.setClickable(True)
            del_btn.setFocusable(True)

            def _on_reset(v):
                try:
                    self_ref._forked_selected_plugin[0] = None
                    sc2 = self_ref._forked_search_container_ref[0]
                    et2 = self_ref._forked_search_ref[0]
                    wrap2 = self_ref._forked_search_wrap_ref[0]
                    old = self_ref._forked_selected_card_ref[0]
                    if old is not None and sc2 is not None:
                        sc2.removeView(old)
                    self_ref._forked_selected_card_ref[0] = None
                    if et2 is not None:
                        et2.setText("")
                    target2 = wrap2 if wrap2 is not None else et2
                    if target2 is not None:
                        target2.setVisibility(View.VISIBLE)
                    if et2 is not None:
                        et2.requestFocus()
                except Exception as e:
                    log(f"suggest: forked reset error: {e}")

            del_btn.setOnClickListener(OnClickListener(_on_reset))
            card.addView(del_btn, LayoutHelper.createLinear(32, 32, Gravity.CENTER_VERTICAL, 4, 0, 0, 0))

            lp_card = LinearLayout.LayoutParams(-1, -2)
            lp_card.topMargin = dp(8)
            sc.addView(card, lp_card)
            self._forked_selected_card_ref[0] = card

            card.setAlpha(0.0)
            card.animate().alpha(1.0).setDuration(180).start()
        except Exception as e:
            log(f"suggest: _show_forked_selected_card error: {e}")


    def _attach_keyboard_scroll(self, act, root):
        # scrolls content up when keyboard appears so focused field stays visible above btn
        try:
            from android.view import ViewTreeObserver as _VTO
            from android.graphics import Rect
            from java import dynamic_proxy

            _VtoProxy = dynamic_proxy(_VTO.OnGlobalLayoutListener)
            self_ref = self
            last_offset = [0]

            class _KeyboardScrollListener(_VtoProxy):
                def onGlobalLayout(self2):
                    try:
                        sv = self_ref._scroll_ref[0]
                        wrapper = self_ref._submit_wrapper_ref[0]
                        if sv is None:
                            return

                        r = Rect()
                        root.getWindowVisibleDisplayFrame(r)
                        screen_h = root.getRootView().getHeight()
                        keyboard_h = screen_h - r.bottom

                        # btn_wrapper height adds extra obstruction when visible
                        btn_h = 0
                        try:
                            if wrapper is not None and wrapper.getVisibility() == 0:
                                btn_h = wrapper.getHeight()
                        except Exception:
                            pass

                        total_obstruction = keyboard_h + btn_h

                        if total_obstruction > screen_h * 0.15:
                            # keyboard is open — scroll focused field into view
                            focused = act.getCurrentFocus()
                            if focused is None:
                                return
                            field_loc = [0, 0]
                            focused.getLocationInWindow(field_loc)
                            field_bottom = field_loc[1] + focused.getHeight()
                            visible_bottom = r.bottom - btn_h
                            gap = AndroidUtilities.dp(16)
                            if field_bottom > visible_bottom - gap:
                                offset = field_bottom - (visible_bottom - gap)
                                if offset != last_offset[0]:
                                    last_offset[0] = offset
                                    sv.smoothScrollBy(0, offset)
                        else:
                            # keyboard closed — restore if we scrolled
                            if last_offset[0] != 0:
                                last_offset[0] = 0
                    except Exception as e:
                        log(f"suggest: keyboard scroll error: {e}")

            root.getViewTreeObserver().addOnGlobalLayoutListener(_KeyboardScrollListener())
        except Exception as e:
            log(f"suggest: _attach_keyboard_scroll error: {e}")

    def _collect_draft(self) -> dict:
        draft = {}
        try:
            et = self._desc_edit_ref[0]
            if et is not None:
                draft["description"] = str(et.getText())
        except Exception:
            pass
        try:
            note_et = self._note_edit_ref[0]
            if note_et is not None:
                draft["note"] = str(note_et.getText())
        except Exception:
            pass
        try:
            socials = []
            for _, et in self._social_inputs:
                val = str(et.getText()).strip()
                if val:
                    socials.append(val)
            if socials:
                draft["socials"] = socials
        except Exception:
            pass
        try:
            url_et = self._changelog_edit_ref[0]
            if url_et is not None:
                val = str(url_et.getText()).strip()
                if val:
                    draft["changelog_url"] = val
        except Exception:
            pass
        try:
            toggle = self._forked_switch_ref[0]
            if toggle is not None:
                draft["forked_enabled"] = bool(toggle.getTag())
            plugin = self._forked_selected_plugin[0]
            if isinstance(plugin, dict):
                draft["forked_plugin"] = plugin
        except Exception:
            pass
        # file info
        if self._selected_name:
            draft["file_name"] = self._selected_name
        if self._selected_size is not None:
            draft["file_size"] = self._selected_size
        if self._draft_main_path and _os.path.isfile(self._draft_main_path):
            draft["draft_main_path"] = self._draft_main_path
        if self._draft_extra_paths:
            valid = []
            for i, (_, ename, esize) in enumerate(self._extra_uris):
                p = self._draft_extra_paths[i] if i < len(self._draft_extra_paths) else None
                if p and _os.path.isfile(p):
                    valid.append({"path": p, "name": ename or "", "size": esize})
            if valid:
                draft["draft_extra_files"] = valid
        return draft

    def _apply_draft(self, draft: dict, act):
        # restore saved files
        try:
            main_path = draft.get("draft_main_path", "")
            file_name = draft.get("file_name", "")
            file_size = draft.get("file_size")
            if main_path and _os.path.isfile(main_path):
                self._draft_main_path = main_path
                self._selected_name = file_name
                self._selected_size = file_size
                # show file card
                container = self._selected_card_container_ref[0]
                upload_card = self._upload_card_ref[0]
                if container is not None and upload_card is not None:
                    selected = _make_selected_file_card(act, file_name, file_size)
                    container.removeAllViews()
                    container.addView(selected, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))
                    container.setVisibility(View.VISIBLE)
                    upload_card.setVisibility(View.GONE)
        except Exception as e:
            log(f"suggest: _apply_draft files error: {e}")
        try:
            for ef in draft.get("draft_extra_files", []):
                p = ef.get("path", "")
                ename = ef.get("name", "")
                esize = ef.get("size")
                if p and _os.path.isfile(p):
                    self._extra_uris.append((None, ename, esize))
                    self._draft_extra_paths.append(p)
                    container = self._selected_card_container_ref[0]
                    if container is not None:
                        selected = _make_selected_file_card(act, ename, esize)
                        lp = LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0)
                        container.addView(selected, lp)
        except Exception as e:
            log(f"suggest: _apply_draft extra files error: {e}")
        # restore text fields
        try:
            desc = draft.get("description", "")
            if desc:
                et = self._desc_edit_ref[0]
                if et is not None:
                    _fill_description(et, desc)
        except Exception as e:
            log(f"suggest: _apply_draft desc error: {e}")
        try:
            note = draft.get("note", "")
            if note:
                note_et = self._note_edit_ref[0]
                if note_et is not None:
                    note_et.setText(note)
        except Exception as e:
            log(f"suggest: _apply_draft note error: {e}")
        try:
            socials = draft.get("socials", [])
            container = self._social_links_container_ref[0]
            if socials and container is not None:
                for link in socials:
                    row_ref = [None]

                    def _on_delete(v2, rr=row_ref):
                        try:
                            row, et2 = rr[0]
                            container.removeView(row)
                            self._social_inputs = [x for x in self._social_inputs if x[0] is not row]
                        except Exception as e2:
                            log(f"suggest: draft social delete error: {e2}")

                    row, et_s = _make_social_input_row(act, str(strings.suggest_social_placeholder), _on_delete)
                    row_ref[0] = (row, et_s)
                    et_s.setText(link)
                    self._social_inputs.append((row, et_s))
                    lp = LinearLayout.LayoutParams(-1, -2)
                    lp.topMargin = AndroidUtilities.dp(8)
                    container.addView(row, lp)
        except Exception as e:
            log(f"suggest: _apply_draft socials error: {e}")
        try:
            changelog_url = draft.get("changelog_url", "")
            if changelog_url:
                url_et = self._changelog_edit_ref[0]
                if url_et is not None:
                    url_et.setText(changelog_url)
        except Exception as e:
            log(f"suggest: _apply_draft changelog error: {e}")
        try:
            forked_enabled = draft.get("forked_enabled", False)
            forked_plugin = draft.get("forked_plugin")
            toggle = self._forked_switch_ref[0]
            if forked_enabled and toggle is not None:
                toggle.setTag(True)
                _update_md3_chip(toggle, True)
                sc = self._forked_search_container_ref[0]
                if sc is not None:
                    sc.setVisibility(View.VISIBLE)
            if forked_plugin and isinstance(forked_plugin, dict):
                self._forked_selected_plugin[0] = forked_plugin
                self._show_forked_selected_card(act, forked_plugin)
        except Exception as e:
            log(f"suggest: _apply_draft forked error: {e}")

    def _save_current_draft(self):
        try:
            draft = self._collect_draft()
            # only persist if there is actual user content to restore
            has_content = (
                draft.get("file_name") or
                draft.get("description") or
                draft.get("note") or
                draft.get("socials") or
                draft.get("changelog_url") or
                draft.get("forked_plugin")
            )
            if has_content:
                _save_draft(self._rm_rid, draft)
                log(f"suggest: draft saved for {self._rm_rid}")
            else:
                log(f"suggest: nothing to save, skipping draft")
        except Exception as e:
            log(f"suggest: _save_current_draft error: {e}")

    def _do_submit(self):
        from android_utils import run_on_ui_thread
        from client_utils import send_request, RequestCallback, get_messages_controller, run_on_queue, PLUGINS_QUEUE, send_document
        from org.telegram.tgnet import TLRPC
        from ui.bulletin import BulletinHelper

        sp = self._suggest_config
        config = sp.get("config", {}) if isinstance(sp, dict) else {}
        acc_user = str(config.get("acc_user") or "")
        log(f"suggest._do_submit: acc_user={acc_user!r}")
        if not acc_user:
            BulletinHelper.show_error(str(strings.suggest_no_config))
            return

        if self._selected_uri is None and not (self._draft_main_path and _os.path.isfile(self._draft_main_path)):
            log("suggest._do_submit: no file selected")
            return

        frag = get_last_fragment()
        act = frag.getParentActivity() if frag else None
        if not act:
            log("suggest._do_submit: no activity")
            return

        # collect caption fields
        desc = ""
        try:
            et = self._desc_edit_ref[0]
            if et is not None:
                desc = str(et.getText()).strip()
        except Exception as e:
            log(f"suggest._do_submit: desc read error: {e}")
        if not desc:
            desc = "Default"

        socials = []
        try:
            for row, et in self._social_inputs:
                val = str(et.getText()).strip()
                if val:
                    socials.append(val)
        except Exception as e:
            log(f"suggest._do_submit: socials read error: {e}")

        socials_block = "\n".join(f"• {s}" for s in socials) if socials else "None"

        changelog = "None"
        try:
            versions = self._pending_versions[0]
            if versions is not None:
                # plugin is an update — read changelog url
                url_et = self._changelog_edit_ref[0]
                url = str(url_et.getText()).strip() if url_et is not None else ""
                if url:
                    changelog = url
                else:
                    changelog = "Not updated"
        except Exception as e:
            log(f"suggest._do_submit: changelog read error: {e}")

        forked_link = "None"
        try:
            selected_plugin = self._forked_selected_plugin[0]
            toggle = self._forked_switch_ref[0]
            is_forked = toggle is not None and bool(toggle.getTag())
            if is_forked and selected_plugin is not None:
                plugin_id = str(selected_plugin.get("id") or "")
                repometa = self._repo_data.get("repometa") if isinstance(self._repo_data, dict) else None
                rm_rid = repometa.get("rm_rid") if isinstance(repometa, dict) else None
                if plugin_id and rm_rid:
                    forked_link = f"tg://packit?plugin={plugin_id}&repo={rm_rid}"
        except Exception as e:
            log(f"suggest._do_submit: forked read error: {e}")

        note = ""
        try:
            note_et = self._note_edit_ref[0]
            if note_et is not None:
                note = str(note_et.getText()).strip()
        except Exception as e:
            log(f"suggest._do_submit: note read error: {e}")

        use_json = False
        try:
            raw_json = config.get("json", 0)
            use_json = bool(int(raw_json)) if raw_json not in (True, False) else bool(raw_json)
        except (TypeError, ValueError):
            use_json = bool(config.get("json", False))

        if use_json:
            import json as _json
            payload = {
                "description": desc,
                "socials": socials,
                "changelog": changelog,
                "forked": forked_link,
            }
            if note:
                payload["note"] = note
            caption = _json.dumps(payload, ensure_ascii=False)
        else:
            caption = f"Description:\n{desc}\n\nSocials:\n{socials_block}\n\nChangelog:\n{changelog}\n\nForked:\n{forked_link}"
            if note:
                caption += f"\n\nNote:\n{note}"
        log(f"suggest._do_submit: caption={caption!r}")

        # show loading state on button
        self._set_submit_loading(act)

        self_ref = self

        def _task():
            import os
            try:
                main_name = self_ref._selected_name or ""

                # use already-saved draft file if present, otherwise copy from uri
                if self_ref._draft_main_path and os.path.isfile(self_ref._draft_main_path):
                    log(f"suggest._task: using draft main file path={self_ref._draft_main_path}")
                    main_path = self_ref._draft_main_path
                else:
                    log(f"suggest._task: copying main file name={main_name!r} uri={self_ref._selected_uri}")
                    main_path = _copy_uri_to_temp(self_ref._selected_uri, act, main_name)
                if not main_path:
                    raise Exception("failed to get main file path")
                log(f"suggest._task: main_path={main_path}")

                extra_paths = []
                for i, (uri, name, size) in enumerate(self_ref._extra_uris):
                    draft_p = self_ref._draft_extra_paths[i] if i < len(self_ref._draft_extra_paths) else None
                    if draft_p and os.path.isfile(draft_p):
                        log(f"suggest._task: using draft extra file [{i}] path={draft_p}")
                        extra_paths.append(draft_p)
                    elif uri is not None:
                        log(f"suggest._task: copying extra name={name!r}")
                        p = _copy_uri_to_temp(uri, act, name or "")
                        if p:
                            extra_paths.append(p)
                            log(f"suggest._task: extra_path={p}")

                # collect paths that live in filesDir (blocked by isInternalUri)
                files_dir_marker = "/files/"
                hook_paths = set()
                if files_dir_marker in main_path:
                    hook_paths.add(main_path)
                for p in extra_paths:
                    if files_dir_marker in p:
                        hook_paths.add(p)

                # hook isInternalUri to allow our draft paths through
                uri_hook = None
                if hook_paths and self_ref._plugin is not None:
                    log(f"suggest._task: hooking isInternalUri for {len(hook_paths)} path(s)")
                    uri_hook = _hook_is_internal_uri(self_ref._plugin, hook_paths)

                # copy draft files to cache dir so upload thread can read them
                import shutil, tempfile
                from file_utils import get_cache_dir

                def _stage_for_upload(src: str, display_name: str) -> str:
                    suffix = ""
                    dot = display_name.rfind(".")
                    if dot >= 0:
                        suffix = display_name[dot:]
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=suffix,
                        dir=get_cache_dir()
                    )
                    tmp.close()
                    shutil.copy2(src, tmp.name)
                    log(f"suggest._task: staged {src} -> {tmp.name}")
                    return tmp.name

                staged_main = None
                staged_extras = []

                if files_dir_marker in main_path:
                    staged_main = _stage_for_upload(main_path, main_name)
                staged_extras = []
                for i, p in enumerate(extra_paths):
                    if files_dir_marker in p:
                        name_s = (self_ref._extra_uris[i][1] or "") if i < len(self_ref._extra_uris) else ""
                        staged_extras.append(_stage_for_upload(p, name_s))
                    else:
                        staged_extras.append(None)

                send_main_path = staged_main if staged_main else main_path
                send_extra_paths = [
                    staged_extras[i] if staged_extras[i] else extra_paths[i]
                    for i in range(len(extra_paths))
                ]

                def _cleanup():
                    if uri_hook is not None:
                        try:
                            for h in uri_hook:
                                self_ref._plugin.unhook_method(h)
                            log("suggest: unhooked isInternalUri")
                        except Exception as e:
                            log(f"suggest: unhook isInternalUri error: {e}")
                    # delete staged copies and non-draft temp files
                    for p in ([staged_main] if staged_main else []) + [s for s in staged_extras if s]:
                        try:
                            os.unlink(p)
                            log(f"suggest: cleaned up staged {p}")
                        except Exception as ex:
                            log(f"suggest: cleanup staged error {p}: {ex}")
                    for p in [main_path] + extra_paths:
                        if files_dir_marker not in p:
                            try:
                                os.unlink(p)
                                log(f"suggest: cleaned up temp {p}")
                            except Exception as ex:
                                log(f"suggest: cleanup error {p}: {ex}")

                # resolve username to get access_hash, then send
                def _on_resolved(response, error):
                    if error or not response or not response.users:
                        err_text = error.text if error else "no users"
                        log(f"suggest: resolve error: {err_text}")
                        _cleanup()
                        run_on_ui_thread(lambda: (
                            BulletinHelper.show_error(str(strings.suggest_resolve_error)),
                            self_ref._restore_submit_btn()
                        ))
                        return

                    try:
                        user = response.users.get(0)
                        peer_id = int(user.id)
                        get_messages_controller().putUsers(response.users, False)
                        log(f"suggest: resolved acc_user={acc_user} peer_id={peer_id}")

                        # build extra captions before leaving queue thread
                        import json as _json2
                        extra_captions = []
                        for i, p in enumerate(send_extra_paths):
                            name_str = (self_ref._extra_uris[i][1] or "") if i < len(self_ref._extra_uris) else ""
                            extra_captions.append(_json2.dumps({"additional": [name_str, i + 1]}, ensure_ascii=False))

                        # send_document calls SendMessagesHelper which requires main thread
                        def _send_on_main():
                            try:
                                log(f"suggest: sending main document path={send_main_path}")
                                send_document(peer_id, send_main_path, caption=caption)
                                log(f"suggest: main document sent ok")
                                for i, p in enumerate(send_extra_paths):
                                    log(f"suggest: sending extra document [{i}] path={p}")
                                    send_document(peer_id, p, caption=extra_captions[i])
                                    log(f"suggest: extra document [{i}] sent ok")
                                log("suggest: all documents enqueued, showing success")
                                self_ref._submitted = True
                                _clear_draft(self_ref._rm_rid)
                                log(f"suggest: draft cleared for {self_ref._rm_rid}")
                                BulletinHelper.show_success(str(strings.suggest_sent))
                                self_ref._finish_fragment()

                                # cleanup temp files 30s after successful submit
                                def _deferred_cleanup():
                                    import time
                                    time.sleep(30)
                                    _cleanup()
                                    log("suggest: deferred cleanup done")

                                import threading
                                threading.Thread(target=_deferred_cleanup, daemon=True).start()
                            except Exception as e:
                                log(f"suggest: send_on_main error: {e}")
                                BulletinHelper.show_error(str(strings.suggest_send_error))
                                self_ref._restore_submit_btn()

                        run_on_ui_thread(_send_on_main)
                    except Exception as e:
                        log(f"suggest: send error: {e}")
                        _cleanup()
                        run_on_ui_thread(lambda: (
                            BulletinHelper.show_error(str(strings.suggest_send_error)),
                            self_ref._restore_submit_btn()
                        ))

                log(f"suggest: resolving username={acc_user}")
                req = TLRPC.TL_contacts_resolveUsername()
                req.username = acc_user
                send_request(req, RequestCallback(_on_resolved))
            except Exception as e:
                log(f"suggest._do_submit task error: {e}")
                run_on_ui_thread(lambda: (
                    BulletinHelper.show_error(str(strings.suggest_send_error)),
                    self_ref._restore_submit_btn()
                ))

        run_on_queue(_task, PLUGINS_QUEUE)
    def _show_submit_btn(self, act):
        wrapper = self._submit_wrapper_ref[0]
        if wrapper is None or wrapper.getVisibility() == View.VISIBLE:
            return
        try:
            from android.animation import AnimatorSet, ObjectAnimator
            from android.view.animation import DecelerateInterpolator
            wrapper.setVisibility(View.VISIBLE)
            wrapper.measure(0, 0)
            slide_from = float(wrapper.getMeasuredHeight() + AndroidUtilities.dp(8))
            wrapper.setTranslationY(slide_from)
            wrapper.setAlpha(0.0)

            # MD3 standard: slide up + fade, 300ms FastOutSlowIn
            ty = ObjectAnimator.ofFloat(wrapper, "translationY", slide_from, 0.0)
            ty.setDuration(300)
            ty.setInterpolator(DecelerateInterpolator(2.0))

            alpha = ObjectAnimator.ofFloat(wrapper, "alpha", 0.0, 1.0)
            alpha.setDuration(200)
            alpha.setInterpolator(DecelerateInterpolator())

            aset = AnimatorSet()
            aset.playTogether(ty, alpha)
            aset.start()
        except Exception as e:
            log(f"suggest: _show_submit_btn anim error: {e}")
            try:
                wrapper.setVisibility(View.VISIBLE)
                wrapper.setAlpha(1.0)
                wrapper.setTranslationY(0.0)
            except Exception:
                pass

    def _set_submit_loading(self, act):
        try:
            btn = self._submit_btn_ref
            if btn is None:
                return
            btn.setEnabled(False)
            btn.setClickable(False)
            btn.removeAllViews()
            from org.telegram.ui.Components import CircularProgressDrawable
            dp = AndroidUtilities.dp
            btn_text_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
            d = CircularProgressDrawable(btn_text_color)
            try:
                d.size = float(dp(20))
                d.thickness = float(dp(2))
            except Exception:
                pass
            spinner = ImageView(act)
            spinner.setImageDrawable(d)
            spinner.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
            spinner.setPadding(0, dp(14), 0, dp(14))
            btn.addView(spinner, FrameLayout.LayoutParams(-1, dp(20 + 28), Gravity.CENTER))
        except Exception as e:
            log(f"suggest: _set_submit_loading error: {e}")
            try:
                from android.widget import ProgressBar
                btn = self._submit_btn_ref
                if btn:
                    btn.removeAllViews()
                    pb = ProgressBar(act)
                    pb.setIndeterminate(True)
                    btn.addView(pb, FrameLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER))
            except Exception:
                pass

    def _restore_submit_btn(self):
        try:
            btn = self._submit_btn_ref
            if btn is None:
                return
            btn.removeAllViews()
            lbl = self._submit_lbl_ref[0]
            if lbl is not None:
                from android.widget import FrameLayout as FL
                btn.addView(lbl, FL.LayoutParams(-1, -2, Gravity.CENTER))
            btn.setEnabled(True)
            btn.setClickable(True)
        except Exception as e:
            log(f"suggest: _restore_submit_btn error: {e}")

    def _finish_fragment(self):
        try:
            frag = self._fragment_ref[0]
            if frag:
                frag.finishFragment()
            else:
                f = get_last_fragment()
                if f:
                    f.finishFragment()
        except Exception as e:
            log(f"suggest: _finish_fragment error: {e}")

    def beforeCreateView(self):
        if self.content_view is not None:
            try:
                parent = self.content_view.getParent()
                if parent is not None:
                    parent.removeView(self.content_view)
            except Exception as e:
                log(f"suggest: stale view cleanup error: {e}")
            self.content_view = None

        frag = get_last_fragment()
        if not frag:
            return None
        act = frag.getParentActivity()
        if not act:
            return None

        try:
            dp = AndroidUtilities.dp

            root = FrameLayout(act)
            root.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))

            scroll = ScrollView(act)
            scroll.setVerticalScrollBarEnabled(False)
            scroll.setFillViewport(True)
            self._scroll_ref[0] = scroll

            content = LinearLayout(act)
            content.setOrientation(LinearLayout.VERTICAL)
            content.setPadding(dp(16), dp(16), dp(16), dp(16))

            try:
                # MD3 titleLarge: 22sp
                title_tv = TextView(act)
                title_tv.setText(str(strings.suggest_submit_title))
                title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 22)
                title_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                title_tv.setTypeface(title_tv.getTypeface(), 1)
                title_tv.setGravity(Gravity.START)
                content.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 16))
            except Exception as e:
                log(f"suggest: title_tv error: {e}")

            outer = LinearLayout(act)
            outer.setOrientation(LinearLayout.VERTICAL)

            upload_card = _make_upload_card(act)
            self._upload_card_ref[0] = upload_card

            selected_container = LinearLayout(act)
            selected_container.setOrientation(LinearLayout.VERTICAL)
            selected_container.setGravity(Gravity.CENTER_VERTICAL)
            selected_container.setMinimumHeight(dp(112))
            selected_container.setVisibility(View.GONE)
            self._selected_card_container_ref[0] = selected_container

            self_ref = self

            # hook onActivityResult before launching the picker
            if self._plugin is not None and self._picker_hook_ref is None:
                self._picker_hook_ref = _hook_activity_result(
                    self._plugin, act,
                    {_PICK_REQUEST_CODE, _PICK_EXTRA_REQUEST_CODE},
                    self_ref._on_file_picked
                )

            def _on_card_click(v):
                _launch_file_picker(act, _PICK_REQUEST_CODE)

            upload_card.setOnClickListener(OnClickListener(_on_card_click))

            selected_container.setClickable(True)
            selected_container.setFocusable(True)
            selected_container.setOnClickListener(OnClickListener(_on_card_click))
            _apply_ripple(selected_container, corner_dp=12)

            outer.addView(upload_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))
            outer.addView(selected_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))

            try:
                config = {}
                sp = self._suggest_config
                if isinstance(sp, dict):
                    config = sp.get("config", {})

                rules = config.get("rules", "")
                rules_name = config.get("rules_name", "")

                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod

                rules_row = LinearLayout(act)
                rules_row.setOrientation(LinearLayout.VERTICAL)

                # header row: icon + "About approval" in white
                header_row = LinearLayout(act)
                header_row.setOrientation(LinearLayout.HORIZONTAL)
                header_row.setGravity(Gravity.CENTER_VERTICAL)
                header_row.setPadding(0, 0, 0, dp(4))

                rules_icon = ImageView(act)
                info_icon_id = _resolve_icon("msg_info")
                if info_icon_id:
                    rules_icon.setImageResource(info_icon_id)
                    rules_icon.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                rules_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
                header_row.addView(rules_icon, LayoutHelper.createLinear(16, 16, Gravity.CENTER_VERTICAL, 0, 0, 6, 0))

                header_tv = TextView(act)
                header_tv.setText(str(strings.suggest_rules_header))
                header_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                header_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                try:
                    header_tv.setTypeface(AndroidUtilities.bold())
                except Exception:
                    pass
                header_row.addView(header_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))
                rules_row.addView(header_row, LayoutHelper.createLinear(-1, -2))

                # prefix + link on one line
                rules_tv = TextView(act)
                if rules:
                    link_text = f"[{rules_name}]({rules})" if rules_name else rules
                    combined = f"{strings.suggest_rules_prefix} {link_text}"
                    try:
                        rules_tv.setText(LocaleUtils.fullyFormatText(combined))
                        rules_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                        rules_tv.setMovementMethod(LinkMovementMethod.getInstance())
                    except Exception:
                        rules_tv.setText(combined)
                else:
                    rules_tv.setText(str(strings.suggest_no_rules))
                rules_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                rules_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                rules_row.addView(rules_tv, LayoutHelper.createLinear(-1, -2))

                self._rules_tv_ref[0] = rules_row
                outer.addView(rules_row, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))
            except Exception as e:
                log(f"suggest: rules_tv error: {e}")

            content.addView(outer, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))

            btn_height_dp = 56
            btn_margin_dp = 16
            bottom_padding = AndroidUtilities.dp(btn_height_dp + btn_margin_dp * 2)

            scroll.addView(content, LayoutHelper.createScroll(-1, -2, 0))
            root.addView(scroll, FrameLayout.LayoutParams(-1, -1))

            # MD3 FilledButton pinned to bottom, hidden until first file is picked
            try:
                from android.widget import FrameLayout as FL
                from android.util import TypedValue as TV

                btn_wrapper = FL(act)
                btn_wrapper.setPadding(
                    AndroidUtilities.dp(btn_margin_dp), AndroidUtilities.dp(8),
                    AndroidUtilities.dp(btn_margin_dp), AndroidUtilities.dp(btn_margin_dp)
                )
                try:
                    btn_wrapper.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                except Exception:
                    pass
                btn_wrapper.setVisibility(View.GONE)
                self._submit_wrapper_ref[0] = btn_wrapper

                submit_btn = FL(act)
                submit_btn.setClickable(True)
                submit_btn.setFocusable(True)
                # MD3 FilledButton: fully rounded corner 100dp
                try:
                    base = Theme.getColor(Theme.key_featuredStickers_addButton)
                    pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
                    submit_btn.setBackground(
                        Theme.createSimpleSelectorRoundRectDrawable(AndroidUtilities.dp(100), base, pressed)
                    )
                except Exception:
                    pass
                submit_btn.setPadding(0, AndroidUtilities.dp(16), 0, AndroidUtilities.dp(16))

                # MD3 labelLarge: 14sp medium
                submit_lbl = TextView(act)
                submit_lbl.setText(str(strings.suggest_submit_btn))
                submit_lbl.setTextSize(TV.COMPLEX_UNIT_DIP, 14)
                submit_lbl.setTypeface(AndroidUtilities.bold())
                submit_lbl.setGravity(Gravity.CENTER)
                try:
                    submit_lbl.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
                except Exception:
                    submit_lbl.setTextColor(0xFFFFFFFF)

                submit_btn.addView(submit_lbl, FL.LayoutParams(-1, -2, Gravity.CENTER))
                btn_wrapper.addView(submit_btn, FL.LayoutParams(-1, AndroidUtilities.dp(btn_height_dp)))

                btn_lp = FrameLayout.LayoutParams(-1, -2)
                btn_lp.gravity = Gravity.BOTTOM
                root.addView(btn_wrapper, btn_lp)

                # push scroll content above the button
                content.setPadding(
                    content.getPaddingLeft(), content.getPaddingTop(),
                    content.getPaddingRight(), content.getPaddingBottom() + bottom_padding
                )

                self_ref_submit = self
                submit_btn.setOnClickListener(OnClickListener(lambda v: self_ref_submit._do_submit()))
                self._submit_btn_ref = submit_btn
                self._submit_lbl_ref[0] = submit_lbl
            except Exception as e:
                log(f"suggest: submit_btn error: {e}")

            self._attach_keyboard_scroll(act, root)
            self.content_view = root

            # if restoring a draft, show fields immediately (no file picked yet)
            if self._pending_draft:
                self._show_fields_section(act)
                self._show_submit_btn(act)

            return root
        except Exception as e:
            log(f"suggest: beforeCreateView build error: {e}")
            return None


def show_suggest_fragment(repo_data: dict, plugin=None):
    try:
        fragment = get_last_fragment()
        if not fragment:
            return

        rm_rid = "default"
        try:
            repometa = repo_data.get("repometa") if isinstance(repo_data, dict) else None
            if isinstance(repometa, dict):
                rm_rid = repometa.get("rm_rid") or "default"
        except Exception:
            pass

        if _has_draft(rm_rid):
            act = fragment.getParentActivity()
            if act:
                from ui.alert import AlertDialogBuilder

                def _open_with_draft():
                    draft = _load_draft(rm_rid)
                    _do_open_suggest(repo_data, plugin, rm_rid, draft)

                def _open_fresh():
                    _clear_draft(rm_rid)
                    _do_open_suggest(repo_data, plugin, rm_rid, None)

                builder = AlertDialogBuilder(act)
                builder.set_title(str(strings.suggest_save_title))
                builder.set_message(str(strings.suggest_save_message))
                builder.set_positive_button(str(strings.suggest_save_restore), lambda b, w: (_open_with_draft(), b.dismiss()))
                builder.set_negative_button(str(strings.suggest_save_reset), lambda b, w: (_open_fresh(), b.dismiss()))
                builder.make_button_red(AlertDialogBuilder.BUTTON_NEGATIVE)
                builder.show()
                return

        _do_open_suggest(repo_data, plugin, rm_rid, None)
    except Exception as e:
        log(f"suggest: show_suggest_fragment error: {e}")


def _do_open_suggest(repo_data: dict, plugin, rm_rid: str, draft):
    try:
        fragment = get_last_fragment()
        if not fragment:
            return
        delegate = SuggestFragment(repo_data, plugin)
        delegate._rm_rid = rm_rid
        if draft:
            delegate._pending_description[0] = draft.get("description") or None
            delegate._pending_draft = draft
        new_fragment = UniversalFragment(delegate)
        fragment.presentFragment(new_fragment)
        try:
            new_fragment.setTitle(strings.suggest_title, False, 0)
            action_bar = new_fragment.getActionBar()
            if action_bar:
                action_bar.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray))
                try:
                    back_icon = getattr(R_tg.drawable, "ic_ab_back", 0)
                    if back_icon:
                        action_bar.setBackButtonImage(back_icon)
                        action_bar.setBackButtonContentDescription(strings.suggest_back_button)
                        try:
                            back_button = action_bar.getBackButton()
                            if back_button:
                                def _on_back_click(v):
                                    f = get_last_fragment()
                                    if f:
                                        f.finishFragment()
                                back_button.setOnClickListener(OnClickListener(_on_back_click))
                        except Exception:
                            pass
                except Exception as e:
                    log(f"suggest: back button error: {e}")
            delegate._fragment_ref[0] = new_fragment
        except Exception as e:
            log(f"suggest: actionBar setup error: {e}")
    except Exception as e:
        log(f"suggest: _do_open_suggest error: {e}")