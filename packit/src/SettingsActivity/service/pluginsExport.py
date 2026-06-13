# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import os
import json
import zipfile
import threading

from android_utils import run_on_ui_thread
from client_utils import get_last_fragment
from ui.bulletin import BulletinHelper

try:
    from elyx import strings
except Exception as e:
    logx(f"pluginsExport: import strings failed: {e}", False)
    strings = None


def _resolvePluginsDir() -> str | None:
    try:
        from file_utils import get_plugins_dir
        return get_plugins_dir()
    except Exception:
        pass
    try:
        from org.telegram.messenger import ApplicationLoader
        files_dir = ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath()
        return os.path.join(files_dir, "plugins")
    except Exception as e:
        logx(f"pluginsExport._resolvePluginsDir: {e}", False)
        return None


def _resolveLocalConfigPath() -> str | None:
    try:
        from ...utils.paths import getConfigsDir
        return os.path.join(getConfigsDir(), "localConfig.json")
    except Exception as e:
        logx(f"pluginsExport._resolveLocalConfigPath: {e}", False)
        return None


def _readPluginMeta(filepath: str) -> dict:
    import ast
    import re
    meta = {}
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(1024 * 5)
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ("__id__", "__name__", "__version__", "__min_version__", "__app_version__", "__sdk_version__", "__icon__"):
                            if isinstance(node.value, (ast.Constant, ast.Str)):
                                meta[target.id] = node.value.value if isinstance(node.value, ast.Constant) else node.value.s
        except Exception:
            patterns = {
                "__id__": r'^__id__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__name__": r'^__name__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__version__": r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__min_version__": r'^__min_version__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__app_version__": r'^__app_version__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__sdk_version__": r'^__sdk_version__\s*=\s*[\'"]([^\'"]+)[\'"]',
                "__icon__": r'^__icon__\s*=\s*[\'"]([^\'"]+)[\'"]',
            }
            for key, pattern in patterns.items():
                m = re.search(pattern, content, re.MULTILINE)
                if m:
                    meta[key] = m.group(1)
    except Exception as e:
        logx(f"pluginsExport._readPluginMeta: {e}", False)
    return meta


def _buildConfigScl(selected_files: list, export_settings: bool, export_locally: bool,
                    plugins_dir: str, local_cfg_path: str | None) -> str:
    from ...scl.scl import Doc
    doc = Doc.new()
    doc.set("type", "local" if export_locally else "external")
    doc.set("settings", export_settings)
    doc.set("count", len(selected_files))
    return doc.serialize()


def _buildLocalScl(selected_files: list, plugins_dir: str) -> str:
    # list of plugin descriptors: id, name, path (relative to archive root), version
    from ...scl.scl import Doc
    doc = Doc.new()

    listBuilder = doc.newList()
    for fname in selected_files:
        fpath = os.path.join(plugins_dir, fname)
        meta = _readPluginMeta(fpath) if os.path.isfile(fpath) else {}
        plugin_id = meta.get("__id__") or os.path.splitext(fname)[0]
        name = meta.get("__name__") or plugin_id
        version = meta.get("__version__") or None
        rel_path = f"plugins/{fname}"

        min_ver = meta.get("__min_version__") or None
        app_ver = meta.get("__app_version__") or None
        sdk_ver = meta.get("__sdk_version__") or None
        icon = meta.get("__icon__") or None

        if app_ver:
            app_version_val = app_ver
        elif min_ver:
            app_version_val = f">={min_ver}"
        else:
            app_version_val = None

        entry = doc.newStruct()
        entry.set("id", plugin_id)
        entry.set("name", name)
        entry.set("path", rel_path)
        if version is not None:
            entry.set("version", version)
        if app_version_val is not None:
            entry.set("app_version", app_version_val)
        if sdk_ver is not None:
            entry.set("sdk_version", sdk_ver)
        if icon is not None:
            entry.set("icon", icon)
        listBuilder.append(entry.build())

    doc.set("plugins", listBuilder.build())
    return doc.serialize()


def _buildSettingsJson(selected_files: list, plugins_dir: str) -> str:
    settings_path = os.path.join(plugins_dir, "plugin_settings.json")
    all_settings = {}
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                all_settings = json.load(f)
        except Exception as e:
            logx(f"pluginsExport._buildSettingsJson: read failed: {e}", False)

    result = {}
    for fname in selected_files:
        fpath = os.path.join(plugins_dir, fname)
        if not os.path.isfile(fpath):
            continue
        meta = _readPluginMeta(fpath)
        plugin_id = meta.get("__id__") or os.path.splitext(fname)[0]
        if plugin_id in all_settings:
            result[plugin_id] = all_settings[plugin_id]

    return json.dumps(result, ensure_ascii=False, indent=2)


def buildArchive(selected_files: list, export_settings: bool, export_locally: bool, archive_name: str = "plugins"):
    try:
        from java import jclass, dynamic_proxy
        from java.io import File
        from hook_utils import find_class
        from ui.alert import AlertDialogBuilder

        fragment = get_last_fragment()
        act = fragment.getParentActivity() if fragment and hasattr(fragment, "getParentActivity") else None

        spinner_dlg = [None]

        def _show_spinner():
            try:
                builder = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
                builder.setMessage(str(strings["utilities_afp_building"]))
                dlg = builder.show()
                spinner_dlg[0] = dlg
            except Exception as e:
                logx(f"pluginsExport.buildArchive._show_spinner: {e}", False)

        def _dismiss_spinner():
            try:
                if spinner_dlg[0] is not None:
                    spinner_dlg[0].dismiss()
                    spinner_dlg[0] = None
            except Exception as e:
                logx(f"pluginsExport.buildArchive._dismiss_spinner: {e}", False)

        if act is not None:
            run_on_ui_thread(_show_spinner)

        def _build():
            try:
                try:
                    from elyx import settings as elyxSettings
                    download_path = elyxSettings.get("download_path", "/storage/emulated/0/Download")
                except Exception:
                    download_path = "/storage/emulated/0/Download"

                plugins_dir = _resolvePluginsDir()
                if not plugins_dir:
                    run_on_ui_thread(_dismiss_spinner)
                    run_on_ui_thread(lambda: BulletinHelper.show_error(strings["utilities_afp_error"]))
                    return

                local_cfg_path = _resolveLocalConfigPath()

                os.makedirs(download_path, exist_ok=True)
                import random
                import string
                safe_name = "".join(c for c in archive_name if c.isalnum() or c in "-_") or "plugins"
                suffix = "".join(random.choices(string.ascii_lowercase, k=4))
                file_path = os.path.join(download_path, f"{safe_name}-{suffix}.afp")

                with zipfile.ZipFile(file_path, "w") as zf:
                    # config.scl at archive root
                    config_scl = _buildConfigScl(selected_files, export_settings, export_locally,
                                                  plugins_dir, local_cfg_path)
                    zf.writestr("config.scl", config_scl)

                    # plugin files in plugins/
                    for fname in selected_files:
                        fpath = os.path.join(plugins_dir, fname)
                        if os.path.isfile(fpath):
                            zf.write(fpath, f"plugins/{fname}")

                    # settings.json at archive root (optional)
                    if export_settings:
                        settings_json = _buildSettingsJson(selected_files, plugins_dir)
                        zf.writestr("settings.json", settings_json)

                    # local.scl at archive root (only for local export)
                    if export_locally:
                        local_scl = _buildLocalScl(selected_files, plugins_dir)
                        zf.writestr("local.scl", local_scl)

                def open_share():
                    _dismiss_spinner()
                    try:
                        ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                        cur_fragment = get_last_fragment()
                        if not cur_fragment:
                            return

                        ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")
                        _fragment = cur_fragment

                        class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
                            def __init__(self):
                                super().__init__()

                            def didShare(self):
                                def _show_bulletin():
                                    try:
                                        from org.telegram.messenger import R as R_tg
                                        BulletinFactory = find_class("org.telegram.ui.Components.BulletinFactory")
                                        container = _fragment.getParentActivity().getWindow().getDecorView()
                                        rp = _fragment.getResourceProvider()
                                        BulletinFactory.of(container, rp).createSimpleBulletin(R_tg.raw.voip_invite, strings["utilities_afp_shared"]).show()
                                    except Exception as e:
                                        logx(f"pluginsExport.ShareDelegate.didShare: {e}", False)
                                run_on_ui_thread(_show_bulletin)

                            def didCopy(self):
                                return False

                        temp_file = File(file_path)
                        share_alert = ShareAlert(
                            cur_fragment.getParentActivity(),
                            None, None,
                            temp_file.getAbsolutePath(),
                            None, None,
                            False, None, None,
                            False, False, False,
                            None, None
                        )
                        share_alert.setDelegate(ShareDelegate())
                        cur_fragment.showDialog(share_alert)
                    except Exception as e:
                        logx(f"pluginsExport.buildArchive.open_share: {e}", False)
                        BulletinHelper.show_error(strings["utilities_afp_error"])

                run_on_ui_thread(open_share)
            except Exception as e:
                logx(f"pluginsExport.buildArchive._build: {e}", False)
                run_on_ui_thread(_dismiss_spinner)
                run_on_ui_thread(lambda: BulletinHelper.show_error(strings["utilities_afp_error"]))

        threading.Thread(target=_build, daemon=True).start()
    except Exception as e:
        logx(f"pluginsExport.buildArchive: {e}", False)
        run_on_ui_thread(lambda: BulletinHelper.show_error(strings["utilities_afp_error"]))