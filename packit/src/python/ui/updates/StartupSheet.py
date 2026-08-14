# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import threading
import time

from android.view import Gravity, View
from android.widget import FrameLayout, LinearLayout, ScrollView, TextView, ImageView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android_utils import run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment, run_on_queue

try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    logx(f"startupSheet: import BottomSheet/Theme failed: {e}", False)
try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView
except Exception as e:
    logx(f"startupSheet: import LayoutHelper/BackupImageView failed: {e}", False)
try:
    from org.telegram.messenger import AndroidUtilities, ApplicationLoader, ImageLocation, MediaDataController
except Exception as e:
    logx(f"startupSheet: import AndroidUtilities failed: {e}", False)

try:
    from elyx import strings, settings
except Exception as e:
    logx(f"startupSheet: import elyx failed: {e}", False)

from .Fragment import (
    _get_repos, _check_updates, _filter_ignored,
    _ignore_until_next, _ignore_forever,
)

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
        card_bg = Theme.getColor(Theme.key_windowBackgroundGray)
    except Exception:
        card_bg = 0xFF303030

    expanded = [False]

    outer = LinearLayout(act)
    outer.setOrientation(LinearLayout.VERTICAL)
    outer.setClickable(True)
    outer.setFocusable(True)

    border = GradientDrawable()
    border.setShape(GradientDrawable.RECTANGLE)
    border.setCornerRadius(dp(14))
    border.setColor(card_bg)
    try:
        border.setStroke(dp(1), Theme.getColor(Theme.key_divider))
    except Exception:
        pass
    outer.setBackground(border)

    # header row: icon + name/version + state chip
    header_row = LinearLayout(act)
    header_row.setOrientation(LinearLayout.HORIZONTAL)
    header_row.setGravity(Gravity.CENTER_VERTICAL)
    header_row.setPadding(dp(14), dp(12), dp(14), dp(12))

    icon_size_dp = 40
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
            header_row.addView(icon_view, icon_lp)
            from ...utils.Stickers import load_sticker
            load_sticker(icon_view, icon_str, icon_size_dp)
        except Exception as e:
            logx(f"startupSheet: icon error for '{pid}': {e}", False)

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

    ver_row = LinearLayout(act)
    ver_row.setOrientation(LinearLayout.HORIZONTAL)
    ver_row.setGravity(Gravity.CENTER_VERTICAL)

    ver_tv = TextView(act)
    ver_tv.setText(f"{local_v} → {repo_v}")
    ver_tv.setTextColor(text_gray)
    ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 12)
    ver_row.addView(ver_tv, LayoutHelper.createLinear(-2, -2))

    if state:
        chip = _make_state_chip(act, state)
        chip_lp = LinearLayout.LayoutParams(-2, -2)
        chip_lp.leftMargin = dp(6)
        ver_row.addView(chip, chip_lp)

    center_col.addView(ver_row, LayoutHelper.createLinear(-1, -2, 0, 2, 0, 0))

    header_row.addView(center_col, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    chevron = ImageView(act)
    chevron.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    try:
        from hook_utils import find_class as _fc
        R_tg = _fc("org.telegram.messenger.R")
        chevron.setImageResource(getattr(R_tg.drawable, "arrow_more", 0))
    except Exception:
        pass
    chevron.setColorFilter(text_gray)
    header_row.addView(chevron, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

    outer.addView(header_row, LayoutHelper.createLinear(-1, -2))

    # divider
    divider = View(act)
    try:
        divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
    except Exception:
        divider.setBackgroundColor(0x33000000)
    divider.setVisibility(View.GONE)
    outer.addView(divider, LayoutHelper.createLinear(-1, 1, 14, 0, 14, 0))

    # buttons area
    btns = LinearLayout(act)
    btns.setOrientation(LinearLayout.VERTICAL)
    btns.setPadding(dp(14), dp(10), dp(14), dp(12))
    btns.setVisibility(View.GONE)

    btn_height = dp(42)

    update_btn = FrameLayout(act)
    update_btn.setClickable(True)
    update_btn.setFocusable(True)
    update_btn_bg = [Theme.createSimpleSelectorRoundRectDrawable(dp(28), accent, accent_pressed)]
    update_btn.setBackground(update_btn_bg[0])

    update_tv = TextView(act)
    update_tv.setText(str(strings.startup_updates_update))
    update_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    update_tv.setGravity(Gravity.CENTER)
    update_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
    try:
        update_tv.setTypeface(AndroidUtilities.bold())
    except Exception:
        pass
    update_btn.addView(update_tv, FrameLayout.LayoutParams(-1, -1))

    update_icon_iv = ImageView(act)
    update_icon_iv.setScaleType(ImageView.ScaleType.CENTER)
    update_icon_iv.setVisibility(View.GONE)
    update_btn.addView(update_icon_iv, FrameLayout.LayoutParams(-1, -1))

    update_lp = LinearLayout.LayoutParams(-1, btn_height)
    update_lp.bottomMargin = dp(6)
    btns.addView(update_btn, update_lp)

    ignore_btn = FrameLayout(act)
    ignore_btn.setClickable(True)
    ignore_btn.setFocusable(True)
    try:
        ignore_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            dp(28),
            Theme.getColor(Theme.key_graySection),
            Theme.getColor(Theme.key_listSelector)
        ))
    except Exception:
        ignore_btn_bg = GradientDrawable()
        ignore_btn_bg.setShape(GradientDrawable.RECTANGLE)
        ignore_btn_bg.setCornerRadius(dp(28))
        ignore_btn_bg.setColor(card_bg)
        ignore_btn.setBackground(ignore_btn_bg)

    ignore_tv = TextView(act)
    ignore_tv.setText(str(strings.startup_updates_ignore))
    ignore_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
    ignore_tv.setGravity(Gravity.CENTER)
    ignore_tv.setTextColor(accent)
    try:
        ignore_tv.setTypeface(AndroidUtilities.bold())
    except Exception:
        pass
    ignore_btn.addView(ignore_tv, FrameLayout.LayoutParams(-1, -1))
    ignore_lp = LinearLayout.LayoutParams(-1, btn_height)
    btns.addView(ignore_btn, ignore_lp)

    outer.addView(btns, LayoutHelper.createLinear(-1, -2))

    def _set_update_btn_state(state: str):
        # state: "loading" | "done" | "idle"
        try:
            update_btn.setEnabled(state == "idle")
            update_btn.setClickable(state == "idle")
            if state == "idle":
                update_tv.setVisibility(View.VISIBLE)
                update_icon_iv.setVisibility(View.GONE)
                update_icon_iv.setImageDrawable(None)
                update_btn.setBackground(update_btn_bg[0])
            elif state == "loading":
                update_tv.setVisibility(View.GONE)
                update_icon_iv.setVisibility(View.VISIBLE)
                try:
                    from org.telegram.ui.Components import CircularProgressDrawable
                    icon_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                    d = CircularProgressDrawable(icon_color)
                    try:
                        d.size = float(dp(20))
                        d.thickness = float(dp(2))
                    except Exception:
                        pass
                    update_icon_iv.setImageDrawable(d)
                except Exception as e:
                    logx(f"startupSheet: spinner create error: {e}", False)
                    update_tv.setVisibility(View.VISIBLE)
                    update_icon_iv.setVisibility(View.GONE)
            elif state == "done":
                update_tv.setVisibility(View.GONE)
                update_icon_iv.setVisibility(View.VISIBLE)
                try:
                    from hook_utils import find_class as _fc
                    R_tg = _fc("org.telegram.messenger.R")
                    check_icon_id = getattr(R_tg.drawable, "msg_select", 0)
                except Exception:
                    check_icon_id = 0
                if check_icon_id:
                    update_icon_iv.setImageResource(check_icon_id)
                try:
                    icon_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                except Exception:
                    icon_color = 0xFFFFFFFF
                update_icon_iv.setColorFilter(icon_color)
        except Exception as e:
            logx(f"startupSheet: _set_update_btn_state error: {e}", False)

    update_btn.setOnClickListener(OnClickListener(lambda v: on_action("update", item, _set_update_btn_state)))
    ignore_btn.setOnClickListener(OnClickListener(lambda v: on_action("ignore", item, None)))

    def on_card_click(v):
        expanded[0] = not expanded[0]
        try:
            chevron.animate().rotation(180.0 if expanded[0] else 0.0).setDuration(200).start()
        except Exception:
            chevron.setRotation(180.0 if expanded[0] else 0.0)
        if expanded[0]:
            divider.setVisibility(View.VISIBLE)
            btns.setAlpha(0.0)
            btns.setVisibility(View.VISIBLE)
            btns.measure(
                View.MeasureSpec.makeMeasureSpec(outer.getWidth(), View.MeasureSpec.AT_MOST),
                View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
            )
            target_h = btns.getMeasuredHeight()
            btns.getLayoutParams().height = 0
            btns.requestLayout()
            try:
                from android.animation import ValueAnimator, Animator
                from java import dynamic_proxy

                class _UpdateExpand(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                    def onAnimationUpdate(self, a):
                        btns.getLayoutParams().height = int(a.getAnimatedValue())
                        btns.requestLayout()

                class _EndExpand(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        btns.getLayoutParams().height = -2
                        btns.requestLayout()
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                anim = ValueAnimator.ofInt(0, target_h)
                anim.setDuration(220)
                anim.addUpdateListener(_UpdateExpand())
                anim.addListener(_EndExpand())
                anim.start()
                btns.animate().alpha(1.0).setDuration(220).start()
            except Exception:
                btns.getLayoutParams().height = -2
                btns.setAlpha(1.0)
                btns.requestLayout()
        else:
            try:
                from android.animation import ValueAnimator, Animator
                from java import dynamic_proxy
                start_h = btns.getMeasuredHeight()

                class _UpdateCollapse(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                    def onAnimationUpdate(self, a):
                        btns.getLayoutParams().height = int(a.getAnimatedValue())
                        btns.requestLayout()

                class _EndCollapse(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        btns.setVisibility(View.GONE)
                        divider.setVisibility(View.GONE)
                        btns.getLayoutParams().height = -2
                        btns.setAlpha(1.0)
                        btns.requestLayout()
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                anim = ValueAnimator.ofInt(start_h, 0)
                anim.setDuration(180)
                anim.addUpdateListener(_UpdateCollapse())
                anim.addListener(_EndCollapse())
                anim.start()
                btns.animate().alpha(0.0).setDuration(180).start()
            except Exception:
                btns.setVisibility(View.GONE)
                divider.setVisibility(View.GONE)

    outer.setOnClickListener(OnClickListener(on_card_click))

    return outer


def _show_sheet(updates: list, plugin, on_sheet_closed=None):
    try:
        frag = get_last_fragment()
        if not frag:
            logx("startupSheet: no fragment", True)
            if on_sheet_closed:
                on_sheet_closed(None)
            return
        act = frag.getParentActivity()
        if not act:
            logx("startupSheet: no activity", True)
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

        total_items = len(updates)
        done_count = [0]
        acted_items = []

        def _check_all_done():
            logx(f"startupSheet: _check_all_done done={done_count[0]} total={total_items}", True)
            if done_count[0] >= total_items:
                logx("startupSheet: all items done, dismissing sheet", True)
                try:
                    sheet.dismiss()
                except Exception as e:
                    logx(f"startupSheet: _check_all_done dismiss error: {e}", False)

        def _on_action(action: str, item: dict, set_btn_state=None):
            pid = item.get("id", "?")
            logx(f"startupSheet: _on_action action='{action}' plugin='{pid}'", True)
            if action == "ignore":
                acted_items.append((action, item, set_btn_state))
                done_count[0] += 1
                logx(f"startupSheet: ignored '{pid}', done={done_count[0]}/{total_items}", True)
                try:
                    sheet.dismiss()
                except Exception:
                    pass
                if on_sheet_closed:
                    on_sheet_closed(acted_items)
            elif action == "update":
                original_set_state = set_btn_state

                def _wrapped_set_state(state: str, _orig=original_set_state):
                    logx(f"startupSheet: btn_state='{state}' plugin='{pid}'", True)
                    if _orig:
                        _orig(state)
                    if state == "done":
                        done_count[0] += 1
                        logx(f"startupSheet: update done '{pid}', done={done_count[0]}/{total_items}", True)
                        run_on_ui_thread(_check_all_done)

                acted_items.append((action, item, _wrapped_set_state))
                logx(f"startupSheet: starting install for '{pid}'", True)
                if on_sheet_closed:
                    on_sheet_closed(acted_items)

        for item in updates:
            card = _make_item_card(act, item, plugin_ref, _on_action)
            card_lp = LinearLayout.LayoutParams(-1, -2)
            card_lp.bottomMargin = dp(8)
            items_container.addView(card, card_lp)

        try:
            accent_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            accent_pressed = accent

        ignore_all_btn = FrameLayout(act)
        ignore_all_btn.setClickable(True)
        ignore_all_btn.setFocusable(True)
        ignore_all_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            dp(28), accent, accent_pressed
        ))
        ignore_all_btn.setPadding(0, dp(14), 0, dp(14))

        ignore_all_tv = TextView(act)
        ignore_all_tv.setText(str(strings.startup_updates_ignore_all))
        ignore_all_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        ignore_all_tv.setGravity(Gravity.CENTER)
        ignore_all_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        try:
            ignore_all_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        ignore_all_btn.addView(ignore_all_tv, FrameLayout.LayoutParams(-1, -2))

        def _ignore_all(v=None):
            try:
                for it in updates:
                    _ignore_until_next(None, it["id"], it.get("repo_id", ""), it.get("repo_version", ""))
                sheet.dismiss()
                if on_sheet_closed:
                    on_sheet_closed(None)
            except Exception as e:
                logx(f"startupSheet: _ignore_all error: {e}", False)

        ignore_all_btn.setOnClickListener(OnClickListener(_ignore_all))
        root.addView(ignore_all_btn, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 8))

        close_btn = FrameLayout(act)
        close_btn.setClickable(True)
        close_btn.setFocusable(True)
        close_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            dp(28),
            Theme.getColor(Theme.key_graySection),
            Theme.getColor(Theme.key_listSelector)
        ))
        close_btn.setPadding(0, dp(14), 0, dp(14))

        close_tv = TextView(act)
        close_tv.setText(str(strings.startup_updates_close))
        close_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        close_tv.setGravity(Gravity.CENTER)
        close_tv.setTextColor(accent)
        try:
            close_tv.setTypeface(AndroidUtilities.bold())
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
        logx(f"startupSheet: _show_sheet error: {e}", False)
        if on_sheet_closed:
            on_sheet_closed(None)


def _apply_actions_and_refresh(acted_items, plugin):
    has_updates = False
    has_ignores = False
    try:
        for entry in (acted_items or []):
            action, item = entry[0], entry[1]
            set_btn_state = entry[2] if len(entry) > 2 else None
            if action == "ignore":
                has_ignores = True
                _ignore_until_next(None, item["id"], item.get("repo_id", ""), item.get("repo_version", ""))
            elif action == "update":
                has_updates = True
                _do_install(item, plugin, set_btn_state)
    except Exception as e:
        logx(f"startupSheet: _apply_actions_and_refresh error: {e}", False)

    # if only updates were triggered (no ignores), skip refresh — installs are async
    if has_updates and not has_ignores:
        return

    def task():
        try:
            time.sleep(1.5)
            updates = _filter_ignored(None, _check_updates(None))
            if updates:
                run_on_ui_thread(lambda: _show_sheet(
                    updates, plugin,
                    on_sheet_closed=_make_closed_handler(plugin)
                ))
        except Exception as e:
            logx(f"startupSheet: refresh task error: {e}", False)

    threading.Thread(target=task, daemon=True).start()


def _make_closed_handler(plugin):
    def on_closed(acted_items):
        if acted_items is None:
            # user closed or ignored all — no refresh
            return
        _apply_actions_and_refresh(acted_items, plugin)
    return on_closed


def _do_install(item: dict, plugin, set_btn_state=None):
    pid = item["id"]
    repo_id = item.get("repo_id", "")
    repos = _get_repos()
    repo = None
    for r in repos:
        if str(r.get("id") or "") == repo_id:
            repo = r
            break
    if not repo:
        logx(f"startupSheet: _do_install repo '{repo_id}' not found", True)
        return

    if set_btn_state:
        run_on_ui_thread(lambda: set_btn_state("loading"))

    def task():
        try:
            from ...deeplinks.Install import _resolvePluginsUrl
            from ...utils.Paths import getPluginsDir
            from ...core.Core import install_plugin_silent
            import requests as _req
            import os

            plugins_url = _resolvePluginsUrl(repo)
            if not plugins_url:
                if set_btn_state:
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                return

            r = _req.get(plugins_url, timeout=20, headers={"User-Agent": "PackIt/1.0"})
            if r.status_code != 200:
                if set_btn_state:
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                return

            data = r.json()
            plugins_raw = data.get("plugins", {})
            plugin_data = None
            if isinstance(plugins_raw, dict):
                info = plugins_raw.get(pid)
                if isinstance(info, dict):
                    plugin_data = {"id": pid, **info}
            elif isinstance(plugins_raw, list):
                for p in plugins_raw:
                    if isinstance(p, dict) and p.get("id") == pid:
                        plugin_data = p
                        break

            if not plugin_data:
                if set_btn_state:
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                return

            url = plugin_data.get("link") or plugin_data.get("raw")
            if not url:
                logx(f"startupSheet: _do_install no link for '{pid}'", True)
                if set_btn_state:
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                return

            plugins_dir = getPluginsDir()
            try:
                os.makedirs(plugins_dir, exist_ok=True)
            except Exception:
                pass

            file_path = os.path.join(plugins_dir, f".temp_{pid}.plugin")
            dl = _req.get(url, timeout=30, headers={"User-Agent": "PackIt/1.0"})
            if dl.status_code != 200:
                logx(f"startupSheet: _do_install download failed for '{pid}': HTTP {dl.status_code}", True)
                if set_btn_state:
                    run_on_ui_thread(lambda: set_btn_state("idle"))
                return
            with open(file_path, "wb") as f:
                f.write(dl.content)

            def on_complete():
                if set_btn_state:
                    run_on_ui_thread(lambda: set_btn_state("done"))

            def on_error(error):
                logx(f"startupSheet: _do_install install error for '{pid}': {error}", True)
                if set_btn_state:
                    run_on_ui_thread(lambda: set_btn_state("idle"))

            install_plugin_silent(file_path, plugin_data, repo_id, on_complete=on_complete, on_error=on_error)
        except Exception as e:
            logx(f"startupSheet: _do_install task error for '{pid}': {e}", False)
            if set_btn_state:
                run_on_ui_thread(lambda: set_btn_state("idle"))

    run_on_queue(task)


def check_and_show_startup_updates(plugin=None):
    def task():
        try:
            try:
                from ...utils.InstallIndex import purge_missing
                purge_missing()
            except Exception as e:
                logx(f"startupSheet: purge_missing error: {e}", False)

            updates = _filter_ignored(None, _check_updates(None))
            if not updates:
                logx("startupSheet: no updates found", True)
                return

            time.sleep(2.0)

            run_on_ui_thread(lambda: _show_sheet(
                updates, plugin,
                on_sheet_closed=_make_closed_handler(plugin)
            ))
        except Exception as e:
            logx(f"startupSheet: check error: {e}", False)

    threading.Thread(target=task, daemon=True).start()