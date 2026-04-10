import os
import ast
import re
import traceback
import ctypes

from android.widget import LinearLayout, TextView, FrameLayout, ImageView, ScrollView
from android.view import View, Gravity, MotionEvent
from android.graphics.drawable import GradientDrawable
from android.graphics import Color
from java import dynamic_proxy
from android.util import TypedValue
from android_utils import log, run_on_ui_thread, OnClickListener
from client_utils import get_last_fragment

try:
    from org.telegram.ui.ActionBar import BottomSheet, Theme
except Exception as e:
    import android_utils as _au; _au.log(f"ExportBottomSheet: import BottomSheet/Theme failed: {e}")
    BottomSheet = None
    Theme = None

try:
    from org.telegram.ui.Components import LayoutHelper, BackupImageView
except Exception as e:
    import android_utils as _au; _au.log(f"ExportBottomSheet: import LayoutHelper failed: {e}")
    LayoutHelper = None
    BackupImageView = None

try:
    from org.telegram.messenger import AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"ExportBottomSheet: import AndroidUtilities failed: {e}")
    AndroidUtilities = None

try:
    from org.telegram.messenger import MediaDataController, ImageLocation
except Exception as e:
    import android_utils as _au; _au.log(f"ExportBottomSheet: import MediaDataController/ImageLocation failed: {e}")
    MediaDataController = None
    ImageLocation = None

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"ExportBottomSheet: import elyx failed: {e}")
    strings = None

try:
    from ui.bulletin import BulletinHelper
except Exception as e:
    import android_utils as _au; _au.log(f"ExportBottomSheet: import BulletinHelper failed: {e}")
    BulletinHelper = None


def _c(color: int) -> int:
    # ebani chocoпай
    return ctypes.c_int32(color).value


def _resolveIcon(name):
    try:
        from hook_utils import find_class
        R = find_class("org.telegram.messenger.R")
        return getattr(R.drawable, name)
    except Exception:
        return None


def _tryLoadSticker(iv, icon_str: str, size_dp: int) -> bool:
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
        log(f"ExportBottomSheet._tryLoadSticker: {e}\n{traceback.format_exc()}")
        return False


def _scheduleStickerRetry(iv, icon_str: str, size_dp: int):
    import threading
    import time

    def _retry():
        time.sleep(2.0)
        run_on_ui_thread(lambda: _tryLoadSticker(iv, icon_str, size_dp))

    threading.Thread(target=_retry, daemon=True).start()


def _readPluginMeta(filepath):
    meta = {}
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(1024 * 5)
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ("__id__", "__name__", "__version__", "__icon__"):
                            if isinstance(node.value, (ast.Constant, ast.Str)):
                                meta[target.id] = node.value.value if isinstance(node.value, ast.Constant) else node.value.s
        except Exception:
            pass

        if not meta:
            patterns = {
                "__id__": r'^__id__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__name__": r'^__name__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__version__": r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__icon__": r'^__icon__\s*=\s*[\'"]([^\'"]+)[\'"]',
            }
            for key, pattern in patterns.items():
                m = re.search(pattern, content, re.MULTILINE)
                if m:
                    meta[key] = m.group(1)
    except Exception as e:
        log(f"ExportBottomSheet._readPluginMeta: {e}\n{traceback.format_exc()}")
    return meta


def loadPlugins():
    # returns list of (filename, name, version, icon)
    try:
        from file_utils import get_plugins_dir
        plugins_dir = get_plugins_dir()
    except Exception:
        try:
            from org.telegram.messenger import ApplicationLoader
            files_dir = ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath()
            plugins_dir = os.path.join(files_dir, "plugins")
        except Exception as e:
            log(f"ExportBottomSheet.loadPlugins: cannot resolve plugins dir: {e}\n{traceback.format_exc()}")
            return []

    result = []
    try:
        for fname in sorted(os.listdir(plugins_dir)):
            if not fname.endswith((".py", ".plugin")):
                continue
            if fname.startswith(".temp"):
                continue
            fpath = os.path.join(plugins_dir, fname)
            meta = _readPluginMeta(fpath)
            name = meta.get("__name__") or os.path.splitext(fname)[0]
            version = meta.get("__version__") or ""
            icon = meta.get("__icon__") or ""
            result.append((fname, name, version, icon))
    except Exception as e:
        log(f"ExportBottomSheet.loadPlugins: {e}\n{traceback.format_exc()}")
    return result


def _animateChevron(chevron, expanded):
    try:
        chevron.animate().rotation(180.0 if expanded else 0.0).setDuration(200).start()
    except Exception:
        chevron.setRotation(180.0 if expanded else 0.0)


def _createSectionHeader(act, title, on_toggle):
    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setPadding(0, AndroidUtilities.dp(10), 0, AndroidUtilities.dp(10))
    row.setClickable(True)
    row.setFocusable(True)

    title_tv = TextView(act)
    title_tv.setText(title)
    title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    try:
        title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
        title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception:
        pass
    row.addView(title_tv, LayoutHelper.createLinear(0, -2, 1.0))

    chevron = ImageView(act)
    chevron.setScaleType(ImageView.ScaleType.CENTER_INSIDE)
    arrow_id = _resolveIcon("arrow_more")
    if arrow_id is not None:
        chevron.setImageResource(arrow_id)
    try:
        chevron.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
    except Exception:
        pass
    row.addView(chevron, LayoutHelper.createLinear(20, 20, Gravity.CENTER_VERTICAL, 8, 0, 0, 0))

    state = {"expanded": False}

    def toggle(v):
        state["expanded"] = not state["expanded"]
        _animateChevron(chevron, state["expanded"])
        on_toggle(state["expanded"])

    row.setOnClickListener(OnClickListener(toggle))
    return row


def _makeCheckbox2(act, checked):
    try:
        from org.telegram.ui.Components import CheckBox2
        cb = CheckBox2(act, 21)
        cb.setColor(Theme.key_radioBackgroundChecked, Theme.key_radioBackground, Theme.key_checkboxCheck)
        cb.setDrawUnchecked(True)
        cb.setDrawBackgroundAsArc(14)
        cb.setChecked(checked, False)
        return cb
    except Exception as e:
        log(f"ExportBottomSheet._makeCheckbox2: {e}")
        return None


def _createCheckRow(act, label, version_str, icon_str, checked, on_change):
    # [sticker?] [name (truncated)] [version gray] [CheckBox2]
    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setPadding(AndroidUtilities.dp(4), AndroidUtilities.dp(10), AndroidUtilities.dp(4), AndroidUtilities.dp(10))
    row.setClickable(True)
    row.setFocusable(True)

    icon_size_dp = 34
    show_sticker = bool(icon_str and "/" in icon_str and BackupImageView is not None)
    if show_sticker:
        try:
            icon_view = BackupImageView(act)
            icon_view.setRoundRadius(AndroidUtilities.dp(8))
            try:
                icon_view.getImageReceiver().setCrossfadeWithOldImage(True)
            except Exception:
                pass
            row.addView(icon_view, LayoutHelper.createLinear(icon_size_dp, icon_size_dp, Gravity.CENTER_VERTICAL, 0, 0, 10, 0))
            loaded = _tryLoadSticker(icon_view, icon_str, icon_size_dp)
            if not loaded:
                _scheduleStickerRetry(icon_view, icon_str, icon_size_dp)
        except Exception as e:
            log(f"ExportBottomSheet._createCheckRow: icon error: {e}\n{traceback.format_exc()}")

    name_tv = TextView(act)
    name_tv.setText(label)
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    name_tv.setSingleLine(True)
    name_tv.setHorizontalFadingEdgeEnabled(True)
    name_tv.setFadingEdgeLength(AndroidUtilities.dp(24))
    try:
        name_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception:
        pass
    row.addView(name_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    if version_str:
        ver_tv = TextView(act)
        ver_tv.setText(f" {version_str}")
        ver_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
        try:
            ver_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
        except Exception:
            pass
        row.addView(ver_tv, LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL))

    state = {"checked": checked}

    cb = _makeCheckbox2(act, checked)
    if cb is not None:
        cb_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(21), AndroidUtilities.dp(21))
        cb_lp.leftMargin = AndroidUtilities.dp(8)
        row.addView(cb, cb_lp)

    def click(v):
        state["checked"] = not state["checked"]
        if cb is not None:
            cb.setChecked(state["checked"], True)
        on_change(state["checked"])

    row.setOnClickListener(OnClickListener(click))
    return row, state, cb


def _createOptionRow(act, label, checked, on_change):
    # settings-section row without icon
    row = LinearLayout(act)
    row.setOrientation(LinearLayout.HORIZONTAL)
    row.setGravity(Gravity.CENTER_VERTICAL)
    row.setPadding(AndroidUtilities.dp(4), AndroidUtilities.dp(10), AndroidUtilities.dp(4), AndroidUtilities.dp(10))
    row.setClickable(True)
    row.setFocusable(True)

    name_tv = TextView(act)
    name_tv.setText(label)
    name_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
    try:
        name_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
    except Exception:
        pass
    row.addView(name_tv, LayoutHelper.createLinear(0, -2, 1.0, Gravity.CENTER_VERTICAL))

    state = {"checked": checked}

    cb = _makeCheckbox2(act, checked)
    if cb is not None:
        cb_lp = LinearLayout.LayoutParams(AndroidUtilities.dp(21), AndroidUtilities.dp(21))
        cb_lp.leftMargin = AndroidUtilities.dp(8)
        row.addView(cb, cb_lp)

    def click(v):
        state["checked"] = not state["checked"]
        if cb is not None:
            cb.setChecked(state["checked"], True)
        on_change(state["checked"])

    row.setOnClickListener(OnClickListener(click))
    return row, state


def _createButton(act, text, primary, on_click):
    btn = FrameLayout(act)
    if primary:
        try:
            base = Theme.getColor(Theme.key_featuredStickers_addButton)
            pressed = Theme.getColor(Theme.key_featuredStickers_addButtonPressed)
        except Exception:
            base = _c(0xFF2AABEE)
            pressed = base
        btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(AndroidUtilities.dp(28), base, pressed))
    else:
        try:
            btn.setBackground(Theme.createSimpleSelectorRoundRectDrawable(
                AndroidUtilities.dp(28),
                Theme.getColor(Theme.key_graySection),
                Theme.getColor(Theme.key_listSelector)
            ))
        except Exception:
            pass
    btn.setPadding(0, AndroidUtilities.dp(14), 0, AndroidUtilities.dp(14))
    btn.setClickable(True)
    btn.setFocusable(True)

    tv = TextView(act)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16)
    tv.setGravity(Gravity.CENTER)
    try:
        tv.setTypeface(AndroidUtilities.bold())
        if primary:
            tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_buttonText))
        else:
            tv.setTextColor(Theme.getColor(Theme.key_featuredStickers_addButton))
    except Exception:
        pass
    btn.addView(tv, FrameLayout.LayoutParams(-1, -2))
    btn.setOnClickListener(OnClickListener(lambda v: on_click()))
    return btn


def _createDivider(act):
    d = View(act)
    d.setMinimumHeight(AndroidUtilities.dp(1))
    try:
        d.setBackgroundColor(Theme.getColor(Theme.key_divider))
    except Exception:
        pass
    return d


def show(plugins, on_export):
    # on_export(selected_files: list[str], export_settings: bool, export_locally: bool)
    fragment = get_last_fragment()
    if not fragment:
        return
    act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
    if not act:
        return

    def _show():
        try:
            count = len(plugins)

            sheet = BottomSheet(act, False, fragment.getResourceProvider())
            sheet.setApplyBottomPadding(False)
            sheet.setApplyTopPadding(False)

            outer = LinearLayout(act)
            outer.setOrientation(LinearLayout.VERTICAL)
            try:
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadii([
                    AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                    AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                    0, 0, 0, 0,
                ])
                bg.setColor(Theme.getColor(Theme.key_dialogBackground))
                outer.setBackground(bg)
            except Exception:
                try:
                    outer.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                except Exception:
                    pass

            pad_h = 20

            # header
            title_tv = TextView(act)
            title_tv.setText(str(strings["utilities_export_title"]))
            title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 20)
            try:
                title_tv.setTypeface(AndroidUtilities.getTypeface("fonts/rmedium.ttf"))
                title_tv.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
            except Exception:
                pass

            if count == 0:
                subtitle = str(strings["utilities_export_subtitle_zero"])
            elif count == 1:
                subtitle = str(strings["utilities_export_subtitle_one"])
            else:
                subtitle = str(strings["utilities_export_subtitle"]).replace("{count}", str(count))

            subtitle_tv = TextView(act)
            subtitle_tv.setText(subtitle)
            subtitle_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 14)
            subtitle_tv.setSingleLine(True)
            try:
                subtitle_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            except Exception:
                pass

            title_col = LinearLayout(act)
            title_col.setOrientation(LinearLayout.VERTICAL)
            title_col.addView(title_tv, LayoutHelper.createLinear(-2, -2))
            title_col.addView(subtitle_tv, LayoutHelper.createLinear(-2, -2, 0, 4, 0, 0))

            toggle_btn = FrameLayout(act)
            toggle_btn_size = AndroidUtilities.dp(28)
            try:
                toggle_btn.setBackground(Theme.createSelectorDrawable(
                    Theme.getColor(Theme.key_listSelector), 1, AndroidUtilities.dp(14)
                ))
            except Exception:
                toggle_btn.setClickable(True)
                toggle_btn.setFocusable(True)
            toggle_btn.setClickable(True)
            toggle_btn.setFocusable(True)

            toggle_iv = ImageView(act)
            toggle_iv.setScaleType(ImageView.ScaleType.CENTER)
            _toggle_icon = _resolveIcon("msg_photo_settings")
            if _toggle_icon is not None:
                toggle_iv.setImageResource(_toggle_icon)
            try:
                toggle_iv.setColorFilter(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
            except Exception:
                pass
            toggle_btn.addView(toggle_iv, FrameLayout.LayoutParams(
                AndroidUtilities.dp(20), AndroidUtilities.dp(20), Gravity.CENTER
            ))

            title_frame = FrameLayout(act)
            title_frame.addView(title_col, FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT
            ))
            toggle_lp = FrameLayout.LayoutParams(
                toggle_btn_size, toggle_btn_size,
                Gravity.TOP | Gravity.END
            )
            title_frame.addView(toggle_btn, toggle_lp)

            outer.addView(title_frame, LayoutHelper.createLinear(-1, -2, pad_h, 16, pad_h, 16))
            outer.addView(_createDivider(act), LayoutHelper.createLinear(-1, 1))

            # plugins section
            plugin_states = {}
            plugin_checkboxes = {}

            def _updateSubtitle():
                n = sum(1 for st in plugin_states.values() if st.get("checked", True))
                total = len(plugin_states)
                if n == 0:
                    text = str(strings["utilities_export_subtitle_none"])
                elif n == total:
                    text = str(strings["utilities_export_subtitle_zero"])
                elif n == 1:
                    text = str(strings["utilities_export_subtitle_one"])
                else:
                    text = str(strings["utilities_export_subtitle"]).replace("{count}", str(n))
                subtitle_tv.setText(text)

            # plugins_list goes inside a ScrollView with capped height
            plugins_list = LinearLayout(act)
            plugins_list.setOrientation(LinearLayout.VERTICAL)

            for fname, name, version, icon in plugins:
                row, state, cb = _createCheckRow(act, name, version, icon, True, lambda c: _updateSubtitle())
                plugin_states[fname] = state
                plugin_checkboxes[fname] = cb
                plugins_list.addView(row, LayoutHelper.createLinear(-1, -2))

            def _onToggleAll(v):
                for fn, st in plugin_states.items():
                    st["checked"] = not st["checked"]
                    cb_ref = plugin_checkboxes.get(fn)
                    if cb_ref is not None:
                        cb_ref.setChecked(st["checked"], True)
                _updateSubtitle()

            toggle_btn.setOnClickListener(OnClickListener(_onToggleAll))

            # ScrollView wraps only the plugin list, capped at 5 rows
            plugin_row_px = AndroidUtilities.dp(54)
            plugins_scroll = ScrollView(act)
            plugins_scroll.setNestedScrollingEnabled(True)
            plugins_scroll.setVerticalScrollBarEnabled(False)
            plugins_scroll.addView(plugins_list)

            # fix: prevent bottom sheet from stealing scroll gesture when list is at top/bottom edge
            class _ScrollTouchListener(dynamic_proxy(View.OnTouchListener)):
                def __init__(self):
                    super().__init__()
                def onTouch(self, v, event):
                    try:
                        action = event.getActionMasked()
                        if action == MotionEvent.ACTION_DOWN:
                            v.getParent().requestDisallowInterceptTouchEvent(True)
                        elif action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                            v.getParent().requestDisallowInterceptTouchEvent(False)
                    except Exception:
                        pass
                    return False

            plugins_scroll.setOnTouchListener(_ScrollTouchListener())

            scroll_height_px = min(len(plugins), 5) * plugin_row_px

            # container: FrameLayout holds scroll + top/bottom gradient overlays
            fade_height_dp = 16
            plugins_wrap = FrameLayout(act)
            plugins_wrap.setVisibility(View.GONE)
            plugins_wrap.addView(
                plugins_scroll,
                FrameLayout.LayoutParams(-1, scroll_height_px)
            )

            try:
                bg_color = Theme.getColor(Theme.key_dialogBackground)
                transparent = Color.argb(0, (bg_color >> 16) & 0xFF, (bg_color >> 8) & 0xFF, bg_color & 0xFF)

                top_fade = FrameLayout(act)
                top_grd = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, [bg_color, transparent])
                top_fade.setBackground(top_grd)
                top_fade.setClickable(False)
                plugins_wrap.addView(
                    top_fade,
                    FrameLayout.LayoutParams(-1, AndroidUtilities.dp(fade_height_dp), Gravity.TOP)
                )

                bottom_fade = FrameLayout(act)
                bottom_grd = GradientDrawable(GradientDrawable.Orientation.BOTTOM_TOP, [bg_color, transparent])
                bottom_fade.setBackground(bottom_grd)
                bottom_fade.setClickable(False)
                plugins_wrap.addView(
                    bottom_fade,
                    FrameLayout.LayoutParams(-1, AndroidUtilities.dp(fade_height_dp), Gravity.BOTTOM)
                )
            except Exception as e:
                log(f"ExportBottomSheet: gradient overlay error: {e}")

            plugins_wrap_lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                scroll_height_px
            )
            plugins_wrap_lp.leftMargin = AndroidUtilities.dp(pad_h)
            plugins_wrap_lp.rightMargin = AndroidUtilities.dp(pad_h)

            plugins_header = _createSectionHeader(
                act,
                str(strings["utilities_export_plugins_section"]),
                lambda expanded: plugins_wrap.setVisibility(View.VISIBLE if expanded else View.GONE)
            )
            outer.addView(plugins_header, LayoutHelper.createLinear(-1, -2, pad_h, 0, pad_h, 0))
            outer.addView(plugins_wrap, plugins_wrap_lp)

            outer.addView(_createDivider(act), LayoutHelper.createLinear(-1, 1))

            settings_container = LinearLayout(act)
            settings_container.setOrientation(LinearLayout.VERTICAL)
            settings_container.setVisibility(View.GONE)

            settings_row, export_settings_state = _createOptionRow(
                act, str(strings["utilities_export_plugin_settings"]), False, lambda c: None
            )
            settings_container.addView(settings_row, LayoutHelper.createLinear(-1, -2))

            locally_row, export_locally_state = _createOptionRow(
                act, str(strings["utilities_export_locally"]), True, lambda c: None
            )
            settings_container.addView(locally_row, LayoutHelper.createLinear(-1, -2))

            settings_header = _createSectionHeader(
                act,
                str(strings["utilities_export_settings_section"]),
                lambda expanded: settings_container.setVisibility(View.VISIBLE if expanded else View.GONE)
            )
            outer.addView(settings_header, LayoutHelper.createLinear(-1, -2, pad_h, 0, pad_h, 0))
            outer.addView(settings_container, LayoutHelper.createLinear(-1, -2, pad_h, 0, pad_h, 0))

            outer.addView(_createDivider(act), LayoutHelper.createLinear(-1, 1, 0, 8, 0, 0))

            # buttons
            def _onExport():
                selected = [fname for fname, _n, _v, _i in plugins if plugin_states.get(fname, {}).get("checked", True)]
                if not selected:
                    sheet.dismiss()
                    BulletinHelper.show_error(strings["utilities_export_empty"])
                    return
                incl_settings = export_settings_state.get("checked", False)
                locally = export_locally_state.get("checked", True)
                if not locally:
                    sheet.dismiss()
                    BulletinHelper.show_error(strings["not_ready_yet"])
                    return
                sheet.dismiss()
                on_export(selected, incl_settings, locally)

            export_btn = _createButton(act, str(strings["utilities_export_btn"]), True, _onExport)
            outer.addView(export_btn, LayoutHelper.createLinear(-1, -2, pad_h, 8, pad_h, 8))

            close_btn = _createButton(act, str(strings["close_button"]), False, lambda: sheet.dismiss())
            outer.addView(close_btn, LayoutHelper.createLinear(-1, -2, pad_h, 0, pad_h, 8))

            sheet.setCustomView(outer)

            try:
                from .viewUtils import applyFontToTree
                applyFontToTree(outer)
            except Exception:
                pass

            sheet.show()

        except Exception as e:
            log(f"ExportBottomSheet.show: {e}\n{traceback.format_exc()}")

    run_on_ui_thread(_show)
