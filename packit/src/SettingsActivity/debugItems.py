from android_utils import log
from client_utils import get_last_fragment
from java import dynamic_proxy
from android.content import DialogInterface


def _show_bulletin(msg: str):
    try:
        from android_utils import run_on_ui_thread
        from ui.bulletin import BulletinHelper
        run_on_ui_thread(lambda: BulletinHelper.show_info(msg))
    except Exception as e:
        log(f"debugItems: _show_bulletin: {e}")


def _test_native_error():
    try:
        _ = 123 / 0
    except Exception as e:
        log(f"debugItems: test native error triggered: {e}")
        from ..nativeLoader import showNativeErrorSheet
        showNativeErrorSheet("libpackitdb.so", str(e))


def _migrate_achievements():
    try:
        import os
        import ctypes
        import zlib
        from ..ui.AchievementsActivity.service.AchivementsEngine import (
            _get_current_account_id, _get_configs_dir, _save_account, _db_to_dict, _lib, _BUF_SIZE
        )

        account_id = _get_current_account_id()
        configs_dir = _get_configs_dir()
        old_path = f"{configs_dir}/achievements.packdb"

        if not os.path.exists(old_path):
            log("debugItems: migrate: old achievements.packdb not found")
            _show_bulletin("No old file found (achievements.packdb missing)")
            return

        if _lib is None:
            log("debugItems: migrate: _lib is None")
            _show_bulletin("Native lib not loaded")
            return

        buf = (ctypes.c_uint8 * _BUF_SIZE)()
        out_len = ctypes.c_uint32(_BUF_SIZE)
        rc = _lib.packdb_read_raw(old_path.encode(), account_id.encode(), buf, ctypes.byref(out_len))
        if rc == -3:
            log(f"debugItems: migrate: INVALID sig in old file for {account_id}")
            _show_bulletin("Signature mismatch — old file belongs to a different account")
            return
        if rc != 0:
            log(f"debugItems: migrate: read_raw error {rc}")
            _show_bulletin(f"Read error: {rc}")
            return

        compressed = bytes(buf[:out_len.value])
        try:
            raw = zlib.decompress(compressed)
        except Exception as e:
            log(f"debugItems: migrate: decompress error: {e}")
            _show_bulletin(f"Decompress error: {e}")
            return

        raw_buf = (ctypes.c_uint8 * len(raw))(*raw)
        db = _lib.packdb_open_from_payload(old_path.encode(), account_id.encode(), raw_buf, len(raw))
        if not db:
            log("debugItems: migrate: packdb_open_from_payload returned NULL")
            _show_bulletin("Failed to open old db")
            return

        data = _db_to_dict(db)
        _lib.packdb_close(db)
        _save_account(data, account_id)
        log(f"debugItems: migrate: done for {account_id}")
        _show_bulletin("Migration done")
    except Exception as e:
        log(f"debugItems: _migrate_achievements: {e}")
        _show_bulletin(f"Error: {e}")


def _inspect_class():
    try:
        from org.telegram.ui.ActionBar import AlertDialog as TgAlertDialog, Theme as TgTheme
        from org.telegram.ui.Components import EditTextBoldCursor
        from android.widget import LinearLayout
        from android.util import TypedValue
        from org.telegram.messenger import AndroidUtilities
        from org.telegram.ui.Components import LayoutHelper
        from java import dynamic_proxy as _dp

        frag = get_last_fragment()
        if not frag:
            return
        act = frag.getParentActivity()
        if not act:
            return

        layout = LinearLayout(act)
        layout.setOrientation(LinearLayout.VERTICAL)

        edit = EditTextBoldCursor(act)
        edit.lineYFix = True
        edit.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 18)
        edit.setHintText("com.example.ClassName")
        edit.setTextColor(TgTheme.getColor(TgTheme.key_dialogTextBlack))
        edit.setHintColor(TgTheme.getColor(TgTheme.key_groupcreate_hintText))
        edit.setFocusable(True)
        edit.setInputType(0x20001)
        edit.setCursorColor(TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputFieldActivated))
        edit.setLineColors(
            TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputField),
            TgTheme.getColor(TgTheme.key_windowBackgroundWhiteInputFieldActivated),
            TgTheme.getColor(TgTheme.key_text_RedRegular)
        )
        edit.setBackground(None)
        edit.setPadding(0, AndroidUtilities.dp(6), 0, AndroidUtilities.dp(6))
        layout.addView(edit, LayoutHelper.createLinear(-1, -2, 24, 0, 24, 10))

        dialog_ref = [None]

        def on_ok(dialog, which):
            class_name = str(edit.getText()).strip()
            if not class_name:
                return
            if dialog_ref[0]:
                dialog_ref[0].dismiss()
            _dump_class_info(class_name)

        class _OkListener(_dp(TgAlertDialog.OnButtonClickListener)):
            def __init__(self): super().__init__()
            def onClick(self, dialog, which): on_ok(dialog, which)

        class _ShowListener(_dp(TgAlertDialog.OnShowListener)):
            def __init__(self): super().__init__()
            def onShow(self, dialog):
                edit.requestFocus()
                AndroidUtilities.showKeyboard(edit)

        builder = TgAlertDialog.Builder(act)
        builder.setTitle("Inspect class")
        builder.makeCustomMaxHeight()
        builder.setView(layout)
        builder.setWidth(AndroidUtilities.dp(292))
        builder.setPositiveButton("Inspect", _OkListener())
        builder.setNegativeButton("Cancel", None)
        dialog = builder.create()
        dialog_ref[0] = dialog
        dialog.setOnShowListener(_ShowListener())
        dialog.show()
    except Exception as e:
        log(f"debugItems._inspect_class: {e}")


def _dump_class_info(class_name: str):
    try:
        from hook_utils import find_class
        cls = find_class(class_name)
        if not cls:
            log(f"inspect: class not found: {class_name}")
            return
        java_cls = cls.getClass()
        log(f"inspect: === {class_name} ===")
        for m in java_cls.getDeclaredMethods():
            params = [p.getName() for p in m.getParameterTypes()]
            ret = m.getReturnType().getName()
            log(f"inspect: method {m.getName()} params={params} -> {ret}")
        for f in java_cls.getDeclaredFields():
            log(f"inspect: field {f.getName()} type={f.getType().getName()}")
        log(f"inspect: === end {class_name} ===")
    except Exception as e:
        log(f"debugItems._dump_class_info: {e}")


def show_debug_menu():
    try:
        from org.telegram.ui.ActionBar import AlertDialog
        from java import jarray
        from java.lang import CharSequence as JCharSequence

        frag = get_last_fragment()
        if not frag:
            return
        act = frag.getParentActivity()
        if not act:
            return

        def _trigger_startup_sheet():
            from ..ui.pluginsUpdates.startupSheet import check_and_show_startup_updates
            check_and_show_startup_updates()

        ITEMS = [
            ("Native error", _test_native_error),
            ("Startup updates sheet", _trigger_startup_sheet),
            ("Migrate current account to new", _migrate_achievements),
            ("Inspect class", _inspect_class),
        ]

        labels = jarray(JCharSequence)([item[0] for item in ITEMS])

        class _OnClick(dynamic_proxy(DialogInterface.OnClickListener)):
            def onClick(self, dialog, which):
                try:
                    ITEMS[which][1]()
                except Exception as e:
                    log(f"debugItems.on_click: {e}")

        builder = AlertDialog.Builder(act)
        builder.setTitle("Debug")
        builder.setItems(labels, _OnClick())
        builder.setNegativeButton("Cancel", None)
        builder.show()
    except Exception as e:
        log(f"debugItems.show_debug_menu: {e}")
