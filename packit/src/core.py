import os
import requests
from android_utils import log, run_on_ui_thread
from client_utils import run_on_queue, get_last_fragment
from ui.bulletin import BulletinHelper
from java.io import File, FileOutputStream
try:
    from org.telegram.messenger import ApplicationLoader
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


def install_plugin(plugin_info: dict):
    plugin_id = plugin_info.get("id")
    url = plugin_info.get("link") or plugin_info.get("raw")

    if not plugin_id or not url:
        BulletinHelper.show_error("Plugin has no link")
        return

    fragment = get_last_fragment()
    if not fragment:
        return

    def task():
        try:
            BulletinHelper.show_info("Downloading plugin...")

            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                log(f"core.install_plugin: failed to download '{plugin_id}' from '{url}': HTTP {r.status_code}")
                raise Exception(f"HTTP {r.status_code}")

            pkg = ApplicationLoader.applicationContext.getPackageName()
            plugins_dir = f"/data/data/{pkg}/files/plugins"
            try:
                os.makedirs(plugins_dir, exist_ok=True)
            except Exception:
                pass

            temp_path = os.path.join(plugins_dir, f".temp_{plugin_id}.plugin")
            with open(temp_path, "wb") as f:
                f.write(r.content)

            def open_dialog():
                try:
                    PluginsController.getInstance().showInstallDialog(fragment, temp_path, True)
                except Exception as e:
                    BulletinHelper.show_error(f"Failed to open install dialog: {e}")

            run_on_ui_thread(open_dialog)
        except Exception as e:
            log(f"core.install_plugin: error downloading '{plugin_id}' from '{url}': {e}")
            run_on_ui_thread(lambda: BulletinHelper.show_error("An error occurred while downloading"))

    run_on_queue(task)


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