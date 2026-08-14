# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

from packutil import logx
import threading

from ui.settings import Header, Text, Divider, Input
from ui.alert import AlertDialogBuilder
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import run_on_ui_thread

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ...utils.ImportFailed import showImportFailedAlert as _sifa; _sifa()


def _calcPluginsDirSize():
    try:
        import os
        try:
            from file_utils import get_plugins_dir
            plugins_dir = get_plugins_dir()
        except Exception:
            from org.telegram.messenger import ApplicationLoader
            files_dir = ApplicationLoader.applicationContext.getFilesDir().getAbsolutePath()
            plugins_dir = os.path.join(files_dir, "plugins")

        total_bytes = 0
        count = 0
        for fname in os.listdir(plugins_dir):
            if not fname.endswith((".py", ".plugin")) or fname.startswith(".temp"):
                continue
            try:
                total_bytes += os.path.getsize(os.path.join(plugins_dir, fname))
                count += 1
            except Exception:
                pass
        return count, total_bytes
    except Exception as e:
        logx(f"utilities._calcPluginsDirSize: {e}", False)
        return 0, 0


def _formatSize(total_bytes):
    if total_bytes >= 1024 * 1024:
        return f"{total_bytes / (1024 * 1024):.2f} MB"
    return f"{total_bytes / 1024:.2f} KB"


class UtilitiesSettings:
    def __init__(self):
        self._archive_name = "plugins"
        self._export_subtext = str(strings["utilities_export_subtext_loading"])
        self._size_loaded = False
        threading.Thread(target=self._loadSubtextInBackground, daemon=True).start()

    def _loadSubtextInBackground(self):
        try:
            count, total_bytes = _calcPluginsDirSize()
            size_str = _formatSize(total_bytes)
            self._export_subtext = (
                str(strings["utilities_export_subtext"])
                .replace("{count}", str(count))
                .replace("{size}", size_str)
            )
            self._size_loaded = True
            self._reloadSettings()
        except Exception as e:
            logx(f"utilities._loadSubtextInBackground: {e}", False)

    def _reloadSettings(self):
        try:
            from com.exteragram.messenger.plugins import PluginsController
            PluginsController.getInstance().loadPluginSettings("shareui_packit")
        except Exception as e:
            logx(f"utilities._reloadSettings: {e}", False)

    def _on_export(self, selected_files, export_settings, export_locally):
        from .service.PluginsExport import buildArchive
        archive_name = self._archive_name.strip() or "plugins"
        buildArchive(selected_files, export_settings, export_locally, archive_name)

    def _share_afp(self, view):
        fragment = get_last_fragment()
        if not fragment:
            return
        act = fragment.getParentActivity() if hasattr(fragment, "getParentActivity") else None
        if not act:
            return

        dlg_ref = [None]

        def show_spinner():
            try:
                loading = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
                loading.set_cancelable(False)
                dlg_ref[0] = loading.create()
                dlg_ref[0].show()
            except Exception as e:
                logx(f"utilities._share_afp: show_spinner error: {e}", False)

        def dismiss_spinner():
            try:
                if dlg_ref[0]:
                    dlg_ref[0].dismiss()
            except Exception as e:
                logx(f"utilities._share_afp: dismiss_spinner error: {e}", False)

        def load_and_show():
            try:
                from ..dialogs.ExportBottomSheet import loadPlugins, show as showExportSheet
                plugins = loadPlugins()
                run_on_ui_thread(lambda: (dismiss_spinner(), showExportSheet(plugins, self._on_export)))
            except Exception as e:
                logx(f"utilities._share_afp: load_and_show error: {e}", False)
                run_on_ui_thread(lambda: (dismiss_spinner(), BulletinHelper.show_error(strings["utilities_afp_error"])))

        run_on_ui_thread(show_spinner)
        threading.Thread(target=load_and_show, daemon=True).start()

    def build(self):
        return [
            Header(text=strings["utilities_header"]),
            Text(
                text=strings["utilities_share_afp"],
                subtext=self._export_subtext,
                icon="msg_shareout",
                on_click=self._share_afp
            ),
            Input(
                key="utilities_archive_name",
                text=strings["utilities_archive_name_label"],
                default="plugins",
                icon="menu_tag_rename",
                on_change=lambda v: setattr(self, "_archive_name", v)
            ),
            Divider(text=strings["utilities_afp_divider"]),
        ]