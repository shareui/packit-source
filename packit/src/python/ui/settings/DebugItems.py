# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later


from packutil import logx
from client_utils import get_last_fragment
from java import dynamic_proxy
from android.content import DialogInterface


def _show_bulletin(msg: str):
    try:
        from android_utils import run_on_ui_thread
        from ui.bulletin import BulletinHelper
        run_on_ui_thread(lambda: BulletinHelper.show_info(msg))
    except Exception as e:
        logx(f"debugItems: _show_bulletin: {e}", False)


def _test_native_error():
    try:
        _ = 123 / 0
    except Exception as e:
        logx(f"debugItems: test native error triggered: {e}", False)
        from ...core.NativeLoader import showNativeErrorSheet
        showNativeErrorSheet("libpackitdb.so", str(e))


def _migrate_achievements():
    try:
        import os
        import ctypes
        import zlib
        from ..achievements.service.AchivementsEngine import (
            _get_current_account_id, _get_configs_dir, _save_account, _db_to_dict, _lib, _BUF_SIZE
        )

        account_id = _get_current_account_id()
        configs_dir = _get_configs_dir()
        old_path = f"{configs_dir}/achievements.packdb"

        if not os.path.exists(old_path):
            logx("debugItems: migrate: old achievements.packdb not found", True)
            _show_bulletin("No old file found (achievements.packdb missing)")
            return

        if _lib is None:
            logx("debugItems: migrate: _lib is None", True)
            _show_bulletin("Native lib not loaded")
            return

        buf = (ctypes.c_uint8 * _BUF_SIZE)()
        out_len = ctypes.c_uint32(_BUF_SIZE)
        rc = _lib.packdb_read_raw(old_path.encode(), account_id.encode(), buf, ctypes.byref(out_len))
        if rc == -3:
            logx(f"debugItems: migrate: INVALID sig in old file for {account_id}", True)
            _show_bulletin("Signature mismatch — old file belongs to a different account")
            return
        if rc != 0:
            logx(f"debugItems: migrate: read_raw error {rc}", True)
            _show_bulletin(f"Read error: {rc}")
            return

        compressed = bytes(buf[:out_len.value])
        try:
            raw = zlib.decompress(compressed)
        except Exception as e:
            logx(f"debugItems: migrate: decompress error: {e}", False)
            _show_bulletin(f"Decompress error: {e}")
            return

        raw_buf = (ctypes.c_uint8 * len(raw))(*raw)
        db = _lib.packdb_open_from_payload(old_path.encode(), account_id.encode(), raw_buf, len(raw))
        if not db:
            logx("debugItems: migrate: packdb_open_from_payload returned NULL", True)
            _show_bulletin("Failed to open old db")
            return

        data = _db_to_dict(db)
        _lib.packdb_close(db)
        _save_account(data, account_id)
        logx(f"debugItems: migrate: done for {account_id}", True)
        _show_bulletin("Migration done")
    except Exception as e:
        logx(f"debugItems: _migrate_achievements: {e}", False)
        _show_bulletin(f"Error: {e}")


def _show_class_input_dialog(title: str, on_submit):
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
            on_submit(class_name)

        class _OkListener(_dp(TgAlertDialog.OnButtonClickListener)):
            def __init__(self): super().__init__()
            def onClick(self, dialog, which): on_ok(dialog, which)

        class _ShowListener(_dp(TgAlertDialog.OnShowListener)):
            def __init__(self): super().__init__()
            def onShow(self, dialog):
                edit.requestFocus()
                AndroidUtilities.showKeyboard(edit)

        builder = TgAlertDialog.Builder(act)
        builder.setTitle(title)
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
        logx(f"debugItems._show_class_input_dialog: {e}", False)


def _inspect_class():
    _show_class_input_dialog("Inspect class", lambda name: _dump_class_info(name, methods=True, fields=True))


def _inspect_methods():
    _show_class_input_dialog("Inspect methods", lambda name: _dump_class_info(name, methods=True, fields=False))


def _resolve_java_class(class_name: str):
    from hook_utils import find_class
    cls = None
    try:
        cls = find_class(class_name)
    except Exception:
        pass
    if cls is None:
        try:
            frag = get_last_fragment()
            if frag is not None:
                cl = frag.getClass().getClassLoader()
                if cl is not None:
                    cls = cl.loadClass(class_name)
        except Exception:
            pass
    if cls is None:
        return None, None
    java_cls = None
    try:
        from java.lang import Thread as JThread
        from java.lang import Class as JClass
        cl = JThread.currentThread().getContextClassLoader()
        java_cls = JClass.forName(class_name, True, cl)
    except Exception:
        pass
    if java_cls is None:
        try:
            frag = get_last_fragment()
            from java.lang import Class as JClass
            cl = frag.getClass().getClassLoader()
            java_cls = JClass.forName(class_name, True, cl)
        except Exception:
            pass
    if java_cls is None:
        java_cls = cls.getClass()
    return cls, java_cls


def _dump_class_info(class_name: str, methods: bool = True, fields: bool = True):
    try:
        cls, java_cls = _resolve_java_class(class_name)
        if java_cls is None:
            # try dex scan
            simple_name = class_name.split(".")[-1]
            candidates = []
            try:
                from java.lang import Thread as JThread
                from hook_utils import get_private_field
                cl = JThread.currentThread().getContextClassLoader()
                path_list = get_private_field(cl, "pathList")
                dex_elements = get_private_field(path_list, "dexElements")
                for elem in dex_elements:
                    dex_file = get_private_field(elem, "dexFile")
                    if dex_file is None:
                        continue
                    entries = dex_file.entries()
                    while entries.hasMoreElements():
                        entry = str(entries.nextElement())
                        if entry.endswith(f".{simple_name}") or entry == simple_name:
                            candidates.append(entry)
            except Exception as e:
                logx(f"inspect: dex scan failed: {e}", False)
            if candidates:
                logx(f"inspect: dex candidates for '{simple_name}': {candidates}", True)
                _show_bulletin(f"Not found, dex has {len(candidates)} candidate(s) — check log")
            else:
                _show_bulletin(f"Class not found: {class_name}")
            return
        if methods:
            try:
                for m in java_cls.getDeclaredMethods():
                    try:
                        params = [p.getName() for p in m.getParameterTypes()]
                        ret = m.getReturnType().getName()
                        logx(f"method {m.getName()} {params} -> {ret}", True)
                    except Exception as me:
                        logx(f"method dump error: {me}", True)
            except Exception as e:
                logx(f"getDeclaredMethods failed: {e}", False)
        if fields:
            try:
                for f in java_cls.getDeclaredFields():
                    try:
                        logx(f"field {f.getName()} {f.getType().getName()}", True)
                    except Exception as fe:
                        logx(f"field dump error: {fe}", True)
            except Exception as e:
                logx(f"getDeclaredFields failed: {e}", False)
        logx(f"inspect done: {class_name}", True)
    except Exception as e:
        logx(f"debugItems._dump_class_info: {e}", False)


def _check_build_info():
    try:
        from ...utils.BuildInfo import (
            getBuildClientName, getBuildClientPkg,
            getCurrClientName, getCurrClientPkg,
            getBuildStaticVersion, getClientVersion
        )
        logx(f"buildInfo.getBuildClientName: {getBuildClientName()}", True)
        logx(f"buildInfo.getBuildClientPkg: {getBuildClientPkg()}", True)
        logx(f"buildInfo.getCurrClientName: {getCurrClientName()}", True)
        logx(f"buildInfo.getCurrClientPkg: {getCurrClientPkg()}", True)
        logx(f"buildInfo.getBuildStaticVersion: {getBuildStaticVersion()}", True)
        logx(f"buildInfo.getClientVersion: {getClientVersion()}", True)
    except Exception as e:
        logx(f"debugItems._check_build_info: {e}", False)


def _migrate_installdate_to_b64():
    try:
        import os, json, base64
        from ...utils.LocalConfig import _get_install_date_path
        path = _get_install_date_path()
        if not os.path.exists(path):
            _show_bulletin("InstallDate not found")
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        date_val = data.get("date", "")
        if not date_val:
            _show_bulletin("No date field")
            return
            
        try:
            decoded = base64.b64decode(date_val).decode("utf-8")
            from datetime import date
            date.fromisoformat(decoded)
            _show_bulletin("Already migrated")
            return
        except Exception:
            pass
            
        b64_date = base64.b64encode(date_val.encode("utf-8")).decode("utf-8")
        data["date"] = b64_date
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        _show_bulletin("Migrated to b64")
    except Exception as e:
        logx(f"debugItems._migrate_installdate_to_b64: {e}", False)
        _show_bulletin(f"Error: {e}")


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
            from ..updates.StartupSheet import check_and_show_startup_updates
            check_and_show_startup_updates()

        def _update_repos_cache():
            from ...core.RepositoryManager import RepositoryManager
            RepositoryManager().updateAllCaches(
                on_complete=lambda: _show_bulletin("Repos cache updated")
            )

        ITEMS = [
            ("Native error", _test_native_error),
            ("Startup updates sheet", _trigger_startup_sheet),
            ("Update repos cache", _update_repos_cache),
            ("Migrate current account to new", _migrate_achievements),
            ("Inspect class", _inspect_class),
            ("Inspect methods", _inspect_methods),
            ("Check Build Info", _check_build_info),
            ("migrate to 64", _migrate_installdate_to_b64),
        ]

        labels = jarray(JCharSequence)([item[0] for item in ITEMS])

        class _OnClick(dynamic_proxy(DialogInterface.OnClickListener)):
            def onClick(self, dialog, which):
                try:
                    ITEMS[which][1]()
                except Exception as e:
                    logx(f"debugItems.on_click: {e}", False)

        builder = AlertDialog.Builder(act)
        builder.setTitle("Debug")
        builder.setItems(labels, _OnClick())
        builder.setNegativeButton("Cancel", None)
        builder.show()
    except Exception as e:
        logx(f"debugItems.show_debug_menu: {e}", False)