# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os
import threading
import requests
from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from hook_utils import find_class
from ui.bulletin import BulletinHelper
from android.widget import ProgressBar, LinearLayout
from java import dynamic_proxy
try:
    from elyx import strings as _strings
except Exception:
    _strings = None
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

_install_listeners = []
_install_listeners_lock = threading.Lock()


def _s(key, **kwargs):
    # safe string lookup with fallback to key
    try:
        if kwargs:
            return str(_strings(key, **kwargs))
        return str(_strings[key])
    except Exception:
        return key
# test2

def add_install_listener(fn):
    # fn(plugin_id: str) called on UI thread after successful install
    with _install_listeners_lock:
        if fn not in _install_listeners:
            _install_listeners.append(fn)


def remove_install_listener(fn):
    with _install_listeners_lock:
        try:
            _install_listeners.remove(fn)
        except ValueError:
            pass


def _fire_install_listeners(plugin_id: str):
    with _install_listeners_lock:
        listeners = list(_install_listeners)
    for fn in listeners:
        try:
            fn(plugin_id)
        except Exception as e:
            logx(f"core: install listener error: {e}", False)


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

def install_plugin(plugin_info: dict, icon_view=None, button=None, original_icon_id=None, loading_view=None, on_finish=None, install_ui=None, all_plugins: list = None, rm_rid: str = "", succ_download=None):
    deps = plugin_info.get("deps") or []
    if deps:
        from .ui.PluginListActivity.sheets.depsSheet import show_deps_sheet
        def on_confirmed():
            _do_install(plugin_info, icon_view, button, original_icon_id, loading_view, on_finish, install_ui, rm_rid=rm_rid, succ_download=succ_download)
        show_deps_sheet(install_ui, plugin_info, on_confirmed, all_plugins=all_plugins, on_cancel=on_finish)
        return
    _do_install(plugin_info, icon_view, button, original_icon_id, loading_view, on_finish, install_ui, rm_rid=rm_rid, succ_download=succ_download)


def _open_install_dialog(temp_path, plugin_info, fragment, loading_view, button, icon_view, original_icon_id, on_finish, rm_rid="", write_index=True):
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

        plugin_id = str(plugin_info.get("id") or "")

        observer_ref = [None]
        done_ref = [False]

        def _commit_index():
            # write PackIt's install index for whichever engine handled the
            # install. Both helpers dedupe by id and consume their pending
            # state, so this is safe to run alongside InstallDismissHook.
            if not (write_index and rm_rid):
                return
            try:
                if _is_elyx_plugin(plugin_info):
                    from .utils.installIndex import commit_elyx_pending
                    commit_elyx_pending(plugin_info, rm_rid, original_path=temp_path)
                else:
                    from .utils.installIndex import commit_pending
                    commit_pending()
            except Exception as e:
                logx(f"core: index commit error: {e}", False)

        def _on_plugins_updated():
            if done_ref[0]:
                return
            # check the plugin is now actually installed
            try:
                installed = PluginsController.getInstance().getPluginEngine(plugin_id) is not None
            except Exception:
                installed = False
            if not installed:
                return
            done_ref[0] = True
            # unregister observer
            try:
                if observer_ref[0] is not None:
                    NotificationCenter.getGlobalInstance().removeObserver(
                        observer_ref[0], NotificationCenter.pluginsUpdated
                    )
                    observer_ref[0] = None
            except Exception as e:
                logx(f"core: removeObserver error: {e}", False)
            # write the install index from this reliable post-install signal
            # (covers both native and elyx installs), then fire callbacks
            _commit_index()
            try:
                if on_finish:
                    on_finish(True)
            except Exception:
                pass
            _fire_install_listeners(plugin_id)

            try:
                restart = plugin_info.get("restart")
                logx(f"core: check restart={restart}", True)
                if restart in ("required", "optional"):
                    logx("core: calling show_restart_dialog", True)
                    from .ui.restartDialog import show_restart_dialog
                    show_restart_dialog(restart, fragment)
            except Exception as e:
                logx(f"core: restart dialog error: {e}", False)

        try:
            NotificationCenterDelegate = find_class(
                "org.telegram.messenger.NotificationCenter$NotificationCenterDelegate"
            )

            class _InstallObserver(dynamic_proxy(NotificationCenterDelegate)):
                def didReceivedNotification(self, id, account, *args):
                    run_on_ui_thread(_on_plugins_updated)

            obs = _InstallObserver()
            NotificationCenter.getGlobalInstance().addObserver(obs, NotificationCenter.pluginsUpdated)
            observer_ref[0] = obs
        except Exception as e:
            logx(f"core: addObserver error: {e}", False)
            # fallback: fire on_finish with False so caller isn't stuck
            try:
                if on_finish:
                    on_finish(False)
            except Exception:
                pass

        if _is_elyx_plugin(plugin_info):
            # elyx goes through the same host entry as native plugins: the
            # temp file carries .eaf, so the controller routes it to the
            # elyx engine, which shows the SDK's own install sheet.
            # (elyxcore 0.9.9b no longer exports ElyxEngine from the
            # package root, so the old direct call broke with ImportError.)
            from java.io import File as _JFile
            eng = None
            try:
                eng = PluginsController.getPluginEngine(_JFile(temp_path))
            except Exception as e:
                logx(f"core: getPluginEngine check error: {e}", False)
            if eng is not None:
                logx(f"core: elyx install via host showInstallDialog ('{temp_path}')", True)
                PluginsController.getInstance().showInstallDialog(fragment, temp_path, True)
            else:
                # extension not claimed by any engine (e.g. customized
                # allowed_extensions) — call the elyx engine directly
                logx("core: no engine claimed elyx temp file, using direct engine call", True)
                try:
                    from elyxcore._plugin_engine import ElyxEngine
                except ImportError:
                    from elyxcore import ElyxEngine  # older SDKs
                from com.exteragram.messenger.plugins.ui.components import InstallPluginBottomSheet
                install_params = InstallPluginBottomSheet.PluginInstallParams(temp_path, False)
                ElyxEngine.instance.showInstallDialog(fragment, install_params)
        else:
            if write_index:
                from .utils.installIndex import set_pending
                set_pending(plugin_info, rm_rid)
            PluginsController.getInstance().showInstallDialog(fragment, temp_path, True)

    except Exception as e:
        logx(f"core: _open_install_dialog error: {e}", False)
        BulletinHelper.show_error(_s("core_failed_install_dialog", error=e))
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
    from .utils.paths import getPluginCacheDir
    cache_dir = getPluginCacheDir(subdir)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, filename)




# keep old name as alias so fragment.py import stays valid
def _sha256_file(path: str) -> str:
    return hashFile(path)


def _do_install(plugin_info: dict, icon_view=None, button=None, original_icon_id=None, loading_view=None, on_finish=None, install_ui=None, rm_rid: str = "", succ_download=None):
    plugin_id = plugin_info.get("id")
    url = plugin_info.get("link") or plugin_info.get("raw")

    if not plugin_id or not url:
        BulletinHelper.show_error(_s("core_plugin_no_link"))
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
    url_pre = plugin_info.get("link") or plugin_info.get("raw") or ""
    filename_pre = url_pre.split("/")[-1] or f"{plugin_id}.plugin"
    cache_path_pre = _get_plugin_cache_path(None, filename_pre)
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
        builder.set_title(_s("downloading_progress_title"))
        builder.set_cancelable(False)
        dlg = builder.show()
        dlg.set_progress(0)

    def task():
        try:
            from .utils.paths import getPluginsDir
            plugins_dir = getPluginsDir()
            try:
                os.makedirs(plugins_dir, exist_ok=True)
            except Exception:
                pass

            # elyx archives get .eaf so PluginsController.getPluginEngine
            # routes the file to the elyx engine by extension
            temp_ext = ".eaf" if _is_elyx_plugin(plugin_info) else ".plugin"
            temp_path = os.path.join(plugins_dir, f".temp_{plugin_id}{temp_ext}")
            # check local plugin cache
            filename = url.split("/")[-1] or f"{plugin_id}.plugin"
            cache_path = _get_plugin_cache_path(None, filename)
            if os.path.exists(cache_path):
                try:
                    if matchesStoredHash(
                        cache_path,
                        sha256=str(plugin_info.get("hash") or ""),
                        bithash=str(plugin_info.get("bithash") or ""),
                        label=str(plugin_info.get("id") or cache_path),
                    ):
                        logx(f"core: cache hit for '{plugin_id}', using local file", True)
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
                        logx(f"core: succ_download (cache) for '{plugin_id}'", True)
                        if succ_download:
                            run_on_ui_thread(succ_download)
                        run_on_ui_thread(lambda: _open_install_dialog(
                            temp_path, plugin_info, fragment,
                            loading_view, button, icon_view, original_icon_id, on_finish, rm_rid
                        ))
                        return
                    else:
                        logx(f"core: cache miss for '{plugin_id}': hash mismatch, re-downloading", True)
                except Exception as e:
                    logx(f"core: cache check error for '{plugin_id}': {e}", False)

            r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"})
            if r.status_code != 200:
                logx(f"core.install_plugin: failed to download '{plugin_id}' from '{url}': HTTP {r.status_code}", True)
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
            expected_hash = str(plugin_info.get("hash") or plugin_info.get("bithash") or "")
            if expected_hash:
                try:
                    import shutil
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                    shutil.copy2(temp_path, cache_path)
                    os.chmod(cache_path, 0o644)
                    logx(f"core: cached '{plugin_id}' to {cache_path}", True)
                except Exception as e:
                    # cache is best-effort; permission errors on some devices are expected
                    logx(f"core: skipping cache for '{plugin_id}': {e}", False)

            _dismiss_dialog(dlg)

            logx(f"core: succ_download (network) for '{plugin_id}'", True)
            if succ_download:
                run_on_ui_thread(succ_download)

            run_on_ui_thread(lambda: _open_install_dialog(
                temp_path, plugin_info, fragment,
                loading_view, button, icon_view, original_icon_id, on_finish, rm_rid
            ))
        except Exception as e:
            logx(f"core.install_plugin: error downloading '{plugin_id}' from '{url}': {e}", False)
            _dismiss_dialog(dlg)
            run_on_ui_thread(lambda: BulletinHelper.show_error(_s("core_download_error")))
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
        BulletinHelper.show_error(_s("core_iconpack_no_link"))
        return

    fragment = get_last_fragment()
    if not fragment:
        return

    from ui.alert import AlertDialogBuilder
    ctx = fragment.getContext()
    builder = AlertDialogBuilder(ctx, AlertDialogBuilder.ALERT_TYPE_LOADING)
    builder.set_title(_s("downloading_progress_title"))
    builder.set_cancelable(False)
    dlg = builder.show()
    dlg.set_progress(0)

    def task():
        try:
            r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "PackIt/1.0 (Android; github.com/shareui/packit)"})
            if r.status_code != 200:
                logx(f"core.install_icon_pack: HTTP {r.status_code} for '{pack_id}'", True)
                _dismiss_dialog(dlg)
                run_on_ui_thread(lambda: BulletinHelper.show_error(_s("core_iconpack_http_error", code=r.status_code)))
                return

            from .utils.paths import getIconPackTmpPath
            tmp_path = getIconPackTmpPath(pack_id)

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

            _dismiss_dialog(dlg)

            # hand off to exteraGram's native icon-pack installer:
            # parses the archive, shows the native preview/install sheet,
            # installs + enables the pack and shows the success bulletin.
            from java import jclass
            IconManager = jclass("com.exteragram.messenger.icons.IconManager")

            def open_native_installer():
                try:
                    frag = get_last_fragment()
                    if not frag:
                        logx("core.install_icon_pack: no fragment for handleIconPack", True)
                        return
                    IconManager.INSTANCE.handleIconPack(frag, tmp_path)
                    logx(f"core.install_icon_pack: handleIconPack invoked for '{pack_id}'", True)
                except Exception as e:
                    logx(f"core.install_icon_pack: handleIconPack error: {e}", False)
                    run_on_ui_thread(lambda: BulletinHelper.show_error(_s("core_installation_failed")))

            # tmp file is read asynchronously by the host coroutine; leave it
            # for the normal icon-pack cache cleanup instead of deleting now.
            run_on_ui_thread(open_native_installer)
        except Exception as e:
            logx(f"core.install_icon_pack: error: {e}", False)
            _dismiss_dialog(dlg)
            run_on_ui_thread(lambda: BulletinHelper.show_error(_s("core_iconpack_download_error")))

    threading.Thread(target=task, daemon=True).start()


def install_plugin_silent(file_path: str, plugin_data: dict, repo_id: str, on_complete=None, on_error=None):
    # installs a plugin from a local file without showing the standard install dialog.
    # for elyx plugins: uses ElyxEngine.instance.load_from_archive.
    # for regular plugins: uses python_engine.loadPluginFromFile + setPluginEnabled.
    # on_complete() and on_error(error) are called on background thread (not UI thread).
    pid = str(plugin_data.get("id") or "")

    is_elyx = False
    try:
        tags = plugin_data.get("tags") or []
        is_elyx = any(
            isinstance(t, (list, tuple)) and len(t) > 0 and t[0] == "Elyx"
            for t in tags
        )
    except Exception as e:
        logx(f"core.install_plugin_silent: tag check error for '{pid}': {e}", False)

    logx(f"core.install_plugin_silent: is_elyx={is_elyx} for '{pid}'", True)

    if is_elyx:
        try:
            from zipfile import ZipFile
            try:
                # elyxcore 0.9.9b keeps these in private modules only
                from elyxcore._plugin import ElyxPlugin
                from elyxcore._plugin_engine import ElyxEngine
            except ImportError:
                from elyxcore import ElyxPlugin, ElyxEngine  # older SDKs
            from .utils.installIndex import commit_elyx_pending

            elyx_plugin = ElyxPlugin(plzip=ZipFile(file_path, "r"), raise_errors=False)

            def _elyx_complete():
                logx(f"core.install_plugin_silent: elyx install complete for '{pid}'", True)
                try:
                    commit_elyx_pending(plugin_data, repo_id, original_path=file_path)
                except Exception as e:
                    logx(f"core.install_plugin_silent: commit_elyx_pending error for '{pid}': {e}", False)
                if on_complete:
                    try:
                        on_complete()
                    except Exception as e:
                        logx(f"core.install_plugin_silent: on_complete error for '{pid}': {e}", False)

            def _elyx_error(error):
                logx(f"core.install_plugin_silent: elyx install error for '{pid}': {error}", True)
                if on_error:
                    try:
                        on_error(error)
                    except Exception as e:
                        logx(f"core.install_plugin_silent: on_error error for '{pid}': {e}", False)

            ElyxEngine.instance.load_from_archive(elyx_plugin, True, _elyx_complete, _elyx_error)
        except Exception as e:
            logx(f"core.install_plugin_silent: elyx path error for '{pid}': {e}", False)
            if on_error:
                try:
                    on_error(e)
                except Exception:
                    pass
        return

    try:
        from elyxcore import gen
        from org.telegram.messenger import Utilities
        from .utils.installIndex import set_pending, commit_pending

        Callback = gen(Utilities.Callback, "run")
        python_engine = PluginsController.getEngines().get("python")

        try:
            set_pending(plugin_data, repo_id)
        except Exception as e:
            logx(f"core.install_plugin_silent: set_pending error for '{pid}': {e}", False)

        def _on_enabled(error):
            if error:
                logx(f"core.install_plugin_silent: setPluginEnabled error for '{pid}': {error}", True)
                if on_error:
                    try:
                        on_error(error)
                    except Exception:
                        pass
                return
            try:
                commit_pending()
            except Exception as e:
                logx(f"core.install_plugin_silent: commit_pending error for '{pid}': {e}", False)
            if on_complete:
                try:
                    on_complete()
                except Exception as e:
                    logx(f"core.install_plugin_silent: on_complete error for '{pid}': {e}", False)

        def _on_installed(error):
            if not error:
                return python_engine.setPluginEnabled(pid, True, Callback(_on_enabled))
            logx(f"core.install_plugin_silent: loadPluginFromFile error for '{pid}': {error}", True)
            if on_error:
                try:
                    on_error(error)
                except Exception:
                    pass

        run_on_ui_thread(lambda: python_engine.loadPluginFromFile(file_path, None, Callback(_on_installed)))
    except Exception as e:
        logx(f"core.install_plugin_silent: error for '{pid}': {e}", False)
        if on_error:
            try:
                on_error(e)
            except Exception:
                pass


def onlyLocalInstallNoUi(file_path: str, plugin_id: str, on_done):
    # installs plugin from local file_path, no index write, no UI.
    # on_done(error) called on UI thread. error is None on success.
    try:
        from elyxcore import gen
        from org.telegram.messenger import Utilities

        Callback = gen(Utilities.Callback, "run")
        python_engine = PluginsController.getEngines().get("python")

        def on_enabled(error):
            if error:
                logx(f"core.onlyLocalInstallNoUi: setPluginEnabled error for '{plugin_id}': {error}", True)
            run_on_ui_thread(lambda: on_done(error))

        def on_installed(error):
            if not error:
                return python_engine.setPluginEnabled(plugin_id, True, Callback(on_enabled))
            logx(f"core.onlyLocalInstallNoUi: loadPluginFromFile error for '{plugin_id}': {error}", True)
            run_on_ui_thread(lambda: on_done(error))

        run_on_ui_thread(lambda: python_engine.loadPluginFromFile(file_path, None, Callback(on_installed)))
    except Exception as err:
        logx(f"core.onlyLocalInstallNoUi: error for '{plugin_id}': {err}", True)
        run_on_ui_thread(lambda: on_done(err))


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