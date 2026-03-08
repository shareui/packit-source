import os
import requests
import threading
from android_utils import log
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from java.io import File, FileOutputStream


def share_plugin_file(plugin_info: dict, display_name: str, activity):
    threading.Thread(target=_do_share, args=(plugin_info, display_name), daemon=True).start()


def _do_share(plugin_info: dict, display_name: str):
    try:
        from android_utils import run_on_ui_thread
        from java import jclass, dynamic_proxy
        from ui.alert import AlertDialogBuilder

        plugin_id = plugin_info.get("id")
        if not plugin_id:
            run_on_ui_thread(lambda: BulletinHelper.show_error("Plugin has no id"))
            return
        link = plugin_info.get("link") or plugin_info.get("raw")
        if not link:
            run_on_ui_thread(lambda: BulletinHelper.show_error("Plugin has no download link"))
            return

        fragment = get_last_fragment()
        act = fragment.getParentActivity() if fragment else None

        dlg_ref = [None]

        def show_spinner():
            try:
                if not act:
                    return
                loading = AlertDialogBuilder(act, AlertDialogBuilder.ALERT_TYPE_SPINNER)
                loading.set_cancelable(False)
                dlg_ref[0] = loading.create()
                dlg_ref[0].show()
            except Exception as e:
                log(f"share: show_spinner error: {e}")

        def dismiss_spinner():
            try:
                if dlg_ref[0]:
                    dlg_ref[0].dismiss()
            except Exception as e:
                log(f"share: dismiss_spinner error: {e}")

        run_on_ui_thread(show_spinner)

        try:
            from elyx import settings
            download_path = settings.get("download_path", "/storage/emulated/0/Download")
        except Exception:
            download_path = "/storage/emulated/0/Download"

        url_filename = link.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
        _, url_ext = os.path.splitext(url_filename)
        filename = f"{plugin_id}{url_ext}" if url_ext else f"{plugin_id}.plugin"

        os.makedirs(download_path, exist_ok=True)
        file_path = os.path.join(download_path, filename)
        log(f"share: downloading {link} -> {file_path}")

        r = requests.get(link, timeout=30)
        if r.status_code != 200:
            run_on_ui_thread(dismiss_spinner)
            run_on_ui_thread(lambda: BulletinHelper.show_error("Failed to download plugin for sharing"))
            return
        temp_file = File(file_path)
        if temp_file.exists():
            temp_file.delete()
        fos = FileOutputStream(temp_file)
        fos.write(r.content)
        fos.close()
        log(f"share: written {temp_file.length()} bytes")

        def open_share():
            try:
                dismiss_spinner()
                from hook_utils import find_class
                ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                frag = get_last_fragment()
                if not frag:
                    return

                ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")

                class ShareDelegate(dynamic_proxy(ShareDelegateClass)):
                    def __init__(self):
                        super().__init__()

                    def didShare(self):
                        pass

                    def didCopy(self):
                        return False

                share_alert = ShareAlert(
                    frag.getParentActivity(),
                    None, None,
                    temp_file.getAbsolutePath(),
                    None, None,
                    False, None, None,
                    False, False, False,
                    None, None
                )
                share_alert.setDelegate(ShareDelegate())
                frag.showDialog(share_alert)
            except Exception as e:
                log(f"share: open_share error: {e}")
                BulletinHelper.show_error("Failed to share plugin")

        run_on_ui_thread(open_share)
    except Exception as e:
        log(f"share: _do_share error: {e}")
        from android_utils import run_on_ui_thread
        run_on_ui_thread(lambda: BulletinHelper.show_error("Failed to share plugin"))