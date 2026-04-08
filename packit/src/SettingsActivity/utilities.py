import os
import threading
import zipfile

from ui.settings import Header, Text, Divider
from ui.bulletin import BulletinHelper
from client_utils import get_last_fragment
from android_utils import log, run_on_ui_thread

try:
    from elyx import strings
except Exception as e:
    import android_utils as _au; _au.log(f"import elyx import strings failed: {e}")
    from ..utils.importFailed import showImportFailedAlert as _sifa; _sifa()


class UtilitiesSettings:
    def _do_share_afp(self, selected_files, export_settings, export_locally):
        try:
            from java import jclass, dynamic_proxy
            from java.io import File, FileOutputStream
            from hook_utils import find_class

            try:
                from elyx import settings as elyxSettings
                download_path = elyxSettings.get("download_path", "/storage/emulated/0/Download")
            except Exception:
                download_path = "/storage/emulated/0/Download"

            os.makedirs(download_path, exist_ok=True)
            file_path = os.path.join(download_path, "empty.afp")

            # create empty zip renamed to .afp
            with zipfile.ZipFile(file_path, "w") as zf:
                pass

            def open_share():
                try:
                    ShareAlert = find_class("org.telegram.ui.Components.ShareAlert")
                    fragment = get_last_fragment()
                    if not fragment:
                        return

                    ShareDelegateClass = jclass("org.telegram.ui.Components.ShareAlert$ShareAlertDelegate")
                    _fragment = fragment

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
                                    log(f"utilities.ShareDelegate.didShare: {e}")
                            run_on_ui_thread(_show_bulletin)

                        def didCopy(self):
                            return False

                    temp_file = File(file_path)
                    share_alert = ShareAlert(
                        fragment.getParentActivity(),
                        None, None,
                        temp_file.getAbsolutePath(),
                        None, None,
                        False, None, None,
                        False, False, False,
                        None, None
                    )
                    share_alert.setDelegate(ShareDelegate())
                    fragment.showDialog(share_alert)
                except Exception as e:
                    log(f"utilities._do_share_afp.open_share: {e}")
                    BulletinHelper.show_error(strings["utilities_afp_error"])

            run_on_ui_thread(open_share)
        except Exception as e:
            log(f"utilities._do_share_afp: {e}")
            run_on_ui_thread(lambda: BulletinHelper.show_error(strings["utilities_afp_error"]))

    def _on_export(self, selected_files, export_settings, export_locally):
        t = threading.Thread(
            target=self._do_share_afp,
            args=(selected_files, export_settings, export_locally),
            daemon=True
        )
        t.start()

    def _share_afp(self, view):
        try:
            from ..ui.ExportBottomSheet import show as showExportSheet
            showExportSheet(self._on_export)
        except Exception as e:
            log(f"utilities._share_afp: {e}")

    def build(self):
        return [
            Header(text=strings["utilities_header"]),
            Text(
                text=strings["utilities_share_afp"],
                icon="msg_unarchive",
                on_click=self._share_afp
            ),
            Divider(),
        ]
