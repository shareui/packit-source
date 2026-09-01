# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import traceback
import threading
from android_utils import run_on_ui_thread
from android.view import Gravity, View, MotionEvent, VelocityTracker
from android.widget import FrameLayout, LinearLayout, TextView
from android.util import TypedValue
from android.animation import ValueAnimator, Animator
from android.graphics.drawable import GradientDrawable
from android.graphics import Color
from java import dynamic_proxy


def _make_icon_view(activity, icon_str: str, size_dp: int):
    from org.telegram.ui.Components import BackupImageView
    from org.telegram.messenger import AndroidUtilities
    if not icon_str or "/" not in icon_str:
        return None
    try:
        iv = BackupImageView(activity)
        iv.setRoundRadius(AndroidUtilities.dp(24))
        try:
            iv.getImageReceiver().setCrossfadeWithOldImage(True)
        except Exception:
            pass
        from ...utils.Stickers import load_sticker
        load_sticker(iv, icon_str, size_dp)
        return iv
    except Exception as _cython_exc_e:
        e = _cython_exc_e
        logx(f"ImportBottomSheet._make_icon_view: {e}", False)
        return None


def show(plugins: list, count: int, file_path: str = "", total_count: int = 0, settings: bool = True):
    # plugins: list of dicts with keys name, version, icon
    from client_utils import get_last_fragment
    fragment = get_last_fragment()
    if not fragment:
        return

    def _show():
        try:
            from elyx import strings
            from org.telegram.ui.ActionBar import BottomSheet, Theme
            from org.telegram.ui.Components import LayoutHelper
            from org.telegram.messenger import AndroidUtilities

            activity = fragment.getParentActivity()
            if not activity:
                return

            sheet = BottomSheet(activity, False, fragment.getResourceProvider())
            sheet.fixNavigationBar()

            pad_h = AndroidUtilities.dp(16)
            pad_top = AndroidUtilities.dp(20)

            size_dp = 112
            # slot = icon + gap of ~1 icon width so neighbors are barely visible
            slot_dp = int(size_dp * 1.8)

            try:
                gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            except Exception:
                gray_color = 0xFF888888

            try:
                text_color = Theme.getColor(Theme.key_windowBackgroundWhiteBlackText)
            except Exception:
                text_color = 0xFF000000

            n = len(plugins)

            # carousel state
            state = {"index": 0, "offset": 0.0, "anim": None}

            # outer wrapper: everything except the static buttons
            # touch covers entire this area
            outer = FrameLayout(activity)

            # content column: icon row + name + version + spacer + hint
            # clipping is disabled so adjacent icons bleed into chevron/button zones
            content_col = LinearLayout(activity)
            content_col.setOrientation(LinearLayout.VERTICAL)
            content_col.setGravity(Gravity.CENTER_HORIZONTAL)
            content_col.setClipChildren(False)
            content_col.setClipToPadding(False)

            outer_lp = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            )
            outer.addView(content_col, outer_lp)

            icon_row = FrameLayout(activity)
            icon_row.setClipChildren(False)
            icon_row.setClipToPadding(False)
            lp_row = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                AndroidUtilities.dp(size_dp)
            )
            lp_row.topMargin = pad_top
            content_col.addView(icon_row, lp_row)

            # icon_views holds the container (FrameLayout with iv + checkbox inside)
            icon_views = []
            icon_checkboxes = []
            slot_px_init = float(AndroidUtilities.dp(slot_dp))

            cb_size_dp = 21
            # negative margin so half the checkbox overhangs the icon edge
            cb_margin_dp = -(cb_size_dp // 2)

            for i, info in enumerate(plugins):
                iv = _make_icon_view(activity, info.get("icon") or "", size_dp)

                # container holds icon + checkbox, moves as one unit
                container = FrameLayout(activity)
                container.setClipChildren(False)
                container.setClipToPadding(False)

                lp_container = FrameLayout.LayoutParams(
                    AndroidUtilities.dp(size_dp),
                    AndroidUtilities.dp(size_dp),
                    Gravity.CENTER
                )
                container.setTranslationX(float(i) * slot_px_init)

                if iv is not None:
                    iv_lp = FrameLayout.LayoutParams(
                        AndroidUtilities.dp(size_dp),
                        AndroidUtilities.dp(size_dp),
                        Gravity.CENTER
                    )
                    container.addView(iv, iv_lp)
                else:
                    # fallback stub matching InstallPluginBottomSheet: circle 78dp, icon plugins_filled with 16dp padding
                    try:
                        from org.telegram.ui.ActionBar import Theme
                        from android.widget import ImageView
                        from android.graphics import PorterDuffColorFilter, PorterDuff
                        from org.telegram.messenger import R as R_tg

                        icon_view = ImageView(activity)
                        icon_view.setScaleType(ImageView.ScaleType.FIT_CENTER)
                        icon_view.setImageResource(R_tg.drawable.plugins_filled)
                        icon_view.setColorFilter(PorterDuffColorFilter(
                            Theme.getColor(Theme.key_featuredStickers_buttonText),
                            PorterDuff.Mode.SRC_IN
                        ))
                        p = AndroidUtilities.dp(16)
                        icon_view.setPadding(p, p, p, p)
                        icon_view.setBackground(Theme.createCircleDrawable(
                            AndroidUtilities.dp(78),
                            Theme.getColor(Theme.key_featuredStickers_addButton)
                        ))

                        stub_lp = FrameLayout.LayoutParams(
                            AndroidUtilities.dp(78),
                            AndroidUtilities.dp(78),
                            Gravity.CENTER
                        )
                        container.addView(icon_view, stub_lp)
                    except Exception as _cython_exc_e:
                        e = _cython_exc_e
                        logx(f"ImportBottomSheet: fallback icon error: {e}", False)

                cb = None
                try:
                    from org.telegram.ui.Components import CheckBox2
                    cb = CheckBox2(activity, cb_size_dp)
                    cb.setColor(
                        Theme.key_radioBackgroundChecked,
                        Theme.key_radioBackground,
                        Theme.key_checkboxCheck
                    )
                    cb.setDrawUnchecked(True)
                    cb.setDrawBackgroundAsArc(14)
                    cb.setChecked(True, False)
                    cb.setAlpha(0.0)
                    cb_lp = FrameLayout.LayoutParams(
                        AndroidUtilities.dp(cb_size_dp),
                        AndroidUtilities.dp(cb_size_dp),
                        Gravity.BOTTOM | Gravity.END
                    )
                    cb_lp.bottomMargin = AndroidUtilities.dp(cb_margin_dp)
                    cb_lp.rightMargin = AndroidUtilities.dp(cb_margin_dp)
                    container.addView(cb, cb_lp)
                except Exception as _cython_exc_e:
                    e = _cython_exc_e
                    logx(f"ImportBottomSheet: checkbox create error: {e}", False)

                icon_row.addView(container, lp_container)
                icon_views.append(container)
                icon_checkboxes.append(cb)

            label_row = FrameLayout(activity)
            label_row.setClipChildren(False)
            label_row.setClipToPadding(False)
            lp_labels = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp_labels.topMargin = AndroidUtilities.dp(12)
            content_col.addView(label_row, lp_labels)

            label_views = []
            for i, info in enumerate(plugins):
                label_block = LinearLayout(activity)
                label_block.setOrientation(LinearLayout.VERTICAL)
                label_block.setGravity(Gravity.CENTER_HORIZONTAL)

                name_tv = TextView(activity)
                name_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
                name_tv.setText(info.get("name") or "")
                try:
                    name_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                    name_tv.setTextColor(text_color)
                except Exception:
                    pass
                lp_name = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
                lp_name.leftMargin = pad_h
                lp_name.rightMargin = pad_h
                label_block.addView(name_tv, lp_name)

                ver_tv = TextView(activity)
                ver_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
                version_str = info.get("version") or ""
                ver_tv.setText(f"v{version_str}" if version_str else "")
                try:
                    ver_tv.setTextColor(gray_color)
                except Exception:
                    pass
                lp_ver = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
                lp_ver.topMargin = AndroidUtilities.dp(4)
                lp_ver.leftMargin = pad_h
                lp_ver.rightMargin = pad_h
                label_block.addView(ver_tv, lp_ver)

                lp_block = FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.WRAP_CONTENT,
                    Gravity.CENTER_HORIZONTAL
                )
                label_block.setTranslationX(float(i) * slot_px_init)
                label_row.addView(label_block, lp_block)
                label_views.append(label_block)

            # spacer
            spacer = View(activity)
            content_col.addView(spacer, LayoutHelper.createLinear(-1, 16))

            # hint
            hint_tv = TextView(activity)
            hint_tv.setGravity(Gravity.CENTER_HORIZONTAL)
            hint_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            try:
                hint_tv.setTextColor(gray_color)
            except Exception:
                pass
            lp_hint = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp_hint.leftMargin = pad_h
            lp_hint.rightMargin = pad_h
            content_col.addView(hint_tv, lp_hint)

            # horizontal fade overlays on both sides of icon_row
            try:
                bg_color = Theme.getColor(Theme.key_dialogBackground)
                transparent = Color.argb(0, (bg_color >> 16) & 0xFF, (bg_color >> 8) & 0xFF, bg_color & 0xFF)
                fade_w_dp = 44

                left_fade = FrameLayout(activity)
                left_grd = GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, [bg_color, transparent])
                left_fade.setBackground(left_grd)
                left_fade.setClickable(False)
                left_fade.setFocusable(False)
                lp_lf = FrameLayout.LayoutParams(
                    AndroidUtilities.dp(fade_w_dp),
                    AndroidUtilities.dp(size_dp),
                    Gravity.START | Gravity.TOP
                )
                lp_lf.topMargin = pad_top
                outer.addView(left_fade, lp_lf)

                right_fade = FrameLayout(activity)
                right_grd = GradientDrawable(GradientDrawable.Orientation.RIGHT_LEFT, [bg_color, transparent])
                right_fade.setBackground(right_grd)
                right_fade.setClickable(False)
                right_fade.setFocusable(False)
                lp_rf = FrameLayout.LayoutParams(
                    AndroidUtilities.dp(fade_w_dp),
                    AndroidUtilities.dp(size_dp),
                    Gravity.END | Gravity.TOP
                )
                lp_rf.topMargin = pad_top
                outer.addView(right_fade, lp_rf)
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"ImportBottomSheet: fade overlay error: {e}", False)
            # shrink factor per slot away from center (0.12 = 12% per step, min 0.6)
            scale_per_slot = 0.12

            def applyOffset(offset_px: float):
                slot_px = float(AndroidUtilities.dp(slot_dp))
                cur = state["index"]
                center = cur + offset_px / slot_px
                for i, container in enumerate(icon_views):
                    container.setTranslationX((i - cur) * slot_px - offset_px)
                    dist = abs(i - center)
                    s = max(0.6, 1.0 - scale_per_slot * dist)
                    container.setScaleX(s)
                    container.setScaleY(s)
                for i, lb in enumerate(label_views):
                    lb.setTranslationX((i - cur) * slot_px - offset_px)
                    dist = abs(i - center)
                    s = max(0.6, 1.0 - scale_per_slot * dist)
                    lb.setScaleX(s)
                    lb.setScaleY(s)

            applyOffset(0.0)

            # selection mode state
            sel_state = {"active": False, "checked": [True] * n}

            def updateHintText():
                if sel_state["active"]:
                    hint_count = sum(1 for c in sel_state["checked"] if c)
                else:
                    hint_count = count
                hint_tv.setText(str(strings["afp_import_hint"]).replace("{0}", str(hint_count)))

            updateHintText()

            def enterSelectionMode(idx: int):
                sel_state["active"] = True
                for i in range(n):
                    sel_state["checked"][i] = (i == idx)
                for i, cb in enumerate(icon_checkboxes):
                    if cb is None:
                        continue
                    cb.setChecked(sel_state["checked"][i], False)
                    cb.animate().alpha(1.0).setDuration(150).start()

            def exitSelectionMode():
                sel_state["active"] = False
                for cb in icon_checkboxes:
                    if cb is not None:
                        cb.animate().alpha(0.0).setDuration(150).start()

            def toggleCheck(idx: int):
                if not (0 <= idx < n):
                    return
                sel_state["checked"][idx] = not sel_state["checked"][idx]
                cb = icon_checkboxes[idx] if idx < len(icon_checkboxes) else None
                if cb is not None:
                    cb.setChecked(sel_state["checked"][idx], True)

            def snapTo(target_idx: int, vel_px: float):
                if state["anim"] is not None:
                    try:
                        state["anim"].cancel()
                    except Exception:
                        pass
                    state["anim"] = None

                slot_px = float(AndroidUtilities.dp(slot_dp))
                cur = state["index"]
                start_offset = state["offset"]
                end_offset = float(target_idx - cur) * slot_px

                anim = ValueAnimator.ofFloat(start_offset, end_offset)

                class _Update(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                    def __init__(self): super().__init__()
                    def onAnimationUpdate(self, va):
                        v = float(va.getAnimatedValue())
                        state["offset"] = v
                        applyOffset(v)

                class _End(dynamic_proxy(Animator.AnimatorListener)):
                    def __init__(self): super().__init__()
                    def onAnimationEnd(self, a, *args):
                        state["index"] = target_idx
                        state["offset"] = 0.0
                        applyOffset(0.0)
                        state["anim"] = None
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                anim.addUpdateListener(_Update())
                anim.addListener(_End())

                dist = abs(end_offset - start_offset)
                slot_px_d = float(AndroidUtilities.dp(slot_dp))
                max_off_d = float(n - 1 - cur) * slot_px_d
                min_off_d = -float(cur) * slot_px_d
                is_rubber = start_offset > max_off_d or start_offset < min_off_d
                if is_rubber:
                    dur = 320
                elif abs(vel_px) > 100:
                    dur = max(150, min(380, int(dist / abs(vel_px) * 1000)))
                else:
                    dur = 260

                from android.view.animation import DecelerateInterpolator
                anim.setDuration(dur)
                anim.setInterpolator(DecelerateInterpolator(1.8))
                anim.start()
                state["anim"] = anim

            # touch on entire outer area
            touch_state = {
                "down_x": 0.0,
                "down_y": 0.0,
                "tracking": False,
                "vt": None,
                "long_timer": None,
                "long_fired": False,
            }

            LONG_PRESS_MS = 1000

            class _TouchListener(dynamic_proxy(View.OnTouchListener)):
                def __init__(self): super().__init__()

                def onTouch(self, v, ev):
                    action = ev.getAction()

                    if action == MotionEvent.ACTION_DOWN:
                        auto_state["active"] = False
                        touch_state["down_x"] = ev.getX()
                        touch_state["down_y"] = ev.getY()
                        touch_state["tracking"] = False
                        touch_state["long_fired"] = False
                        touch_state["pressed_idx"] = state["index"]
                        vt = VelocityTracker.obtain()
                        touch_state["vt"] = vt
                        touch_state["at_edge"] = False
                        vt.addMovement(ev)
                        if state["anim"] is not None:
                            try:
                                state["anim"].cancel()
                            except Exception:
                                pass
                            state["anim"] = None

                        import threading as _th
                        import time as _time

                        # token per gesture — prevents stale timer from firing
                        token = object()
                        touch_state["long_token"] = token
                        touch_state["long_activated"] = False
                        touch_state["drag_select_active"] = False
                        touch_state["drag_select_dx"] = 0.0
                        touch_state["drag_select_origin_x"] = ev.getX()
                        touch_state["drag_scroll_running"] = False

                        def _timer_thread():
                            _time.sleep(LONG_PRESS_MS / 1000.0)
                            cur_token = touch_state.get("long_token")
                            if cur_token is not token:
                                return
                            if touch_state["tracking"]:
                                return
                            touch_state["long_activated"] = True

                            def _on_ui():
                                try:
                                    v.performHapticFeedback(1)
                                except Exception:
                                    pass
                                if sel_state["active"]:
                                    exitSelectionMode()
                                else:
                                    idx = touch_state.get("pressed_idx", state["index"])
                                    enterSelectionMode(idx)

                            run_on_ui_thread(_on_ui)

                        t = _th.Thread(target=_timer_thread, daemon=True)
                        touch_state["long_timer"] = t
                        t.start()
                        return True

                    elif action == MotionEvent.ACTION_MOVE:
                        vt = touch_state["vt"]
                        if vt is not None:
                            vt.addMovement(ev)
                        dx = ev.getX() - touch_state["down_x"]
                        dy = ev.getY() - touch_state["down_y"]

                        # drag-select mode: long press already fired, finger now dragging
                        if touch_state.get("long_activated") and sel_state["active"] and not touch_state["tracking"]:
                            drag_dx = ev.getX() - touch_state.get("drag_select_origin_x", touch_state["down_x"])
                            touch_state["drag_select_dx"] = drag_dx
                            touch_state["drag_select_active"] = True
                            # start scroll thread once
                            if not touch_state.get("drag_scroll_running"):
                                touch_state["drag_scroll_running"] = True
                                import threading as _dth
                                import time as _dtime
                                import math as _dmath

                                def _drag_scroll():
                                    last_idx = state["index"]
                                    # mark starting plugin as selected
                                    run_on_ui_thread(lambda: _select_current())
                                    while touch_state.get("drag_select_active"):
                                        ddx = touch_state.get("drag_select_dx", 0.0)
                                        if abs(ddx) < AndroidUtilities.dp(12):
                                            _dtime.sleep(0.05)
                                            continue
                                        # speed: max 1 step per ~56ms at full drag, slowest ~420ms (+30%)
                                        slot_px = float(AndroidUtilities.dp(slot_dp))
                                        max_drag = slot_px * 2.0
                                        ratio = min(1.0, abs(ddx) / max_drag)
                                        interval = (0.6 - ratio * 0.52) * 0.7
                                        _dtime.sleep(interval)
                                        if not touch_state.get("drag_select_active"):
                                            break
                                        direction = 1 if ddx > 0 else -1

                                        def _step(d=direction):
                                            cur = state["index"]
                                            target = cur + d
                                            if 0 <= target < n:
                                                snapTo(target, 0.0)
                                                sel_state["checked"][target] = not sel_state["checked"][target]
                                                cb = icon_checkboxes[target] if target < len(icon_checkboxes) else None
                                                if cb is not None:
                                                    cb.setChecked(sel_state["checked"][target], True)
                                                updateImportBtnText(True)
                                                updateHintText()
                                        run_on_ui_thread(_step)
                                    touch_state["drag_scroll_running"] = False

                                def _select_current():
                                    ci = state["index"]
                                    if 0 <= ci < n:
                                        sel_state["checked"][ci] = True
                                        cb = icon_checkboxes[ci] if ci < len(icon_checkboxes) else None
                                        if cb is not None:
                                            cb.setChecked(True, True)
                                        updateImportBtnText(True)
                                        updateHintText()

                                _dth.Thread(target=_drag_scroll, daemon=True).start()
                            return True

                        if not touch_state["tracking"]:
                            if abs(dx) > abs(dy) and abs(dx) > AndroidUtilities.dp(8):
                                touch_state["tracking"] = True
                                touch_state["long_token"] = None
                                touch_state["down_x"] = ev.getX()
                            return True
                        state["offset"] -= dx
                        touch_state["down_x"] = ev.getX()
                        slot_px = float(AndroidUtilities.dp(slot_dp))
                        max_off = float(n - 1 - state["index"]) * slot_px
                        min_off = -float(state["index"]) * slot_px
                        raw = state["offset"]
                        if raw > max_off:
                            over = raw - max_off
                            import math
                            limit = float(AndroidUtilities.dp(slot_dp)) * 0.55
                            damped = limit * (1.0 - math.exp(-over / limit))
                            state["offset"] = max_off + damped
                            if not touch_state.get("at_edge"):
                                touch_state["at_edge"] = True
                                try:
                                    v.performHapticFeedback(3)
                                except Exception:
                                    pass
                        elif raw < min_off:
                            over = min_off - raw
                            import math
                            limit = float(AndroidUtilities.dp(slot_dp)) * 0.55
                            damped = limit * (1.0 - math.exp(-over / limit))
                            state["offset"] = min_off - damped
                            if not touch_state.get("at_edge"):
                                touch_state["at_edge"] = True
                                try:
                                    v.performHapticFeedback(3)
                                except Exception:
                                    pass
                        else:
                            state["offset"] = raw
                            touch_state["at_edge"] = False
                            touch_state["edge_ticks"] = 0
                        applyOffset(state["offset"])
                        return True

                    elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                        was_tracking = touch_state["tracking"]
                        was_long_activated = touch_state.get("long_activated", False)
                        was_drag_select = touch_state.get("drag_select_active", False)
                        # stop drag-select scroll thread
                        touch_state["drag_select_active"] = False
                        # cancel token only on drag — short tap must let timer finish naturally
                        if was_tracking:
                            touch_state["long_token"] = None

                        vt = touch_state["vt"]
                        vel_x = 0.0
                        if vt is not None:
                            vt.computeCurrentVelocity(1000)
                            vel_x = float(vt.getXVelocity())
                            vt.recycle()
                            touch_state["vt"] = None

                        touch_state["tracking"] = False

                        if was_drag_select:
                            # snap to whichever icon carousel landed on
                            snapTo(state["index"], 0.0)
                            return True

                        if not was_tracking:
                            # short tap only — long press already handled on detection, not on release
                            if sel_state["active"] and not was_long_activated:
                                touch_state["long_token"] = None
                                toggleCheck(state["index"])
                            return False

                        slot_px = float(AndroidUtilities.dp(slot_dp))
                        cur = state["index"]
                        offset = state["offset"]

                        fling_thresh = float(AndroidUtilities.dp(400))
                        if vel_x < -fling_thresh:
                            target = min(n - 1, cur + 1)
                        elif vel_x > fling_thresh:
                            target = max(0, cur - 1)
                        else:
                            target = max(0, min(n - 1, int(round(cur + offset / slot_px))))

                        snapTo(target, vel_x)
                        return True

                    return False

            outer.setOnTouchListener(_TouchListener())

            # auto-scroll: starts after 1s if n > 1 and user never touched
            auto_state = {"active": True, "thread": None, "direction": 1}

            def _auto_scroll():
                import time
                time.sleep(1.0)
                if not auto_state["active"] or n < 2:
                    return
                while auto_state["active"]:
                    time.sleep(1.5)
                    if not auto_state["active"]:
                        break

                    def _step():
                        if not auto_state["active"]:
                            return
                        cur = state["index"]
                        d = auto_state["direction"]
                        target = cur + d
                        if target >= n:
                            auto_state["direction"] = -1
                            target = cur - 1
                        elif target < 0:
                            auto_state["direction"] = 1
                            target = cur + 1
                        if 0 <= target < n:
                            snapTo(target, 0.0)

                    run_on_ui_thread(_step)

            if n > 1:
                t = threading.Thread(target=_auto_scroll, daemon=True)
                auto_state["thread"] = t
                t.start()

            # root: outer (carousel + chevrons overlay) + static buttons
            root = LinearLayout(activity)
            root.setOrientation(LinearLayout.VERTICAL)

            root.addView(outer, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ))

            # import button
            try:
                from org.telegram.ui.Stories.recorder import ButtonWithCounterView
                import_btn = ButtonWithCounterView(activity, True, fragment.getResourceProvider())
                import_btn.setRound()
                import_btn_ref = [import_btn]

                def updateImportBtnText(animated: bool):
                    btn = import_btn_ref[0]
                    if btn is None:
                        return
                    if sel_state["active"]:
                        checked_count = sum(1 for c in sel_state["checked"] if c)
                        if checked_count == n:
                            btn.setText(str(strings["afp_import_still_all"]), animated)
                        else:
                            btn.setText(f"{str(strings['afp_import_btn'])} ({checked_count})", animated)
                    else:
                        btn.setText(f"{str(strings['afp_import_btn'])} {str(strings['afp_import_all'])}", animated)

                # patch enterSelectionMode and exitSelectionMode to update button
                _orig_enter = enterSelectionMode
                _orig_exit = exitSelectionMode
                _orig_toggle = toggleCheck

                def enterSelectionMode(idx: int):
                    _orig_enter(idx)
                    updateImportBtnText(True)
                    updateHintText()

                def exitSelectionMode():
                    _orig_exit()
                    updateImportBtnText(True)
                    updateHintText()

                def toggleCheck(idx: int):
                    _orig_toggle(idx)
                    if sel_state["active"]:
                        if sum(1 for c in sel_state["checked"] if c) == 0:
                            touch_state["long_token"] = None
                            exitSelectionMode()
                        else:
                            updateImportBtnText(True)
                            updateHintText()

                updateImportBtnText(False)

                class _ImportClick(dynamic_proxy(View.OnClickListener)):
                    def __init__(self): super().__init__()
                    def onClick(self, v):
                        if sel_state["active"]:
                            selected = [p for i, p in enumerate(plugins) if sel_state["checked"][i]]
                        else:
                            selected = plugins
                        sheet.dismiss()
                        try:
                            from .ConfirmImportBottomSheet import show as showConfirm
                            showConfirm(file_path, selected, total_count=total_count or len(plugins), settings=settings)
                        except Exception as _cython_exc_e:
                            e = _cython_exc_e
                            logx(f"ImportBottomSheet: open confirm error: {e}", False)

                import_btn.setOnClickListener(_ImportClick())
                import_lp = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    AndroidUtilities.dp(48)
                )
                import_lp.topMargin = AndroidUtilities.dp(16)
                import_lp.leftMargin = pad_h
                import_lp.rightMargin = pad_h
                root.addView(import_btn, import_lp)
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"ImportBottomSheet: import btn error: {e}", False)

            # close button
            try:
                from org.telegram.ui.Stories.recorder import ButtonWithCounterView
                close_btn = ButtonWithCounterView(activity, False, fragment.getResourceProvider())
                close_btn.setRound()
                close_btn.setNeutral()
                close_btn.setText(str(strings["close_button"]), False)

                class _CloseClick(dynamic_proxy(View.OnClickListener)):
                    def __init__(self): super().__init__()
                    def onClick(self, v):
                        sheet.dismiss()

                close_btn.setOnClickListener(_CloseClick())
                close_lp = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    AndroidUtilities.dp(48)
                )
                close_lp.topMargin = AndroidUtilities.dp(8)
                close_lp.leftMargin = pad_h
                close_lp.rightMargin = pad_h
                root.addView(close_btn, close_lp)
            except Exception as _cython_exc_e:
                e = _cython_exc_e
                logx(f"ImportBottomSheet: close btn error: {e}", False)

            sheet.setCustomView(root)
            sheet.show()

        except Exception as _cython_exc_e:
            e = _cython_exc_e
            logx(f"ImportBottomSheet.show: {e}\n{traceback.format_exc()}", False)

    run_on_ui_thread(_show)