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

OBF_IconPackStorage_EXTERAGRAM = "x.yj5"
OBF_InstallIconPackBottomSheet_EXTERAGRAM = "x.jk5"

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

        def _on_plugins_updated():
            # check the plugin is now actually installed
            try:
                installed = PluginsController.getInstance().getPluginEngine(plugin_id) is not None
            except Exception:
                installed = False
            if not installed:
                return
            # unregister observer
            try:
                if observer_ref[0] is not None:
                    NotificationCenter.getGlobalInstance().removeObserver(
                        observer_ref[0], NotificationCenter.pluginsUpdated
                    )
                    observer_ref[0] = None
            except Exception as e:
                logx(f"core: removeObserver error: {e}", False)
            # fire callbacks
            try:
                if on_finish:
                    on_finish(True)
            except Exception:
                pass
            if write_index and _is_elyx_plugin(plugin_info) and rm_rid:
                try:
                    from .utils.installIndex import commit_elyx_pending
                    commit_elyx_pending(plugin_info, rm_rid, original_path=temp_path)
                except Exception as e:
                    logx(f"core: elyx index commit error: {e}", False)
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
            from elyxcore import ElyxEngine
            from com.exteragram.messenger.plugins.ui.components import InstallPluginBottomSheet
            install_params = InstallPluginBottomSheet.PluginInstallParams(temp_path, False)
            ElyxEngine.instance.showInstallDialog(fragment, install_params)
        else:
            if write_index:
                from .utils.installIndex import set_pending
                set_pending(plugin_info, rm_rid)
            PluginsController.getInstance().showInstallDialog(fragment, temp_path, True)

    except Exception as e:
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

            temp_path = os.path.join(plugins_dir, f".temp_{plugin_id}.plugin")
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

            from java import jclass

            IconPackStorageCls = jclass(OBF_IconPackStorage_EXTERAGRAM)
            FileCls = jclass("java.io.File")
            tmp_file_obj = FileCls(tmp_path)

            # resolve InstallDelegate and InstallIconPackBottomSheet:
            # 1. try cache, 2. fallback to OBF constants, 3. dex scan only if SRCH_OBF_ICONS_CLASSES=True
            InstallIconPackBottomSheet = None
            _install_delegate_name = None
            InstallDelegate = None
            _sheet_class_name = None
            _cached_icon_pack_cls_name = None

            def _load_classes_from_cache() -> bool:
                try:
                    from .utils.paths import getClassesCachePath
                    import json as _j
                    p = getClassesCachePath()
                    if not os.path.exists(p):
                        return False
                    with open(p, "r") as f:
                        data = _j.load(f)
                    d = data.get("delegate")
                    s = data.get("sheet")
                    ip = data.get("icon_pack")
                    if not d or not s:
                        return False
                    nonlocal _install_delegate_name, InstallDelegate, _sheet_class_name, InstallIconPackBottomSheet, _cached_icon_pack_cls_name
                    _install_delegate_name = d
                    InstallDelegate = jclass(d)
                    _sheet_class_name = s
                    InstallIconPackBottomSheet = jclass(s)
                    if ip:
                        _cached_icon_pack_cls_name = ip
                    logx(f"core.install_icon_pack: classes loaded from cache: delegate={d} sheet={s} icon_pack={ip}", True)
                    return True
                except Exception as e:
                    logx(f"core.install_icon_pack: cache load error: {e}", False)
                    return False

            def _save_classes_to_cache(delegate: str, sheet: str, icon_pack: str = ""):
                try:
                    from .utils.paths import getClassesCachePath
                    import json as _j
                    p = getClassesCachePath()
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, "w") as f:
                        _j.dump({"delegate": delegate, "sheet": sheet, "icon_pack": icon_pack}, f)
                    logx(f"core.install_icon_pack: classes cached: delegate={delegate} sheet={sheet} icon_pack={icon_pack}", True)
                except Exception as e:
                    logx(f"core.install_icon_pack: cache save error: {e}", False)

            if not _load_classes_from_cache():
                try:
                    cl = IconPackStorageCls.getClass().getClassLoader()
                    DexFileCls = jclass("dalvik.system.DexFile")
                    appInfo = jclass("android.app.ActivityThread").currentApplication().getApplicationInfo()
                    dex = DexFileCls(appInfo.sourceDir)
                    entries = dex.entries()
                    while entries.hasMoreElements():
                        cname = str(entries.nextElement())
                        # only scan short obfuscated names in same namespace
                        if not (cname.startswith("x.") and len(cname) <= 8):
                            continue
                        try:
                            cls = cl.loadClass(cname)
                            if not cls.isInterface():
                                continue
                            methods = cls.getDeclaredMethods()
                            if len(methods) != 1:
                                continue
                            pts = [p.getName() for p in methods[0].getParameterTypes()]
                            if pts == ["boolean", "boolean"]:
                                _install_delegate_name = cname
                                logx(f"core.install_icon_pack: InstallDelegate found via DexFile: {cname}", True)
                                break
                        except Exception:
                            continue
                    dex.close()
                    if _install_delegate_name:
                        InstallDelegate = jclass(_install_delegate_name)
                except Exception as e:
                    logx(f"core.install_icon_pack: InstallDelegate DexFile scan error: {e}", False)

                try:
                    cl_s = IconPackStorageCls.getClass().getClassLoader()
                    DexFileCls_s = jclass("dalvik.system.DexFile")
                    appInfo_s = jclass("android.app.ActivityThread").currentApplication().getApplicationInfo()
                    dex_s = DexFileCls_s(appInfo_s.sourceDir)
                    entries_s = dex_s.entries()
                    while entries_s.hasMoreElements():
                        cname_s = str(entries_s.nextElement())
                        if not (cname_s.startswith("x.") and len(cname_s) <= 8):
                            continue
                        try:
                            c_s = cl_s.loadClass(cname_s)
                            if c_s.isInterface():
                                continue
                            for ctor_s in c_s.getDeclaredConstructors():
                                pts_s = [p.getName() for p in ctor_s.getParameterTypes()]
                                # ctor: (Context/Activity, IconPack, InstallDelegate)
                                if (len(pts_s) == 3
                                        and "Context" in pts_s[0]
                                        and pts_s[1].startswith("x.") and len(pts_s[1]) <= 8
                                        and _install_delegate_name
                                        and pts_s[2] == _install_delegate_name):
                                    _sheet_class_name = cname_s
                                    logx(f"core.install_icon_pack: InstallIconPackBottomSheet found via DexFile: {cname_s}", True)
                                    break
                        except Exception:
                            pass
                        if _sheet_class_name:
                            break
                    dex_s.close()
                    if _sheet_class_name:
                        InstallIconPackBottomSheet = jclass(_sheet_class_name)
                except Exception as e:
                    logx(f"core.install_icon_pack: InstallIconPackBottomSheet DexFile scan error: {e}", False)

                if _install_delegate_name and _sheet_class_name:
                    _save_classes_to_cache(_install_delegate_name, _sheet_class_name)

            if InstallIconPackBottomSheet is None:
                logx(f"core.install_icon_pack: InstallIconPackBottomSheet not found, falling back to OBF name", True)
                try:
                    InstallIconPackBottomSheet = jclass(OBF_InstallIconPackBottomSheet_EXTERAGRAM)
                except Exception as e:
                    logx(f"core.install_icon_pack: InstallIconPackBottomSheet fallback load failed: {e}", False)

            # R8 removed INSTANCE field but methods are instance methods on the singleton.
            # Get the singleton via static field that holds self-reference (Kotlin object companion pattern).
            IconPackStorageInst = None
            try:
                cls_obj = IconPackStorageCls.getClass()
                for f in cls_obj.getDeclaredFields():
                    f.setAccessible(True)
                    val = f.get(None)
                    if val is not None and val.getClass().getName() == OBF_IconPackStorage_EXTERAGRAM:
                        IconPackStorageInst = val
                        logx(f"core.install_icon_pack: IconPackStorage instance via field '{f.getName()}'", True)
                        break
                if IconPackStorageInst is None:
                    # fallback: use the jclass wrapper itself as receiver
                    IconPackStorageInst = IconPackStorageCls
                    logx(f"core.install_icon_pack: IconPackStorage instance fallback to jclass", True)
            except Exception as e:
                logx(f"core.install_icon_pack: IconPackStorage instance error: {e}", False)
                IconPackStorageInst = IconPackStorageCls

            # find installPack (q) by name — used later in open_sheet
            installPackMethod = None
            RunBlocking = None
            EmptyCoroutineContext = None
            Function2 = None
            try:
                for m in IconPackStorageCls.getClass().getDeclaredMethods():
                    pts = [p.getName() for p in m.getParameterTypes()]
                    if pts == ["java.io.File", "kotlin.coroutines.Continuation"] and m.getName() == "q":
                        m.setAccessible(True)
                        installPackMethod = m
                        break
            except Exception as e:
                logx(f"core.install_icon_pack: installPack method resolve error: {e}", False)

            try:
                RunBlocking = jclass("kotlinx.coroutines.BuildersKt")
                EmptyCoroutineContext = jclass("kotlin.coroutines.EmptyCoroutineContext")
                Function2 = jclass("kotlin.jvm.functions.Function2")
            except Exception as e:
                logx(f"core.install_icon_pack: coroutine classes load error: {e}", False)

            # IconManager is lazy-loaded and obfuscated — skip for now, setActiveCustomPack is non-critical
            IconManager = None
            IconManagerSetActivePack = None

            def getKotlinInstance(cls, label):
                try:
                    cls_obj = cls.getClass()
                    for f in cls_obj.getDeclaredFields():
                        f.setAccessible(True)
                        val = f.get(None)
                        if val is not None and val.getClass().getName() == cls_obj.getName():
                            logx(f"core.install_icon_pack: {label} instance via field '{f.getName()}'", True)
                            return val
                    return None
                except Exception as e:
                    logx(f"core.install_icon_pack: {label} instance failed: {e}", False)
                    return None

            # parse zip on Python side to avoid Chaquopy converting IconPack->bool via suspend reflection
            import zipfile
            import json as _json
            parsed_pack = None
            try:
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    if "metadata.json" not in zf.namelist():
                        logx(f"core.install_icon_pack: metadata.json not found in zip", True)
                    else:
                        meta = _json.loads(zf.read("metadata.json").decode("utf-8"))
                        pack_id_meta = meta.get("packId") or meta.get("id") or ""
                        pack_name = meta.get("packName") or meta.get("name") or ""
                        pack_author = meta.get("author", "Unknown")
                        pack_version = meta.get("version", "1.0")
                        icons_json = meta.get("icons") or {}
                        import tempfile
                        extract_dir = tempfile.mkdtemp(prefix="iconpack_preview_")
                        zf.extractall(extract_dir)
                        FileCls2 = jclass("java.io.File")
                        loc_file = FileCls2(extract_dir)
                        HashMapCls = jclass("java.util.HashMap")
                        icons_map = HashMapCls()
                        for k, v in icons_json.items():
                            icons_map.put(k, v)
                        # find IconPack class via DexFile — R8 may have renamed it
                        cl = IconPackStorageCls.getClass().getClassLoader()
                        IconPackCls = None
                        if _cached_icon_pack_cls_name:
                            try:
                                IconPackCls = cl.loadClass(_cached_icon_pack_cls_name)
                                logx(f"core.install_icon_pack: IconPack class loaded from cache: {_cached_icon_pack_cls_name}", True)
                            except Exception as e:
                                logx(f"core.install_icon_pack: IconPack cache load failed: {e}", False)
                                IconPackCls = None
                        if IconPackCls is None:
                            try:
                                DexFileCls2 = jclass("dalvik.system.DexFile")
                                appInfo2 = jclass("android.app.ActivityThread").currentApplication().getApplicationInfo()
                                dex2 = DexFileCls2(appInfo2.sourceDir)
                                entries2 = dex2.entries()
                                while entries2.hasMoreElements():
                                    cname2 = str(entries2.nextElement())
                                    try:
                                        c2 = cl.loadClass(cname2)
                                        ctors2 = c2.getDeclaredConstructors()
                                        for ctor2 in ctors2:
                                            p2 = [p.getName() for p in ctor2.getParameterTypes()]
                                            if p2[:4] == ["java.lang.String"] * 4 and "java.io.File" in p2 and "java.util.Map" in p2:
                                                IconPackCls = c2
                                                logx(f"core.install_icon_pack: IconPack class found: {cname2}", True)
                                                break
                                    except Exception:
                                        pass
                                    if IconPackCls is not None:
                                        break
                                dex2.close()
                            except Exception as dex_e:
                                logx(f"core.install_icon_pack: IconPack DexFile scan error: {dex_e}", True)

                        if IconPackCls is not None:
                            _save_classes_to_cache(
                                _install_delegate_name or "",
                                _sheet_class_name or "",
                                IconPackCls.getName()
                            )

                        if IconPackCls is None:
                            logx(f"core.install_icon_pack: IconPack class not found", True)
                        else:
                            ctors = IconPackCls.getDeclaredConstructors()
                            logx(f"core.install_icon_pack: IconPack ctors: {[(c.getName(), [p.getName() for p in c.getParameterTypes()]) for c in ctors]}", True)
                            for ctor in ctors:
                                ptypes = [p.getName() for p in ctor.getParameterTypes()]
                                if any("DefaultConstructorMarker" in p for p in ptypes):
                                    continue
                                if ptypes[:4] != ["java.lang.String"] * 4:
                                    continue
                                ctor.setAccessible(True)
                                try:
                                    n = len(ptypes)
                                    if n == 7:
                                        parsed_pack = ctor.newInstance(pack_id_meta, pack_name, pack_author, pack_version, icons_map, None, loc_file)
                                    elif n == 6:
                                        parsed_pack = ctor.newInstance(pack_id_meta, pack_name, pack_author, pack_version, icons_map, loc_file)
                                    elif n == 5:
                                        parsed_pack = ctor.newInstance(pack_id_meta, pack_name, pack_author, pack_version, icons_map)
                                    else:
                                        continue
                                    logx(f"core.install_icon_pack: IconPack created ctor({n} args): id={pack_id_meta} name={pack_name}", True)
                                    break
                                except Exception as ce:
                                    logx(f"core.install_icon_pack: ctor({n} args) failed: {ce}", True)
                if parsed_pack is None:
                    logx(f"core.install_icon_pack: IconPack construction failed for '{pack_id}'", True)
            except Exception as e:
                logx(f"core.install_icon_pack: zip parse error: {e}", False)



            _dismiss_dialog(dlg)

            if parsed_pack is None:
                logx(f"core.install_icon_pack: parsePackFromZip returned None for '{pack_id}'", True)
                run_on_ui_thread(lambda: BulletinHelper.show_error(_s("core_iconpack_read_failed")))
                return

            def open_sheet(pp=parsed_pack):
                try:
                    frag = get_last_fragment()
                    if not frag:
                        return

                    if InstallIconPackBottomSheet is None or InstallDelegate is None:
                        logx(f"core.install_icon_pack: InstallIconPackBottomSheet or InstallDelegate not loaded", True)
                        return

                    class _Delegate(dynamic_proxy(InstallDelegate)):
                        def __init__(self):
                            super().__init__()
                        def a(self, enableAfterInstall, isUpdate):
                            def do_install():
                                try:
                                    if installPackMethod is None:
                                            logx(f"core.install_icon_pack: installPack method not found", True)
                                            return

                                    class _InstallBlock(dynamic_proxy(Function2)):
                                        def invoke(self, scope, cont):
                                            return installPackMethod.invoke(IconPackStorageInst, tmp_file_obj, cont)

                                    try:
                                        install_result = RunBlocking.runBlocking(EmptyCoroutineContext.INSTANCE, _InstallBlock())
                                        logx(f"core.install_icon_pack: installPack result={install_result}", True)
                                    except Exception as e:
                                        logx(f"core.install_icon_pack: installPack runBlocking error: {e}", False)
                                        install_result = None

                                    result = install_result is not None and bool(install_result)

                                    if result:
                                        if enableAfterInstall and IconManager is not None and IconManagerSetActivePack is not None:
                                            try:
                                                im_inst = getKotlinInstance(IconManager, "IconManager")
                                                if im_inst is None:
                                                    im_inst = IconManager
                                                IconManagerSetActivePack.setAccessible(True)
                                                run_on_ui_thread(lambda: IconManagerSetActivePack.invoke(im_inst, pack_id))
                                            except Exception as e:
                                                logx(f"core.install_icon_pack: setActiveCustomPack error: {e}", False)
                                        elif enableAfterInstall:
                                            logx(f"core.install_icon_pack: IconManager not found, skipping setActiveCustomPack", True)
                                        run_on_ui_thread(lambda: BulletinHelper.show_success(_s("core_iconpack_installed", name=name)))
                                    else:
                                        run_on_ui_thread(lambda: BulletinHelper.show_error(_s("core_installation_failed")))
                                except Exception as ex:
                                    logx(f"core.install_icon_pack: installPack error: {ex}", True)
                                    run_on_ui_thread(lambda: BulletinHelper.show_error(_s("core_error_generic", error=ex)))
                                finally:
                                    try:
                                        os.remove(tmp_path)
                                    except Exception:
                                        pass
                            threading.Thread(target=do_install, daemon=True).start()

                    # Chaquopy can't call obfuscated constructors with args directly — use reflection
                    delegate_inst = _Delegate()
                    ctx = frag.getContext()
                    sheet = None
                    try:
                        realSheetCls = InstallIconPackBottomSheet.getClass() if InstallIconPackBottomSheet is not None else None
                        if realSheetCls is None:
                            logx(f"core.install_icon_pack: realSheetCls is None, cannot create sheet", True)
                        else:
                            for ctor in realSheetCls.getDeclaredConstructors():
                                ptypes = [p.getName() for p in ctor.getParameterTypes()]
                                if (len(ptypes) == 3
                                        and "Context" in ptypes[0]
                                        and _install_delegate_name
                                        and ptypes[2] == _install_delegate_name):
                                    ctor.setAccessible(True)
                                    sheet = ctor.newInstance(ctx, pp, delegate_inst)
                                    logx(f"core.install_icon_pack: sheet created via ctor {ptypes}", True)
                                    break
                            if sheet is None:
                                all_ctors = [(c.getName(), [p.getName() for p in c.getParameterTypes()]) for c in realSheetCls.getDeclaredConstructors()]
                                logx(f"core.install_icon_pack: sheet ctor not found, ctors={all_ctors}", True)
                    except Exception as se:
                        logx(f"core.install_icon_pack: sheet ctor error: {se}", True)
                    if sheet is None:
                        BulletinHelper.show_error(_s("core_install_sheet_failed", error="sheet ctor failed"))
                        return
                    frag.showDialog(sheet)
                except Exception as ex:
                    logx(f"core.install_icon_pack: open_sheet error: {ex}", True)
                    BulletinHelper.show_error(_s("core_install_sheet_failed", error=ex))

            run_on_ui_thread(open_sheet)
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
            from elyxcore import ElyxPlugin, ElyxEngine
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