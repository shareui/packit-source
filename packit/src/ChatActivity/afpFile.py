import threading
import traceback
import zipfile

from base_plugin import MethodHook
from hook_utils import find_class
from android_utils import log
from java.lang import Integer


class _AfpFileHandler(MethodHook):
    def __init__(self, plugin):
        self.lib = plugin

    def before_hooked_method(self, param):
        try:
            filename = str(param.args[1])
            if filename.split(".")[-1] != "afp":
                return

            file_path = str(param.args[0].getAbsolutePath())
            param.setResult(False)
            threading.Thread(target=self._read, args=(file_path, filename), daemon=True).start()
        except Exception as e:
            log(f"afpFile: before_hooked_method error: {e}")

    def _read(self, file_path: str, filename: str):
        from ..scl.scl import parse
        from ..scl.opts import ParseOpts
        from ..utils.paths import getTempDir
        import os
        import shutil
        import time

        parseOpts = ParseOpts()

        ts = int(time.time())
        base_name = filename.rsplit(".", 1)[0]
        tmp_dir = os.path.join(getTempDir(), f"afp_preview_{base_name}_{ts}")

        try:
            tmp_parent = getTempDir()
            for entry in os.listdir(tmp_parent):
                if entry.startswith("afp_preview_"):
                    try:
                        shutil.rmtree(os.path.join(tmp_parent, entry))
                    except Exception:
                        pass
            os.makedirs(tmp_dir, exist_ok=True)
        except Exception as e:
            log(f"afpFile: tmp_dir setup error: {e}")
            return

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(tmp_dir)
        except Exception as e:
            log(f"afpFile: unzip error: {e}")
            return

        config_path = os.path.join(tmp_dir, "config.scl")
        if not os.path.isfile(config_path):
            log("afpFile: config.scl not found in archive")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_src = f.read()
            config_doc = parse(config_src, parseOpts)
        except Exception as e:
            log(f"afpFile: config.scl parse error: {e}")
            return

        try:
            type_val = config_doc["type"]
            if type_val is None:
                log("afpFile: type field missing in config.scl")
                return
            afp_type = type_val.asString()
        except Exception as e:
            log(f"afpFile: type read error: {e}")
            return

        plugins = []

        if afp_type == "local":
            local_path = os.path.join(tmp_dir, "local.scl")
            if not os.path.isfile(local_path):
                log("afpFile: local.scl not found")
            else:
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        local_src = f.read()
                    local_doc = parse(local_src, parseOpts)
                    plugins_val = local_doc["plugins"]
                    if plugins_val is not None:
                        i = 0
                        while True:
                            entry = plugins_val[i]
                            if entry is None:
                                break
                            info = {"name": "", "version": "", "icon": ""}
                            name_val = entry["name"]
                            ver_val = entry["version"]
                            icon_val = entry["icon"]
                            if name_val is not None:
                                info["name"] = name_val.asString()
                            if ver_val is not None:
                                info["version"] = ver_val.asString()
                            if icon_val is not None:
                                info["icon"] = icon_val.asString()
                            plugins.append(info)
                            i += 1
                except Exception as e:
                    log(f"afpFile: local.scl parse error: {e}")

        if not plugins:
            plugins = [{"name": "", "version": "", "icon": ""}]

        try:
            count_val = config_doc["count"]
            if count_val is None:
                log("afpFile: count field missing in config.scl")
                return
            count = count_val.asInt()
        except Exception as e:
            log(f"afpFile: count read error: {e}")
            return

        try:
            from .ImportBottomSheet import show as showImportSheet
            showImportSheet(plugins, count)
        except Exception as e:
            log(f"afpFile: show ImportBottomSheet error: {e}")


def setup_afp_file_hook(plugin) -> list:
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

        hooks.append(plugin.hook_method(method, _AfpFileHandler(plugin), Integer.MAX_VALUE))
        log("afpFile: hook registered")
    except Exception as e:
        log(f"afpFile: setup error: {e}")
    return hooks
