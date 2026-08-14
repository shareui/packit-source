# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os
import ctypes
import traceback
import zipfile

from android_utils import run_on_ui_thread, OnClickListener
from android.view import Gravity, View
from android.widget import FrameLayout, LinearLayout, TextView
from android.util import TypedValue
from android.graphics.drawable import GradientDrawable
from java import dynamic_proxy


def _selected_size(file_path: str, plugins: list) -> int:
    # sum uncompressed sizes of selected plugin entries by their path field in the zip
    try:
        total = 0
        with zipfile.ZipFile(file_path, "r") as zf:
            names = set(zf.namelist())
            for p in plugins:
                path = p.get("path") or ""
                if path and path in names:
                    total += zf.getinfo(path).file_size
        return total
    except Exception as e:
        logx(f"ConfirmImportBottomSheet: size error: {e}", False)
        return 0


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def _merge_plugin_settings(file_path: str, plugin_ids: list):
    # reads settings.json from archive root, merges entries for given plugin_ids into client plugin_settings.json
    import json
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            if "settings.json" not in zf.namelist():
                logx("ConfirmImportBottomSheet: settings.json not found in archive", True)
                return
            archive_settings = json.loads(zf.read("settings.json").decode("utf-8"))
    except Exception as e:
        logx(f"ConfirmImportBottomSheet: failed to read settings.json from archive: {e}", False)
        return

    try:
        from org.telegram.messenger import ApplicationLoader
        client_path = ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath() + "/plugins/plugin_settings.json"
    except Exception as e:
        logx(f"ConfirmImportBottomSheet: failed to get filesDir: {e}", False)
        return

    try:
        with open(client_path, "r", encoding="utf-8") as f:
            client_settings = json.load(f)
    except FileNotFoundError:
        client_settings = {}
    except Exception as e:
        logx(f"ConfirmImportBottomSheet: failed to read client plugin_settings.json: {e}", False)
        return

    merged = 0
    for plugin_id in plugin_ids:
        if plugin_id in archive_settings:
            client_settings[plugin_id] = archive_settings[plugin_id]
            merged += 1
            logx(f"ConfirmImportBottomSheet: merged settings for '{plugin_id}'", True)

    if merged == 0:
        logx("ConfirmImportBottomSheet: no settings to merge for installed plugins", True)
        return

    try:
        with open(client_path, "w", encoding="utf-8") as f:
            json.dump(client_settings, f, ensure_ascii=False, indent=2)
        logx(f"ConfirmImportBottomSheet: wrote settings for {merged} plugin(s)", True)
    except Exception as e:
        logx(f"ConfirmImportBottomSheet: failed to write client plugin_settings.json: {e}", False)


def _make_chip(act, text, color_key):
    try:
        from org.telegram.ui.ActionBar import Theme
        color = Theme.getColor(getattr(Theme, color_key))
    except Exception:
        from org.telegram.ui.ActionBar import Theme
        color = Theme.getColor(Theme.key_windowBackgroundWhiteGrayText)
    r = (color >> 16) & 0xFF
    g = (color >> 8) & 0xFF
    b = color & 0xFF
    fill = ctypes.c_int32((0x33 << 24) | (r << 16) | (g << 8) | b).value
    text_color = ctypes.c_int32((0xFF << 24) | (r << 16) | (g << 8) | b).value
    bg = GradientDrawable()
    bg.setShape(GradientDrawable.RECTANGLE)
    try:
        from org.telegram.messenger import AndroidUtilities
        bg.setCornerRadius(AndroidUtilities.dp(6))
        pad = AndroidUtilities.dp(7)
        pad_v = AndroidUtilities.dp(3)
    except Exception:
        bg.setCornerRadius(6)
        pad = 7
        pad_v = 3
    bg.setColor(fill)
    tv = TextView(act)
    tv.setText(text)
    tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 11)
    tv.setTextColor(text_color)
    tv.setBackground(bg)
    tv.setPadding(pad, pad_v, pad, pad_v)
    return tv


def show(file_path: str, plugins: list, total_count: int = 0, settings: bool = True):
    # plugins: selected list of dicts with keys name, version, icon, path
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
            from org.telegram.ui.Stories.recorder import ButtonWithCounterView

            activity = fragment.getParentActivity()
            if not activity:
                return

            count = len(plugins)
            size_bytes = _selected_size(file_path, plugins)
            size_str = _format_size(size_bytes) if size_bytes > 0 else "? KB"

            sheet = BottomSheet(activity, False, fragment.getResourceProvider())
            sheet.fixNavigationBar()

            pad_h = AndroidUtilities.dp(16)

            root = LinearLayout(activity)
            root.setOrientation(LinearLayout.VERTICAL)

            try:
                bg = GradientDrawable()
                bg.setShape(GradientDrawable.RECTANGLE)
                bg.setCornerRadii([
                    AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                    AndroidUtilities.dp(20), AndroidUtilities.dp(20),
                    0, 0, 0, 0,
                ])
                bg.setColor(Theme.getColor(Theme.key_dialogBackground))
                root.setBackground(bg)
            except Exception:
                try:
                    root.setBackgroundColor(Theme.getColor(Theme.key_dialogBackground))
                except Exception:
                    pass

            # description text
            desc_tv = TextView(activity)
            desc_text = str(strings["afp_confirm_desc"]).replace("{count}", str(count)).replace("{size}", size_str)
            desc_tv.setText(desc_text)
            desc_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
            desc_tv.setGravity(Gravity.CENTER_HORIZONTAL)
            try:
                desc_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
            except Exception:
                pass
            desc_lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            desc_lp.topMargin = AndroidUtilities.dp(20)
            desc_lp.leftMargin = pad_h
            desc_lp.rightMargin = pad_h
            root.addView(desc_tv, desc_lp)

            # size chip
            try:
                chip = _make_chip(activity, size_str, "key_color_cyan")
                chip_lp = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
                chip_lp.gravity = Gravity.CENTER_HORIZONTAL
                chip_lp.topMargin = AndroidUtilities.dp(8)
                root.addView(chip, chip_lp)
            except Exception as e:
                logx(f"ConfirmImportBottomSheet: chip error: {e}", False)

            import_with_settings = [False]

            # "import with settings" checkbox row - only shown when archive has settings
            if settings:
                try:
                    settings_row = LinearLayout(activity)
                    settings_row.setOrientation(LinearLayout.HORIZONTAL)
                    settings_row.setGravity(Gravity.CENTER_VERTICAL)
                    settings_row.setPadding(
                        AndroidUtilities.dp(4), AndroidUtilities.dp(10),
                        AndroidUtilities.dp(4), AndroidUtilities.dp(10)
                    )
                    settings_row.setClickable(True)
                    settings_row.setFocusable(True)

                    cb = None
                    try:
                        from org.telegram.ui.Components import CheckBox2
                        cb = CheckBox2(activity, 21)
                        cb.setColor(Theme.key_radioBackgroundChecked, Theme.key_radioBackground, Theme.key_checkboxCheck)
                        cb.setDrawUnchecked(True)
                        cb.setDrawBackgroundAsArc(14)
                        cb.setChecked(False, False)
                        cb_lp = LinearLayout.LayoutParams(
                            AndroidUtilities.dp(21), AndroidUtilities.dp(21)
                        )
                        cb_lp.rightMargin = AndroidUtilities.dp(8)
                        settings_row.addView(cb, cb_lp)
                    except Exception as e:
                        logx(f"ConfirmImportBottomSheet: checkbox error: {e}", False)

                    settings_label = TextView(activity)
                    settings_label.setText(str(strings["afp_import_with_settings"]))
                    settings_label.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 15)
                    try:
                        settings_label.setTextColor(Theme.getColor(Theme.key_dialogTextBlack))
                    except Exception:
                        pass
                    settings_row.addView(
                        settings_label,
                        LayoutHelper.createLinear(-2, -2, Gravity.CENTER_VERTICAL)
                    )

                    def _onSettingsRowClick(v):
                        import_with_settings[0] = not import_with_settings[0]
                        if cb is not None:
                            cb.setChecked(import_with_settings[0], True)

                    settings_row.setOnClickListener(OnClickListener(_onSettingsRowClick))

                    settings_row_lp = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT
                    )
                    settings_row_lp.gravity = Gravity.CENTER_HORIZONTAL
                    settings_row_lp.topMargin = AndroidUtilities.dp(12)
                    root.addView(settings_row, settings_row_lp)
                except Exception as e:
                    logx(f"ConfirmImportBottomSheet: settings row error: {e}", False)

            # import button
            try:
                import_btn = ButtonWithCounterView(activity, True, fragment.getResourceProvider())
                import_btn.setRound()
                import_btn.setText(str(strings["afp_import_btn"]), False)

                # wrap in FrameLayout so we can overlay a spinner without touching ButtonWithCounterView internals
                btn_wrapper = FrameLayout(activity)
                btn_wrapper.addView(import_btn, FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT
                ))

                spinner_overlay_ref = [None]

                def _set_btn_loading(is_loading):
                    try:
                        import_btn.setEnabled(not is_loading)
                        import_btn.setText("" if is_loading else str(strings["afp_import_btn"]), False)
                        if is_loading:
                            try:
                                from org.telegram.ui.Components import CircularProgressDrawable
                                from android.widget import ImageView
                                btn_color = Theme.getColor(Theme.key_featuredStickers_buttonText)
                                d = CircularProgressDrawable(btn_color)
                                try:
                                    d.size = float(AndroidUtilities.dp(20))
                                    d.thickness = float(AndroidUtilities.dp(2))
                                except Exception as e:
                                    logx(f"ConfirmImportBottomSheet: spinner size error: {e}", False)
                                spin_iv = ImageView(activity)
                                spin_iv.setImageDrawable(d)
                                spin_iv.setScaleType(ImageView.ScaleType.CENTER)
                                overlay_lp = FrameLayout.LayoutParams(
                                    FrameLayout.LayoutParams.MATCH_PARENT,
                                    FrameLayout.LayoutParams.MATCH_PARENT
                                )
                                overlay_lp.gravity = Gravity.CENTER
                                btn_wrapper.addView(spin_iv, overlay_lp)
                                spinner_overlay_ref[0] = spin_iv
                            except Exception as e:
                                logx(f"ConfirmImportBottomSheet: spinner create error: {e}", False)
                        else:
                            if spinner_overlay_ref[0] is not None:
                                try:
                                    btn_wrapper.removeView(spinner_overlay_ref[0])
                                except Exception as e:
                                    logx(f"ConfirmImportBottomSheet: spinner remove error: {e}", False)
                                spinner_overlay_ref[0] = None
                    except Exception as e:
                        logx(f"ConfirmImportBottomSheet: _set_btn_loading error: {e}", False)

                class _ImportClick(dynamic_proxy(View.OnClickListener)):
                    def __init__(self): super().__init__()
                    def onClick(self, v):
                        import threading
                        import zipfile
                        from ..Core import onlyLocalInstallNoUi
                        from ..utils.Paths import getTempDir
                        from ui.bulletin import BulletinHelper
                        from org.telegram.messenger import R as R_tg

                        total = len(plugins)
                        done_count = [0]
                        failed = []  # list of {name, error}
                        installed_ids = []  # plugin_ids that installed successfully
                        lock = threading.Lock()

                        run_on_ui_thread(lambda: _set_btn_loading(True))

                        def _show_errors_sheet(errors):
                            try:
                                from org.telegram.messenger import AndroidUtilities as AU
                                err_sheet = BottomSheet(activity, False, fragment.getResourceProvider())
                                err_sheet.fixNavigationBar()

                                err_root = LinearLayout(activity)
                                err_root.setOrientation(LinearLayout.VERTICAL)
                                try:
                                    err_bg = GradientDrawable()
                                    err_bg.setShape(GradientDrawable.RECTANGLE)
                                    err_bg.setCornerRadii([
                                        AU.dp(20), AU.dp(20),
                                        AU.dp(20), AU.dp(20),
                                        0, 0, 0, 0,
                                    ])
                                    err_bg.setColor(Theme.getColor(Theme.key_dialogBackground))
                                    err_root.setBackground(err_bg)
                                except Exception:
                                    pass

                                from android.widget import ScrollView
                                scroll = ScrollView(activity)

                                inner = LinearLayout(activity)
                                inner.setOrientation(LinearLayout.VERTICAL)
                                inner.setPadding(pad_h, AU.dp(16), pad_h, AU.dp(8))

                                # header
                                header_tv = TextView(activity)
                                header_tv.setText(str(strings["afp_problematic_plugins"]))
                                header_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 17)
                                header_tv.setTypeface(AndroidUtilities.bold())
                                try:
                                    header_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                                except Exception:
                                    pass
                                inner.addView(header_tv, LinearLayout.LayoutParams(
                                    LinearLayout.LayoutParams.MATCH_PARENT,
                                    LinearLayout.LayoutParams.WRAP_CONTENT
                                ))

                                # each failed plugin
                                import ctypes as _ct
                                from android.view import MotionEvent

                                try:
                                    red_color = Theme.getColor(Theme.key_color_red)
                                except Exception:
                                    red_color = 0xFFFF7043
                                r_c = (red_color >> 16) & 0xFF
                                g_c = (red_color >> 8) & 0xFF
                                b_c = red_color & 0xFF
                                fill_color = _ct.c_int32((0x18 << 24) | (r_c << 16) | (g_c << 8) | b_c).value
                                stroke_color = _ct.c_int32((0xFF << 24) | (r_c << 16) | (g_c << 8) | b_c).value

                                def _make_err_bg():
                                    bg = GradientDrawable()
                                    bg.setShape(GradientDrawable.RECTANGLE)
                                    bg.setCornerRadius(AU.dp(10))
                                    bg.setColor(fill_color)
                                    bg.setStroke(AU.dp(1), stroke_color)
                                    return bg

                                def _attach_err_copy(frame, tv, plugin_id, err_text):
                                    copy_text = f"{plugin_id} error: {err_text}"

                                    class _ErrTouch(dynamic_proxy(View.OnTouchListener)):
                                        def __init__(self): super().__init__()
                                        def onTouch(self, v, event):
                                            try:
                                                action = event.getActionMasked()
                                                if action == MotionEvent.ACTION_DOWN:
                                                    frame.animate().scaleX(0.95).scaleY(0.95).setDuration(100).start()
                                                elif action == MotionEvent.ACTION_UP:
                                                    frame.animate().scaleX(1.0).scaleY(1.0).setDuration(150).start()
                                                    try:
                                                        from org.telegram.messenger import AndroidUtilities as AU2
                                                        AU2.addToClipboard(copy_text)
                                                    except Exception as ex:
                                                        logx(f"ConfirmImportBottomSheet: err copy error: {ex}", True)
                                                    tv.setText(str(strings["afp_copied"]))
                                                    def _restore(ref=tv, orig=err_text):
                                                        ref.setText(orig)
                                                    run_on_ui_thread(_restore, 300)
                                                elif action == MotionEvent.ACTION_CANCEL:
                                                    frame.animate().scaleX(1.0).scaleY(1.0).setDuration(150).start()
                                            except Exception:
                                                pass
                                            return True
                                    tv.setOnTouchListener(_ErrTouch())
                                    tv.setClickable(True)
                                    tv.setFocusable(True)

                                def _lock_frame_height(frame):
                                    # fix height after first layout so text change doesn't resize the box
                                    from android.view import ViewTreeObserver
                                    from java import dynamic_proxy as dp2

                                    class _LayoutListener(dp2(ViewTreeObserver.OnGlobalLayoutListener)):
                                        def __init__(self): super().__init__()
                                        def onGlobalLayout(self):
                                            try:
                                                h = frame.getHeight()
                                                if h > 0:
                                                    lp = frame.getLayoutParams()
                                                    lp.height = h
                                                    frame.setLayoutParams(lp)
                                                    frame.getViewTreeObserver().removeOnGlobalLayoutListener(self)
                                            except Exception:
                                                pass
                                    try:
                                        frame.getViewTreeObserver().addOnGlobalLayoutListener(_LayoutListener())
                                    except Exception as e:
                                        logx(f"ConfirmImportBottomSheet: lock_frame_height error: {e}", False)

                                def _trim_err(err_str: str) -> str:
                                    # keep only first line for non-validation errors (java stacktraces)
                                    nl = err_str.find("\n\t")
                                    if nl != -1:
                                        return err_str[:nl].strip()
                                    return err_str

                                for entry in errors:
                                    name = entry.get("name") or entry.get("id") or "unknown"
                                    plugin_id = entry.get("id") or entry.get("name") or "unknown"
                                    err_str = _trim_err(str(entry.get("error") or "unknown error"))

                                    # title: "There is an error in plugin {name}:"
                                    title_tv = TextView(activity)
                                    title_tv.setText(str(strings("afp_plugin_error", name=name)))
                                    title_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                                    title_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                                    try:
                                        title_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText))
                                    except Exception:
                                        pass
                                    title_lp = LinearLayout.LayoutParams(
                                        LinearLayout.LayoutParams.MATCH_PARENT,
                                        LinearLayout.LayoutParams.WRAP_CONTENT
                                    )
                                    title_lp.topMargin = AU.dp(12)
                                    inner.addView(title_tv, title_lp)

                                    # error text in red-bordered box, clickable to copy
                                    # height locked after first layout so "Copied!" doesn't resize the box
                                    err_frame = FrameLayout(activity)
                                    err_frame.setBackground(_make_err_bg())

                                    err_tv = TextView(activity)
                                    err_tv.setText(err_str)
                                    err_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                                    err_tv.setGravity(Gravity.CENTER)
                                    err_tv.setTextColor(stroke_color)
                                    err_tv.setPadding(AU.dp(10), AU.dp(8), AU.dp(10), AU.dp(8))
                                    err_tv_lp = FrameLayout.LayoutParams(
                                        FrameLayout.LayoutParams.MATCH_PARENT,
                                        FrameLayout.LayoutParams.MATCH_PARENT
                                    )
                                    err_tv_lp.gravity = Gravity.CENTER
                                    err_frame.addView(err_tv, err_tv_lp)

                                    _lock_frame_height(err_frame)
                                    _attach_err_copy(err_frame, err_tv, plugin_id, err_str)
                                    err_lp = LinearLayout.LayoutParams(
                                        LinearLayout.LayoutParams.MATCH_PARENT,
                                        LinearLayout.LayoutParams.WRAP_CONTENT
                                    )
                                    err_lp.topMargin = AU.dp(6)
                                    inner.addView(err_frame, err_lp)

                                # footer
                                ok_count = total - len(errors)
                                if ok_count > 0:
                                    footer_tv = TextView(activity)
                                    footer_tv.setText(str(strings["afp_rest_installed"]))
                                    footer_tv.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 13)
                                    footer_tv.setGravity(Gravity.CENTER_HORIZONTAL)
                                    try:
                                        footer_tv.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteGrayText))
                                    except Exception:
                                        pass
                                    footer_lp = LinearLayout.LayoutParams(
                                        LinearLayout.LayoutParams.MATCH_PARENT,
                                        LinearLayout.LayoutParams.WRAP_CONTENT
                                    )
                                    footer_lp.topMargin = AU.dp(12)
                                    inner.addView(footer_tv, footer_lp)

                                scroll.addView(inner)
                                err_root.addView(scroll, LinearLayout.LayoutParams(
                                    LinearLayout.LayoutParams.MATCH_PARENT,
                                    LinearLayout.LayoutParams.WRAP_CONTENT
                                ))

                                # copy all errors button
                                copy_btn = ButtonWithCounterView(activity, True, fragment.getResourceProvider())
                                copy_btn.setRound()
                                copy_btn.setText(str(strings["afp_copy_all_errors"]), False)

                                def _on_copy(v):
                                    all_text = "\n\n".join(
                                        f"{e.get('id') or e.get('name') or 'unknown'} error: {_trim_err(str(e.get('error') or ''))}"
                                        for e in errors
                                    )
                                    try:
                                        from org.telegram.messenger import AndroidUtilities as AU2
                                        AU2.addToClipboard(all_text)
                                    except Exception as ex:
                                        logx(f"ConfirmImportBottomSheet: copy error: {ex}", True)
                                    copy_btn.setText(str(strings["afp_copied"]), True)

                                copy_btn.setOnClickListener(OnClickListener(_on_copy))
                                copy_lp = LinearLayout.LayoutParams(
                                    LinearLayout.LayoutParams.MATCH_PARENT,
                                    AU.dp(48)
                                )
                                copy_lp.topMargin = AU.dp(12)
                                copy_lp.leftMargin = pad_h
                                copy_lp.rightMargin = pad_h
                                err_root.addView(copy_btn, copy_lp)

                                # close button
                                err_close_btn = ButtonWithCounterView(activity, False, fragment.getResourceProvider())
                                err_close_btn.setRound()
                                err_close_btn.setNeutral()
                                err_close_btn.setText(str(strings["close_button"]), False)
                                err_close_btn.setOnClickListener(OnClickListener(lambda v: err_sheet.dismiss()))
                                close2_lp = LinearLayout.LayoutParams(
                                    LinearLayout.LayoutParams.MATCH_PARENT,
                                    AU.dp(48)
                                )
                                close2_lp.topMargin = AU.dp(8)
                                close2_lp.leftMargin = pad_h
                                close2_lp.rightMargin = pad_h
                                err_root.addView(err_close_btn, close2_lp)

                                err_sheet.setCustomView(err_root)
                                err_sheet.show()
                            except Exception as e:
                                logx(f"ConfirmImportBottomSheet: errors sheet error: {e}\n{traceback.format_exc()}", False)

                        def on_plugin_done(plugin_name, error, plugin_id=None):
                            with lock:
                                done_count[0] += 1
                                if error:
                                    failed.append({"name": plugin_name, "error": error})
                                elif plugin_id:
                                    installed_ids.append(plugin_id)
                                all_done = done_count[0] >= total
                            if not all_done:
                                return
                            if import_with_settings[0] and installed_ids:
                                _merge_plugin_settings(file_path, installed_ids)
                            sheet.dismiss()
                            if failed:
                                def _show():
                                    try:
                                        BulletinHelper.show_with_button(
                                            "Completed with several errors",
                                            R_tg.raw.error,
                                            "Details",
                                            lambda: _show_errors_sheet(failed),
                                            fragment
                                        )
                                    except Exception as e:
                                        logx(f"ConfirmImportBottomSheet: bulletin error: {e}", False)
                                run_on_ui_thread(_show)
                            else:
                                run_on_ui_thread(lambda: BulletinHelper.show_success(str(strings["afp_import_success"])))

                        def _run_installs():
                            try:
                                import re as _re
                                from ..utils.AppVersion import _parse_version, _get_app_version
                                tmp_dir = getTempDir()
                                os.makedirs(tmp_dir, exist_ok=True)
                                with zipfile.ZipFile(file_path, "r") as zf:
                                    for p in plugins:
                                        arc_path = p.get("path") or ""
                                        plugin_name = p.get("name") or os.path.splitext(os.path.basename(arc_path))[0]

                                        # validate id
                                        plugin_id = p.get("id") or os.path.splitext(os.path.basename(arc_path))[0]
                                        logx(f"ConfirmImportBottomSheet: validating id='{plugin_id}' for '{plugin_name}'", True)
                                        id_valid = (
                                            2 <= len(plugin_id) <= 32
                                            and plugin_id[0].isalpha()
                                            and bool(_re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', plugin_id))
                                        )
                                        if not id_valid:
                                            logx(f"ConfirmImportBottomSheet: id validation failed for '{plugin_name}': id='{plugin_id}'", True)
                                            on_plugin_done(plugin_name, "ID must be 2-32 characters long, the first character is always a letter and must not contain any non-English letters.")
                                            continue
                                        logx(f"ConfirmImportBottomSheet: id ok for '{plugin_name}'", True)

                                        # validate app_version
                                        app_version_expr = str(p.get("app_version") or "").strip()
                                        logx(f"ConfirmImportBottomSheet: validating app_version='{app_version_expr}' for '{plugin_name}'", True)
                                        if app_version_expr:
                                            try:
                                                client_ver = _get_app_version()
                                                if app_version_expr.startswith(">=") or app_version_expr.startswith("=>"):
                                                    op, req_str = ">=", app_version_expr[2:]
                                                elif app_version_expr.startswith("<=") or app_version_expr.startswith("=<"):
                                                    op, req_str = "<=", app_version_expr[2:]
                                                elif app_version_expr.startswith("=="):
                                                    op, req_str = "==", app_version_expr[2:]
                                                else:
                                                    op, req_str = None, None

                                                if op is not None:
                                                    client_t = _parse_version(client_ver)
                                                    req_t = _parse_version(req_str.strip())
                                                    if op == ">=":
                                                        compat = client_t >= req_t
                                                    elif op == "<=":
                                                        compat = client_t <= req_t
                                                    else:
                                                        compat = client_t == req_t
                                                    logx(f"ConfirmImportBottomSheet: app_version check: client={client_ver} {op} required={req_str.strip()} -> compat={compat}", True)
                                                    if not compat:
                                                        on_plugin_done(plugin_name, f"The client version is not compatible with the plugin. Client version: {client_ver}, plugin version: {app_version_expr}.")
                                                        continue
                                                else:
                                                    logx(f"ConfirmImportBottomSheet: app_version '{app_version_expr}' has no known operator, skipping check", True)
                                            except Exception as e:
                                                logx(f"ConfirmImportBottomSheet: app_version check error for '{plugin_name}': {e}", False)
                                        logx(f"ConfirmImportBottomSheet: app_version ok for '{plugin_name}'", True)

                                        if not arc_path:
                                            on_plugin_done(plugin_name, "missing path")
                                            continue
                                        try:
                                            zf.extract(arc_path, tmp_dir)
                                            extracted = os.path.join(tmp_dir, arc_path)
                                        except Exception as e:
                                            logx(f"ConfirmImportBottomSheet: extract error for {arc_path}: {e}", False)
                                            on_plugin_done(plugin_name, e)
                                            continue
                                        logx(f"ConfirmImportBottomSheet: starting install for '{plugin_name}' id='{plugin_id}'", True)
                                        onlyLocalInstallNoUi(extracted, plugin_id,
                                                             lambda err, _n=plugin_name, _id=plugin_id: on_plugin_done(_n, err, _id))
                            except Exception as e:
                                logx(f"ConfirmImportBottomSheet: _run_installs error: {e}\n{traceback.format_exc()}", False)
                                for p in plugins:
                                    on_plugin_done(p.get("name") or "unknown", e)

                        if total == 0:
                            sheet.dismiss()
                        else:
                            threading.Thread(target=_run_installs, daemon=True).start()

                import_btn.setOnClickListener(_ImportClick())
                import_lp = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    AndroidUtilities.dp(48)
                )
                import_lp.topMargin = AndroidUtilities.dp(16)
                import_lp.leftMargin = pad_h
                import_lp.rightMargin = pad_h
                root.addView(btn_wrapper, import_lp)
            except Exception as e:
                logx(f"ConfirmImportBottomSheet: import btn error: {e}", False)

            # close button
            try:
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
            except Exception as e:
                logx(f"ConfirmImportBottomSheet: close btn error: {e}", False)

            sheet.setCustomView(root)
            sheet.show()

        except Exception as e:
            logx(f"ConfirmImportBottomSheet.show: {e}\n{traceback.format_exc()}", False)

    run_on_ui_thread(_show)