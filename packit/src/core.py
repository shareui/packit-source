import os
import threading
import requests
from android_utils import log, run_on_ui_thread
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
from android.widget import ProgressBar, LinearLayout
try:
    from org.telegram.messenger import ApplicationLoader, AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.plugins import PluginsController
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.plugins import PluginsController failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import NotificationCenter
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import NotificationCenter failed: {e}")
    from .other.importFailed import showImportFailedAlert as _sifa; _sifa()
import time
import signal


def _get_real_dialog(dlg):
    try:
        return dlg.get_dialog() if hasattr(dlg, "get_dialog") else dlg
    except Exception:
        return dlg

def _is_showing(dlg):
    try:
        real = _get_real_dialog(dlg)
        return real and hasattr(real, "isShowing") and real.isShowing()
    except Exception:
        return False

def _set_progress(dlg, value: int):
    def action():
        try:
            if _is_showing(dlg):
                dlg.set_progress(value)
        except Exception:
            pass
    run_on_ui_thread(action)

def _dismiss_dialog(dlg):
    def action():
        try:
            real = _get_real_dialog(dlg)
            if real and real.isShowing():
                real.dismiss()
        except Exception:
            pass
    run_on_ui_thread(action)


def _is_elyx_plugin(plugin_info: dict) -> bool:
    tags = plugin_info.get("tags") or []
    for tag in tags:
        if isinstance(tag, (list, tuple)) and len(tag) > 0 and tag[0] == "Elyx":
            return True
    return False

def install_plugin(plugin_info: dict, icon_view=None, button=None, original_icon_id=None, loading_view=None, on_finish=None):
    plugin_id = plugin_info.get("id")
    url = plugin_info.get("link") or plugin_info.get("raw")

    if not plugin_id or not url:
        BulletinHelper.show_error("Plugin has no link")
        try:
            if on_finish:
                run_on_ui_thread(lambda: on_finish(False))
        except Exception:
            pass
        return

    fragment = get_last_fragment()
    if not fragment:
        try:
            if on_finish:
                run_on_ui_thread(lambda: on_finish(False))
        except Exception:
            pass
        return

    # called from UI thread (onClick), so we create dialog synchronously here
    from ui.alert import AlertDialogBuilder
    ctx = fragment.getContext()
    builder = AlertDialogBuilder(ctx, AlertDialogBuilder.ALERT_TYPE_LOADING)
    builder.set_title("Downloading...")
    builder.set_cancelable(False)
    dlg = builder.show()
    dlg.set_progress(0)

    def task():
        try:
            r = requests.get(url, stream=True, timeout=30)
            if r.status_code != 200:
                log(f"core.install_plugin: failed to download '{plugin_id}' from '{url}': HTTP {r.status_code}")
                _dismiss_dialog(dlg)
                if r.status_code == 404:
                    try:
                        from elyx import strings as _strings
                        _msg = _strings["file_not_found"]
                    except Exception:
                        _msg = "File not found :("
                    run_on_ui_thread(lambda: BulletinHelper.show_error(_msg))
                    try:
                        if on_finish:
                            run_on_ui_thread(lambda: on_finish(False))
                    except Exception:
                        pass
                    return
                raise Exception(f"HTTP {r.status_code}")

            pkg = ApplicationLoader.applicationContext.getPackageName()
            plugins_dir = f"/data/data/{pkg}/files/plugins"
            try:
                os.makedirs(plugins_dir, exist_ok=True)
            except Exception:
                pass

            temp_path = os.path.join(plugins_dir, f".temp_{plugin_id}.plugin")

            content_length = r.headers.get("content-length")
            total = int(content_length) if content_length else 0
            downloaded = 0

            # read raw compressed stream so downloaded bytes match content-length
            r.raw.decode_content = False
            encoding = r.headers.get("content-encoding", "").lower()
            with open(temp_path, "wb") as f:
                if encoding in ("gzip", "deflate") and total:
                    import zlib
                    decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
                    while True:
                        chunk = r.raw.read(8192)
                        if not chunk:
                            break
                        try:
                            f.write(decompressor.decompress(chunk))
                        except Exception:
                            f.write(chunk)
                        downloaded += len(chunk)
                        percent = min(99, int(downloaded * 100 / total))
                        _set_progress(dlg, percent)
                    try:
                        f.write(decompressor.flush())
                    except Exception:
                        pass
                else:
                    while True:
                        chunk = r.raw.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        if total:
                            downloaded += len(chunk)
                            percent = min(99, int(downloaded * 100 / total))
                            _set_progress(dlg, percent)

            _dismiss_dialog(dlg)

            def open_install_dialog():
                try:
                    if loading_view and button and icon_view:
                        def _restore_icon():
                            try:
                                button.removeView(loading_view)
                            except Exception:
                                pass
                            icon_view.setImageResource(original_icon_id)
                            lp = LinearLayout.LayoutParams(AndroidUtilities.dp(20), AndroidUtilities.dp(20))
                            lp.rightMargin = AndroidUtilities.dp(6)
                            button.addView(icon_view, 0, lp)
                            button.invalidate()

                        run_on_ui_thread(_restore_icon)

                    if _is_elyx_plugin(plugin_info):
                        from elyxcore import ElyxEngine
                        from com.exteragram.messenger.plugins.ui.components import InstallPluginBottomSheet
                        install_params = InstallPluginBottomSheet.PluginInstallParams(temp_path, False)
                        ElyxEngine.instance.showInstallDialog(fragment, install_params)
                    else:
                        PluginsController.getInstance().showInstallDialog(fragment, temp_path, True)
                    try:
                        from .other.achievements import increment_category
                        increment_category("Installing plugins")
                    except Exception as e:
                        log(f"core.install_plugin: achievements increment error: {e}")
                    try:
                        if on_finish:
                            on_finish(True)
                    except Exception:
                        pass
                except Exception as e:
                    BulletinHelper.show_error(f"Failed to open install dialog: {e}")
                    try:
                        if on_finish:
                            on_finish(False)
                    except Exception:
                        pass

            run_on_ui_thread(open_install_dialog)
        except Exception as e:
            log(f"core.install_plugin: error downloading '{plugin_id}' from '{url}': {e}")
            _dismiss_dialog(dlg)
            run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while downloading"))
            try:
                if on_finish:
                    run_on_ui_thread(lambda: on_finish(False))
            except Exception:
                pass

    threading.Thread(target=task, daemon=True).start()


class PackItCore:
    def __init__(self, repoManager):
        self.repoManager = repoManager

    def _showErrorOnUi(self, text: str):
        def show():
            BulletinHelper.show_error(text)
        run_on_ui_thread(show)

    def _showSuccessOnUi(self, text: str):
        def show():
            BulletinHelper.show_success(text)
        run_on_ui_thread(show)