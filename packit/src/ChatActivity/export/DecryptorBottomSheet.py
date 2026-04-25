import json
import threading
import traceback
from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log, run_on_ui_thread
from java.lang import Integer


def _kill_process(*_):
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
            from ...ChatActivity.export.bin.writer import _get_user_id, _get_install_ts
            from ...ChatActivity.export.bin.reader import read_file
            from elyx import strings

            current_user_id = _get_user_id()
            install_ts      = _get_install_ts()

            blocks, export_user_id = read_file(file_path, current_user_id, install_ts)

            if export_user_id != current_user_id:
                run_on_ui_thread(lambda: BulletinHelper_show_wrong_account(strings))
                return

            import_level = None
            import_xp    = None
            if "achievements" in blocks:
                try:
                    from ...ui.AchievementsActivity.service.AchivementsEngine import get_level_info
                    achievements_data = json.loads(blocks["achievements"])

                    def _is_hashed_id(k: str) -> bool:
                        return len(k) == 16 and all(c in "0123456789abcdef" for c in k)

                    if isinstance(achievements_data, dict) and achievements_data and all(_is_hashed_id(k) for k in achievements_data):
                        from ...ui.AchievementsActivity.service.AchivementsEngine import _hash_account_id
                        account_data = achievements_data.get(_hash_account_id(export_user_id), {})
                    elif isinstance(achievements_data, dict):
                        account_data = achievements_data
                    else:
                        account_data = {}

                    import_level, import_xp, _ = get_level_info(account_data)
                except Exception as e:
                    log(f"decryptorUi: failed to extract level info: {e}")

            from client_utils import get_last_fragment
            from .ImportBottomSheet import show_import_bottom_sheet

            def on_confirm():
                from ...ui.AchievementsActivity.service.AchivementsEngine import _hash_account_id
                account_id = _hash_account_id(export_user_id)
                threading.Thread(target=self._restore, args=(blocks, account_id), daemon=True).start()

            def show():
                frag = get_last_fragment()
                if frag:
                    show_import_bottom_sheet(frag, len(blocks), on_confirm, import_level, import_xp)

            run_on_ui_thread(show)
        except Exception:
            self.lib.log(traceback.format_exc())
            self._show_error()

    def _restore(self, blocks: dict, account_id: str):
        try:
            from ...ChatActivity.export.bin.reader import _write_blocks
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


def BulletinHelper_show_wrong_account(strings):
    try:
        from ui.bulletin import BulletinHelper
        BulletinHelper.show_error(strings["import_db_wrong_account"])
    except Exception as e:
        log(f"decryptorUi: show_wrong_account: {e}")


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
