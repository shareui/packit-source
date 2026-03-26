import os
import threading
import requests
from android_utils import log, run_on_ui_thread
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper
from android.widget import ProgressBar, LinearLayout
from java import dynamic_proxy
try:
    from org.telegram.messenger import ApplicationLoader, AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import ApplicationLoader failed: {e}")
    from .utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from com.exteragram.messenger.plugins import PluginsController
except Exception as e:
    import android_utils as _au; _au.log(f"import com.exteragram.messenger.plugins import PluginsController failed: {e}")
    from .utils.importFailed import showImportFailedAlert as _sifa; _sifa()
try:
    from org.telegram.messenger import NotificationCenter
except Exception as e:
    import android_utils as _au; _au.log(f"import org.telegram.messenger import NotificationCenter failed: {e}")
    from .utils.importFailed import showImportFailedAlert as _sifa; _sifa()
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
    if dlg is None:
        return
    def action():
        try:
            if _is_showing(dlg):
                dlg.set_progress(value)
        except Exception:
            pass
    run_on_ui_thread(action)

def _dismiss_dialog(dlg):
    if dlg is None:
        return
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

def install_plugin(plugin_info: dict, icon_view=None, button=None, original_icon_id=None, loading_view=None, on_finish=None, install_ui=None, all_plugins: list = None, rm_rid: str = ""):
    deps = plugin_info.get("deps") or []
    if deps:
        from .ui.PluginListActivity.depsSheet import show_deps_sheet
        def on_confirmed():
            _do_install(plugin_info, icon_view, button, original_icon_id, loading_view, on_finish, install_ui, rm_rid=rm_rid)
        show_deps_sheet(install_ui, plugin_info, on_confirmed, all_plugins=all_plugins, on_cancel=on_finish)
        return
    _do_install(plugin_info, icon_view, button, original_icon_id, loading_view, on_finish, install_ui, rm_rid=rm_rid)


def _open_install_dialog(temp_path, plugin_info, fragment, loading_view, button, icon_view, original_icon_id, on_finish, rm_rid=""):
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
            from .utils.installIndex import set_pending
            set_pending(plugin_info, rm_rid)
            PluginsController.getInstance().showInstallDialog(fragment, temp_path, True)

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


from .utils.hashUtil import hashFile, getHashMethod, METHOD_SHA256, METHOD_BITHASH, matchesStoredHash


def _get_plugin_cache_path(pkg: str, filename: str) -> str:
    # cache is isolated per hash method
    method = getHashMethod()
    subdir = "BitHash" if method == METHOD_BITHASH else "sha256"
    cache_dir = f"/data/data/{pkg}/files/packitCache/pluginCache/{subdir}"
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, filename)




# keep old name as alias so fragment.py import stays valid
def _sha256_file(path: str) -> str:
    return hashFile(path)


def _do_install(plugin_info: dict, icon_view=None, button=None, original_icon_id=None, loading_view=None, on_finish=None, install_ui=None, rm_rid: str = ""):
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

    # check cache before showing the heavy loading dialog
    pkg_pre = ApplicationLoader.applicationContext.getPackageName()
    url_pre = plugin_info.get("link") or plugin_info.get("raw") or ""
    filename_pre = url_pre.split("/")[-1] or f"{plugin_id}.plugin"
    cache_path_pre = _get_plugin_cache_path(pkg_pre, filename_pre)
    has_cache = False
    if os.path.exists(cache_path_pre):
        try:
            has_cache = matchesStoredHash(
                cache_path_pre,
                sha256=str(plugin_info.get("hash") or ""),
                bithash=str(plugin_info.get("bithash") or ""),
                label=str(plugin_info.get("id") or cache_path_pre),
            )
        except Exception:
            pass

    from ui.alert import AlertDialogBuilder
    ctx = fragment.getContext()
    if has_cache:
        dlg = None
    else:
        builder = AlertDialogBuilder(ctx, AlertDialogBuilder.ALERT_TYPE_LOADING)
        builder.set_title("Downloading...")
        builder.set_cancelable(False)
        dlg = builder.show()
        dlg.set_progress(0)

    def task():
        try:
            pkg = ApplicationLoader.applicationContext.getPackageName()
            plugins_dir = f"/data/data/{pkg}/files/plugins"
            try:
                os.makedirs(plugins_dir, exist_ok=True)
            except Exception:
                pass

            temp_path = os.path.join(plugins_dir, f".temp_{plugin_id}.plugin")
            # check local plugin cache
            filename = url.split("/")[-1] or f"{plugin_id}.plugin"
            cache_path = _get_plugin_cache_path(pkg, filename)
            if os.path.exists(cache_path):
                try:
                    if matchesStoredHash(
                        cache_path,
                        sha256=str(plugin_info.get("hash") or ""),
                        bithash=str(plugin_info.get("bithash") or ""),
                        label=str(plugin_info.get("id") or cache_path),
                    ):
                        log(f"core: cache hit for '{plugin_id}', using local file")
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                        with open(cache_path, "rb") as src, open(temp_path, "wb") as dst:
                            while True:
                                chunk = src.read(65536)
                                if not chunk:
                                    break
                                dst.write(chunk)
                        os.chmod(temp_path, 0o644)
                        _set_progress(dlg, 100)
                        _dismiss_dialog(dlg)
                        run_on_ui_thread(lambda: _open_install_dialog(
                            temp_path, plugin_info, fragment,
                            loading_view, button, icon_view, original_icon_id, on_finish, rm_rid
                        ))
                        return
                    else:
                        log(f"core: cache miss for '{plugin_id}': hash mismatch, re-downloading")
                except Exception as e:
                    log(f"core: cache check error for '{plugin_id}': {e}")

            r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"})
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

            # save to cache if hash provided
            if expected_hash:
                try:
                    import shutil
                    shutil.copy2(temp_path, cache_path)
                    os.chmod(cache_path, 0o644)
                    log(f"core: cached '{plugin_id}' to {cache_path}")
                except Exception as e:
                    log(f"core: failed to cache '{plugin_id}': {e}")

            _dismiss_dialog(dlg)

            run_on_ui_thread(lambda: _open_install_dialog(
                temp_path, plugin_info, fragment,
                loading_view, button, icon_view, original_icon_id, on_finish, rm_rid
            ))
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


def install_icon_pack(icon_info: dict):
    pack_id = icon_info.get("id")
    url = icon_info.get("link")
    name = str(icon_info.get("name") or pack_id or "Unknown")
    author = str(icon_info.get("author") or "")
    version = str(icon_info.get("version") or "1.0")

    if not pack_id or not url:
        BulletinHelper.show_error("Icon pack has no link")
        return

    fragment = get_last_fragment()
    if not fragment:
        return

    from ui.alert import AlertDialogBuilder
    ctx = fragment.getContext()
    builder = AlertDialogBuilder(ctx, AlertDialogBuilder.ALERT_TYPE_LOADING)
    builder.set_title("Downloading...")
    builder.set_cancelable(False)
    dlg = builder.show()
    dlg.set_progress(0)

    def task():
        try:
            r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"})
            if r.status_code != 200:
                log(f"core.install_icon_pack: HTTP {r.status_code} for '{pack_id}'")
                _dismiss_dialog(dlg)
                run_on_ui_thread(lambda: BulletinHelper.show_error(f"Download failed: HTTP {r.status_code}"))
                return

            pkg = ApplicationLoader.applicationContext.getPackageName()
            tmp_path = f"/data/data/{pkg}/cache/packit_iconpack_{pack_id}.icons"

            content_length = r.headers.get("content-length")
            total = int(content_length) if content_length else 0
            downloaded = 0
            r.raw.decode_content = True
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = r.raw.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    if total:
                        downloaded += len(chunk)
                        _set_progress(dlg, min(99, int(downloaded * 100 / total)))

            # parse pack on background thread — parsePackFromZip is a suspend function
            # must be called with a valid Continuation, not None
            # use kotlinx runBlocking which provides a proper coroutine context
            from hook_utils import find_class

            IconPackStorage = find_class("com.exteragram.messenger.icons.IconPackStorage")
            IconManager = find_class("com.exteragram.messenger.icons.IconManager")
            InstallIconPackBottomSheet = find_class("com.exteragram.messenger.icons.ui.components.InstallIconPackBottomSheet")
            File = find_class("java.io.File")
            tmp_file_obj = File(tmp_path)

            result_holder = [None]
            done_event = threading.Event()

            Continuation = find_class("kotlin.coroutines.Continuation")
            EmptyCoroutineContext = find_class("kotlin.coroutines.EmptyCoroutineContext")

            class _ParseCont(dynamic_proxy(Continuation)):
                def getContext(self):
                    return EmptyCoroutineContext.INSTANCE
                def resumeWith(self, result):
                    # kotlin inline Result<T> at JVM level passes value directly on success
                    result_holder[0] = result
                    done_event.set()

            IconPackStorage.INSTANCE.parsePackFromZip(tmp_file_obj, _ParseCont())
            done_event.wait(timeout=30)

            parsed_pack = result_holder[0]

            _dismiss_dialog(dlg)

            if parsed_pack is None:
                log(f"core.install_icon_pack: parsePackFromZip returned None for '{pack_id}'")
                run_on_ui_thread(lambda: BulletinHelper.show_error("Failed to read icon pack"))
                return

            def open_sheet(pp=parsed_pack):
                try:
                    frag = get_last_fragment()
                    if not frag:
                        return

                    class _Delegate(dynamic_proxy(InstallIconPackBottomSheet.InstallDelegate)):
                        def __init__(self):
                            super().__init__()
                        def onInstall(self, enableAfterInstall, isUpdate):
                            def do_install():
                                try:
                                    install_done = threading.Event()
                                    install_result = [None]

                                    class _InstCont(dynamic_proxy(Continuation)):
                                        def getContext(self):
                                            return EmptyCoroutineContext.INSTANCE
                                        def resumeWith(self, res):
                                            install_result[0] = res
                                            install_done.set()

                                    IconPackStorage.INSTANCE.installPack(tmp_file_obj, _InstCont())
                                    install_done.wait(timeout=60)

                                    result = bool(install_result[0]) if install_result[0] is not None else False

                                    if result:
                                        if enableAfterInstall:
                                            run_on_ui_thread(lambda: IconManager.INSTANCE.setActiveCustomPack(pack_id))
                                        run_on_ui_thread(lambda: BulletinHelper.show_success(f"'{name}' installed"))
                                    else:
                                        run_on_ui_thread(lambda: BulletinHelper.show_error("Installation failed"))
                                except Exception as ex:
                                    log(f"core.install_icon_pack: installPack error: {ex}")
                                    run_on_ui_thread(lambda: BulletinHelper.show_error(f"Error: {ex}"))
                                finally:
                                    try:
                                        os.remove(tmp_path)
                                    except Exception:
                                        pass
                            threading.Thread(target=do_install, daemon=True).start()

                    sheet = InstallIconPackBottomSheet(frag.getContext(), pp, _Delegate())
                    frag.showDialog(sheet)
                except Exception as ex:
                    log(f"core.install_icon_pack: open_sheet error: {ex}")
                    BulletinHelper.show_error(f"Failed to open install sheet: {ex}")

            run_on_ui_thread(open_sheet)
        except Exception as e:
            log(f"core.install_icon_pack: error: {e}")
            _dismiss_dialog(dlg)
            run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while downloading"))

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