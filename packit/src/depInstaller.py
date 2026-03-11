import os
import threading
import requests
from android_utils import log, run_on_ui_thread
from elyx import strings
from ui.bulletin import BulletinHelper
try:
    from org.telegram.messenger import ApplicationLoader, AndroidUtilities
except Exception as e:
    import android_utils as _au; _au.log(f"depInstaller: import ApplicationLoader failed: {e}")
try:
    from com.exteragram.messenger.plugins import PluginsController
except Exception as e:
    import android_utils as _au; _au.log(f"depInstaller: import PluginsController failed: {e}")


def _get_engine():
    try:
        it = PluginsController.engines.values().iterator()
        while it.hasNext():
            engine = it.next()
            if engine is not None and "PythonPluginsEngine" in type(engine).__name__:
                return engine
        return None
    except Exception as e:
        log(f"depInstaller: _get_engine failed: {e}")
        return None


def _download_to_temp(url: str, dep_id: str) -> str:
    # returns temp file path or raises
    pkg = ApplicationLoader.applicationContext.getPackageName()
    plugins_dir = f"/data/data/{pkg}/files/plugins"
    try:
        os.makedirs(plugins_dir, exist_ok=True)
    except Exception:
        pass
    temp_path = os.path.join(plugins_dir, f".dep_temp_{dep_id}.plugin")
    r = requests.get(url, stream=True, timeout=30)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")
    r.raw.decode_content = True
    with open(temp_path, "wb") as f:
        while True:
            chunk = r.raw.read(8192)
            if not chunk:
                break
            f.write(chunk)
    return temp_path


def _install_dep_silent(dep_id: str, dep_url: str, on_done):
    # on_done(success: bool) called on any thread
    def task():
        try:
            log(f"depInstaller: downloading dep '{dep_id}' from '{dep_url}'")
            temp_path = _download_to_temp(dep_url, dep_id)
        except Exception as e:
            log(f"depInstaller: download failed for '{dep_id}': {e}")
            on_done(False)
            return

        engine = _get_engine()
        if not engine:
            log(f"depInstaller: no engine available for '{dep_id}'")
            on_done(False)
            return

        installed = [False]
        done_event = threading.Event()

        def on_loaded(result):
            # result is dep_id string on success, None on failure
            if result:
                log(f"depInstaller: loaded '{dep_id}', enabling...")
                engine.setPluginEnabled(dep_id, True, _enable_callback(dep_id, installed, done_event))
            else:
                log(f"depInstaller: loadPluginFromFile failed for '{dep_id}'")
                done_event.set()

        try:
            from org.telegram.messenger import Utilities
            engine.loadPluginFromFile(temp_path, None, Utilities.Callback(on_loaded))
        except Exception as e:
            log(f"depInstaller: loadPluginFromFile error for '{dep_id}': {e}")
            on_done(False)
            return

        done_event.wait(timeout=30)
        try:
            os.remove(temp_path)
        except Exception:
            pass
        on_done(installed[0])

    threading.Thread(target=task, daemon=True).start()


def _enable_callback(dep_id: str, installed: list, done_event: threading.Event):
    def cb(result):
        installed[0] = result is not None
        log(f"depInstaller: enabled '{dep_id}': {installed[0]}")
        done_event.set()
    try:
        from org.telegram.messenger import Utilities
        return Utilities.Callback(cb)
    except Exception:
        # fallback: return a callable directly if Utilities.Callback unavailable
        return cb


def install_missing_deps(missing_deps: list, all_plugins: list, on_all_done):
    # missing_deps: [dep_id, ...]
    # all_plugins: full plugin list from repo json
    # on_all_done(success: bool) — called on worker thread when all done (or first failure)
    meta_map = {}
    for p in (all_plugins or []):
        if isinstance(p, dict) and p.get("id"):
            meta_map[p["id"]] = p

    def install_next(i: int):
        if i >= len(missing_deps):
            on_all_done(True)
            return
        dep_id = missing_deps[i]
        meta = meta_map.get(dep_id) or {}
        dep_url = meta.get("link") or meta.get("raw")
        if not dep_url:
            log(f"depInstaller: no link for dep '{dep_id}', skipping")
            install_next(i + 1)
            return

        def on_done(success: bool):
            if not success:
                log(f"depInstaller: failed to install dep '{dep_id}'")
                on_all_done(False)
                return
            install_next(i + 1)

        _install_dep_silent(dep_id, dep_url, on_done)

    install_next(0)
