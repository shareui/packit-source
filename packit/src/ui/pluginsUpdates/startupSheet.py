import threading
import time

from android.view import Gravity, MotionEvent, View
from android.widget import FrameLayout, LinearLayout, ScrollView, TextView, ImageView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment, run_on_queue

try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    log(f"startupSheet: import BottomSheet/Theme failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView
except Exception as e:
    log(f"startupSheet: import LayoutHelper/BackupImageView failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, ApplicationLoader, ImageLocation, MediaDataController
except Exception as e:
    log(f"startupSheet: import AndroidUtilities failed: {e}")

try:
    from elyx import strings, settings
except Exception as e:
    log(f"startupSheet: import elyx failed: {e}")

from .fragment import (
    _get_repos, _check_updates, _filter_ignored,
    _ignore_until_next, _ignore_forever,
)

_STICKER_RETRY_DELAY = 2.0


def _try_load_sticker(iv, icon_str: str, size_dp: int) -> bool:
    try:
        if not icon_str or "/" not in icon_str:
            return False
        pack_name, index_str = icon_str.split("/", 1)
        sticker_index = int(index_str)
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
        if ss and getattr(ss, "documents", None) and ss.documents.size() > sticker_index:
            doc = ss.documents.get(sticker_index)
            iv.setImage(
                ImageLocation.getForDocument(doc),
                f"{size_dp}_{size_dp}",
                None, None, 0, 1
            )
            return True
        try:
            mdc.loadStickersByEmojiOrName(pack_name, False, False)
        except Exception:
            pass
        return False
    except Exception as e:
        log(f"startupSheet: _try_load_sticker error: {e}")
        return False


def _schedule_sticker_retry(iv, icon_str: str, size_dp: int):
    def _retry():
        time.sleep(_STICKER_RETRY_DELAY)
        run_on_ui_thread(lambda: _try_load_sticker(iv, icon_str, size_dp))
    threading.Thread(target=_retry, daemon=True).start()


def _make_state_chip(act, state: str):
    import ctypes
    _STATE_COLOR_KEYS = {
        "release": "key_color_green",
        "beta":    "key_color_orange",
        "alpha":   "key_color_red",
    }
    color_key = _STATE_COLOR_KEYS.get(state.lower(), "key_windowBackgroundWhiteGrayText")
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
    tv.setText(state)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    tv.setTextColor(text_color)
    tv.setBackground(bg)
    tv.setPadding(
        AndroidUtilities.dp(7), AndroidUtilities.dp(3),
        AndroidUtilities.dp(7), AndroidUtilities.dp(3)
    )
    return tv


def _make_item_card(act, item: dict, plugin_ref, on_action):
    dp = AndroidUtilities.dp
    pid = item["id"]
    display_name = item.get("plugin_name") or pid
    icon_str = item.get("icon") or ""
    local_v = item.get("local_version") or ""
    repo_v = item.get("repo_version") or ""
    state = item.get("state") or ""
    repo_name = item.get("repo_name") or item.get("repo_id") or ""

    text_primary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
    text_gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
    try:
        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        accent_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
    except Exception:
        accent = 0xFF2196F3
        accent_pressed = accent
    try:
        gray_bg = Theme.getColor(Theme.key_windowBackgroundGray)
    except Exception:
        gray_bg = 0xFF303030

    icon_size_dp = 44

    card_bg = GradientDrawable()
    card_bg.setShape(GradientDrawable.RECTANGLE)
    card_bg.setCornerRadius(dp(14))
    try:
        card_bg.setColor(Theme.getColor(Theme.key_windowBackgroundWhite))
    except Exception:
        card_bg.setColor(0xFFFFFFFF)
    try:
        border_color = Theme.getColor(Theme.key_divider)
    except Exception:
        border_color = 0x33000000
    card_bg.setStroke(dp(1), border_color)

    outer = LinearLayout(act)
    outer.setOrientation(LinearLayout.VERTICAL)
    outer.setBackground(card_bg)
    outer.setClickable(True)
    outer.setFocusable(True)
    outer.setPadding(dp(14), dp(12), dp(14), dp(12))

    collapsed = LinearLayout(act)
    collapsed.setOrientation(LinearLayout.HORIZONTAL)
    collapsed.setGravity(Gravity.CENTER_VERTICAL)

    show_icon = bool(icon_str and icon_str != "Unknown" and "/" in icon_str)
    if show_icon:
        try:
            icon_view = BackupImageView(act)
            icon_view.setRoundRadius(dp(10))
            try:
                icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            icon_lp = LinearLayout.LayoutParams(dp(icon_size_dp), dp(icon_size_dp))
            icon_lp.rightMargin = dp(12)
            collapsed.addView(icon_view, icon_lp)
            loaded = _try_load_sticker(icon_view, icon_str, icon_size_dp)
            if not loaded:
                _schedule_sticker_retry(icon_view, icon_str, icon_size_dp)
        except Exception as e:
            log(f"startupSheet: icon error for '{pid}': {e}")

    center_col = LinearLayout(act)
    center_col.setOrientation(LinearLayout.VERTICAL)
    center_col.setGravity(Gravity.CENTER_VERTICAL)

    name_tv = TextView(act)
    name_tv.setText(display_name)
    name_tv.setTextColor(text_primary)
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    try:
        name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        pass
    name_tv.setSingleLine(True)
    center_col.addView(name_tv, LayoutHelper.createLinear(-1, -2))

    ver_tv = TextView(act)
    ver_tv.setText(f"{local_v} \u2192 {repo_v}")
    ver_tv.setTextColor(text_gray)
    ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    center_col.addView(ver_tv, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

    collapsed.addView(center_col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    from hook_utils import find_class as _fc
    try:
        R_tg = _fc("org.telegram.messenger.R")
        arrow_icon_id = getattr(R_tg.drawable, "arrow_more", 0)
    except Exception:
        arrow_icon_id = 0

    chevron = ImageView(act)
    chevron.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    if arrow_icon_id:
        chevron.setImageResource(arrow_icon_id)
    chevron.setColorFilter(text_gray)
    collapsed.addView(chevron, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

    outer.addView(collapsed, LayoutHelper.createLinear(-1, -2))

    expanded = LinearLayout(act)
    expanded.setOrientation(LinearLayout.VERTICAL)
    expanded.setVisibility(View.GONE)

    divider = View(act)
    try:
        divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
    except Exception:
        divider.setBackgroundColor(0x33000000)
    expanded.addView(divider, LayoutHelper.createLinear(-1, 1, 0, 10, 0, 10))

    ver_row = LinearLayout(act)
    ver_row.setOrientation(LinearLayout.HORIZONTAL)
    ver_row.setGravity(Gravity.CENTER_VERTICAL)

    ver_full_tv = TextView(act)
    ver_full_tv.setText(f"{local_v} \u2192 {repo_v}")
    ver_full_tv.setTextColor(text_gray)
    ver_full_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
    ver_row.addView(ver_full_tv, LayoutHelper.createLinear(-2, -2))

    if state:
        chip = _make_state_chip(act, state)
        chip_lp = LinearLayout.LayoutParams(-2, -2)
        chip_lp.leftMargin = dp(6)
        ver_row.addView(chip, chip_lp)

    expanded.addView(ver_row, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 4))

    if repo_name:
        repo_tv = TextView(act)
        repo_tv.setText(f"{repo_name} repository")
        repo_tv.setTextColor(text_gray)
        repo_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
        expanded.addView(repo_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 10))

    update_btn = FrameLayout(act)
    update_btn.setClickable(True)
    update_btn.setFocusable(True)
    update_btn.setBackground(
        Theme.createSimpleSelectorRoundRectDrawable(dp(10), accent, accent_pressed)
    )
    update_btn.setPadding(0, dp(10), 0, dp(10))

    update_tv = TextView(act)
    update_tv.setText(str(strings.startup_updates_update))
    update_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    update_tv.setGravity(Gravity.CENTER)
    update_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    try:
        update_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        pass
    update_btn.addView(update_tv, FrameLayout.LayoutParams(-1, -2))
    expanded.addView(update_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

    ignore_btn_bg = GradientDrawable()
    ignore_btn_bg.setShape(GradientDrawable.RECTANGLE)
    ignore_btn_bg.setCornerRadius(dp(10))
    ignore_btn_bg.setColor(gray_bg)

    ignore_btn = FrameLayout(act)
    ignore_btn.setClickable(True)
    ignore_btn.setFocusable(True)
    ignore_btn.setBackground(ignore_btn_bg)
    ignore_btn.setPadding(0, dp(10), 0, dp(10))

    ignore_tv = TextView(act)
    ignore_tv.setText(str(strings.startup_updates_ignore))
    ignore_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    ignore_tv.setGravity(Gravity.CENTER)
    ignore_tv.setTextColor(accent)
    try:
        ignore_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        pass
    ignore_btn.addView(ignore_tv, FrameLayout.LayoutParams(-1, -2))
    expanded.addView(ignore_btn, LayoutHelper.createLinear(-1, -2))

    outer.addView(expanded, LayoutHelper.createLinear(-1, -2))

    class _TouchListener(dynamic_proxy(View.OnTouchListener)):
        def __init__(self): super().__init__()
        def onTouch(self, v, event):
            try:
                action = event.getActionMasked()
                if action == MotionEvent.ACTION_DOWN:
                    v.animate().scaleX(0.97).scaleY(0.97).setDuration(100).start()
                elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    v.animate().scaleX(1.0).scaleY(1.0).setDuration(200).start()
            except Exception:
                pass
            return False

    outer.setOnTouchListener(_TouchListener())

    is_expanded = [False]

    def _toggle(v=None):
        is_expanded[0] = not is_expanded[0]
        try:
            chevron.animate().rotation(180.0 if is_expanded[0] else 0.0).setDuration(200).start()
        except Exception:
            chevron.setRotation(180.0 if is_expanded[0] else 0.0)

        if is_expanded[0]:
            expanded.setAlpha(0.0)
            expanded.setVisibility(View.VISIBLE)
            expanded.measure(
                View.MeasureSpec.makeMeasureSpec(outer.getWidth(), View.MeasureSpec.AT_MOST),
                View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED),
            )
            target_h = expanded.getMeasuredHeight()
            expanded.getLayoutParams().height = 0
            expanded.requestLayout()
            try:
                from android.animation import ValueAnimator, Animator

                class _UpdExp(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                    def onAnimationUpdate(self, a):
                        expanded.getLayoutParams().height = int(a.getAnimatedValue())
                        expanded.requestLayout()

                class _EndExp(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        expanded.getLayoutParams().height = -2
                        expanded.requestLayout()
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                anim = ValueAnimator.ofInt(0, target_h)
                anim.setDuration(220)
                anim.addUpdateListener(_UpdExp())
                anim.addListener(_EndExp())
                anim.start()
                expanded.animate().alpha(1.0).setDuration(220).start()
            except Exception:
                expanded.getLayoutParams().height = -2
                expanded.setAlpha(1.0)
                expanded.requestLayout()
        else:
            try:
                from android.animation import ValueAnimator, Animator
                start_h = expanded.getMeasuredHeight()

                class _UpdCol(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                    def onAnimationUpdate(self, a):
                        expanded.getLayoutParams().height = int(a.getAnimatedValue())
                        expanded.requestLayout()

                class _EndCol(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        expanded.setVisibility(View.GONE)
                        expanded.getLayoutParams().height = -2
                        expanded.setAlpha(1.0)
                        expanded.requestLayout()
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                anim = ValueAnimator.ofInt(start_h, 0)
                anim.setDuration(180)
                anim.addUpdateListener(_UpdCol())
                anim.addListener(_EndCol())
                anim.start()
                expanded.animate().alpha(0.0).setDuration(180).start()
            except Exception:
                expanded.setVisibility(View.GONE)

    outer.setOnClickListener(OnClickListener(_toggle))
    update_btn.setOnClickListener(OnClickListener(lambda v: on_action("update", item)))
    ignore_btn.setOnClickListener(OnClickListener(lambda v: on_action("ignore", item)))

    return outer


def _show_sheet(updates: list, plugin, on_sheet_closed=None):
    try:
        frag = get_last_fragment()
        if not frag:
            log("startupSheet: no fragment")
            if on_sheet_closed:
                on_sheet_closed(None)
            return
        act = frag.getParentActivity()
        if not act:
            log("startupSheet: no activity")
            if on_sheet_closed:
                on_sheet_closed(None)
            return
        resource_provider = frag.getResourceProvider()

        plugin_ref = [plugin]
        sheet = BottomSheet(act, False, resource_provider)
        sheet.fixNavigationBar()

        dp = AndroidUtilities.dp
        text_primary = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
        text_gray = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        try:
            accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        except Exception:
            accent = 0xFF2196F3
        try:
            gray_bg = Theme.getColor(Theme.key_windowBackgroundGray)
        except Exception:
            gray_bg = 0xFF303030

        scroll = ScrollView(act)
        scroll.setFillViewport(True)

        root = LinearLayout(act)
        root.setOrientation(LinearLayout.VERTICAL)
        root.setPadding(dp(16), dp(16), dp(16), dp(8))
        scroll.addView(root)

        title_tv = TextView(act)
        title_tv.setText(str(strings.startup_updates_title))
        title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
        title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        title_tv.setTextColor(text_primary)
        try:
            title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        root.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        subtitle_tv = TextView(act)
        subtitle_tv.setText(str(strings.startup_updates_subtitle))
        subtitle_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        subtitle_tv.setGravity(Gravity.CENTER_HORIZONTAL)
        subtitle_tv.setTextColor(text_gray)
        root.addView(subtitle_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 14))

        items_container = LinearLayout(act)
        items_container.setOrientation(LinearLayout.VERTICAL)
        root.addView(items_container, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 12))

        acted_items = []

        def _on_action(action: str, item: dict):
            acted_items.append((action, item))
            try:
                sheet.dismiss()
            except Exception:
                pass
            if on_sheet_closed:
                on_sheet_closed(acted_items)

        for item in updates:
            card = _make_item_card(act, item, plugin_ref, _on_action)
            card_lp = LinearLayout.LayoutParams(-1, -2)
            card_lp.bottomMargin = dp(8)
            items_container.addView(card, card_lp)

        ignore_all_btn = FrameLayout(act)
        ignore_all_btn.setClickable(True)
        ignore_all_btn.setFocusable(True)
        ia_bg = GradientDrawable()
        ia_bg.setShape(GradientDrawable.RECTANGLE)
        ia_bg.setCornerRadius(dp(12))
        ia_bg.setColor(gray_bg)
        ignore_all_btn.setBackground(ia_bg)
        ignore_all_btn.setPadding(0, dp(12), 0, dp(12))

        ignore_all_tv = TextView(act)
        ignore_all_tv.setText(str(strings.startup_updates_ignore_all))
        ignore_all_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        ignore_all_tv.setGravity(Gravity.CENTER)
        ignore_all_tv.setTextColor(accent)
        try:
            ignore_all_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        ignore_all_btn.addView(ignore_all_tv, FrameLayout.LayoutParams(-1, -2))

        def _ignore_all(v=None):
            try:
                pkg = ApplicationLoader.applicationContext.getPackageName()
                for it in updates:
                    _ignore_until_next(pkg, it["id"], it.get("repo_id", ""), it.get("repo_version", ""))
                sheet.dismiss()
                if on_sheet_closed:
                    on_sheet_closed(None)
            except Exception as e:
                log(f"startupSheet: _ignore_all error: {e}")

        ignore_all_btn.setOnClickListener(OnClickListener(_ignore_all))
        root.addView(ignore_all_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 6))

        close_btn = FrameLayout(act)
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        cl_bg = GradientDrawable()
        cl_bg.setShape(GradientDrawable.RECTANGLE)
        cl_bg.setCornerRadius(dp(12))
        cl_bg.setColor(gray_bg)
        close_btn.setBackground(cl_bg)
        close_btn.setPadding(0, dp(12), 0, dp(12))

        close_tv = TextView(act)
        close_tv.setText(str(strings.startup_updates_close))
        close_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
        close_tv.setGravity(Gravity.CENTER)
        close_tv.setTextColor(text_primary)
        try:
            close_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            pass
        close_btn.addView(close_tv, FrameLayout.LayoutParams(-1, -2))

        def _on_close(v=None):
            sheet.dismiss()
            if on_sheet_closed:
                on_sheet_closed(None)

        close_btn.setOnClickListener(OnClickListener(_on_close))
        root.addView(close_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

        sheet.setCustomView(scroll)
        sheet.show()
    except Exception as e:
        log(f"startupSheet: _show_sheet error: {e}")
        if on_sheet_closed:
            on_sheet_closed(None)


def _apply_actions_and_refresh(acted_items, plugin):
    try:
        pkg = ApplicationLoader.applicationContext.getPackageName()
        for action, item in (acted_items or []):
            if action == "ignore":
                _ignore_until_next(pkg, item["id"], item.get("repo_id", ""), item.get("repo_version", ""))
            elif action == "update":
                _do_install(item, plugin)
    except Exception as e:
        log(f"startupSheet: _apply_actions_and_refresh error: {e}")

    def task():
        try:
            time.sleep(1.5)
            pkg = ApplicationLoader.applicationContext.getPackageName()
            updates = _filter_ignored(pkg, _check_updates(pkg))
            if updates:
                run_on_ui_thread(lambda: _show_sheet(
                    updates, plugin,
                    on_sheet_closed=_make_closed_handler(plugin)
                ))
        except Exception as e:
            log(f"startupSheet: refresh task error: {e}")

    threading.Thread(target=task, daemon=True).start()


def _make_closed_handler(plugin):
    def on_closed(acted_items):
        if acted_items is None:
            # user closed or ignored all — no refresh
            return
        _apply_actions_and_refresh(acted_items, plugin)
    return on_closed


def _do_install(item: dict, plugin):
    pid = item["id"]
    repo_id = item.get("repo_id", "")
    repos = _get_repos()
    repo = None
    for r in repos:
        if str(r.get("id") or "") == repo_id:
            repo = r
            break
    if not repo:
        log(f"startupSheet: _do_install repo '{repo_id}' not found")
        return

    def task():
        try:
            from ...deeplinks.install import _resolvePluginsUrl
            from ...core import install_plugin
            import requests as _req

            plugins_url = _resolvePluginsUrl(repo)
            if not plugins_url:
                return

            r = _req.get(plugins_url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
            if r.status_code != 200:
                return

            data = r.json()
            plugins_raw = data.get("plugins", {})
            plugin_data = None
            all_plugins = []
            if isinstance(plugins_raw, dict):
                for _pid, info in plugins_raw.items():
                    if isinstance(info, dict):
                        all_plugins.append({"id": _pid, **info})
                info = plugins_raw.get(pid)
                if isinstance(info, dict):
                    plugin_data = {"id": pid, **info}
            elif isinstance(plugins_raw, list):
                all_plugins = [p for p in plugins_raw if isinstance(p, dict)]
                for p in plugins_raw:
                    if isinstance(p, dict) and p.get("id") == pid:
                        plugin_data = p
                        break

            if not plugin_data:
                return

            run_on_ui_thread(lambda: install_plugin(plugin_data, all_plugins=all_plugins, rm_rid=repo_id))
        except Exception as e:
            log(f"startupSheet: _do_install task error for '{pid}': {e}")

    run_on_queue(task)


def check_and_show_startup_updates(plugin=None):
    def task():
        try:
            pkg = ApplicationLoader.applicationContext.getPackageName()

            try:
                from ...utils.installIndex import purge_missing
                purge_missing()
            except Exception as e:
                log(f"startupSheet: purge_missing error: {e}")

            updates = _filter_ignored(pkg, _check_updates(pkg))
            if not updates:
                log("startupSheet: no updates found")
                return

            time.sleep(2.0)

            run_on_ui_thread(lambda: _show_sheet(
                updates, plugin,
                on_sheet_closed=_make_closed_handler(plugin)
            ))
        except Exception as e:
            log(f"startupSheet: check error: {e}")

    threading.Thread(target=task, daemon=True).start()
