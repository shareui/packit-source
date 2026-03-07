import struct
import threading
import traceback
from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log, run_on_ui_thread
from java.lang import Integer


def _kill_process():
    try:
        from android.os import Process
        Process.killProcess(Process.myPid())
    except Exception as e:
        log(f"decryptorUi._kill_process: {e}")


class _DocumentHandler(MethodHook):
    def __init__(self, plugin):
        self.lib = plugin

    def before_hooked_method(self, param):
        try:
            filename = str(param.args[1])
            if filename.split(".")[-1] != "packit":
                return

            param.setResult(False)
            file_path = str(param.args[0].getAbsolutePath())
            threading.Thread(target=self._prepare_and_show, args=(file_path,), daemon=True).start()
        except Exception:
            self.lib.log(traceback.format_exc())

    def _prepare_and_show(self, file_path: str):
        try:
            from ...other.exportBin.writer import _decipher, _get_user_id
            from ...other.exportBin.reader import _parse_blocks, _parse_user_id
            from elyx import strings

            with open(file_path, "rb") as f:
                raw = f.read()

            seed = struct.unpack("<I", raw[:4])[0]
            plaintext = _decipher(raw[4:], seed)

            export_user_id = _parse_user_id(plaintext)
            current_user_id = _get_user_id()
            if export_user_id != current_user_id:
                from ui.bulletin import BulletinHelper
                run_on_ui_thread(lambda: BulletinHelper.show_error(strings["import_db_wrong_account"]))
                return

            blocks = _parse_blocks(plaintext)

            from client_utils import get_last_fragment
            from .importBottomSheet import show_import_bottom_sheet

            def on_confirm():
                from ...other.achievements import _hash_account_id
                threading.Thread(target=self._restore, args=(blocks, _hash_account_id(export_user_id)), daemon=True).start()

            def show():
                frag = get_last_fragment()
                if frag:
                    show_import_bottom_sheet(frag, len(blocks), on_confirm)

            run_on_ui_thread(show)
        except Exception:
            self.lib.log(traceback.format_exc())
            self._show_error()

    def _restore(self, blocks: dict, account_id: str):
        try:
            from ...other.exportBin.reader import _write_blocks
            from client_utils import get_last_fragment
            from ui.bulletin import BulletinHelper
            from org.telegram.messenger import R
            from elyx import strings

            _write_blocks(blocks, account_id)

            def show():
                frag = get_last_fragment()
                if frag:
                    BulletinHelper.show_with_button(
                        strings["import_db_done"],
                        R.raw.contact_check,
                        strings["reload"],
                        _kill_process,
                        frag
                    )

            run_on_ui_thread(show)
        except Exception:
            self.lib.log(traceback.format_exc())

    def _show_error(self):
        try:
            from ui.bulletin import BulletinHelper
            from elyx import strings

            run_on_ui_thread(lambda: BulletinHelper.show_error(strings["import_db_error"]))
        except Exception:
            self.lib.log(traceback.format_exc())


def setup_packit_file_hook(plugin) -> list:
    hooks = []
    try:
        method = [
            i for i in (
                find_class("org.telegram.messenger.AndroidUtilities")
                .getClass()
                .getDeclaredMethods()
            )
            if repr(i) == (
                "<java.lang.reflect.Method 'public static boolean org.telegram.messenger.AndroidUtilities.openForView"
                "(java.io.File,java.lang.String,java.lang.String,android.app.Activity,"
                "org.telegram.ui.ActionBar.Theme$ResourcesProvider,boolean)'>"
            )
        ][0]

        hooks.append(plugin.hook_method(method, _DocumentHandler(plugin), Integer.MAX_VALUE))
        log("decryptorUi: hook registered")
    except Exception as e:
        log(f"decryptorUi: setup error: {e}")
    return hooks
