# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from android.view import Gravity, MotionEvent, View
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


def _apply_press_scale(view):
    try:
        class _TouchListener(dynamic_proxy(View.OnTouchListener)):
            def __init__(self):
                super().__init__()

            def onTouch(self, v, event):
                try:
                    action = event.getActionMasked()
                    if action == MotionEvent.ACTION_DOWN:
                        v.animate().scaleX(0.96).scaleY(0.96).setDuration(80).start()
                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        v.animate().scaleX(1.0).scaleY(1.0).setDuration(160).start()
                except Exception:
                    pass
                return False

        view.setOnTouchListener(_TouchListener())
    except Exception as e:
        log(f"suggest: _apply_press_scale error: {e}")


def _make_upload_card(act):
    dp = AndroidUtilities.dp

    try:
        from android.graphics.drawable import GradientDrawable
        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(dp(16))
        card_bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
        try:
            card_bg.setStroke(
                dp(1),
                Theme.getColor(Theme.key_windowBackgroundWhiteGrayText) & 0x30FFFFFF | 0x18000000
            )
        except Exception as e:
            log(f"suggest: card stroke error: {e}")
    except Exception as e:
        log(f"suggest: card_bg error: {e}")
        card_bg = None

    card = FrameLayout(act)
    card.setClickable(True)
    card.setFocusable(True)
    card.setMinimumHeight(dp(120))
    if card_bg:
        card.setBackground(card_bg)
    else:
        card.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite))

    inner = LinearLayout(act)
    inner.setOrientation(LinearLayout.VERTICAL)
    inner.setGravity(Gravity.CENTER)
    inner.setPadding(dp(24), dp(28), dp(24), dp(28))

    icon_view = ImageView(act)
    icon_id = _resolve_icon("msg_archive")
    if icon_id:
        icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
    icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    inner.addView(icon_view, LayoutHelper.createLinear(36, 36, Gravity.CENTER_HORIZONTAL, 0, 0, 0, 12))

    label = TextView(act)
    label.setText(strings.suggest_upload_label)
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    label.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
    label.setGravity(Gravity.CENTER)
    inner.addView(label, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL))

    sub = TextView(act)
    sub.setText(strings.suggest_upload_sub)
    sub.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
    sub.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    sub.setGravity(Gravity.CENTER)
    inner.addView(sub, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_HORIZONTAL, 0, 4, 0, 0))

    card.addView(inner, FrameLayout.LayoutParams(-1, -2))
    return card


def _make_selected_file_card(act, file_name, file_size_bytes=None):
    dp = AndroidUtilities.dp

    try:
        from android.graphics.drawable import GradientDrawable
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(10))
        bg.setColor(Theme.getColor(Theme.key_featuredStickers_addButton) & 0x1AFFFFFF | 0x1A000000)
        try:
            bg.setStroke(
                dp(1),
                Theme.getColor(Theme.key_featuredStickers_addButton) & 0x40FFFFFF | 0x20000000
            )
        except Exception:
            pass
    except Exception as e:
        log(f"suggest: selected card bg error: {e}")
        bg = None

    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setPadding(dp(12), dp(10), dp(12), dp(10))
    if bg:
        row.setBackground(bg)

    icon_view = ImageView(act)
    icon_id = _resolve_icon("msg_sendfile")
    if icon_id:
        icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
    icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    row.addView(icon_view, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

    name_tv = TextView(act)
    name_tv.setText(file_name)
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
    name_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
    name_tv.setSingleLine(True)
    try:
        from android.text import TextUtils
        name_tv.setEllipsize(TextUtils.TruncateAt.MIDDLE)
    except Exception as e:
        log(f"suggest: ellipsize error: {e}")
    row.addView(name_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    if file_size_bytes is not None:
        size_tv = TextView(act)
        size_tv.setText(_format_file_size(file_size_bytes))
        size_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        size_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        size_tv.setGravity(Gravity.CENTER_VERTICAL)
        row.addView(size_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

    return row


def _animate_card_transition(upload_card, selected_container, rules_tv=None):
    try:
        from android.animation import AnimatorSet, ObjectAnimator, Animator, ValueAnimator
        from android.view.animation import DecelerateInterpolator, OvershootInterpolator, AccelerateDecelerateInterpolator
        from android.view import ViewGroup
        from java import dynamic_proxy

        dp = AndroidUtilities.dp

        # measure upload_card real height so we can collapse it smoothly
        upload_card.measure(
            ViewGroup.MeasureSpec.makeMeasureSpec(upload_card.getWidth(), ViewGroup.MeasureSpec.EXACTLY),
            ViewGroup.MeasureSpec.makeMeasureSpec(0, ViewGroup.MeasureSpec.UNSPECIFIED),
        )
        from_h = upload_card.getMeasuredHeight()

        # upload card: fade out
        out_alpha = ObjectAnimator.ofFloat(upload_card, "alpha", 1.0, 0.0)
        out_alpha.setDuration(160)
        out_alpha.setInterpolator(DecelerateInterpolator())

        # collapse upload_card height to 0 so content below rises naturally
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
        collapse.setDuration(300)
        collapse.setStartDelay(80)
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

        # selected card: fade in + slide up from small offset (content already rising)
        in_alpha = ObjectAnimator.ofFloat(selected_container, "alpha", 0.0, 1.0)
        in_alpha.setDuration(240)
        in_alpha.setStartDelay(140)
        in_alpha.setInterpolator(DecelerateInterpolator())

        in_ty = ObjectAnimator.ofFloat(selected_container, "translationY", float(dp(16)), 0.0)
        in_ty.setDuration(300)
        in_ty.setStartDelay(120)
        in_ty.setInterpolator(OvershootInterpolator(1.4))

        animators = [out_alpha, collapse, in_alpha, in_ty]

        # rules_tv follows: same rise, slight delay after selected card
        if rules_tv is not None:
            rules_alpha = ObjectAnimator.ofFloat(rules_tv, "alpha", 0.0, 1.0)
            rules_alpha.setDuration(260)
            rules_alpha.setStartDelay(200)
            rules_alpha.setInterpolator(DecelerateInterpolator())

            rules_ty = ObjectAnimator.ofFloat(rules_tv, "translationY", float(dp(16)), 0.0)
            rules_ty.setDuration(300)
            rules_ty.setStartDelay(180)
            rules_ty.setInterpolator(DecelerateInterpolator(1.4))

            rules_tv.setAlpha(0.0)
            rules_tv.setTranslationY(float(dp(16)))

            animators.extend([rules_alpha, rules_ty])

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

    try:
        from android.graphics.drawable import GradientDrawable
        bg = GradientDrawable()
        bg.setShape(GradientDrawable.RECTANGLE)
        bg.setCornerRadius(dp(10))
        bg.setColor(0)
        try:
            bg.setStroke(
                dp(1),
                Theme.getColor(Theme.key_featuredStickers_addButton) & 0x60FFFFFF | 0x30000000
            )
        except Exception:
            pass
    except Exception as e:
        log(f"suggest: add_another bg error: {e}")
        bg = None

    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER)
    if bg:
        row.setBackground(bg)

    # 123
    lp_height = card_height_px if card_height_px > 0 else dp(40)

    icon_view = ImageView(act)
    icon_id = _resolve_icon("msg_addbot")
    if icon_id:
        icon_view.setImageResource(icon_id)
        icon_view.setColorFilter(Theme.getColor(Theme.key_featuredStickers_addButton))
    icon_view.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    row.addView(icon_view, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 8, 0))

    label = TextView(act)
    label.setText(strings.suggest_add_another_file)
    label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
    label.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
    label.setGravity(Gravity.CENTER_VERTICAL)
    row.addView(label, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

    return row, lp_height


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

    def onFragmentCreate(self, *_):
        try:
            rm_rid = None
            repometa = self._repo_data.get("repometa") if isinstance(self._repo_data, dict) else None
            if isinstance(repometa, dict):
                rm_rid = repometa.get("rm_rid")
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
            self._selected_uri = uri
            self._selected_name = name
            self._selected_size = size
        else:
            self._extra_uris.append((uri, name, size))

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
                    _animate_card_transition(upload_card, container, self._rules_tv_ref[0])

                    self._refresh_add_another_btn(act, container)
                else:
                    # extra file: slide new card in from random side, slide button down out
                    selected = _make_selected_file_card(act, name, size)
                    btn = self._add_another_btn_ref[0]

                    import random
                    from_left = random.choice((True, False))

                    if btn is not None:
                        idx = container.indexOfChild(btn)
                        insert_idx = idx if idx >= 0 else -1
                    else:
                        insert_idx = -1

                    if insert_idx >= 0:
                        container.addView(selected, insert_idx, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))
                    else:
                        container.addView(selected, LayoutHelper.createLinear(-1, -2, 0, 4, 0, 0))

                    try:
                        from android.animation import AnimatorSet, ObjectAnimator, Animator
                        from android.view.animation import DecelerateInterpolator, AccelerateInterpolator

                        screen_w = float(act.getResources().getDisplayMetrics().widthPixels)
                        slide_from = -screen_w if from_left else screen_w

                        selected.setAlpha(0.0)
                        selected.setTranslationX(slide_from)

                        card_in_tx = ObjectAnimator.ofFloat(selected, "translationX", slide_from, 0.0)
                        card_in_tx.setDuration(300)
                        card_in_tx.setInterpolator(DecelerateInterpolator(1.4))

                        card_in_a = ObjectAnimator.ofFloat(selected, "alpha", 0.0, 1.0)
                        card_in_a.setDuration(200)
                        card_in_a.setInterpolator(DecelerateInterpolator())

                        animators = [card_in_tx, card_in_a]

                        if btn is not None:
                            btn_out_ty = ObjectAnimator.ofFloat(btn, "translationY", 0.0, float(AndroidUtilities.dp(48)))
                            btn_out_ty.setDuration(220)
                            btn_out_ty.setInterpolator(AccelerateInterpolator())

                            btn_out_a = ObjectAnimator.ofFloat(btn, "alpha", 1.0, 0.0)
                            btn_out_a.setDuration(180)
                            btn_out_a.setInterpolator(AccelerateInterpolator())

                            animators.extend([btn_out_ty, btn_out_a])

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

                        # clear ref so _refresh_add_another_btn won't remove it early
                        self._add_another_btn_ref[0] = None

                        aset.addListener(_ExtraAnimEnd())
                        aset.start()
                    except Exception as e:
                        log(f"suggest: extra file anim error: {e}")
                        if btn is not None:
                            container.removeView(btn)
                            self._add_another_btn_ref[0] = None
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
        allow_multi = False
        if isinstance(sp, dict):
            allow_multi = bool(sp.get("settings", {}).get("allow_multi_files", False))

        total_files = 1 + len(self._extra_uris)
        if not allow_multi or total_files >= _MAX_FILES:
            return

        dp = AndroidUtilities.dp

        # measure selected file card height for matching
        card_h = dp(40)
        try:
            from android.view import ViewGroup
            first_child = container.getChildAt(0)
            if first_child is not None:
                first_child.measure(
                    ViewGroup.MeasureSpec.makeMeasureSpec(0, ViewGroup.MeasureSpec.UNSPECIFIED),
                    ViewGroup.MeasureSpec.makeMeasureSpec(0, ViewGroup.MeasureSpec.UNSPECIFIED),
                )
                measured = first_child.getMeasuredHeight()
                if measured > 0:
                    card_h = measured
        except Exception as e:
            log(f"suggest: measure card height error: {e}")

        btn, btn_h = _make_add_another_card(act, card_h)
        btn.setClickable(True)
        btn.setFocusable(True)

        def _on_add_click(v):
            _launch_file_picker(act, _PICK_EXTRA_REQUEST_CODE)

        btn.setOnClickListener(OnClickListener(_on_add_click))
        _apply_press_scale(btn)

        lp = LinearLayout.LayoutParams(-1, btn_h)
        lp.topMargin = AndroidUtilities.dp(4)
        container.addView(btn, lp)
        self._add_another_btn_ref[0] = btn

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

            content = LinearLayout(act)
            content.setOrientation(LinearLayout.VERTICAL)
            content.setPadding(dp(16), dp(16), dp(16), dp(16))

            try:
                title_tv = TextView(act)
                title_tv.setText(str(strings.suggest_submit_title))
                title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                title_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                title_tv.setTypeface(title_tv.getTypeface(), 1)
                title_tv.setGravity(Gravity.START)
                content.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))
            except Exception as e:
                log(f"suggest: title_tv error: {e}")

            outer = LinearLayout(act)
            outer.setOrientation(LinearLayout.VERTICAL)

            upload_card = _make_upload_card(act)
            self._upload_card_ref[0] = upload_card

            selected_container = LinearLayout(act)
            selected_container.setOrientation(LinearLayout.VERTICAL)
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
            _apply_press_scale(upload_card)

            selected_container.setClickable(True)
            selected_container.setFocusable(True)
            selected_container.setOnClickListener(OnClickListener(_on_card_click))
            _apply_press_scale(selected_container)

            outer.addView(upload_card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))
            outer.addView(selected_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))
            content.addView(outer, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))

            try:
                config = {}
                sp = self._suggest_config
                if isinstance(sp, dict):
                    config = sp.get("config", {})

                rules = config.get("rules", "")
                rules_name = config.get("rules_name", "")

                if rules:
                    if rules_name:
                        rules_raw = f"Please read the plugin approval rules for this repository: [{rules_name}]({rules})"
                    else:
                        rules_raw = f"Please read the plugin approval rules for this repository: {rules}"
                else:
                    rules_raw = str(strings.suggest_no_rules)

                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod

                rules_tv = TextView(act)
                rules_tv.setText(LocaleUtils.fullyFormatText(rules_raw))
                rules_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                rules_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                rules_tv.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                rules_tv.setMovementMethod(LinkMovementMethod.getInstance())
                rules_tv.setGravity(Gravity.START)
                self._rules_tv_ref[0] = rules_tv
                content.addView(rules_tv, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 0))
            except Exception as e:
                log(f"suggest: rules_tv error: {e}")

            scroll.addView(content, LayoutHelper.createScroll(-1, -2, 0))
            root.addView(scroll, FrameLayout.LayoutParams(-1, -1))

            self.content_view = root
            return root
        except Exception as e:
            log(f"suggest: beforeCreateView build error: {e}")
            return None


def show_suggest_fragment(repo_data: dict, plugin=None):
    try:
        fragment = get_last_fragment()
        if not fragment:
            return
        delegate = SuggestFragment(repo_data, plugin)
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
        log(f"suggest: show_suggest_fragment error: {e}")