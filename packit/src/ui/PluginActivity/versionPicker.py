import threading
from android_utils import log, run_on_ui_thread, OnClickListener, OnLongClickListener
from client_utils import get_last_fragment
try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"versionPicker: import elyx failed: {e}")
try:
    from org.telegram.ui.ActionBar import Theme
except Exception:
    pass
try:
    from org.telegram.ui.Components import LayoutHelper
    from org.telegram.messenger import AndroidUtilities
except Exception:
    pass

def _build_version_entries(plugin):
    # returns list sorted newest first
    def _ver_key(v):
        try:
            from ..PluginListActivity.fragment import _parse_version
            return _parse_version(v)
        except Exception:
            return []

    entries = []
    latest_link = plugin.get("link") or plugin.get("raw") or ""
    if latest_link:
        entries.append({
            "version": str(plugin.get("version") or ""),
            "link": latest_link,
            "app_version": str(plugin.get("app_version") or ""),
        })
    for ver, meta in (plugin.get("versions") or {}).items():
        if not isinstance(meta, dict):
            continue
        link = meta.get("link") or meta.get("raw") or ""
        if not link:
            continue
        entries.append({
            "version": str(ver),
            "link": link,
            "app_version": str(meta.get("app_version") or ""),
        })
    entries.sort(key=lambda e: _ver_key(e["version"]), reverse=True)
    return entries


def _show_version_picker(act, plugin, install_ui, all_plugins, btn, label, btn_text_color, do_install, on_cancel=None, repo_id=""):
    try:
        from org.telegram.ui.ActionBar import Theme
        from org.telegram.ui.Components import LayoutHelper
        from org.telegram.messenger import AndroidUtilities
        from android.widget import LinearLayout, TextView, ScrollView, FrameLayout, ImageView
        from android.view import Gravity, View, ViewGroup
        from android.util import TypedValue
        from android.graphics.drawable import GradientDrawable
        from android_utils import OnClickListener
        from ...utils.app_version import check_app_version as _check_app_version
        import ctypes
        from java import dynamic_proxy

        entries = _build_version_entries(plugin)
        if not entries:
            do_install(plugin, install_ui, all_plugins, btn, label, btn_text_color, act)
            return

        # filter unavailable versions if setting is on
        try:
            from elyx import settings as _s
            if _s.get("hide_unavailable_plugins", False):
                from ...utils.app_version import check_app_version as _check_app_version
                entries = [e for e in entries if not e["app_version"] or _check_app_version(e["app_version"])]
        except Exception:
            pass

        decor = act.getWindow().getDecorView()

        # state
        selected_entry = [None]
        list_expanded = [False]
        overlay_ref = [None]
        list_container_ref = [None]
        header_ver_tv_ref = [None]
        arrow_iv_ref = [None]
        dl_btn_ref = [None]
        row_entries = []  # list of (row, entry, available) for repainting

        accent = Theme.getColor(Theme.key_featuredStickers_addButton)
        accent_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        text_color = Theme.getColor(Theme.key_dialogTextBlack)
        gray_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
        red_color = Theme.getColor(Theme.key_avatar_backgroundRed)
        bg_color = Theme.getColor(Theme.key_dialogBackground)
        divider_color = Theme.getColor(Theme.key_divider)

        def _row_normal_bg():
            return bg_color

        def _row_accent_bg():
            return accent

        def _row_unavail_bg():
            import ctypes as _ct
            r = (red_color >> 16) & 0xFF
            g = (red_color >> 8) & 0xFF
            b = red_color & 0xFF
            return _ct.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value

        def _make_row_bg(color, corner=18, stroke_color=None):
            d = GradientDrawable()
            d.setShape(GradientDrawable.RECTANGLE)
            d.setCornerRadius(AndroidUtilities.dp(corner))
            d.setColor(color)
            if stroke_color is not None:
                d.setStroke(AndroidUtilities.dp(2), stroke_color)
            return d

        def _make_row_ripple_bg(color, corner=18, stroke_color=None):
            # RippleDrawable wrapping the solid bg for native touch feedback
            try:
                from android.graphics.drawable import RippleDrawable
                from android.content.res import ColorStateList as CslA
                from android.graphics import Color as ACol
                base = _make_row_bg(color, corner, stroke_color)
                # ripple mask — same shape
                mask = GradientDrawable()
                mask.setShape(GradientDrawable.RECTANGLE)
                mask.setCornerRadius(AndroidUtilities.dp(corner))
                mask.setColor(ACol.WHITE)
                ripple_c = CslA.valueOf(ctypes.c_int32(0x33FFFFFF).value)
                return RippleDrawable(ripple_c, base, mask)
            except Exception:
                return _make_row_bg(color, corner, stroke_color)

        def _repaint_rows():
            try:
                checked_bg = Theme.getColor(Theme.key_dialogRadioBackgroundChecked)
            except Exception:
                checked_bg = accent
            try:
                checked_text = Theme.getColor(Theme.key_dialogBackground)
            except Exception:
                checked_text = 0xFF000000
            for _row, _entry, _avail, _tv in row_entries:
                if selected_entry[0] is not None and _entry["version"] == selected_entry[0]["version"]:
                    _row.setBackground(_make_row_ripple_bg(checked_bg, stroke_color=checked_bg))
                    _tv.setTextColor(checked_text)
                elif not _avail:
                    _row.setBackground(_make_row_ripple_bg(_row_unavail_bg()))
                    _tv.setTextColor(text_color)
                else:
                    _row.setBackground(_make_row_ripple_bg(_row_normal_bg()))
                    _tv.setTextColor(text_color)

        ANIM_DURATION = 220
        SPRING_DURATION = 380

        def _animate_in():
            try:
                from android.animation import AnimatorSet, ObjectAnimator
                from android.view.animation import OvershootInterpolator, DecelerateInterpolator
                # overlay fades in quickly
                fade_overlay = ObjectAnimator.ofFloat(overlay, "alpha", 0.0, 1.0)
                fade_overlay.setDuration(ANIM_DURATION)
                fade_overlay.setInterpolator(DecelerateInterpolator())
                # card fades in
                fade_card = ObjectAnimator.ofFloat(card, "alpha", 0.0, 1.0)
                fade_card.setDuration(ANIM_DURATION)
                fade_card.setInterpolator(DecelerateInterpolator())
                # card scale with overshoot spring (0.88 -> 1.0 with tension)
                scale_x = ObjectAnimator.ofFloat(card, "scaleX", 0.88, 1.0)
                scale_x.setDuration(SPRING_DURATION)
                scale_x.setInterpolator(OvershootInterpolator(2.0))
                scale_y = ObjectAnimator.ofFloat(card, "scaleY", 0.88, 1.0)
                scale_y.setDuration(SPRING_DURATION)
                scale_y.setInterpolator(OvershootInterpolator(2.0))
                s = AnimatorSet()
                s.playTogether(fade_overlay, fade_card, scale_x, scale_y)
                s.start()
            except Exception as e:
                log(f"version_picker: animate_in error: {e}")

        install_started = [False]

        def _dismiss(restore_btn=False):
            try:
                from android.animation import AnimatorSet, ObjectAnimator, Animator

                fade_overlay = ObjectAnimator.ofFloat(overlay_ref[0], "alpha", overlay_ref[0].getAlpha(), 0.0)
                fade_overlay.setDuration(ANIM_DURATION)
                fade_card = ObjectAnimator.ofFloat(card, "alpha", card.getAlpha(), 0.0)
                fade_card.setDuration(ANIM_DURATION)
                scale_x = ObjectAnimator.ofFloat(card, "scaleX", card.getScaleX(), 0.92)
                scale_x.setDuration(ANIM_DURATION)
                scale_y = ObjectAnimator.ofFloat(card, "scaleY", card.getScaleY(), 0.92)
                scale_y.setDuration(ANIM_DURATION)

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
                log(f"version_picker: animate_out error: {e}")
                try:
                    decor.removeView(overlay_ref[0])
                except Exception:
                    pass

        # dim overlay
        overlay = FrameLayout(act)
        overlay_ref[0] = overlay
        overlay.setBackgroundColor(ctypes.c_int32(0x99000000).value)
        overlay.setClickable(True)
        overlay.setFocusable(True)
        def _on_overlay_click(v):
            if install_started[0] and on_cancel:
                on_cancel()
            _dismiss()

        overlay.setOnClickListener(OnClickListener(_on_overlay_click))

        # card
        card = LinearLayout(act)
        card.setOrientation(LinearLayout.VERTICAL)
        card.setClickable(True)
        card.setFocusable(True)
        # block touches from reaching dim overlay
        card.setOnClickListener(OnClickListener(lambda v: None))

        card_bg = GradientDrawable()
        card_bg.setShape(GradientDrawable.RECTANGLE)
        card_bg.setCornerRadius(AndroidUtilities.dp(16))
        card_bg.setColor(bg_color)
        card.setBackground(card_bg)

        margin_h = AndroidUtilities.dp(32)
        card_lp = FrameLayout.LayoutParams(-1, -2)
        card_lp.gravity = Gravity.CENTER
        card_lp.leftMargin = margin_h
        card_lp.rightMargin = margin_h
        overlay.addView(card, card_lp)

        # version selector row (collapsed header)
        selector_row = LinearLayout(act)
        selector_row.setOrientation(LinearLayout.HORIZONTAL)
        selector_row.setGravity(Gravity.CENTER_VERTICAL)
        selector_row.setPadding(
            AndroidUtilities.dp(16), AndroidUtilities.dp(14),
            AndroidUtilities.dp(12), AndroidUtilities.dp(14)
        )
        selector_row.setClickable(True)
        selector_row.setFocusable(True)

        selector_bg = GradientDrawable()
        selector_bg.setShape(GradientDrawable.RECTANGLE)
        selector_bg.setCornerRadius(AndroidUtilities.dp(18))
        try:
            base = Theme.getColor(Theme.key_windowBackgroundGray)
        except Exception:
            base = 0xFF303030
        selector_bg.setColor(base)
        selector_row.setBackground(selector_bg)

        selector_margin_lp = LinearLayout.LayoutParams(-1, -2)
        selector_margin_lp.setMargins(
            AndroidUtilities.dp(16), AndroidUtilities.dp(16),
            AndroidUtilities.dp(16), 0
        )
        card.addView(selector_row, selector_margin_lp)

        ver_icon = ImageView(act)
        try:
            from hook_utils import find_class
            R_tg = find_class("org.telegram.messenger.R")
            ver_icon.setImageResource(getattr(R_tg.drawable, "msg_select", 0))
            ver_icon.setColorFilter(gray_color)
        except Exception:
            pass
        ver_icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
        ver_icon_lp.rightMargin = AndroidUtilities.dp(10)
        selector_row.addView(ver_icon, ver_icon_lp)

        header_ver_tv = TextView(act)
        header_ver_tv.setText(str(strings["pp_version_picker_title"]))
        header_ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        header_ver_tv.setTextColor(gray_color)
        try:
            header_ver_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        except Exception:
            header_ver_tv.setTypeface(AndroidUtilities.bold())
        header_ver_tv_ref[0] = header_ver_tv
        selector_row.addView(header_ver_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

        arrow_iv = ImageView(act)
        try:
            arrow_iv.setImageResource(getattr(R_tg.drawable, "ic_arrow_down", 0))
            arrow_iv.setColorFilter(gray_color)
        except Exception:
            pass
        arrow_iv_ref[0] = arrow_iv
        arrow_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
        selector_row.addView(arrow_iv, arrow_lp)

        # list container (hidden initially)
        list_wrap = LinearLayout(act)
        list_wrap.setOrientation(LinearLayout.VERTICAL)
        list_wrap.setPadding(
            AndroidUtilities.dp(12), AndroidUtilities.dp(8),
            AndroidUtilities.dp(12), AndroidUtilities.dp(8)
        )

        try:
            dark_field_color = Theme.getColor(Theme.key_windowBackgroundGray)
        except Exception:
            dark_field_color = 0xFF2C2C2C
        list_wrap_bg = GradientDrawable()
        list_wrap_bg.setShape(GradientDrawable.RECTANGLE)
        list_wrap_bg.setCornerRadius(AndroidUtilities.dp(18))
        list_wrap_bg.setColor(dark_field_color)
        list_wrap.setBackground(list_wrap_bg)
        
        list_wrap.setVisibility(View.GONE)
        list_container_ref[0] = list_wrap

        list_margin_lp = LinearLayout.LayoutParams(-1, -2)
        list_margin_lp.setMargins(
            AndroidUtilities.dp(16), AndroidUtilities.dp(6),
            AndroidUtilities.dp(16), 0
        )
        card.addView(list_wrap, list_margin_lp)

        def _make_fade_overlay(orientation, colors):
            d = GradientDrawable()
            d.setShape(GradientDrawable.RECTANGLE)
            d.setOrientation(orientation)
            d.setColors(colors)
            return d

        scroll = ScrollView(act)
        scroll.setVerticalScrollBarEnabled(False)
        scroll_container = FrameLayout(act)
        
        inner_list = LinearLayout(act)
        inner_list.setOrientation(LinearLayout.VERTICAL)
        scroll.addView(inner_list)
        scroll_container.addView(scroll, FrameLayout.LayoutParams(-1, -2))
        top_fade = View(act)
        top_fade.setBackground(_make_fade_overlay(
            GradientDrawable.Orientation.TOP_BOTTOM,
            [dark_field_color, ctypes.c_int32(0x00000000).value]
        ))
        top_fade_lp = FrameLayout.LayoutParams(-1, AndroidUtilities.dp(16))
        top_fade_lp.gravity = Gravity.TOP
        top_fade.setAlpha(0.0)
        scroll_container.addView(top_fade, top_fade_lp)
        
        bottom_fade = View(act)
        bottom_fade.setBackground(_make_fade_overlay(
            GradientDrawable.Orientation.BOTTOM_TOP,
            [dark_field_color, ctypes.c_int32(0x00000000).value]
        ))
        bottom_fade_lp = FrameLayout.LayoutParams(-1, AndroidUtilities.dp(16))
        bottom_fade_lp.gravity = Gravity.BOTTOM
        bottom_fade.setAlpha(0.0)
        scroll_container.addView(bottom_fade, bottom_fade_lp)

        max_scroll_height = AndroidUtilities.dp(190)
        scroll_lp = LinearLayout.LayoutParams(-1, -2)
        scroll_lp.height = -2  # wrap initially, capped by maxHeight logic
        list_wrap.addView(scroll_container, scroll_lp)

        def _update_fade_opacity():
            try:
                scroll_y = scroll.getScrollY()
                max_scroll = inner_list.getMeasuredHeight() - scroll.getHeight()
                
                if max_scroll <= 0:
                    top_fade.setAlpha(0.0)
                    bottom_fade.setAlpha(0.0)
                    return
                
                top_alpha = min(1.0, float(scroll_y) / 50.0)
                bottom_alpha = min(1.0, float(max_scroll - scroll_y) / 50.0)
                top_fade.setAlpha(top_alpha)
                bottom_fade.setAlpha(bottom_alpha)
            except Exception as e:
                log(f"version_picker: fade update error: {e}")

        class _ScrollListener(dynamic_proxy(View.OnScrollChangeListener)):
            def onScrollChange(self, v, scrollX, scrollY, oldScrollX, oldScrollY):
                _update_fade_opacity()
        
        scroll.setOnScrollChangeListener(_ScrollListener())

        def _update_dl_btn():
            if dl_btn_ref[0] is None:
                return
            if selected_entry[0] is None:
                dl_btn_ref[0].setEnabled(False)
                dl_btn_ref[0].setAlpha(0.4)
            else:
                dl_btn_ref[0].setEnabled(True)
                dl_btn_ref[0].setAlpha(1.0)

        def _expand_list():
            try:
                from android.animation import ValueAnimator, Animator
                list_wrap.setVisibility(View.VISIBLE)
                list_wrap.measure(
                    View.MeasureSpec.makeMeasureSpec(card.getWidth(), View.MeasureSpec.AT_MOST),
                    View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
                )
                target_h = list_wrap.getMeasuredHeight()
                if target_h > max_scroll_height:
                    target_h = max_scroll_height
                list_wrap.getLayoutParams().height = 0
                list_wrap.requestLayout()
                anim = ValueAnimator.ofInt(0, target_h)
                anim.setDuration(200)

                class _UpdateExpand(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                    def onAnimationUpdate(self, a):
                        list_wrap.getLayoutParams().height = int(a.getAnimatedValue())
                        list_wrap.requestLayout()

                class _EndExpand(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        final_h = max_scroll_height if target_h == max_scroll_height else -2
                        list_wrap.getLayoutParams().height = final_h
                        list_wrap.requestLayout()
                        _update_fade_opacity()
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                anim.addUpdateListener(_UpdateExpand())
                anim.addListener(_EndExpand())
                anim.start()
                try:
                    arrow_iv_ref[0].animate().rotation(180.0).setDuration(200).start()
                except Exception:
                    arrow_iv_ref[0].setRotation(180.0)
            except Exception as e:
                log(f"version_picker: expand error: {e}")
                list_wrap.setVisibility(View.VISIBLE)

        def _collapse_list():
            try:
                from android.animation import ValueAnimator, Animator
                start_h = list_wrap.getMeasuredHeight()
                anim = ValueAnimator.ofInt(start_h, 0)
                anim.setDuration(180)

                class _UpdateCollapse(dynamic_proxy(ValueAnimator.AnimatorUpdateListener)):
                    def onAnimationUpdate(self, a):
                        list_wrap.getLayoutParams().height = int(a.getAnimatedValue())
                        list_wrap.requestLayout()

                class _EndCollapse(dynamic_proxy(Animator.AnimatorListener)):
                    def onAnimationEnd(self, a, *args):
                        list_wrap.setVisibility(View.GONE)
                        list_wrap.getLayoutParams().height = -2
                        list_wrap.requestLayout()
                    def onAnimationStart(self, a, *args): pass
                    def onAnimationCancel(self, a, *args): pass
                    def onAnimationRepeat(self, a, *args): pass

                anim.addUpdateListener(_UpdateCollapse())
                anim.addListener(_EndCollapse())
                anim.start()
                try:
                    arrow_iv_ref[0].animate().rotation(0.0).setDuration(180).start()
                except Exception:
                    arrow_iv_ref[0].setRotation(0.0)
            except Exception as e:
                log(f"version_picker: collapse error: {e}")
                list_wrap.setVisibility(View.GONE)

        def _toggle_list(v=None):
            list_expanded[0] = not list_expanded[0]
            if list_expanded[0]:
                _expand_list()
            else:
                _collapse_list()

        selector_row.setOnClickListener(OnClickListener(_toggle_list))

        # auto-expand if setting enabled
        try:
            from elyx import settings as _s
            _auto_expand = _s.get("version_picker_auto_expand", False)
        except Exception:
            _auto_expand = False

        # populate version rows
        for i, entry in enumerate(entries):
            ver = entry["version"]
            av = entry["app_version"]
            available = (not av) or _check_app_version(av)

            row = FrameLayout(act)
            row.setClickable(True)
            row.setFocusable(True)

            # initial bg
            if available:
                row.setBackground(_make_row_ripple_bg(_row_normal_bg()))
            else:
                row.setBackground(_make_row_ripple_bg(_row_unavail_bg()))

            row_tv = TextView(act)
            row_tv.setText(ver)
            row_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            row_tv.setGravity(Gravity.CENTER)
            row_tv.setPadding(
                AndroidUtilities.dp(16), AndroidUtilities.dp(13),
                AndroidUtilities.dp(16), AndroidUtilities.dp(13)
            )
            try:
                row_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                row_tv.setTypeface(AndroidUtilities.bold())

            row_entries.append((row, entry, available, row_tv))

            if available:
                row_tv.setTextColor(text_color)

                def _make_select(_e=entry):
                    def _on_select(v):
                        if selected_entry[0] is not None and selected_entry[0]["version"] == _e["version"]:
                            _toggle_list()
                            return
                        selected_entry[0] = _e
                        header_ver_tv_ref[0].setText(str(strings["pp_version_selected"]).format(_e["version"]))
                        header_ver_tv_ref[0].setTextColor(text_color)
                        _repaint_rows()
                        _toggle_list()
                        _update_dl_btn()
                    return _on_select
                row.setOnClickListener(OnClickListener(_make_select()))
            else:
                row_tv.setTextColor(text_color)

                def _make_hint(_row=row, _mv=min_ver):
                    hint_ref = [None]
                    def _on_unavail_click(v):
                        try:
                            from org.telegram.ui.Stories.recorder import HintView2
                            from android.text import Layout
                            prev = hint_ref[0]
                            if prev is not None:
                                try:
                                    prev.hide()
                                    prev.getParent().removeView(prev)
                                except Exception:
                                    pass
                                hint_ref[0] = None
                            hint = (
                                HintView2(_row.getContext(), 3)
                                .setMultilineText(True)
                                .setBgColor(Theme.getColor(Theme.key_undo_background))
                                .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                                .setText(str(strings["pp_version_requires"]).format(_mv) if _mv else str(strings["plugin_version_below_min"]))
                                .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                                .allowBlur(True)
                                .setRounding(AndroidUtilities.dp(12))
                            )
                            try:
                                hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                            except Exception:
                                pass
                            decor.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                            hint_ref[0] = hint
                            def _show():
                                try:
                                    row_loc = [0, 0]
                                    _row.getLocationInWindow(row_loc)
                                    decor_loc = [0, 0]
                                    decor.getLocationInWindow(decor_loc)
                                    cell_y = row_loc[1] - decor_loc[1]
                                    center_x = float(row_loc[0] - decor_loc[0]) + float(_row.getMeasuredWidth()) / 2.0
                                    hint.setTranslationY(float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                                    hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                                    hint.setDuration(3500)
                                    hint.show()
                                except Exception as he:
                                    log(f"version_picker: hint show error: {he}")
                            run_on_ui_thread(_show)
                        except Exception as e:
                            log(f"version_picker: unavail hint error: {e}")
                    return _on_unavail_click
                row.setOnClickListener(OnClickListener(_make_hint()))

            def _make_long_click(_e=entry, _row=row):
                def _on_long_click(v):
                    try:
                        plugin_id = str(plugin.get("id") or "")
                        ver = str(_e["version"])
                        link = f"tg://packit?install&repo={repo_id}&plugin={plugin_id}&version={ver}"
                        from android.content import ClipData
                        clipboard = act.getSystemService(act.CLIPBOARD_SERVICE)
                        clipboard.setPrimaryClip(ClipData.newPlainText("packit_link", link))
                        try:
                            from hook_utils import find_class as _fc
                            BulletinFactory = _fc("org.telegram.ui.Components.BulletinFactory")
                            frag = get_last_fragment()
                            container = decor
                            resource_provider = None
                            try:
                                resource_provider = frag.getResourceProvider()
                            except Exception:
                                pass
                            from hook_utils import find_class as _fc2
                            R_tg = _fc2("org.telegram.messenger.R")
                            icon_raw = getattr(R_tg.raw, "copy", getattr(R_tg.raw, "msg_copy", 0))
                            BulletinFactory.of(container, resource_provider).createSimpleBulletin(
                                icon_raw,
                                "The link with the version has been copied to the clipboard!"
                            ).show()
                        except Exception as be:
                            log(f"version_picker: bulletin error: {be}")
                        return True
                    except Exception as e:
                        log(f"version_picker: long click error: {e}")
                        return False
                return _on_long_click

            row.setOnLongClickListener(OnLongClickListener(_make_long_click()))

            row.addView(row_tv, FrameLayout.LayoutParams(-1, -2))
            row_lp = LinearLayout.LayoutParams(-1, -2)
            row_lp.bottomMargin = AndroidUtilities.dp(6) if i < len(entries) - 1 else 0
            inner_list.addView(row, row_lp)

        # download button
        dl_margin_lp = LinearLayout.LayoutParams(-1, -2)
        dl_margin_lp.setMargins(
            AndroidUtilities.dp(16), AndroidUtilities.dp(16),
            AndroidUtilities.dp(16), AndroidUtilities.dp(16)
        )

        dl_btn = LinearLayout(act)
        dl_btn.setOrientation(LinearLayout.HORIZONTAL)
        dl_btn.setGravity(Gravity.CENTER)
        dl_btn.setClickable(True)
        dl_btn.setFocusable(True)
        dl_btn.setAlpha(0.4)
        dl_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(28), accent, accent_pressed
        ))
        dl_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
        dl_btn_ref[0] = dl_btn

        dl_icon = ImageView(act)
        try:
            dl_icon.setImageResource(getattr(R_tg.drawable, "msg_download", 0))
            dl_icon.setColorFilter(Theme.getColor(Theme.key_featuredStickers_buttonText))
        except Exception:
            pass
        dl_icon_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
        dl_icon_lp.rightMargin = AndroidUtilities.dp(8)
        dl_btn.addView(dl_icon, dl_icon_lp)

        dl_tv = TextView(act)
        dl_tv.setText(str(strings["pp_install"]))
        dl_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
        dl_tv.setGravity(Gravity.CENTER)
        try:
            dl_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        dl_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        dl_btn.addView(dl_tv)

        picker_btn_text_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
        dl_hint_ref = [None]

        def _on_download(v, _dl_btn=dl_btn, _dl_tv=dl_tv):
            entry = selected_entry[0]
            if not entry:
                try:
                    from org.telegram.ui.Stories.recorder import HintView2
                    from android.text import Layout
                    prev = dl_hint_ref[0]
                    if prev is not None:
                        try:
                            prev.hide()
                            prev.getParent().removeView(prev)
                        except Exception:
                            pass
                        dl_hint_ref[0] = None
                    hint = (
                        HintView2(_dl_btn.getContext(), 3)
                        .setMultilineText(True)
                        .setBgColor(Theme.getColor(Theme.key_undo_background))
                        .setTextColor(Theme.getColor(Theme.key_undo_infoColor))
                        .setText(str(strings["pp_select_version_first"]))
                        .setTextAlign(Layout.Alignment.ALIGN_CENTER)
                        .allowBlur(True)
                        .setRounding(AndroidUtilities.dp(12))
                    )
                    try:
                        hint.setMaxWidthPx(HintView2.cutInFancyHalf(hint.getText(), hint.getTextPaint()))
                    except Exception:
                        pass
                    decor.addView(hint, LayoutHelper.createFrame(-1, 100, 55, 32, 0, 32, 0))
                    dl_hint_ref[0] = hint
                    def _show_dl_hint():
                        try:
                            btn_loc = [0, 0]
                            _dl_btn.getLocationInWindow(btn_loc)
                            dv_loc = [0, 0]
                            decor.getLocationInWindow(dv_loc)
                            cell_y = btn_loc[1] - dv_loc[1]
                            center_x = float(btn_loc[0] - dv_loc[0]) + float(_dl_btn.getMeasuredWidth()) / 2.0
                            hint.setTranslationY(float(cell_y - AndroidUtilities.dp(100) - AndroidUtilities.dp(6)))
                            hint.setJointPx(0.0, float(-AndroidUtilities.dp(32)) + center_x)
                            hint.setDuration(3500)
                            hint.show()
                        except Exception as e:
                            log(f"version_picker: dl_hint show error: {e}")
                    run_on_ui_thread(_show_dl_hint)
                except Exception as e:
                    log(f"version_picker: dl_hint error: {e}")
                return
            versioned = dict(plugin)
            versioned["link"] = entry["link"]
            versioned["version"] = entry["version"]
            if entry["app_version"]:
                versioned["app_version"] = entry["app_version"]
            # old versions have no hash in repo — mark so update checker compares by version
            if entry["version"] != str(plugin.get("version") or ""):
                versioned["hash"] = "Outdated"
                versioned["bithash"] = "Outdated"
            # show loading on picker button, then dismiss after install starts
            _dl_btn.setEnabled(False)
            _dl_btn.removeAllViews()
            try:
                from org.telegram.ui.Components import CircularProgressDrawable
                d = CircularProgressDrawable(picker_btn_text_color)
                try:
                    d.size = float(AndroidUtilities.dp(20))
                    d.thickness = float(AndroidUtilities.dp(2))
                except Exception:
                    pass
                spinner = ImageView(act)
                spinner.setImageDrawable(d)
                spinner.setScaleType(ImageView.ScaleType.CENTER)
                _dl_btn.addView(spinner, LayoutHelper.createLinear(20, 20, Gravity.CENTER))
            except Exception:
                from android.widget import ProgressBar
                pb = ProgressBar(act)
                try:
                    pb.setIndeterminate(True)
                except Exception:
                    pass
                _dl_btn.addView(pb, LayoutHelper.createLinear(20, 20, Gravity.CENTER))

            def _after_install(ok):
                _dismiss()

            install_started[0] = True
            do_install(versioned, install_ui, all_plugins, btn, label, btn_text_color, act,
                       on_finish_override=_after_install)

        dl_btn.setOnClickListener(OnClickListener(_on_download))
        card.addView(dl_btn, dl_margin_lp)

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

        def _post_show():
            _animate_in()
            if _auto_expand:
                list_expanded[0] = True
                _expand_list()

        run_on_ui_thread(_post_show)
    except Exception as e:
        log(f"pluginProfile: _show_version_picker error: {e}")
        do_install(plugin, install_ui, all_plugins, btn, label, btn_text_color, act)



