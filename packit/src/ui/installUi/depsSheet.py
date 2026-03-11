from android.view import View, Gravity
from android.widget import LinearLayout, TextView, FrameLayout, ImageView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from android.animation import ObjectAnimator
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment
from hook_utils import find_class
from elyx import strings
try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    import android_utils as _au; _au.log(f"deps_sheet: import BottomSheet failed: {e}")
try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView
except Exception as e:
    import android_utils as _au; _au.log(f"deps_sheet: import LayoutHelper failed: {e}")
try:
    from org.telegram.messenger import AndroidUtilities, MediaDataController, ImageLocation
except Exception as e:
    import android_utils as _au; _au.log(f"deps_sheet: import AndroidUtilities failed: {e}")
try:
    from com.exteragram.messenger.plugins import PluginsController
except Exception as e:
    import android_utils as _au; _au.log(f"deps_sheet: import PluginsController failed: {e}")


def _resolve_icon(name):
    try:
        R_tg = find_class("org.telegram.messenger.R")
        return getattr(R_tg.drawable, name)
    except Exception:
        return 0


def _check_deps_status(deps: list) -> dict:
    result = {}
    try:
        controller = PluginsController.getInstance()
        for dep_id in deps:
            if not isinstance(dep_id, str) or not dep_id:
                continue
            result[dep_id] = controller.getPluginEngine(dep_id) is not None
    except Exception as e:
        log(f"deps_sheet: _check_deps_status error: {e}")
    return result


def _resolve_header_text(status: dict) -> str:
    if not status:
        return strings["deps_sheet_all_installed"]
    installed = sum(1 for v in status.values() if v)
    total = len(status)
    if installed == total:
        return strings["deps_sheet_all_installed"]
    if installed == 0:
        return strings["deps_sheet_none_installed"]
    return strings["deps_sheet_some_missing"]


def _resolve_button_text(status: dict) -> str:
    return strings["deps_sheet_btn_continue"]


def show_deps_sheet(install_ui, plugin_info: dict, on_confirm, all_plugins: list = None, on_cancel=None):
    # on_cancel: called with False when user cancels or deps not met
    deps = plugin_info.get("deps") or []
    if not deps:
        on_confirm()
        return

    deps_meta = {}
    if all_plugins:
        for p in all_plugins:
            if isinstance(p, dict) and p.get("id"):
                deps_meta[p["id"]] = p

    def _show():
        try:
            fragment = get_last_fragment()
            if not fragment:
                on_confirm()
                return
            act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
            if not act:
                on_confirm()
                return

            status = _check_deps_status(deps)
            plugin_id = plugin_info.get("id") or "?"
            for dep_id, dep_installed in status.items():
                log(f"deps_sheet: plugin='{plugin_id}' dep='{dep_id}' installed={dep_installed}")

            header_text = _resolve_header_text(status)
            button_text = _resolve_button_text(status)

            sheet = BottomSheet(act, False, fragment.getResourceProvider())
            try:
                install_ui._setup_bottom_sheet(sheet)
            except Exception:
                pass

            bg_color = Theme.getColor(Theme.key_dialogBackground)
            text_color = Theme.getColor(Theme.key_dialogTextBlack)
            secondary_color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
            accent_color = Theme.getColor(Theme.key_featuredStickers_addButton)

            root = LinearLayout(act)
            root.setOrientation(LinearLayout.VERTICAL)
            root.setPadding(
                AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                AndroidUtilities.dp(20), AndroidUtilities.dp(12)
            )
            try:
                root.setBackground(install_ui._create_rounded_bg(bg_color))
            except Exception:
                root.setBackgroundColor(bg_color)

            title_tv = TextView(act)
            title_tv.setText(strings["deps_sheet_title"])
            title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 22)
            try:
                title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
            except Exception:
                title_tv.setTypeface(AndroidUtilities.bold())
            title_tv.setTextColor(text_color)
            title_tv.setGravity(Gravity.CENTER)
            root.addView(title_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 4))

            header_tv = TextView(act)
            header_tv.setText(header_text)
            header_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            header_tv.setTextColor(secondary_color)
            header_tv.setGravity(Gravity.CENTER)
            root.addView(header_tv, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 16))

            for dep_id in deps:
                if not isinstance(dep_id, str) or not dep_id:
                    continue
                meta = deps_meta.get(dep_id) or {}
                card = _make_dep_card(
                    act,
                    dep_id=dep_id,
                    dep_name=meta.get("name") or dep_id,
                    dep_version=meta.get("version") or "",
                    dep_author=meta.get("author") or "",
                    dep_min_version=meta.get("min_version") or "",
                    dep_icon=meta.get("icon") or "",
                    dep_meta=meta,
                    installed=status.get(dep_id, False),
                    install_ui=install_ui,
                    text_color=text_color,
                    secondary_color=secondary_color,
                    accent_color=accent_color,
                    bg_color=bg_color
                )
                root.addView(card, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 8))

            try:
                btn_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
            except Exception:
                btn_pressed = accent_color

            action_btn = FrameLayout(act)
            action_btn.setClickable(True)
            action_btn.setFocusable(True)
            action_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(28), accent_color, btn_pressed
            ))
            action_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
            action_tv = TextView(act)
            action_tv.setText(button_text)
            action_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            try:
                action_tv.setTypeface(AndroidUtilities.bold())
            except Exception:
                pass
            action_tv.setGravity(Gravity.CENTER)
            action_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
            action_btn.addView(action_tv, FrameLayout.LayoutParams(-1, -2))

            def on_action(v):
                try:
                    sheet.dismiss()
                except Exception as e:
                    log(f"depsSheet: sheet.dismiss error: {e}")
                fresh = _check_deps_status(deps)
                if all(fresh.values()):
                    on_confirm()
                else:
                    if on_cancel:
                        on_cancel(False)
                    try:
                        from org.telegram.ui.Components import BulletinFactory
                        frag = get_last_fragment()
                        container = frag.getParentActivity().getWindow().getDecorView()
                        rp = frag.getResourceProvider()
                        BulletinFactory.of(container, rp).createErrorBulletin(
                            strings["deps_sheet_need_install"]
                        ).show()
                    except Exception as e:
                        log(f"depsSheet: bulletin error: {e}")

            action_btn.setOnClickListener(OnClickListener(on_action))
            try:
                install_ui._apply_press_scale(action_btn)
            except Exception:
                pass
            root.addView(action_btn, LayoutHelper.createLinear(-1, -2, 0, 8, 0, 4))

            cancel_btn = FrameLayout(act)
            cancel_btn.setClickable(True)
            cancel_btn.setFocusable(True)
            cancel_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(28),
                Theme.getColor(Theme.key_graySection),
                Theme.getColor(Theme.key_listSelector)
            ))
            cancel_btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
            cancel_tv = TextView(act)
            cancel_tv.setText(strings["deps_sheet_btn_cancel"])
            cancel_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
            cancel_tv.setGravity(Gravity.CENTER)
            cancel_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
            try:
                cancel_tv.setTypeface(AndroidUtilities.bold())
            except Exception:
                pass
            cancel_btn.addView(cancel_tv, FrameLayout.LayoutParams(-1, -2))

            def on_cancel_click(v):
                try:
                    sheet.dismiss()
                except Exception:
                    pass
                if on_cancel:
                    on_cancel(False)

            cancel_btn.setOnClickListener(OnClickListener(on_cancel_click))
            try:
                install_ui._apply_press_scale(cancel_btn)
            except Exception:
                pass
            root.addView(cancel_btn, LayoutHelper.createLinear(-1, -2, 0, 0, 0, 0))

            sheet.setCustomView(root)
            sheet.show()
        except Exception as e:
            log(f"deps_sheet: show error: {e}")
            on_confirm()

    run_on_ui_thread(_show)


def _make_dep_card(act, dep_id, dep_name, dep_version, dep_author, dep_min_version,
                   dep_icon, dep_meta, installed, install_ui, text_color, secondary_color, accent_color, bg_color):
    expanded = [False]

    try:
        card_bg = Theme.getColor(Theme.key_windowBackgroundGray)
    except Exception:
        card_bg = bg_color

    outer = LinearLayout(act)
    outer.setOrientation(LinearLayout.VERTICAL)
    outer.setClickable(True)
    outer.setFocusable(True)

    border = GradientDrawable()
    border.setShape(GradientDrawable.RECTANGLE)
    border.setCornerRadius(AndroidUtilities.dp(14))
    border.setColor(card_bg)
    outer.setBackground(border)

    # main row: [status icon] [name  v{ver}] [chevron]
    main_row = LinearLayout(act)
    main_row.setOrientation(LinearLayout.HORIZONTAL)
    main_row.setGravity(Gravity.CENTER_VERTICAL)
    main_row.setPadding(
        AndroidUtilities.dp(14), AndroidUtilities.dp(12),
        AndroidUtilities.dp(14), AndroidUtilities.dp(12)
    )

    # sticker icon (if available)
    icon_size_dp = 36
    if dep_icon and "/" in dep_icon:
        try:
            icon_view = BackupImageView(act)
            icon_view.setRoundRadius(AndroidUtilities.dp(8))
            try:
                icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            icon_size_px = AndroidUtilities.dp(icon_size_dp)
            icon_lp = LinearLayout.LayoutParams(icon_size_px, icon_size_px)
            icon_lp.rightMargin = AndroidUtilities.dp(10)
            main_row.addView(icon_view, icon_lp)

            def _try_load(iv=icon_view, icon_s=dep_icon):
                try:
                    pack_name, index_str = icon_s.split("/", 1)
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
                            f"{icon_size_dp}_{icon_size_dp}",
                            None, None, 0, 1
                        )
                        try:
                            ObjectAnimator.ofFloat(iv, "alpha", 0.0, 1.0).setDuration(300).start()
                        except Exception:
                            pass
                        return True
                    return False
                except Exception as e:
                    log(f"depsSheet: icon load error for '{dep_id}': {e}")
                    return False

            if not _try_load():
                try:
                    pack_name = dep_icon.split("/", 1)[0]
                    MediaDataController.getInstance(0).loadStickersByEmojiOrName(pack_name, False, False)
                except Exception:
                    pass
        except Exception as e:
            log(f"depsSheet: icon init error for '{dep_id}': {e}")

    # status icon
    status_icon = ImageView(act)
    status_icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    try:
        red_color = Theme.getColor(Theme.key_avatar_backgroundRed)
    except Exception:
        from android.graphics import Color
        red_color = Color.parseColor("#FF5252")
    try:
        green_color = Theme.getColor(Theme.key_avatar_backgroundGreen)
    except Exception:
        from android.graphics import Color
        green_color = Color.parseColor("#4CAF50")
    if installed:
        status_icon.setImageResource(_resolve_icon("verified_check"))
        status_icon.setColorFilter(green_color)
    else:
        status_icon.setImageResource(_resolve_icon("msg_cancel"))
        status_icon.setColorFilter(red_color)
    main_row.addView(status_icon, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 0, 0, 12, 0))

    # name row: bold name + secondary version inline
    name_row = LinearLayout(act)
    name_row.setOrientation(LinearLayout.HORIZONTAL)
    name_row.setGravity(Gravity.CENTER_VERTICAL)

    name_label = TextView(act)
    name_label.setText(dep_name)
    name_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    try:
        name_label.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
    except Exception:
        name_label.setTypeface(AndroidUtilities.bold())
    name_label.setTextColor(text_color)
    name_row.addView(name_label, LayoutHelper.createLinear(-2, -2))

    if dep_version:
        ver_label = TextView(act)
        ver_label.setText(f"  v{dep_version}")
        ver_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        ver_label.setTextColor(secondary_color)
        name_row.addView(ver_label, LayoutHelper.createLinear(-2, -2))

    main_row.addView(name_row, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    chevron = ImageView(act)
    chevron.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    chevron.setImageResource(_resolve_icon("arrow_more"))
    chevron.setColorFilter(secondary_color)
    main_row.addView(chevron, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

    outer.addView(main_row, LayoutHelper.createLinear(-1, -2))

    # extra info panel
    extra = LinearLayout(act)
    extra.setOrientation(LinearLayout.VERTICAL)
    extra.setVisibility(View.GONE)
    extra.setPadding(AndroidUtilities.dp(14), AndroidUtilities.dp(4), AndroidUtilities.dp(14), AndroidUtilities.dp(12))

    divider = View(act)
    try:
        divider.setBackgroundColor(Theme.getColor(Theme.key_divider))
    except Exception:
        divider.setBackgroundColor(0x33000000)
    extra.addView(divider, LayoutHelper.createLinear(-1, 1, 0, 0, 0, 10))

    def add_info_row(label, value, linkify=False):
        if not value:
            return
        row = LinearLayout(act)
        row.setOrientation(LinearLayout.HORIZONTAL)
        row.setGravity(Gravity.CENTER_VERTICAL)
        row.setPadding(0, AndroidUtilities.dp(3), 0, AndroidUtilities.dp(3))
        lbl = TextView(act)
        lbl.setText(label)
        lbl.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        lbl.setTextColor(secondary_color)
        row.addView(lbl, LayoutHelper.createLinear(-2, -2, 0, 0, 10, 0))
        val = TextView(act)
        if linkify:
            try:
                from com.exteragram.messenger.utils.text import LocaleUtils
                from android.text.method import LinkMovementMethod
                val.setText(LocaleUtils.fullyFormatText(str(value)))
                val.setLinkTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText))
                val.setMovementMethod(LinkMovementMethod.getInstance())
            except Exception:
                val.setText(str(value))
        else:
            val.setText(str(value))
        val.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        val.setTextColor(text_color)
        row.addView(val, LayoutHelper.createLinear(-2, -2))
        extra.addView(row, LayoutHelper.createLinear(-1, -2))

    add_info_row(strings["deps_sheet_label_id"], dep_id)
    add_info_row(strings["deps_sheet_label_author"], dep_author, linkify=True)
    add_info_row(strings["deps_sheet_label_min_version"], dep_min_version)

    if not installed and dep_meta:
        try:
            btn_pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            btn_pressed = accent_color

        install_btn = FrameLayout(act)
        install_btn.setClickable(True)
        install_btn.setFocusable(True)
        install_btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
            AndroidUtilities.dp(20), accent_color, btn_pressed
        ))
        install_btn.setPadding(0, AndroidUtilities.dp(10), 0, AndroidUtilities.dp(10))

        install_tv = TextView(act)
        install_tv.setText(strings["deps_sheet_card_install"])
        install_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
        install_tv.setGravity(Gravity.CENTER)
        install_tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        try:
            install_tv.setTypeface(AndroidUtilities.bold())
        except Exception:
            pass
        install_btn.addView(install_tv, FrameLayout.LayoutParams(-1, -2))

        def _refresh_card(_ok=None):
            try:
                controller = PluginsController.getInstance()
                now_installed = controller.getPluginEngine(dep_id) is not None
                if now_installed:
                    try:
                        green_color = Theme.getColor(Theme.key_avatar_backgroundGreen)
                    except Exception:
                        from android.graphics import Color
                        green_color = Color.parseColor("#4CAF50")
                    status_icon.setImageResource(_resolve_icon("verified_check"))
                    status_icon.setColorFilter(green_color)
                    install_btn.setVisibility(View.GONE)
            except Exception as e:
                log(f"depsSheet: _refresh_card error for '{dep_id}': {e}")

        def on_install(v):
            from ...core import install_plugin
            install_plugin(dep_meta, install_ui=install_ui, on_finish=_refresh_card)

        install_btn.setOnClickListener(OnClickListener(on_install))
        try:
            install_ui._apply_press_scale(install_btn)
        except Exception:
            pass
        extra.addView(install_btn, LayoutHelper.createLinear(-1, -2, 0, 10, 0, 0))

    outer.addView(extra, LayoutHelper.createLinear(-1, -2))

    def on_card_click(v):
        expanded[0] = not expanded[0]
        if expanded[0]:
            extra.setAlpha(0.0)
            extra.setVisibility(View.VISIBLE)
            extra.animate().alpha(1.0).setDuration(220).start()
        else:
            def _hide():
                extra.setVisibility(View.GONE)
                extra.setAlpha(1.0)
            extra.animate().alpha(0.0).setDuration(180).withEndAction(_hide).start()
        try:
            chevron.animate().rotation(180.0 if expanded[0] else 0.0).setDuration(200).start()
        except Exception:
            chevron.setRotation(180.0 if expanded[0] else 0.0)

    outer.setOnClickListener(OnClickListener(on_card_click))
    return outer
